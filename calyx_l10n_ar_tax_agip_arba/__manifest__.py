# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Calyx - AGIP y ARBA Padron (BD Externa)",
    "version": "18.0.1.2.0",
    "author": "Calyx Servicios S.A.",
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting / Localizations / Argentina",
    "summary": "Calyx: extensión con cron mensual para padrón AGIP/ARBA.",
    "depends": [
        "l10n_ar_tax_agip_arba",
    ],
    "data": [
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
}
