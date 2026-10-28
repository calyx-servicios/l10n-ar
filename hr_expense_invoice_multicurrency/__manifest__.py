{
    "name": "Supplier invoices on HR expenses - Multi-currency",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Keep the expense currency when creating or linking vendor bills",
    "description": """
Fixes hr_expense_invoice_calyx (OCA hr_expense_invoice) for expenses in foreign
currency, only for companies located in Argentina (other companies keep the
OCA behaviour):

* The vendor bill created from an expense uses the expense currency and rate.
* The vendor bill keeps the expense rate when its date changes.
* The company amount of the expense is the vendor bill one, so both go with
  the same rate when the vendor bill is completed (e.g. adding perceptions).
* The transfer entry for expenses paid by the employee keeps the amount in
  foreign currency, so it reconciles fully with the vendor bill.
    """,
    "author": "Calyx Servicios",
    "website": "http://odoo.calyx-cloud.com.ar/",
    "depends": ["hr_expense_invoice_calyx"],
    "installable": True,
    "auto_install": False,
    "license": "AGPL-3",
}
