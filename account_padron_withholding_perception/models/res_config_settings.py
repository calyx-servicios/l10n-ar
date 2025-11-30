# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    check_census_on_create = fields.Boolean(
        string="¿Looking for aliquots of withholdings and perceptions in partner?",
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(
            check_census_on_create = self.env['ir.config_parameter'].sudo().get_param(
                'account_padron_withholding_perception.check_census_on_create'))
        return res

    def set_values(self):
        self.ensure_one()
        super(ResConfigSettings, self).set_values()
        param = self.env['ir.config_parameter'].sudo()
        check_census_on_create = self.check_census_on_create or False
        param.set_param('account_padron_withholding_perception.check_census_on_create', check_census_on_create)

