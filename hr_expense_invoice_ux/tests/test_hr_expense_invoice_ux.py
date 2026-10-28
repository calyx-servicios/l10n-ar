from odoo.tests import Form, tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("post_install", "-at_install")
class TestHrExpenseInvoiceUx(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_c.supplier_taxes_id = False
        cls.expense = cls.create_expenses(
            {
                "name": "Gasto pagado por el empleado",
                "product_id": cls.product_c.id,
                "total_amount_currency": 100.0,
                "payment_mode": "own_account",
            }
        )

    def test_vendor_hidden_in_draft_employee_expense(self):
        with Form(self.expense) as expense_form, self.assertRaises(AssertionError):
            expense_form.vendor_id = self.partner_a

    def test_vendor_set_from_form_to_create_vendor_bill(self):
        self.expense.action_submit()
        self.expense._do_approve(check=False)
        with Form(self.expense) as expense_form:
            expense_form.vendor_id = self.partner_a
        self.expense.action_expense_create_invoice()
        self.assertEqual(self.expense.invoice_id.partner_id, self.partner_a)
