from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    payment_group_id = fields.Many2one(
        comodel_name="account.payment.group"
    )
