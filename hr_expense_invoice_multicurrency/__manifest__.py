{
    "name": "Supplier invoices on HR expenses - Multi-currency",
    "version": "18.0.1.0.0",
    "category": "Human Resources",
    "summary": "Keep the expense currency when creating or linking vendor bills",
    "description": """
Fixes hr_expense_invoice (OCA) for expenses in foreign currency, only for
companies located in Argentina (other companies keep the OCA behaviour):

* The vendor bill created from an expense uses the expense currency and rate.
* The amount check between expense and vendor bill converts currencies with
  the expense rate.
* The transfer entry for expenses paid by the employee keeps the amount in
  foreign currency, so it reconciles fully with the vendor bill.
    """,
    "author": "Calyx Servicios",
    "website": "https://grupopgk.calyx-cloud.com.ar/",
    "depends": ["hr_expense_invoice"],
    "installable": True,
    "auto_install": False,
    "license": "AGPL-3",
}
