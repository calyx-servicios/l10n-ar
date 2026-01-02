{
    'name': 'Retenciones Automáticas',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Aplicación automática de retenciones en pagos',
    'description': """    """,
    'author': 'Calyx Servicios S.A.',
    'website': 'http://odoo.calyx-cloud.com.ar/',
    'depends': [
        'account',
        'account_padron_withholding_perception',
        'l10n_ar_tax',
        'account_payment_pro',
    ],
    'data': [
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
