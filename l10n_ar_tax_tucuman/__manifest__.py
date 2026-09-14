# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Padrón Tucumán - BD Externa",
    "version": "19.0.1.1.0",
    "author": "Calyx Servicios S.A.",
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting / Localizations / Argentina",
    "summary": "Percepciones y retenciones de IIBB Tucumán desde la BD externa de padrones.",
    "description": """
Padrón IIBB Tucumán - BD Externa
================================

Resuelve las alícuotas de percepción y retención de Ingresos Brutos de Tucumán
consultando la base de datos externa de padrones (esquema eg_tucuman):

* Agrega el webservice "Padrón Tucumán" a las posiciones fiscales.
* Agrega el campo "Computa sobre bruto" en los impuestos de venta, que calcula la
  percepción sobre Neto + IVA en lugar de Neto.
* Elige el impuesto de base neta o bruta según el padrón.
* En retenciones, elige la marca del padrón (E, CL, CM o art2) según la posición
  fiscal y la configuración de Ingresos Brutos del proveedor.
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
