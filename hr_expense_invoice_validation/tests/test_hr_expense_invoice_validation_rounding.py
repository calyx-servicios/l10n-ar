from odoo import Command
from odoo.tests import Form, tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("post_install", "-at_install")
class TestHrExpenseInvoiceValidationRounding(TestExpenseCommon):
    """BTL: an expense of USD 100 with 21% VAT included, dated before to take the
    rate of that day, gave a vendor bill of USD 99.99 (82.64 + 17.35)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company_data["company"]
        company.country_id = cls.env.ref("base.ar")
        cls.vat = cls.env["account.tax"].create(
            {
                "name": "IVA 21%",
                "amount": 21.0,
                "type_tax_use": "purchase",
                "company_id": company.id,
            }
        )
        # 1 in foreign currency was 1600 in company currency on the expense date,
        # and it's 1700 now
        for date, rate in (("2021-06-01", 1600.0), ("2022-01-01", 1700.0)):
            cls.env["res.currency.rate"].create(
                {
                    "name": date,
                    "inverse_company_rate": rate,
                    "currency_id": cls.other_currency.id,
                    "company_id": company.id,
                }
            )

    def _create_invoice(self, amount):
        expense = self.create_expenses(
            {
                "name": f"Gasto en divisa con IVA {amount}",
                "product_id": self.product_c.id,
                "currency_id": self.other_currency.id,
                "total_amount_currency": amount,
                "tax_ids": [Command.set(self.vat.ids)],
                "date": "2021-06-01",
                "payment_mode": "own_account",
                "vendor_id": self.partner_a.id,
            }
        )
        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Informe en divisa",
                "employee_id": self.expense_employee.id,
                "expense_line_ids": [Command.set(expense.ids)],
            }
        )
        sheet.action_submit()
        sheet.action_approve()
        # As from the interface: saved before anything is read
        self.env.invalidate_all()
        expense.action_expense_create_invoice()
        self.env.flush_all()
        self.env.invalidate_all()
        return expense, sheet, expense.invoice_id

    def _saved(self):
        self.env.flush_all()
        self.env.invalidate_all()

    def test_create_invoice_keeps_expense_amount(self):
        expense, sheet, invoice = self._create_invoice(100.0)
        self.assertEqual(expense.approval_state, "approved")
        self.assertAlmostEqual(invoice.amount_untaxed, 82.64)
        self.assertAlmostEqual(invoice.amount_tax, 17.36)
        self.assertAlmostEqual(invoice.amount_total, 100.0)
        self.assertAlmostEqual(expense.total_amount_currency, 100.0)
        self.assertAlmostEqual(expense.total_amount, 160000.0)
        self.assertAlmostEqual(expense.currency_rate, 1600.0)
        self.assertAlmostEqual(sheet.total_amount, expense.total_amount)

    def test_post_bill_over_approved_amount_by_rounding(self):
        # 100.11 gives 82.74 + 17.38 = 100.12, over the approved amount
        expense, sheet, invoice = self._create_invoice(100.11)
        self.assertAlmostEqual(invoice.amount_total, 100.11)
        invoice.action_post()
        self._saved()
        self.assertEqual(invoice.state, "posted")
        self.assertAlmostEqual(invoice.amount_total, 100.11)
        self.assertAlmostEqual(expense.total_amount_currency, 100.11)

    def test_set_vendor_keeps_expense_amount(self):
        expense, sheet, invoice = self._create_invoice(100.0)
        # Setting the vendor computes the taxes again, as in the user interface
        # (a new partner: partner_b has a fiscal position)
        vendor = self.env["res.partner"].create({"name": "Proveedor"})
        with Form(invoice) as invoice_form:
            invoice_form.partner_id = vendor
        self._saved()
        self.assertEqual(invoice.state, "draft")
        self.assertAlmostEqual(invoice.amount_tax, 17.36)
        self.assertAlmostEqual(invoice.amount_total, 100.0)
        self.assertAlmostEqual(expense.total_amount_currency, 100.0)

    def test_post_bill_keeps_expense_amount(self):
        expense, sheet, invoice = self._create_invoice(100.0)
        invoice.action_post()
        self._saved()
        self.assertEqual(invoice.state, "posted")
        self.assertAlmostEqual(invoice.amount_total, 100.0)
        self.assertAlmostEqual(expense.total_amount_currency, 100.0)
        self.assertAlmostEqual(expense.total_amount, 160000.0)
        self.assertAlmostEqual(sheet.total_amount, 160000.0)

    def test_post_linked_draft_bill_adjusts_tax_rounding(self):
        # A draft bill linked from the expense isn't saved again: adjusted when posting
        expense, sheet, invoice = self._create_invoice(100.0)
        bill = invoice.copy({"invoice_date": invoice.invoice_date})
        bill.invoice_line_ids.write({"tax_ids": [Command.set(self.vat.ids)]})
        expense.invoice_id = bill
        self.assertAlmostEqual(bill.amount_total, 99.99)
        bill.action_post()
        self._saved()
        self.assertAlmostEqual(bill.amount_total, 100.0)
        self.assertAlmostEqual(expense.total_amount_currency, 100.0)

    def test_non_ar_company_keeps_tax_rounding(self):
        self.company_data["company"].country_id = self.env.ref("base.us")
        expense, sheet, invoice = self._create_invoice(100.0)
        self.assertAlmostEqual(invoice.amount_total, 99.99)
