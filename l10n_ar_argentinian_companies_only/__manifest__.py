# -*- coding: utf-8 -*-
{
    'name': "l10n_ar_argentinian_companies_only",

    'summary': "This module makes the ar modules views load only for Argentinian companies",

    'description': """
This module ensures that views specific to Argentinian companies are only loaded when the company is set to Argentina.
    """,

    "author": "Calyx Servicios S.A.",
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",

    'category': 'Localization/Argentina',
    'version': '19.0.1.0.0',

    'depends': [
        'base',
        'contacts',
        'mail',
    ],

    'data': [
        'data/ir_config_parameter.xml',
    ],

}

