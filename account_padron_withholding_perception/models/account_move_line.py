# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"


    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.move_id.partner_id and self.move_id.move_type in ('out_invoice', 'out_refund'): # Customer Invoice
            if self.move_id.partner_id.line_padron_type_ids:
                domain = [
                    ('partner_id', '=', self.move_id.partner_id.id),
                    ('to_date', '>=', self.move_id.invoice_date),
                    ('from_date', '<=', self.move_id.invoice_date),
                ]
                arba_line = self.env['res.partner.arba_alicuot'].search(domain, limit=1)
                if arba_line:
                    tax_id = arba_line.padron_line_id.import_padron_id.padron_type_id.account_tax_perception_id.id
                    self.tax_ids = [(4, tax_id)]



