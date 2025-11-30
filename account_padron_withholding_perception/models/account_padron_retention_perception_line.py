# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, _
from odoo.exceptions import UserError



class AccountPadronRetentionPerceptionLine(models.Model):
    _name = 'account.padron.retention.perception.line'
    _description = _("Account patterns withholding and perception line")

    import_padron_id = fields.Many2one('account.import.padron.ret.perc', string="Import Header", ondelete='cascade')
    padron_type_id = fields.Many2one('account.padron.retention.perception.type',  string='Type Padron', ondelete='cascade')
    arba_alicuot_id = fields.Many2one('res.partner.arba_alicuot', string="Perception Related", ondelete='cascade')
    company_id = fields.Many2one('res.company', related='padron_type_id.company_id')
    in_padron = fields.Boolean(default=True)
    cuit = fields.Char(string='CUIT')
    partner_id = fields.Many2one('res.partner', string="Partner")
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To')
    percentage_retention = fields.Float(string='Percentage Retention')
    percentage_perception = fields.Float(string='Percentage Perception')


    def create_arba_perception_line(self):
        # Crear las percepciones
        for self_obj in self:
            if not self_obj.padron_type_id.company_id:
                raise UserError(_('Please, select a company for padron type: {}'.format(self_obj.padron_type_id.name)))
            vals = {
                'tag_id': self_obj.padron_type_id.account_tag_perception_id.id ,
                'from_date': self_obj.date_from ,
                'to_date': self_obj.date_to ,
                'company_id': self_obj.padron_type_id.company_id.id,
                'alicuota_percepcion': self_obj.percentage_perception,
                'alicuota_retencion': self_obj.percentage_retention,
                'partner_id': self_obj.partner_id.id,
                'padron_line_id': self_obj.id,
            }
            if not self_obj.arba_alicuot_id:

                arba_alicuot = self.env['res.partner.arba_alicuot'].sudo().create(vals)
                self_obj.sudo().write({'arba_alicuot_id': arba_alicuot.id})
            else:
                self_obj.arba_alicuot_id.sudo().write(vals)
