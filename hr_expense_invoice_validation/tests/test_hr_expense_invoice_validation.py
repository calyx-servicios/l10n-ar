import re

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("post_install", "-at_install")
class TestHrExpenseInvoiceValidation(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_c.supplier_taxes_id = False
        # The deferred checks only apply to companies located in Argentina
        cls.company_data["company"].country_id = cls.env.ref("base.ar")
        cls.perception_tax = cls.env["account.tax"].create(
            {
                "name": "Percepción IIBB",
                "amount": 10.0,
                "type_tax_use": "purchase",
                "company_id": cls.company_data["company"].id,
            }
        )
        cls.expense = cls._create_approved_expense("Gasto con percepción")
        cls.expense.action_expense_create_invoice()
        cls.invoice = cls.expense.invoice_id

    @classmethod
    def _create_approved_expense(cls, name):
        # hr_expense_invoice_ux: the vendor bill can't go over the approved amount
        expense = cls.create_expenses(
            {
                "name": name,
                "product_id": cls.product_c.id,
                "total_amount_currency": 100.0,
                "payment_mode": "own_account",
                "vendor_id": cls.partner_a.id,
            }
        )
        expense.action_submit()
        expense._do_approve(check=False)
        return expense

    def _add_perception(self, amount):
        self.invoice.invoice_line_ids = [
            Command.create(
                {"name": "Percepción IIBB", "price_unit": amount, "tax_ids": False}
            )
        ]
        return self.invoice.invoice_line_ids[-1:]

    def _add_perception_tax(self):
        self.invoice.invoice_line_ids.tax_ids = [Command.link(self.perception_tax.id)]

    def _assert_over_approved_amount(self, expense=None):
        # The message of hr_expense_invoice_ux names the expense, the OCA one doesn't
        expense = expense or self.expense
        return self.assertRaisesRegex(ValidationError, re.escape(expense.name))

    def test_draft_bill_total_can_differ(self):
        perception = self._add_perception(10.0)
        self.assertAlmostEqual(self.invoice.amount_total, 110.0)
        perception.price_unit = 5.0
        self.assertAlmostEqual(self.invoice.amount_total, 105.0)
        self.invoice.invoice_line_ids = [Command.unlink(perception.id)]
        self.assertAlmostEqual(self.invoice.amount_total, 100.0)
        self.assertEqual(self.invoice.state, "draft")

    def test_post_bill_within_approved_amount(self):
        self._add_perception(10.0)
        self.invoice.invoice_line_ids[0].price_unit = 90.0
        self.invoice.action_post()
        self.assertEqual(self.invoice.state, "posted")
        self.assertAlmostEqual(self.invoice.amount_total, 100.0)

    def test_post_bill_over_approved_amount(self):
        self._add_perception(10.0)
        with self._assert_over_approved_amount():
            self.invoice.action_post()
        self.assertEqual(self.invoice.state, "draft")

    def test_reset_to_draft_bill_is_checked_again(self):
        self.invoice.action_post()
        self.invoice.button_draft()
        self._add_perception(10.0)
        self.assertEqual(self.invoice.state, "draft")
        with self._assert_over_approved_amount():
            self.invoice.action_post()

    def test_bill_without_expenses(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": self.expense.date,
                "invoice_line_ids": [
                    Command.create(
                        {"name": "Bill", "price_unit": 50.0, "tax_ids": False}
                    )
                ],
            }
        )
        bill.action_post()
        self.assertEqual(bill.state, "posted")

    def test_comparison_uses_product_price_precision(self):
        self.env.ref("product.decimal_price").digits = 0
        # hr_expense_invoice_calyx copies the bill total to the expense, so its
        # check only differs if the expense amount is changed afterwards
        self.expense.total_amount_currency = 100.4
        self.invoice.action_post()
        self.assertEqual(self.invoice.state, "posted")

    def test_non_ar_company_keeps_oca_behaviour(self):
        self.company_data["company"].country_id = self.env.ref("base.us")
        self.expense.total_amount_currency = 90.0
        with self.assertRaises(ValidationError):
            self.invoice._check_invoice_expense_ids()

    def test_draft_perception_over_approved_amount_not_blocked(self):
        self._add_perception_tax()
        self.env.flush_all()
        self.assertEqual(self.invoice.state, "draft")
        self.assertAlmostEqual(self.invoice.amount_total, 110.0)
        self.assertAlmostEqual(self.expense.total_amount, 110.0)
        self.assertGreater(self.expense.total_amount, self.expense.approved_amount)

    def test_post_perception_over_approved_amount_blocked(self):
        self._add_perception_tax()
        with self._assert_over_approved_amount():
            self.invoice.action_post()
        self.assertEqual(self.invoice.state, "draft")
        self.assertEqual(self.expense.state, "approved")
        # Once fixed, the bill can be posted
        self.invoice.invoice_line_ids.tax_ids = [Command.unlink(self.perception_tax.id)]
        self.invoice.action_post()
        self.assertEqual(self.invoice.state, "posted")

    def test_post_bill_under_approved_amount(self):
        self.invoice.invoice_line_ids.price_unit = 80.0
        self.invoice.action_post()
        self.assertEqual(self.invoice.state, "posted")
        self.assertAlmostEqual(self.expense.total_amount, 80.0)

    def test_non_ar_company_blocks_over_approved_amount_on_edit(self):
        self.company_data["company"].country_id = self.env.ref("base.us")
        with self._assert_over_approved_amount():
            self._add_perception_tax()
            self.env.flush_all()

    def test_link_posted_bill_is_checked_immediately(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": self.expense.date,
                "invoice_line_ids": [
                    Command.create(
                        {"name": "Bill", "price_unit": 150.0, "tax_ids": False}
                    )
                ],
            }
        )
        bill.action_post()
        expense = self._create_approved_expense("Gasto con factura publicada")
        with self._assert_over_approved_amount(expense):
            expense.invoice_id = bill
            self.env.flush_all()

    def test_oca_check_deferred_until_posting(self):
        # hr_expense_invoice_calyx copies the bill total to the expense, so its
        # check only fails if the expense amount is changed afterwards
        self.expense.total_amount_currency = 90.0
        self.invoice._check_invoice_expense_ids()
        with self.assertRaises(ValidationError) as error:
            self.invoice.action_post()
        self.assertNotIn(self.expense.name, str(error.exception))
        self.assertEqual(self.invoice.state, "draft")
