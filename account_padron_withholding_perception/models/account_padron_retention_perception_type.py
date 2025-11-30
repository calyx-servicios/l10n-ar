# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, api, _

class AccountPadronRetentionPerceptionType(models.Model):
    _name = 'account.padron.retention.perception.type'
    _description = _("Account Patterns Withholding and Perception type")

    name = fields.Char(string='Name')
    description = fields.Char(string='Description', size=256)
    company_id = fields.Many2one('res.company')
    payment_journal_retention_id = fields.Many2one('account.journal', string="Payment Journal Retention")
    account_tax_retention_id = fields.Many2one('account.tax', string="Account Tax Retention")
    account_tax_perception_id = fields.Many2one('account.tax', string="Account Tax Perception")
    account_tag_perception_id = fields.Many2one('account.account.tag', string="Account Tag Perception")
    minimum_calcule_perception = fields.Float(string='Minimum Calcule Perception')
    minimum_base_perception = fields.Float(string='Minimum Base Perception')
    minimum_calcule_retention = fields.Float(string='Minimum Calcule Retention')
    minimum_base_retention = fields.Float(string='Minimum Base Retention')
    line_partner_ids = fields.Many2many('res.partner', 'res_partner_padron_type_rel',
                                'partner_id', 'padron_type_id', string="Rel Partner Padron",
                                copy=False, readonly=False)
    padron_line_ids = fields.One2many('account.padron.retention.perception.line', 'padron_type_id',
                                string='Lines Retention', readonly=False)
    server_host = fields.Char(string='Server Host')
    server_database = fields.Char(string='Server Database')
    server_user = fields.Char(string='Server User')
    server_password = fields.Char(string='Server Password')
    server_port = fields.Char(string='Server Port')
    type = fields.Selection([
        ('agip', 'AGIP'),
        ('arba', 'ARBA'),
        ('other', 'Other')
    ], string='Type', default='other')
    default_percentage_perception = fields.Float(string='Default Percentage Perception')
    default_percentage_retention = fields.Float(string='Default Percentage Retention')


    def partner_control(self, context=None):
        partner_dic={}
        for rec in self:
            if context and 'partner_dic' in context:
                partner_dic = context['partner_dic']
            else:
                for line_obj in rec.line_partner_ids:
                    partner_dic[str(line_obj.id)] = line_obj
            for line_obj in rec.padron_line_ids:
                if not str(line_obj.partner_id.id) in partner_dic:
                   line_obj.unlink()

