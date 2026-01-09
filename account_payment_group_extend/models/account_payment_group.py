from odoo import models, fields, api, _, Command
from dateutil.relativedelta import relativedelta
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from ast import literal_eval
from datetime import date
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
        string='Retención Ganancias',
        selection=[
            ('imposibilidad_retencion', 'Imposibilidad de Retención'),
            ('no_aplica', 'No Aplica'),
            ('nro_regimen', 'Nro Regimen'),
        ]
    )
    regimen_ganancias_id = fields.Many2one(
        string='Regimen Ganancias',
        comodel_name="afip.tabla_ganancias.alicuotasymontos",
        ondelete='restrict',
    )

    def _compute_wiholding_fields(self):
        for rec in self:
            rec.withholdable_advanced_amount = sum(rec.payment_ids.mapped(
                "withholdable_advanced_amount"
            ))

    @api.onchange("receiptbook_id", "retencion_ganancias", "regimen_ganancias_id")
    @api.constrains("receiptbook_id", "retencion_ganancias", "regimen_ganancias_id")
    def _set_payment_withholding_fields(self):
        for rec in self:
            for payment in rec.payment_ids:
                payment.receiptbook_id = False
                payment.regimen_ganancias_id = False
                if rec.receiptbook_id:
                    payment.receiptbook_id = rec.receiptbook_id.id
                if rec.regimen_ganancias_id:
                    payment.regimen_ganancias_id = rec.regimen_ganancias_id.id
                payment.retencion_ganancias = rec.retencion_ganancias

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
        commands = []
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

            vals = self.get_tax_withholding_vals(tax, self)

            # we set computed_withholding_amount, hacemos round porque
            # si no puede pasarse un valor con mas decimales del que se ve
            # y terminar dando error en el asiento por debitos y creditos no
            # son iguales, algo parecido hace odoo en el compute_all de taxes
            currency = self.currency_id
            period_withholding_amount = currency.round(vals.get('period_withholding_amount', 0.0))
            previous_withholding_amount = 0
            # withholding can not be negative
            computed_withholding_amount = max(0, (period_withholding_amount - previous_withholding_amount))
            payment_withholding = self.l10n_ar_withholding_line_ids.filtered(lambda x: x.tax_id == tax)
            if not computed_withholding_amount:
                # if on refresh no more withholding, we delete if it exists
                if payment_withholding:
                    commands.append(Command.delete(payment_withholding.id))
                continue

            # we copy withholdable_base_amount on base_amount
            # al final vimos con varios clientes que este monto base
            # debe ser la base imponible de lo que se está pagando en este
            # voucher
            vals['base_amount'] = vals.get('withholdable_invoiced_amount', 0.0)
            vals['amount'] = vals.get("amount", 0.0)
            vals['computed_withholding_amount'] = computed_withholding_amount
            vals['period_withholding_amount'] = computed_withholding_amount + vals['previous_withholding_amount']
            prev_payments_domain, prev_withholding_domain = self.get_tax_period_payments_domain(tax, self)
            prev_payments = self.env["account.payment.group"].search(prev_payments_domain)
            previous_withholding = self.env['l10n_ar.payment.withholding'].search(prev_withholding_domain)
            if previous_withholding:
                sum_withholdable_invoiced_amount = sum(previous_withholding.mapped("withholdable_invoiced_amount"))
                vals["accumulated_amount"] = sum_withholdable_invoiced_amount
                vals["total_amount"] = sum_withholdable_invoiced_amount + vals["withholdable_invoiced_amount"]
            regimen = self.regimen_ganancias_id
            non_taxable_amount = 0
            if regimen:
                non_taxable_amount = regimen.montos_no_sujetos_a_retencion
            vals["withholding_non_taxable_amount"] = non_taxable_amount
            vals["withholdable_base_amount"] = vals.get("total_amount", 0) - vals.get("withholding_non_taxable_amount", 0)
            vals["automatic"] = True

            if tax.withholding_type == "tabla_ganancias":
                withholdable_base_amount = vals.get("total_amount", 0) - vals.get("withholding_non_taxable_amount", 0)
                vals["withholdable_base_amount"] = withholdable_base_amount
                percentage = 0
                if self.retencion_ganancias and self.retencion_ganancias == "nro_regimen":
                    regimen = self.regimen_ganancias_id
                    if regimen:
                        partner = self.partner_id
                        if partner and partner.l10n_ar_afip_responsibility_type_id:
                            responsibility = partner.l10n_ar_afip_responsibility_type_id
                            RI = self.env.ref("l10n_ar.res_IVARI")
                            if responsibility and responsibility.id == RI.id:
                                percentage = regimen.porcentaje_inscripto / 100
                            else:
                                percentage = regimen.porcentaje_no_inscripto / 100

                period_withholding_amount = withholdable_base_amount * percentage
                vals['period_withholding_amount'] = period_withholding_amount
                computed_withholding_amount = vals["period_withholding_amount"] - vals["previous_withholding_amount"]
                vals['computed_withholding_amount'] = computed_withholding_amount
                vals['amount'] = computed_withholding_amount
                payment_withholding = self.l10n_ar_withholding_line_ids.filtered(lambda x: x.tax_id == tax)
                if vals['amount'] <= 0:
                    continue


            if "tax_withholding_id" in vals:
                vals.pop("tax_withholding_id")
            if "date" in vals:
                vals.pop("date")
            if "communication" in vals:
                vals.pop("communication")
            if "comment" in vals:
                vals.pop('comment')

            # por ahora no imprimimos el comment, podemos ver de llevarlo a
            # otro campo si es de utilidad
            vals['payment_id'] = False
            vals["payment_group_id"] = self.id
            vals["tax_id"] = tax.id
            self.env["l10n_ar.payment.withholding"].create(vals)

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


    # def post(self):
    #     # hacemos el post de super, y si hay retenciones en l10n_ar_withholding_line_ids, hay que tomarlas y reconciliarlas con las lineas de factura
    #     res = super().post()
    #     import pprint
    #     for rec in self:
    #         for retention in rec.l10n_ar_withholding_line_ids:
    #             pprint.pprint(retention.read())
    #     return res



    def post(self):
        # dont know yet why, but if we came from an invoice context values
        # break behaviour, for eg. with demo user error writing account.account
        # and with other users, error with block date of accounting
        # TODO we should look for a better way to solve this

        create_from_website = self._context.get(
            'create_from_website', False)
        create_from_statement = self._context.get(
            'create_from_statement', False)
        create_from_expense = self._context.get('create_from_expense', False)
        self = self.with_context({})
        for rec in self:
            rec._set_withholding_names()
            if not rec.document_number:
                if rec.receiptbook_id.sequence_id:
                    rec.document_number = rec.receiptbook_id.sequence_id.next_by_id()

            if not rec.payment_ids:
                raise ValidationError(
                    'No puede confirmar un grupo de pagos sin un pago asociado'
                )

            if (rec.payment_subtype == 'double_validation' and
                    rec.payment_difference and (not create_from_statement and
                                                not create_from_expense)):
                raise ValidationError(
                    'Para poder pagar el monto a pagar y monto de pago debe ser igual'
                )

            writeoff_acc_id = False
            writeoff_journal_id = False

            if not create_from_website and not create_from_expense:
                rec.payment_ids.filtered(lambda x: x.state == 'draft').action_post()

            #counterpart_aml = rec.payment_ids.mapped('move_line_ids').filtered(
            counterpart_aml = rec.payment_ids.mapped('invoice_line_ids').filtered(
                lambda r: not r.reconciled and r.account_id.account_type in (
                    'liability_payable', 'asset_receivable'))

            # porque la cuenta podria ser no recivible y ni conciliable
            # (por ejemplo en sipreco)
            if counterpart_aml and rec.to_pay_move_line_ids:
                #(counterpart_aml + (rec.to_pay_move_line_ids)).reconcile(
                #    writeoff_acc_id, writeoff_journal_id)
                # (counterpart_aml + (rec.to_pay_move_line_ids)).reconcile()
                # rec.compute_withholdings()

                rec.retention_move_line_ids.mapped('move_id').action_post()
                lineas_retenciones = rec.retention_move_line_ids
                # filtramos y nos quedamos solo con las retenciones
                lineas_retenciones = lineas_retenciones.filtered(
                    lambda r: not r.reconciled and r.account_id.account_type in (
                        'liability_payable', 'asset_receivable'))
                (counterpart_aml + (rec.to_pay_move_line_ids) + (lineas_retenciones)).reconcile()

            # account.move.line(55261,)   +  account.move.line(55259,)

            rec.state = 'posted'
            if rec.receiptbook_id.mail_template_id:
                rec.message_post_with_template(
                    rec.receiptbook_id.mail_template_id.id,
                )

    def _set_withholding_names(self):
        for rec in self:
            commands = []
            for line in rec.l10n_ar_withholding_line_ids:
                if (not line.name or line.name == '/'):
                    if line.tax_id.l10n_ar_withholding_sequence_id:
                        commands.append(Command.update(line.id, {'name': line.tax_id.l10n_ar_withholding_sequence_id.next_by_id()}))
                    else:
                        raise UserError("Por favor configure una secuencia para el impuesto %s" % line.tax_id.name)
                if commands:
                    rec.l10n_ar_withholding_line_ids = commands

    def _get_payment_group_tax_desc(self, tax_id):
        self.ensure_one()
        if tax_id.withholding_type == "tabla_ganancias":
            if self.retencion_ganancias == "nro_regimen" and self.regimen_ganancias_id:
                reg = self.regimen_ganancias_id
                return f"{reg.codigo_de_regimen} - {reg.concepto_referencia}"
            return False
        else:
            return tax_id.invoice_label

    def get_tax_withholding_vals(self, tax, payment_group, force_withholding_amount_type=None):
        self = tax
        commercial_partner = payment_group.commercial_partner_id

        force_withholding_amount_type = None
        if self.withholding_type == 'partner_tax':
            alicuot_line = self.get_partner_alicuot(
                commercial_partner,
                payment_group.payment_date or fields.Date.context_today(self),
            )
            alicuota = alicuot_line
        self.ensure_one()
        withholding_amount_type = force_withholding_amount_type or \
            self.withholding_amount_type
        withholdable_advanced_amount, withholdable_invoiced_amount = \
            payment_group._get_withholdable_amounts(
                withholding_amount_type, self.withholding_advances)

        accumulated_amount = previous_withholding_amount = 0.0

        total_amount = (
            accumulated_amount +
            withholdable_advanced_amount +
            withholdable_invoiced_amount)
        withholding_non_taxable_minimum = self.withholding_non_taxable_minimum
        withholding_non_taxable_amount = self.withholding_non_taxable_amount
        withholdable_base_amount = (
            (total_amount > withholding_non_taxable_minimum) and
            (total_amount - withholding_non_taxable_amount) or 0.0)
        comment = False
        if self.withholding_type == 'code':
            localdict = {
                'withholdable_base_amount': withholdable_base_amount,
                'payment': payment_group,
                'partner': payment_group.commercial_partner_id,
                'withholding_tax': self,
            }
            eval(
                self.withholding_python_compute, localdict,
                mode="exec", nocopy=True)
            period_withholding_amount = localdict['result']
        else:
            rule = self._get_rule(payment_group)
            percentage = 0.0
            fix_amount = 0.0
            if rule:
                percentage = rule.percentage
                fix_amount = rule.fix_amount
                comment = '%s x %s + %s' % (
                    withholdable_base_amount,
                    percentage,
                    fix_amount)
            if self.withholding_type != 'tabla_ganancias':
                period_withholding_amount = ((total_amount > withholding_non_taxable_minimum) and (
                    withholdable_base_amount * percentage + fix_amount) or 0.0)
            else:
                period_withholding_amount = total_amount

        vals = {
            'withholdable_invoiced_amount': withholdable_invoiced_amount,
            'withholdable_advanced_amount': withholdable_advanced_amount,
            'accumulated_amount': accumulated_amount,
            'total_amount': total_amount,
            'withholding_non_taxable_minimum': withholding_non_taxable_minimum,
            'withholding_non_taxable_amount': withholding_non_taxable_amount,
            'withholdable_base_amount': withholdable_base_amount,
            'period_withholding_amount': period_withholding_amount,
            'previous_withholding_amount': previous_withholding_amount,
            'payment_group_id': payment_group.id,
            'tax_withholding_id': self.id,
            'automatic': True,
            'comment': comment,
        }

        base_amount = vals['withholdable_base_amount']

        if self.withholding_type == 'partner_tax':
            amount = base_amount * (alicuota.alicuota_retencion / 100)
            vals['comment'] = "%s x %s" % (
                base_amount, alicuota.alicuota_retencion / 100)
            vals['period_withholding_amount'] = amount
        elif self.withholding_type == 'tabla_ganancias':
            regimen = payment_group.regimen_ganancias_id
            imp_ganancias_padron = commercial_partner.imp_ganancias_padron
            if (
                    payment_group.retencion_ganancias != 'nro_regimen' or
                    not regimen):
                amount = 0.0
            elif not imp_ganancias_padron:
                raise UserError(
                    'El contacto %s no tiene configurada inscripción en '
                    'impuesto a las ganancias' % commercial_partner.name)
            elif imp_ganancias_padron in ['EX', 'NC']:
                amount = 0.0
            elif imp_ganancias_padron == 'AC':
                if base_amount == 0:
                    base_amount = payment_group.to_pay_amount
                non_taxable_amount = (
                    regimen.montos_no_sujetos_a_retencion)
                vals['withholding_non_taxable_amount'] = non_taxable_amount
                prev_payments = []
                if self.withholding_accumulated_payments:
                    payment_date = str(payment_group.payment_date)[:8]
                    payment_date = payment_date + '00'
                    payments = self.env['account.payment'].search([('payment_type','=','outbound'),('state','=','posted'),('payment_group_id','!=',payment_group.id),\
                                        ('partner_id','=',payment_group.partner_id.id),('used_withholding','=',False),('payment_group_id.retencion_ganancias','=','nro_regimen'),'|',('tax_withholding_id.withholding_type','!=','partner_iibb_padron'),('tax_withholding_id','=',False)])
                    previous_amount = 0
                    for payment in payments:
                        if payment_group.payment_date.month == payment.payment_group_id.payment_date.month and payment_group.payment_date.year == payment.payment_group_id.payment_date.year:
                            if payment_group.payment_date.day >= payment.payment_group_id.payment_date.day:
                                if payment.payment_group_id and payment.payment_group_id.matched_move_line_ids:
                                    for matched_line in payment.payment_group_id.matched_move_line_ids:
                                        matched_amount = matched_line.move_id._get_tax_factor() * (-1) * matched_line.with_context({'payment_group_id': payment.payment_group_id.id}).payment_group_matched_amount
                                    previous_amount += matched_amount
                                else:
                                    previous_amount += payment.amount
                                prev_payments.append(str(payment.id))
                    base_amount += previous_amount
                    vals['withholdable_advanced_amount'] = previous_amount
                    payment_group.write({'temp_payment_ids': ','.join(prev_payments)})

                if base_amount < non_taxable_amount and not prev_payments:
                    base_amount = 0.0
                elif not prev_payments:
                    base_amount -= non_taxable_amount
                elif prev_payments:
                    flag_substract = True
                    for idx in prev_payments:
                        prev_pay_obj = self.env['account.payment'].browse(int(idx))
                        if prev_pay_obj.tax_withholding_id:
                            flag_substract = False
                    if flag_substract:
                        base_amount -= non_taxable_amount

                vals['withholdable_base_amount'] = base_amount
                escala = []
                if payment_group.regimen_ganancias_id.codigo_de_regimen == '119':
                    escala = self.env['afip.tabla_ganancias.escala'].search([
                        ('importe_desde', '<=', base_amount),
                        ('importe_hasta', '>', base_amount),
                        ('cod_regimen', '=', '119')], limit=1)
                else:
                    escala = self.env['afip.tabla_ganancias.escala'].search([
                        ('importe_desde', '<=', base_amount),
                        ('importe_hasta', '>', base_amount),
                    ], limit=1)
                importe_excedente = escala.importe_excedente
                today = payment_group.payment_date
                prev_date = date(today.year,today.month,1)
                prev_payments_domain, prev_withholding_domain = payment_group.get_tax_period_payments_domain(self, payment_group)
                prev_payments = self.env["account.payment.group"].search(prev_payments_domain)
                if prev_payments:
                    vals['withholding_non_taxable_amount'] = 0
                    if vals['withholdable_base_amount'] == 0:
                        vals['withholdable_base_amount'] = vals['total_amount']
                    else:
                        vals['withholdable_base_amount'] = vals['withholdable_base_amount'] + payment_group.partner_id.default_regimen_ganancias_id.montos_no_sujetos_a_retencion
                    vals['period_withholding_amount'] = vals['withholdable_base_amount'] * payment_group.partner_id.default_regimen_ganancias_id.porcentaje_inscripto / 100
                    vals['previous_withholding_amount'] = sum(self.env['l10n_ar.payment.withholding'].search(prev_withholding_domain).mapped('amount'))
                    base_amount = vals['withholdable_base_amount']

                withholdable_base_amount = vals['withholdable_base_amount']
                period_withholding_amount = 0
                prev_payments_with_withholding = self.env['account.payment'].search([('payment_type','=','outbound'),('state','=','posted'),('payment_group_id.payment_date','>=',str(prev_date)),\
                                        ('payment_group_id.payment_date','<=',today),('partner_id','=',payment_group.partner_id.id),('tax_withholding_id','=',self.id)])
                if withholdable_base_amount > 0:
                    period_withholding_amount = withholdable_base_amount * payment_group.partner_id.default_regimen_ganancias_id.porcentaje_inscripto / 100
                if period_withholding_amount < self.withholding_non_taxable_minimum and not prev_payments_with_withholding:
                    period_withholding_amount = 0
                vals['withholdable_base_amount'] = withholdable_base_amount
                vals['period_withholding_amount'] = period_withholding_amount
                vals['date'] = payment_group.payment_date

                if regimen.porcentaje_inscripto == -1:
                    escala = []
                    if payment_group.regimen_ganancias_id.codigo_de_regimen == '119':
                        escala = self.env['afip.tabla_ganancias.escala'].search([
                        ('importe_desde', '<=', base_amount),
                        ('importe_hasta', '>', base_amount),
                        ('cod_regimen', '=', '119')], limit=1)
                    else:
                        escala = self.env['afip.tabla_ganancias.escala'].search([
                        ('importe_desde', '<=', base_amount),
                        ('importe_hasta', '>', base_amount),
                        ], limit=1)
                    if not escala:
                        raise UserError(
                            'No se encontro ninguna escala para el monto'
                            ' %s' % (base_amount))
                    amount = escala.importe_fijo

                    amount += (escala.porcentaje / 100.0) * (
                        base_amount - importe_excedente)

                    vals['period_withholding_amount'] = amount

                    vals['comment'] = "%s + (%s x %s)" % (
                        escala.importe_fijo,
                        base_amount - importe_excedente,
                        escala.porcentaje / 100.0)
                else:
                    amount = period_withholding_amount
                    vals['comment'] = "%s x %s" % (
                        base_amount, regimen.porcentaje_inscripto / 100.0)
            elif imp_ganancias_padron == 'NI':
                amount = base_amount * (
                    regimen.porcentaje_no_inscripto / 100.0)
                vals['comment'] = "%s x %s" % (
                    base_amount, regimen.porcentaje_no_inscripto / 100.0)
            vals['communication'] = "%s - %s" % (
                regimen.codigo_de_regimen, regimen.concepto_referencia)
        vals["amount"] = amount
        return vals

    def get_tax_period_payments_domain(self, tax, payment):
        """
        We make this here so it can be inherited by localizations
        Para un determinado pago (para saber fecha, impuesto y demas) obtenemos dos dominios:
        * previous_payments_domain: dominio para hacer search de payments que nos devuelva los pagos del mismo mes
        que son base de este impuesto (por ej. en ganancias de mismo regimen y que aplica impuesto)
        * previous_withholdings_domain: dominio para hacer search del impuesto aplicado en el mes
        """
        self = tax
        to_date = fields.Date.from_string(payment.date) or datetime.date.today()
        if not self.withholding_accumulated_payments or  self.withholding_accumulated_payments == 'month':
            from_relative_delta = relativedelta(day=1)
        elif self.withholding_accumulated_payments == 'year':
            from_relative_delta = relativedelta(day=1, month=1)
        from_date = to_date + from_relative_delta

        previous_payments_domain = [
            ('partner_id.commercial_partner_id', '=', payment.partner_id.commercial_partner_id.id),
            ('payment_date', '<=', to_date),
            ('payment_date', '>=', from_date),
            ('state', 'not in', ['draft', 'cancel', 'confirmed']),
            ('company_id', '=', payment.company_id.id),
        ]

        # for compatibility with public_budget we check state not in and not
        # state in posted. Just in case someone implements payments cancelled
        # on posted payment group, we remove the cancel payments (not the
        # draft ones as they are also considered by public_budget)
        previous_withholdings_domain = [
            ('payment_group_id.partner_id.commercial_partner_id', '=', payment.partner_id.commercial_partner_id.id),
            ('payment_group_id.payment_date', '<=', to_date),
            ('payment_group_id.payment_date', '>=', from_date),
            ('payment_group_id.state', '=', 'posted'),
            ('tax_id', '=', tax.id),
        ]

        if not isinstance(payment.id, models.NewId):
            previous_payments_domain.append(('id', '!=', payment.id))
            previous_withholdings_domain.append(('payment_group_id.id', '!=', payment.id))

        return (previous_payments_domain, previous_withholdings_domain)
