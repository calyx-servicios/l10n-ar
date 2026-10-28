{
    "name": "Gastos: facturas de proveedor (pago por la compañía, tope y agrupación)",
    "version": "19.0.1.0.1",
    "category": "Human Resources/Expenses",
    "author": "Calyx Servicios",
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "depends": [
        "hr_expense_invoice_calyx",
        "hr_expense_sheet_calyx",
    ],
    "data": [
        "views/hr_expense_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
