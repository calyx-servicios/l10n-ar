# Copyright 2015-2021 Tecnativa - Pedro M. Baeza
# Copyright 2017 Tecnativa - Vicent Cubells
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Supplier invoices on HR expenses (Calyx)",
    "summary": "Copia de hr_expense_invoice (OCA/hr-expense PR #382) hasta que se mergee en 19.0",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "author": "Tecnativa, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/hr-expense",
    "depends": ["hr_expense"],
    "data": [
        "views/account_move_views.xml",
        "views/hr_expense_views.xml",
        "wizard/hr_expense_post_wizard_views.xml",
    ],
    "installable": True,
    "excludes": ["hr_expense_invoice"],
}
