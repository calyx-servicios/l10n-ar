# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields

class ResPartnerArba_alicuot(models.Model):
    _inherit = "res.partner.arba_alicuot"

    padron_line_id = fields.Many2one(
        'account.padron.retention.perception.line',
        string="Line Patterns",
        ondelete='cascade'
    )

