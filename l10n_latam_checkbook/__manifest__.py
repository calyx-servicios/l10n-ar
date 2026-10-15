# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Latam Checkbooks",
    "version": "18.0.1.0.0",
    "author": "Calyx Servicios S.A.",
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "LGPL-3",
    "category": "Accounting / Localizations / Argentina",
    "summary": "Chequeras para numerar cheques propios.",
    "depends": [
        "l10n_latam_check",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_latam_checkbook_views.xml",
        "views/account_journal_views.xml",
        "views/account_payment_views.xml",
    ],
    "installable": True,
    "application": False,
}
