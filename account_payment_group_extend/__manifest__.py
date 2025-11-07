{
    "name": "Extension de Grupos de Pago con Múltiples Métodos",
    "version": "17.0.1.0.30",
    "category": "Accounting",
    "author": "Felipe Carlini",
    "license": "AGPL-3",
    "application": False,
    'installable': True,
    "depends": [
        "account_payment_group",
        "l10n_ar_withholding_ux",
        "l10n_ar_account_withholding",
        "l10n_ar_withholding_automatic"
    ],
    "data": [
        "views/account_payment_group_view.xml",
        "views/account_move_view.xml",
        "views/account_payment_view.xml",
        "views/res_company_view.xml",
        "views/report_withholding_certificate_templates.xml"
    ],
}
