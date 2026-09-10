# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Padrón Tucumán - BD Externa",
    "version": "19.0.1.0.0",
    "author": "Calyx Servicios S.A.",
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting / Localizations / Argentina",
    "summary": "Percepciones de IIBB Tucumán desde la BD externa de padrones.",
    "description": """
Padrón IIBB Tucumán - BD Externa
================================

Resuelve la alícuota de percepción de Ingresos Brutos de Tucumán consultando la
base de datos externa de padrones (esquema eg_tucuman), y aplica el impuesto que
corresponda según la base que informe el padrón:

* Agrega el webservice "Padrón Tucumán" a las posiciones fiscales.
* Agrega el campo "Computa sobre bruto" en los impuestos de venta, que calcula la
  percepción sobre Neto + IVA en lugar de Neto.
* Elige entre las dos variantes de cada alícuota según el padrón.

Sólo percepciones: las retenciones no están implementadas.
""",
    "depends": [
        "l10n_ar_tax",
    ],
    "external_dependencies": {
        "python": ["psycopg2"],
    },
    "data": [
        "views/account_tax_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
