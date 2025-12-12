{
    'name': 'Percepciones Automáticas en Ordenes y Facturas de Venta',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Aplicación automática de percepciones en ventas para Argentina',
    'description': """
        Módulo para calcular y aplicar automáticamente percepciones en facturas de ventas.
        Hereda de account_padron_withholding_perception para extender funcionalidad a ventas.
    """,
    'author': 'Calyx Servicios S.A.',
    'website': 'http://odoo.calyx-cloud.com.ar/',
    'depends': [
        'account',
        'sale',
        'l10n_ar',
        'account_padron_withholding_perception',
    ],
    'data': [
        'data/account_account_tag_data.xml',
        'views/account_move_view.xml',
        'views/sale_order_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
