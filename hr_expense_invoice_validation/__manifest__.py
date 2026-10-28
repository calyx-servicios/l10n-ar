{
    "name": "Supplier invoices Validation on HR expenses",
    "version": "19.0.1.1.0",
    "category": "Accounting",
    "summary": "Check the vendor bill total against its expenses when posting",
    "description": """
For companies located in Argentina, the amount checks between a vendor bill and
its expenses run when posting the vendor bill instead of on every change, so a
draft vendor bill can be completed freely (e.g. adding perceptions):

* hr_expense_invoice_calyx (OCA) check of the vendor bill total.
* hr_expense_invoice_ux check of the approved amount of the expenses.

Other companies keep the behaviour of both modules.
    """,
    "icon": "/account/static/description/icon.png",
    "author": "Calyx Servicios S.A.",
    "website": "https://grupopgk.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": [
        "hr_expense_invoice_ux"
    ],
    "data": [
    ],
    "demo": [],
}
