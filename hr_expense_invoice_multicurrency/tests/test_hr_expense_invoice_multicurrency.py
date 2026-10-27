from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("post_install", "-at_install")
class TestHrExpenseInvoiceMulticurrency(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_hr_expense_invoice=True))
        cls.company_currency = cls.company_data["currency"]
        cls.cash_journal = cls.company_data["default_journal_cash"]
        # With the Accounting app (accountant) installed, a payment only gets a
        # journal entry if its method has an outstanding account
        cls.cash_journal.outbound_payment_method_line_ids.payment_account_id = (
            cls.env["account.chart.template"]
            .with_company(cls.company_data["company"])
            .ref("account_journal_payment_credit_account_id")
        )
        cls.product_c.supplier_taxes_id = False
        # The fix only applies to companies located in Argentina
        cls.company_data["company"].country_id = cls.env.ref("base.ar")
        # other_currency rate is 2.0: 500 in foreign currency = 250 in company one
        cls.expense = cls.env["hr.expense"].create(
            {
                "name": "Gasto en divisa",
                "employee_id": cls.expense_employee.id,
                "product_id": cls.product_c.id,
                "currency_id": cls.other_currency.id,
                "total_amount_currency": 500.0,
            }
        )
        cls.sheet = cls.env["hr.expense.sheet"].create(
            {
                "name": "Informe en divisa",
                "employee_id": cls.expense_employee.id,
                "expense_line_ids": cls.expense,
            }
        )

    def _create_invoice(self):
        self.expense.action_expense_create_invoice()
        invoice = self.expense.invoice_id
        invoice.partner_id = self.partner_a
        return invoice

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

    def _register_payment(self, sheet):
        res = sheet.action_register_payment()
        payment_form = Form(self.env[res["res_model"]].with_context(**res["context"]))
        payment_form.journal_id = self.cash_journal
        payment_form.save().action_create_payments()

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
        self.assertAlmostEqual(self.expense.price_unit, 250.0)

    def test_create_invoice_keeps_manual_rate(self):
        self.expense.total_amount = 300.0
        self.assertAlmostEqual(self.expense.currency_rate, 0.6)
        invoice = self._create_invoice()
        self.assertAlmostEqual(invoice.amount_total, 500.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -300.0)
        self.assertAlmostEqual(self.expense.total_amount_currency, 500.0)
        self.assertAlmostEqual(self.expense.total_amount, 300.0)

    def test_invoice_amount_check_converts_currency(self):
        invoice = self._create_invoice()
        # The check can be deferred until posting (hr_expense_invoice_validation)
        with self.assertRaises(ValidationError):
            invoice.amount_total = 400.0
            invoice.action_post()
        # Same amount in another currency, not equivalent
        with self.assertRaises(ValidationError):
            invoice.currency_id = self.company_currency
            invoice.action_post()
        # hr_expense_invoice mirrors the vendor bill total on its expenses, so a
        # currency mismatch can't be reached through the ORM: check conversion
        expense_company_currency = self.env["hr.expense"].create(
            {
                "name": "Gasto en moneda de la compañía",
                "employee_id": self.expense_employee.id,
                "product_id": self.product_c.id,
                "total_amount_currency": 250.0,
            }
        )
        self.assertAlmostEqual(
            invoice._get_expense_amount_in_move_currency(expense_company_currency),
            500.0,
        )

    def test_bill_keeps_expense_rate_when_date_changes(self):
        invoice = self._create_invoice()
        # other_currency rate was 3.0 in 2016: the vendor bill keeps the expense one
        invoice.invoice_date = "2016-06-01"
        self.assertAlmostEqual(invoice.invoice_currency_rate, 2.0)
        self.assertAlmostEqual(invoice.amount_total, 500.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -250.0)
        # So there's no rate to refresh
        self.assertAlmostEqual(invoice.expected_currency_rate, 2.0)
        invoice.refresh_invoice_currency_rate()
        self.assertAlmostEqual(invoice.amount_total_signed, -250.0)

    def test_bill_keeps_manual_rate_when_date_changes(self):
        self.expense.total_amount = 300.0
        invoice = self._create_invoice()
        invoice.invoice_date = "2016-06-01"
        self.assertAlmostEqual(invoice.amount_total, 500.0)
        self.assertAlmostEqual(invoice.amount_total_signed, -300.0)

    def test_amount_check_uses_expense_rate(self):
        # The vendor bill goes with the expense rate, not with the rate of the day
        self.expense.total_amount = 300.0
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": self.expense.date,
                "invoice_line_ids": [
                    Command.create({"name": "Bill", "price_unit": 300.0, "tax_ids": False})
                ],
            }
        )
        self.assertEqual(bill.currency_id, self.company_currency)
        self.assertAlmostEqual(
            bill._get_expense_amount_in_move_currency(self.expense), 300.0
        )

    def test_sheet_amount_check_converts_currency(self):
        invoice = self._create_invoice()
        invoice.action_post()
        self.sheet._validate_expense_invoice()
        self.expense.total_amount_currency = 400.0
        with self.assertRaises(UserError):
            self.sheet._validate_expense_invoice()

    def test_own_account_transfer_move_in_foreign_currency(self):
        invoice = self._create_invoice()
        invoice.action_post()
        self.sheet.action_approve_expense_sheets()
        self.sheet.action_sheet_move_post()
        self.assertEqual(self.sheet.state, "post")
        transfer_lines = self.expense.transfer_move_ids.line_ids.sorted("balance")
        self.assertEqual(transfer_lines.currency_id, self.other_currency)
        self.assertEqual(transfer_lines.mapped("amount_currency"), [-500.0, 500.0])
        self.assertEqual(transfer_lines.mapped("balance"), [-250.0, 250.0])
        self.assertEqual(invoice.payment_state, "paid")
        self.assertAlmostEqual(self.expense.amount_residual, 500.0)
        self._register_payment(self.sheet)
        self.assertAlmostEqual(self.expense.amount_residual, 0.0)
        self.assertEqual(self.sheet.payment_state, "paid")
        self.assertEqual(self.sheet.state, "done")

    def test_link_bill_sets_price_unit_in_company_currency(self):
        self.expense.invoice_id = self._create_posted_bill(500.0)
        self.assertEqual(self.expense.currency_id, self.other_currency)
        self.assertAlmostEqual(self.expense.total_amount, 250.0)
        self.assertAlmostEqual(self.expense.price_unit, 250.0)

    def test_price_unit_kept_once_submitted(self):
        bill = self._create_posted_bill(500.0)
        self.sheet.action_approve_expense_sheets()
        self.assertEqual(self.expense.state, "approved")
        self.expense.invoice_id = bill
        # Like the core compute, approved expenses are not recomputed, so the
        # value written by hr_expense_invoice (bill currency) is kept
        self.assertAlmostEqual(self.expense.price_unit, 500.0)

    def test_non_ar_company_keeps_oca_behaviour(self):
        self.company_data["company"].country_id = self.env.ref("base.us")
        self.assertNotIn("currency_id", self.expense._prepare_invoice_values())
        invoice = self._create_invoice()
        # hr_expense_invoice creates the bill in company currency
        self.assertEqual(invoice.currency_id, self.company_currency)
        self.assertEqual(self.expense.currency_id, self.company_currency)
        self.assertAlmostEqual(self.expense.price_unit, invoice.amount_total)
        # hr_expense_invoice checks still apply through super()
        with self.assertRaises(ValidationError):
            invoice.amount_total = 400.0
        invoice.action_post()
        self.sheet._validate_expense_invoice()
        self.expense.total_amount_currency = 400.0
        with self.assertRaises(UserError):
            self.sheet._validate_expense_invoice()
