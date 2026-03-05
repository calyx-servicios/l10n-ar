from odoo import api, fields, models


class L10nArPaymentWithholding(models.Model):
    _inherit = "l10n_ar.payment.withholding"

    l10n_ar_cert_number = fields.Char(readonly=True, string="ARBA Withholding Certificate Number")
    l10n_ar_dj_arba_id = fields.Many2one(
        "l10n_ar.dj.arba", "DJ ARBA", help="Declaración Jurada de ARBA asociada a esta retención"
    )
    # Compute en lugar de related para soportar líneas creadas desde payment_group
    # (donde payment_id es NULL y la cadena related company_id.l10n_ar_arba_wh_mode
    # devuelve False porque company_id en el modelo base es related='payment_id.company_id').
    l10n_ar_arba_wh_mode = fields.Selection(
        selection=[("automatic", "Automatic"), ("batch_import", "Batch Import")],
        string="ARBA Withholding Mode",
        compute="_compute_l10n_ar_arba_wh_mode",
    )
    # Campo propio (no related) apuntando al campo definido en account_tax.py de este módulo.
    # Si el impuesto no tiene provincia configurada, el campo devuelve False y el filtro
    # simplemente no selecciona esa línea, sin romper.
    l10n_ar_state_id = fields.Many2one(
        related="tax_id.l10n_ar_state_id",
        string="Provincia (ARBA)",
        store=False,
    )

    @api.depends(
        "payment_group_id.company_id.l10n_ar_arba_wh_mode",
        "payment_id.company_id.l10n_ar_arba_wh_mode",
    )
    def _compute_l10n_ar_arba_wh_mode(self):
        for rec in self:
            company = rec.payment_group_id.company_id or rec.payment_id.company_id
            rec.l10n_ar_arba_wh_mode = company.l10n_ar_arba_wh_mode if company else False

    def send_to_arba(self):
        """Send the withholding to ARBA webservice and store the certificate number"""
        for withholding in self.filtered(lambda x: not x.l10n_ar_cert_number):
            withholding.l10n_ar_dj_arba_id._create_withholding(withholding)
