from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    uses_account_payment_group = fields.Boolean(
        string="Recibos de Cobros/Pagos Argentina"
    )
