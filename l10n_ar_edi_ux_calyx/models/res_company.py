from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _check_match_between_certificate_and_company(self):
        # EXTEND l10n_ar_edi_ux
        """Skip the check in the testing environment: homologation certificates are
        issued by WSASS to the CUIT of whoever requests them, which usually is not
        the company's, and ARCA accepts them."""
        self.ensure_one()
        if self.l10n_ar_afip_ws_environment == "testing":
            return
        return super()._check_match_between_certificate_and_company()
