from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_ar_state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="Provincia",
        domain="[('country_id.code', '=', 'AR')]",
        help="Provincia con la que se asocia este impuesto de retención. "
             "Si se selecciona Buenos Aires, las retenciones con este impuesto "
             "se informarán automáticamente a ARBA.",
    )
