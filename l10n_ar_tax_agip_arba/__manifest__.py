# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "AGIP y ARBA Padron - BD Externa",
    "version": "18.0.1.0.0",
    "author": "Calyx Servicios S.A.",
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting / Localizations / Argentina",
    "summary": "Override de _get_agip_data y _get_arba_data para traer alícuotas desde BD externa.",
    "depends": [
        "l10n_ar_tax",
    ],
    "external_dependencies": {
        "python": ["psycopg2"],
    },
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
