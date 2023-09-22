# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = "res.partner"

    line_padron_type_ids = fields.Many2many('account.padron.retention.perception.type',
                                    'res_partner_padron_type_rel',  'padron_type_id', 'partner_id',
                                    string="Rel Partner Patterns", copy=False, readonly=False)


    @api.model
    def create(self, values):
        record = super(ResPartner, self).create(values)
        if (record.l10n_ar_afip_responsibility_type_id.code not in ('5', '7', '8', '9')) and self.env['ir.config_parameter'].get_param('account_padron_withholding_perception.check_census_on_create') and record.vat:
            padrones = self.env['account.padron.retention.perception.type'].search([]).ids
            record.sudo().write({'line_padron_type_ids': [(6, 0, padrones)]})
        return record

    def write(self, values):
        return_var = None

        for rec in self:
            if 'line_padron_type_ids' in values:
                padron_control = {}
                for line_obj in rec.line_padron_type_ids:
                    padron_control[str(line_obj.id)] = line_obj

                return_var = super(ResPartner, rec).write(values)

                for padron_index in padron_control:
                    padron_control[padron_index].partner_control()

                rec.import_padron_server_partner()
            else:
                return_var = super(ResPartner, rec).write(values)

        return return_var

    def import_padron_server_partner(self, context={}):
        partner_dic={} #padron_type_id
        for partner_obj in self:
            partner_dic[partner_obj.vat] = partner_obj
            context['partner_dic'] = partner_dic
            for padron_obj in partner_obj.line_padron_type_ids:
                result_ids = self.env['account.import.padron.ret.perc'].search([
                                                                ('padron_type_id', '=', padron_obj.id),
                                                                ('state','=', 'open')
                                                                ])
                for import_obj in result_ids:
                    import_obj.import_padron_server(context=context)

    def get_current_alicuota(self, padron_type, date_invoice, company_id):
        current_alicuota = None

        for alicuota in self.arba_alicuot_ids.filtered(lambda x: x.company_id.id == company_id.id):
            if alicuota.tag_id.id == padron_type.account_tag_perception_id.id:
                if alicuota.from_date <= date_invoice <= alicuota.to_date:
                    current_alicuota = alicuota
                    break

        return current_alicuota



