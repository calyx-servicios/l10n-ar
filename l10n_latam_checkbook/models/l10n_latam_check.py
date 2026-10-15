from odoo import api, fields, models


class L10nLatamCheck(models.Model):
    _inherit = "l10n_latam.check"

    name = fields.Char(compute="_compute_name", store=True, readonly=False)

    @api.depends("payment_id.l10n_latam_checkbook_id")
    def _compute_name(self):
        for rec in self:
            checkbook = rec.payment_id.l10n_latam_checkbook_id
            if rec.name or not checkbook or checkbook.type == "electronic":
                rec.name = rec.name
                continue
            siblings = rec.payment_id.l10n_latam_new_check_ids - rec
            rec.name = checkbook._get_next_available_number(
                rec.payment_id.payment_method_line_id,
                [name for name in siblings.mapped("name") if name],
            )
