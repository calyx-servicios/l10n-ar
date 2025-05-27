# -*- coding: utf-8 -*-
{
    "name": "Exemption Withholdings",
    "summary": """
        Adds to the partner the possibility of being
        exempt from withholdings.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["PerezGabriela"],
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Account",
    "version": "17.0.1.0.0",
    "installable": True,
    "application": False,
    "depends": [
        'base',
        'l10n_ar_account_withholding',
        'account_payment_group',
        'l10n_ar_withholding_automatic'
    ],
    "data": [
        'security/ir.model.access.csv',
        'views/res_partner_view.xml',
        'views/exemption_withholding_view.xml',
        # 'views/payment_view.xml',
    ],
}
