# -*- coding: utf-8 -*-
{
    'name': 'Argentina - City Unique Code',
    'summary': 'Sequential unique code on res.city and the Argentina city catalog',
    'description': """
Adds a sequential ``unique_code`` field (000001, 000002, ...) on res.city,
auto-assigned on creation via an ir.sequence, and loads the Argentina city
catalog (name, zip code, AFIP locality code, state), merged from the AFIP
locality table and the CPA locality table with duplicates cross-checked out.
    """,
    'version': '19.0.1.0.0',
    'category': 'Localization/Argentina',
    'license': 'LGPL-3',
    'depends': ['base_address_extended'],
    'data': [
        'data/res_city_sequence.xml',
        'data/res.city.csv',
        'views/res_city_views.xml',
    ],
    'installable': True,
    'application': False,
}
