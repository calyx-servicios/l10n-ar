from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_ar_cert_number = fields.Char(
        readonly=True,
        string="ARBA Withholding Certificate Number",
    )
    l10n_ar_dj_arba_id = fields.Many2one(
        "l10n_ar.dj.arba",
        "DJ ARBA",
        help="Declaración Jurada de ARBA asociada a esta retención",
    )
    # Compute en lugar de related para soportar líneas donde payment_group_id puede ser False.
    l10n_ar_arba_wh_mode = fields.Selection(
        selection=[("automatic", "Automatic"), ("batch_import", "Batch Import")],
        string="ARBA Withholding Mode",
        compute="_compute_l10n_ar_arba_wh_mode",
    )
    # Campo propio (no related) apuntando al campo definido en account_tax.py de este módulo.
    l10n_ar_state_id = fields.Many2one(
        related="tax_withholding_id.l10n_ar_state_id",
        string="Provincia (ARBA)",
        store=False,
    )
    # Booleano para poder usar en attrs de la vista: True cuando el impuesto tiene
    # la provincia de Buenos Aires configurada (base.state_ar_b).
    l10n_ar_is_arba_wh = fields.Boolean(
        string="Es retención ARBA (Pcia. Bs. As.)",
        compute="_compute_l10n_ar_is_arba_wh",
    )

    @api.depends("tax_withholding_id.l10n_ar_state_id")
    def _compute_l10n_ar_is_arba_wh(self):
        state_ar_b = self.env.ref("base.state_ar_b", raise_if_not_found=False)
        for rec in self:
            rec.l10n_ar_is_arba_wh = bool(
                state_ar_b and rec.tax_withholding_id.l10n_ar_state_id == state_ar_b
            )

    @api.depends(
        "payment_group_id.company_id.l10n_ar_arba_wh_mode",
        "company_id.l10n_ar_arba_wh_mode",
    )
    def _compute_l10n_ar_arba_wh_mode(self):
        for rec in self:
            company = rec.payment_group_id.company_id or rec.company_id
            rec.l10n_ar_arba_wh_mode = company.l10n_ar_arba_wh_mode if company else False

    def send_to_arba(self):
        """Send the withholding to ARBA webservice and store the certificate number"""
        for withholding in self.filtered(lambda x: not x.l10n_ar_cert_number):
            withholding.l10n_ar_dj_arba_id._create_withholding(withholding)
