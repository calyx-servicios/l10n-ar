from odoo import Command
from odoo.tests import Form, tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("post_install", "-at_install")
class TestHrExpenseInvoiceMulticurrency(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_currency = cls.company_data["currency"]
        cls.product_c.supplier_taxes_id = False
        # The fix only applies to companies located in Argentina
        cls.company_data["company"].country_id = cls.env.ref("base.ar")
        # other_currency rate is 2.0: 500 in foreign currency = 250 in company one
        cls.expense = cls.create_expenses(
            {
                "name": "Gasto en divisa",
                "product_id": cls.product_c.id,
                "currency_id": cls.other_currency.id,
                "total_amount_currency": 500.0,
                "payment_mode": "own_account",
                "vendor_id": cls.partner_a.id,
            }
        )

    def _approve(self, expenses):
        expenses.action_submit()
        expenses._do_approve(check=False)

    def _create_invoice(self):
        # Approved first: hr_expense_invoice_ux only bills approved expenses
        self._approve(self.expense)
        self.expense.action_expense_create_invoice()
        return self.expense.invoice_id

    def _create_posted_bill(self, amount):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "currency_id": self.other_currency.id,
                "invoice_date": self.expense.date,
                "invoice_line_ids": [
                    Command.create(
                        {"name": "Bill", "price_unit": amount, "tax_ids": False}
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def _pay_employee(self, expense):
        payment_register = (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move", active_ids=expense.account_move_id.ids
            )
            .create(
                {
                    "journal_id": self.company_data["default_journal_bank"].id,
                    "payment_method_line_id": self.outbound_payment_method_line.id,
                }
            )
        )
        return payment_register._create_payments()

    def _skip_if_bills_need_approval(self):
        if "hr_expense_invoice_ux" in self.env.registry._init_modules:
            self.skipTest("hr_expense_invoice_ux only bills approved expenses")

    def test_create_invoice_keeps_expense_currency(self):
        self.assertAlmostEqual(self.expense.total_amount, 250.0)
        invoice = self._create_invoice()
        self.assertEqual(invoice.currency_id, self.other_currency)
        self.assertAlmostEqual(invoice.invoice_line_ids.price_unit, 500.0)
        self.assertAlmostEqual(invoice.amount_total, 500.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -250.0)
        self.assertEqual(self.expense.currency_id, self.other_currency)
        self.assertAlmostEqual(self.expense.total_amount_currency, 500.0)
        self.assertAlmostEqual(self.expense.total_amount, 250.0)

    def test_create_invoice_keeps_manual_rate(self):
        self.expense.total_amount = 300.0
        self.assertAlmostEqual(self.expense.currency_rate, 0.6)
        invoice = self._create_invoice()
        self.assertAlmostEqual(invoice.amount_total, 500.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -300.0)
        self.assertAlmostEqual(self.expense.total_amount_currency, 500.0)
        self.assertAlmostEqual(self.expense.total_amount, 300.0)

    def test_bill_keeps_expense_rate_when_date_changes(self):
        invoice = self._create_invoice()
        # other_currency rate was 3.0 in 2016: the vendor bill keeps the expense one
        invoice.invoice_date = "2016-06-01"
        self.assertAlmostEqual(invoice.invoice_currency_rate, 2.0)
        self.assertAlmostEqual(invoice.amount_total, 500.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -250.0)
        # So there's no rate to refresh
        self.assertEqual(invoice.expected_currency_rate, invoice.invoice_currency_rate)
        invoice.refresh_invoice_currency_rate()
        self.assertAlmostEqual(invoice.amount_total_signed, -250.0)

    def test_bill_keeps_expense_rate_when_date_changes_in_form(self):
        invoice = self._create_invoice()
        with Form(invoice) as invoice_form:
            invoice_form.invoice_date = "2016-06-01"
            self.assertAlmostEqual(invoice_form.invoice_currency_rate, 2.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -250.0)

    def test_bill_keeps_manual_rate_when_date_changes(self):
        self.expense.total_amount = 300.0
        invoice = self._create_invoice()
        invoice.invoice_date = "2016-06-01"
        self.assertAlmostEqual(invoice.amount_total, 500.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -300.0)

    def test_bill_completed_keeps_rate_and_expense_follows(self):
        invoice = self._create_invoice()
        # A perception on the bill: the expense takes the new total and its
        # company amount, so it keeps the bill rate
        invoice.invoice_line_ids.price_unit = 470.0
        invoice.invoice_line_ids = [
            Command.create(
                {"name": "Percepción IIBB", "price_unit": 10.0, "tax_ids": False}
            )
        ]
        self.assertAlmostEqual(invoice.amount_total, 480.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -240.0)
        self.assertAlmostEqual(self.expense.total_amount_currency, 480.0)
        self.assertAlmostEqual(self.expense.total_amount, 240.0)
        self.assertAlmostEqual(self.expense.currency_rate, 0.5)
        self.assertEqual(invoice.expected_currency_rate, invoice.invoice_currency_rate)
        # other_currency rate was 3.0 in 2016: both keep the bill one
        invoice.invoice_date = "2016-06-01"
        self.assertAlmostEqual(invoice.invoice_currency_rate, 2.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -240.0)
        self.assertAlmostEqual(self.expense.total_amount, 240.0)
        self.assertAlmostEqual(self.expense.currency_rate, 0.5)

    def test_bill_manual_rate_is_kept(self):
        invoice = self._create_invoice()
        invoice.invoice_currency_rate = 2.5
        self.assertAlmostEqual(invoice.amount_total_signed, -200.0)
        self.assertAlmostEqual(self.expense.total_amount, 200.0)
        self.assertEqual(invoice.expected_currency_rate, 2.5)
        invoice.invoice_date = "2016-06-01"
        self.assertAlmostEqual(invoice.invoice_currency_rate, 2.5)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_bill_currency_change_takes_rate_of_the_day(self):
        third_currency = self.setup_other_currency("EUR", rates=[("2017-01-01", 4.0)])
        invoice = self._create_invoice()
        with Form(invoice) as invoice_form:
            invoice_form.currency_id = third_currency
        self.assertAlmostEqual(invoice.invoice_currency_rate, 4.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -125.0)
        self.assertEqual(self.expense.currency_id, third_currency)
        self.assertAlmostEqual(self.expense.total_amount, 125.0)

    def test_own_account_transfer_move_in_foreign_currency(self):
        invoice = self._create_invoice()
        invoice.action_post()
        self.post_expenses_with_wizard(self.expense)
        transfer_lines = self.expense.account_move_id.line_ids.sorted("balance")
        self.assertEqual(transfer_lines.currency_id, self.other_currency)
        self.assertEqual(transfer_lines.mapped("amount_currency"), [-500.0, 500.0])
        self.assertEqual(transfer_lines.mapped("balance"), [-250.0, 250.0])
        self.assertEqual(invoice.payment_state, "paid")
        self.assertEqual(
            self.expense.state,
            self.env["account.move"]._get_invoice_in_payment_state(),
        )
        # The employee is paid in the expense currency. account_payment_pro (ADHOC)
        # pays the commercial partner, and the test employee contact belongs to
        # the company
        self.expense_employee.work_contact_id.parent_id = False
        payment = self._pay_employee(self.expense)
        self.assertEqual(payment.currency_id, self.other_currency)
        self.assertAlmostEqual(payment.amount, 500.0)
        self.assertEqual(self.expense.state, "paid")

    def test_create_invoice_sets_price_unit_in_company_currency(self):
        self._skip_if_bills_need_approval()
        self.expense.action_expense_create_invoice()
        self.assertEqual(self.expense.state, "draft")
        self.assertAlmostEqual(self.expense.price_unit, 250.0)

    def test_link_bill_sets_price_unit_in_company_currency(self):
        self._skip_if_bills_need_approval()
        self.expense.invoice_id = self._create_posted_bill(500.0)
        self.assertEqual(self.expense.currency_id, self.other_currency)
        self.assertAlmostEqual(self.expense.total_amount, 250.0)
        self.assertAlmostEqual(self.expense.price_unit, 250.0)

    def test_price_unit_kept_once_approved(self):
        bill = self._create_posted_bill(500.0)
        self._approve(self.expense)
        self.assertEqual(self.expense.state, "approved")
        self.expense.invoice_id = bill
        # Like the core compute, approved expenses are not recomputed, so the
        # value written by hr_expense_invoice_calyx (bill currency) is kept
        self.assertAlmostEqual(self.expense.price_unit, 500.0)

    def test_non_ar_company_keeps_oca_behaviour(self):
        self.company_data["company"].country_id = self.env.ref("base.us")
        self.assertNotIn("currency_id", self.expense._prepare_invoice_values())
        bill = self._create_posted_bill(500.0)
        self._approve(self.expense)
        self.expense.invoice_id = bill
        # The vendor bill takes the rate of the day when its date changes
        bill.button_draft()
        bill.invoice_date = "2016-06-01"
        self.assertAlmostEqual(bill.invoice_currency_rate, 3.0)
        # The expense company amount isn't taken from the bill
        self.assertAlmostEqual(self.expense.total_amount, 250.0)
        # And the transfer entry goes in company currency
        for command in self.expense._prepare_transfer_move_lines_vals():
            self.assertNotIn("currency_id", command[2])
