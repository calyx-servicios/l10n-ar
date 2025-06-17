from odoo import models, fields, api
from odoo.osv import expression
from odoo.exceptions import ValidationError
from ast import literal_eval
import datetime

class AccountPaymentGroup(models.Model):
    _inherit = 'account.payment.group'

    l10n_ar_withholding_line_ids = fields.One2many(
        comodel_name='l10n_ar.payment.withholding',
        inverse_name='payment_group_id',
        string='Withholdings Lines',
    )
    move_id = fields.Many2one(
        string="Asiento contable",
        comodel_name="account.move"
    )
    retention_move_line_ids = fields.One2many(
        comodel_name="account.move.line",
        inverse_name="payment_group_id"
    )
    date = fields.Datetime(
        compute="_compute_dates"
    )
    date_to = fields.Datetime(
        compute="_compute_dates"
    )
    withholdable_advanced_amount = fields.Float(
        compute="_compute_wiholding_fields"
    )
    retencion_ganancias = fields.Selection(
        compute="_compute_wiholding_fields"
    )
    regimen_ganancias_id = fields.Many2one(
        comodel_name="afip.tabla_ganancias.alicuotasymontos",
        compute="_compute_wiholding_fields"
    )

    def _compute_wiholding_fields(self):
        for rec in self:
            rec.withholdable_advanced_amount = sum(rec.payment_ids.mapped(
                "withholdable_advanced_amount"
            ))
            rec.retencion_ganancias = False
            rec.regimen_ganancias_id = False
            if rec.payment_ids:
                rec.retencion_ganancias = rec.payment_ids[0].retencion_ganancias
                if rec.payment_ids[0].regimen_ganancias_id:
                    rec.regimen_ganancias_id = rec.payment_ids[0].regimen_ganancias_id.id

    def _compute_dates(self):
        for rec in self:
            rec.date = datetime.date.today()
            rec.date_to = datetime.date.today()

    def compute_witholdings(self):
        cr = self.env.cr
        LARPW = self.env["l10n_ar.payment.withholding"]
        for rec in self:
            for payment in rec.payment_ids:
                if not(payment.is_internal_transfer or payment.partner_type != 'supplier' or payment.state != 'draft'):
                    try:
                        payment.compute_withholdings()
                        cr.commit()
                    except Exception:
                        pass
            cr.commit()
            for payment in rec.payment_ids:
                for witholding in payment.l10n_ar_withholding_line_ids:
                    LARPW.create({
                        'payment_group_id': rec.id,
                        'tax_id': witholding.tax_id.id if witholding.tax_id else False,
                        'name': witholding.name,
                        'base_amount': witholding.base_amount,
                        'amount': witholding.amount,
                    })

    @api.depends('payment_ids.signed_amount_company_currency', 'l10n_ar_withholding_line_ids')
    def _compute_payments_amount(self):
        for rec in self:
            # this hac is to make it work when creating payment groups with payments without saving + saved records
            payments_amount = sum((rec._origin.payment_ids + rec.payment_ids.filtered(lambda x: not x.ids)).mapped(
                'signed_amount_company_currency'))
            rec.payments_amount = payments_amount + sum(rec.l10n_ar_withholding_line_ids.mapped("amount"))

    @api.constrains("l10n_ar_withholding_line_ids", "payment_ids")
    def _set_retention_move_line_ids(self):
        AM = self.env["account.move"]
        AML = self.env["account.move.line"]
        for rec in self:
            for witholding in rec.l10n_ar_withholding_line_ids:
                if witholding.base_amount <= 0:
                    raise ValidationError(
                        "El Monto imponible de la retención debe tener un valor positivo"
                    )
                if witholding.amount <= 0:
                    raise ValidationError(
                        "El Monto de la retención debe tener un valor positivo"
                    )
            if self.retention_move_line_ids:
                for move in self.retention_move_line_ids.mapped("move_id"):
                    move.unlink()
            for retention in self.retention_move_line_ids:
                retention.unlink()
            if rec.payment_ids:
                destination_account = rec.payment_ids[0].destination_account_id
                name = rec.name if rec.name else "Retenciones"
                move = AM.create({
                    "ref": name,
                    "company_id": rec.company_id.id,
                    "partner_id": rec.partner_id.id if rec.partner_id else False,
                    "date": rec.payment_date
                })
                for witholding in rec.l10n_ar_withholding_line_ids:
                    if witholding.tax_id:
                        amount = witholding.amount
                        if rec.partner_type == "supplier":
                            credit = True
                            debit = False
                        elif rec.partner_type == "customer":
                            debit = True
                            credit = False
                        account = witholding.account_id
                        if not account:
                            raise ValidationError(
                                "En cada linea de retenciones es obligatorio que contenga una cuenta asociada.\n"
                                "La misma esta asociada dentro de la configuración del impuesto.\n"
                                "Impuesto %s" % witholding.tax_id.name
                            )
                        account = account.id
                        AML.create([{
                            "payment_group_id": rec.id,
                            "name": witholding.name,
                            "move_id": move.id,
                            "credit": amount if credit else 0,
                            "debit": amount if debit else 0,
                            "account_id": account,
                            "partner_id": rec.partner_id.id if rec.partner_id else False,
                            "date": rec.payment_date
                        }, {
                            "payment_group_id": rec.id,
                            "name": witholding.name,
                            "move_id": move.id,
                            "credit": amount if debit else 0,
                            "debit": amount if credit else 0,
                            "account_id": destination_account.id,
                            "partner_id": rec.partner_id.id if rec.partner_id else False,
                            "date": rec.payment_date
                        }])
                        if rec.company_id and rec.company_id.l10n_ar_tax_base_account_id:
                            imponible_id = rec.company_id.l10n_ar_tax_base_account_id.id
                            base_amount = witholding.base_amount
                            AML.create([{
                                "payment_group_id": rec.id,
                                "name": witholding.name,
                                "move_id": move.id,
                                "credit": base_amount if credit else 0,
                                "debit": base_amount if debit else 0,
                                "account_id": imponible_id,
                                "partner_id": rec.partner_id.id if rec.partner_id else False,
                                "date": rec.payment_date
                            }, {
                                "payment_group_id": rec.id,
                                "name": witholding.name,
                                "move_id": move.id,
                                "credit": base_amount if debit else 0,
                                "debit": base_amount if credit else 0,
                                "account_id": imponible_id,
                                "partner_id": rec.partner_id.id if rec.partner_id else False,
                                "date": rec.payment_date
                            }])
    def button_journal_entries(self):
        res = super().button_journal_entries()
        domain = res["domain"]
        extra_domain = [('payment_group_id', '=', self.id)]
        res["domain"] = expression.OR([
            domain, extra_domain
        ])
        return res

    @api.constrains("state")
    def _set_witholding_lines_asset_state(self):
        for rec in self:
            if rec.state in ["draft", "cancel", "posted"]:
                move_ids = rec.retention_move_line_ids.mapped("move_id")
                if rec.state == "draft":
                    move_ids = move_ids.filtered(lambda x: x.state != "draft")
                if move_ids:
                    move_ids.write({"state": rec.state})


    def compute_withholdings(self):
        for rec in self:
            rec._compute_withholdings()
            rec._set_retention_move_line_ids()
            rec._set_witholding_lines_asset_state()

    def _compute_withholdings(self):
        if self.partner_type != 'supplier':
            return
        taxes = self.env['account.tax'].with_context(type=None).search([
            ('type_tax_use', '=', 'none'),
            ('withholding_type', '!=', 'none'),
            ('l10n_ar_withholding_payment_type', '=', self.partner_type),
            ('company_id', '=', self.company_id.id),
        ])
        for tax in taxes:
            if (
                    tax.withholding_user_error_message and
                    tax.withholding_user_error_domain):
                try:
                    domain = literal_eval(tax.withholding_user_error_domain)
                except Exception as e:
                    raise ValidationError(_(
                        'Could not eval rule domain "%s".\n'
                        'This is what we get:\n%s' % (tax.withholding_user_error_domain, e)))
                domain.append(('id', '=', self.id))
                if self.search(domain):
                    raise ValidationError(tax.withholding_user_error_message)
            vals = tax.get_withholding_vals(self)
            currency = self.currency_id
            period_withholding_amount = currency.round(vals.get('period_withholding_amount', 0.0))
            previous_withholding_amount = currency.round(vals.get('previous_withholding_amount'))
            computed_withholding_amount = max(0, (period_withholding_amount - previous_withholding_amount))
            vals['base_amount'] = vals.get('withholdable_advanced_amount') + vals.get('withholdable_invoiced_amount')
            vals['amount'] = computed_withholding_amount
            vals['computed_withholding_amount'] = computed_withholding_amount
            if vals["amount"] > 0 and vals["base_amount"] > 0:
                self.env["l10n_ar.payment.withholding"].create({
                    "tax_id": tax.id,
                    "amount": abs(vals["amount"]),
                    "base_amount": abs(vals["base_amount"]),
                    "payment_group_id": self.id
                })

    def _get_withholdable_amounts(
            self, withholding_amount_type, withholding_advances):
        """ Method to help on getting withholding amounts from account.tax
        """
        self.ensure_one()
        if self.state == 'posted':
            untaxed_field = 'matched_amount_untaxed'
            total_field = 'matched_amount'
        else:
            untaxed_field = 'selected_debt_untaxed'
            total_field = 'selected_debt'

        if withholding_amount_type == 'untaxed_amount':
            withholdable_invoiced_amount = self[untaxed_field]
        else:
            withholdable_invoiced_amount = self[total_field]

        withholdable_advanced_amount = 0.0
        if self.withholdable_advanced_amount < 0.0 and \
                self.to_pay_move_line_ids and self.state != 'posted':
            withholdable_advanced_amount = 0.0

            sign = self.partner_type == 'supplier' and -1.0 or 1.0
            sorted_to_pay_lines = sorted(
                self.to_pay_move_line_ids,
                key=lambda a: a.date_maturity or a.date)

            # last line to be reconciled
            partial_line = sorted_to_pay_lines[-1]
            if sign * partial_line.amount_residual < \
                    sign * self.withholdable_advanced_amount:
                raise ValidationError(_(
                    'Seleccionó deuda por %s pero aparentente desea pagar '
                    ' %s. En la deuda seleccionada hay algunos comprobantes de'
                    ' mas que no van a poder ser pagados (%s). Deberá quitar '
                    ' dichos comprobantes de la deuda seleccionada para poder '
                    'hacer el correcto cálculo de las retenciones.' % (
                        self.selected_debt,
                        self.to_pay_amount,
                        partial_line.move_id.display_name,
                        )))

            if withholding_amount_type == 'untaxed_amount' and \
                    partial_line.move_id:
                invoice_factor = partial_line.move_id._get_tax_factor()
            else:
                invoice_factor = 1.0
            withholdable_invoiced_amount -= (
                sign * self.unreconciled_amount * invoice_factor)
        elif withholding_advances:
            if self.state == 'posted':
                if self.unreconciled_amount and \
                   self.withholdable_advanced_amount:
                    withholdable_advanced_amount = self.amount_residual * (
                        self.withholdable_advanced_amount /
                        self.unreconciled_amount)
                else:
                    withholdable_advanced_amount = self.amount_residual
            else:
                withholdable_advanced_amount = \
                    self.withholdable_advanced_amount
        return (withholdable_advanced_amount, withholdable_invoiced_amount)
