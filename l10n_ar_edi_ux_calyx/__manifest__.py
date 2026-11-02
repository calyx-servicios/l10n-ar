# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
#
# Temporary patch over ingadhoc/odoo-argentina-ee :: l10n_ar_edi_ux.
#
# Since commit a3f941f (ingadhoc/odoo-argentina-ee#1038) l10n_ar_edi_ux checks
# that the CUIT of the ARCA certificate matches the company's before asking
# ARCA for a token, whatever the environment. Homologation certificates are
# issued by WSASS to the CUIT of whoever requests them, which usually is not
# the company's, and ARCA accepts them: Odoo's own l10n_ar_edi tests use a
# certificate of CUIT 20313932975 for a company with CUIT 30111111118. The
# check therefore breaks every ARCA connection in the testing environment.
# This module skips it there and keeps it in production.
#
# Drop it once the fix lands upstream.
{
    "name": "Argentinian Electronic Invoicing UX (Calyx)",
    "summary": "Skip the certificate/company CUIT check in the ARCA testing environment",
    "version": "19.0.1.0.0",
    "category": "Localization/Argentina",
    "author": "Calyx Servicios",
    "license": "AGPL-3",
    "depends": ["l10n_ar_edi_ux"],
    "installable": True,
    "application": False,
}
