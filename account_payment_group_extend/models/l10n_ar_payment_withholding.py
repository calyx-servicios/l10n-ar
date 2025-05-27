from odoo import models, fields


class l10nArPaymentRegisterWithholding(models.Model):
    _inherit = 'l10n_ar.payment.withholding'

    payment_group_id = fields.Many2one(
        comodel_name='account.payment.group',
        ondelete='cascade'
    )
    payment_id = fields.Many2one(
        required=False
    )
