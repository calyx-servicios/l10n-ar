##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrExpense(models.Model):
    _inherit = "hr.expense"

    approved_amount = fields.Monetary(
        string="Importe aprobado",
        currency_field="company_currency_id",
        copy=False,
        readonly=True,
        help="Total del gasto al momento de aprobarlo. El total de la factura de proveedor "
        "vinculada no puede superarlo.",
    )

    # === CONSTRAINT METHODS === #

    @api.constrains("invoice_id")
    def _check_invoice_id_approved(self):
        """Administración carga la factura una vez que el gasto está aprobado."""
        for expense in self.filtered("invoice_id"):
            if expense.approval_state != "approved":
                raise ValidationError(
                    self.env._(
                        "Solo se puede vincular una factura de proveedor a un gasto aprobado (%s).",
                        expense.name,
                    )
                )

    @api.constrains("invoice_id", "total_amount")
    def _check_invoice_amount_approved(self):
        for expense in self.filtered(lambda x: x.invoice_id and x.approved_amount):
            invoice = expense.invoice_id
            # amount_total_signed está en moneda de la compañía, como approved_amount
            invoice_amount = abs(invoice.amount_total_signed)
            if expense.company_currency_id.compare_amounts(invoice_amount, expense.approved_amount) > 0:
                raise ValidationError(
                    self.env._(
                        "El total de la factura %(invoice)s (%(invoice_amount)s) supera el importe "
                        "aprobado del gasto %(expense)s (%(approved_amount)s).",
                        invoice=invoice.display_name,
                        invoice_amount=expense.company_currency_id.format(invoice_amount),
                        expense=expense.name,
                        approved_amount=expense.company_currency_id.format(expense.approved_amount),
                    )
                )

    @api.constrains("payment_method_line_id", "sheet_id")
    def _check_sheet_payment_method(self):
        """El método de pago de un informe pagado por la compañía se cambia desde el informe, que
        lo aplica a todas sus líneas; no se puede cambiar en una sola."""
        for expense in self.filtered(lambda x: x.sheet_id and x.payment_mode == "company_account"):
            if expense.payment_method_line_id != expense.sheet_id.payment_method_line_id:
                raise ValidationError(
                    self.env._(
                        "El gasto %(expense)s está en el informe %(sheet)s: cambie el método de pago "
                        "desde el informe, que lo aplica a todos sus gastos.",
                        expense=expense.name,
                        sheet=expense.sheet_id.name,
                    )
                )

    # === COMPUTE METHODS === #

    def _compute_state(self):
        res = super()._compute_state()
        # hr_expense_invoice calcula el estado de los gastos con factura mirando el asiento de
        # transferencia al empleado. Cuando paga la compañía el asiento es el pago de la factura,
        # así que seguimos el criterio del core para lo que paga la compañía: pagado.
        for expense in self.filtered(
            lambda x: x.payment_mode == "company_account" and x.invoice_id and x.account_move_id
        ):
            expense.state = "paid" if expense.account_move_id.state != "draft" else "posted"
        return res

    # === ACTION METHODS === #

    def action_expense_create_invoice(self):
        """Reemplaza al de hr_expense_invoice, que valida la factura cuando paga la compañía: la
        factura queda en borrador para cargar el número de comprobante AFIP antes de validarla."""
        self.ensure_one()
        if self.approval_state != "approved":
            raise UserError(self.env._("La factura de proveedor se crea una vez aprobado el gasto."))
        if not self.vendor_id:
            raise UserError(self.env._("Cargue el proveedor del gasto para crear la factura."))
        invoice = self.env["account.move"].create(self._prepare_invoice_values())
        attachments = self.env["ir.attachment"].search([("res_model", "=", self._name), ("res_id", "=", self.id)])
        for attachment in attachments:
            attachment.copy({"res_model": invoice._name, "res_id": invoice.id})
        self.write({"invoice_id": invoice.id, "quantity": 1})
        return invoice._get_records_action(name=self.env._("Factura de proveedor"))

    def action_post(self):
        res = super().action_post()
        self.filtered(lambda x: x.payment_mode == "company_account" and x.invoice_id)._reconcile_invoice_payments()
        return res

    # === BUSINESS METHODS === #

    def _do_approve(self, check=True):
        expenses_to_approve = self.filtered(lambda x: x.state in {"submitted", "draft"})
        res = super()._do_approve(check=check)
        for expense in expenses_to_approve.filtered(lambda x: x.approval_state == "approved"):
            expense.approved_amount = expense.total_amount
        return res

    def _do_reset_approval(self):
        res = super()._do_reset_approval()
        self.sudo().write({"approved_amount": False})
        return res

    def _prepare_payments_vals(self):
        """Gasto pagado por la compañía con factura de proveedor: en lugar de imputar el gasto (que
        ya está en la factura, con su IVA crédito fiscal), el pago cancela la deuda de la factura con
        el método de pago del gasto."""
        move_vals, payment_vals = super()._prepare_payments_vals()
        if not self.invoice_id:
            return move_vals, payment_vals
        invoice = self.invoice_id
        partner = invoice.commercial_partner_id
        payable_lines = invoice.line_ids.filtered(lambda x: x.display_type == "payment_term" and not x.reconciled)
        balance = -sum(payable_lines.mapped("amount_residual"))
        amount_currency = -sum(payable_lines.mapped("amount_residual_currency"))
        line_vals = {
            "name": self._get_move_line_name(),
            "partner_id": partner.id,
            "currency_id": invoice.currency_id.id,
        }
        move_vals.update(
            {
                "partner_id": partner.id,
                "currency_id": invoice.currency_id.id,
                "line_ids": [
                    Command.create(
                        {
                            **line_vals,
                            "account_id": payable_lines.account_id[:1].id,
                            "balance": balance,
                            "amount_currency": amount_currency,
                        }
                    ),
                    Command.create(
                        {
                            **line_vals,
                            "account_id": self._get_expense_account_destination(),
                            "balance": -balance,
                            "amount_currency": -amount_currency,
                        }
                    ),
                ],
            }
        )
        payment_vals.update(
            {
                "partner_id": partner.id,
                "currency_id": invoice.currency_id.id,
                "amount": amount_currency,
            }
        )
        if "to_pay_move_line_ids" in self.env["account.payment"]._fields:
            # account_payment_pro (ADHOC) completa solo la deuda a pagar con todas las facturas
            # impagas del proveedor y concilia desde la más vieja: forzamos la del gasto.
            payment_vals["to_pay_move_line_ids"] = [Command.set(payable_lines.ids)]
        return move_vals, payment_vals

    def _reconcile_invoice_payments(self):
        for expense in self:
            partner = expense.invoice_id.commercial_partner_id
            lines = (expense.invoice_id.line_ids | expense.account_move_id.line_ids).filtered(
                lambda x, partner=partner: x.account_type == "liability_payable"
                and x.partner_id == partner
                and not x.reconciled
                and x.parent_state == "posted"
            )
            if len(lines.move_id) == 2:
                lines.reconcile()
