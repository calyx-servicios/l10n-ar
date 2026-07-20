{
    "name": "Payment Currency Fixes",
    "version": "17.0.1.0.0",
    "summary": "Correcciones de moneda extranjera y retenciones en pagos",
    "description": """
        Corrige la cotizacion negativa, el importe de pago negativo por
        retenciones y el residual en facturas en moneda extranjera al conciliar
        pagos de account_payment_pro con l10n_ar_withholding_ux.
    """,
    "author": "Calyx Servicios S.A.",
    "website": "https://www.calyxservicios.com.ar/",
    "maintainers": ["Frankofe"],
    "category": "Accounting/Accounting",
    "application": False,
    "depends": [
        "account_payment_pro",
        "l10n_ar_withholding_ux",
    ],
    "data": [],
}
