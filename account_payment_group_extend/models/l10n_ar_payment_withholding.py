from odoo import models, fields, api


class l10nArPaymentRegisterWithholding(models.Model):
    _inherit = 'l10n_ar.payment.withholding'

    payment_group_id = fields.Many2one(
        comodel_name='account.payment.group',
        ondelete='cascade'
    )
    payment_id = fields.Many2one(
        required=False
    )
    account_id = fields.Many2one(
        comodel_name="account.account",
        compute="_compute_account_id",
        string="Cuenta"
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_currency_id",
        store=True,
        related=False
    )

    @api.onchange("tax_id")
    def _compute_account_id(self):
        for rec in self:
            rec.account_id = False
            if rec.payment_group_id and rec.payment_group_id.partner_type:
                partner_type = rec.payment_group_id.partner_type
                if partner_type == "supplier":
                    account = rec.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.account_id)
                elif partner_type == "customer":
                    account = rec.tax_id.refund_repartition_line_ids.filtered(lambda x: x.account_id)
                if account:
                    rec.account_id = account[0].account_id.id

    @api.onchange("payment_group_id", "payment_id")
    def _compute_currency_id(self):
        ARS = self.env.ref("base.ARS").id
        for rec in self:
            rec.currency_id = False
            if rec.payment_group_id:
                rec.currency_id = ARS
            elif rec.payment_id and rec.payment_id.company_currency_id:
                rec.currency_id = rec.payment_id.company_currency_id.id
