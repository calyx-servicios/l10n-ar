from odoo import fields, models


class AccountAccountTag(models.Model):
    _inherit = 'account.account.tag'

    jurisdiction_code = fields.Char(
        string='Código de Jurisdicción',
        size=3,
        help='Código de jurisdicción para IIBB (Ingresos Brutos) en Argentina'
    )
