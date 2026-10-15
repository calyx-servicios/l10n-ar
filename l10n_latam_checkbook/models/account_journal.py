from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_latam_use_checkbooks = fields.Boolean(
        string="Use checkbooks?",
        compute="_compute_l10n_latam_use_checkbooks",
        store=True,
        readonly=False,
        copy=False,
    )
    l10n_latam_checkbook_ids = fields.One2many(
        "l10n_latam.checkbook", "journal_id", "Checkbooks"
    )

    @api.model
    def _get_checkbooks_by_default_country_codes(self):
        return ["AR"]

    @api.depends("outbound_payment_method_line_ids", "company_id")
    def _compute_l10n_latam_use_checkbooks(self):
        country_codes = self._get_checkbooks_by_default_country_codes()
        for rec in self:
            rec.l10n_latam_use_checkbooks = rec.l10n_latam_use_checkbooks or (
                rec.company_id.country_id.code in country_codes
                and "own_checks" in rec.outbound_payment_method_line_ids.mapped("code")
            )
