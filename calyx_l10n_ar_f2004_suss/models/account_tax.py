from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    # Lets accountants explicitly mark withholding taxes reported in AFIP F2004.
    l10n_ar_tax_type = fields.Selection(
        selection_add=[("suss", "SUSS")],
        ondelete={"suss": "set null"},
    )
