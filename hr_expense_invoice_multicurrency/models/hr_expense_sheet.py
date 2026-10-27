from odoo import models
from odoo.exceptions import UserError


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def _validate_expense_invoice(self):
        """For AR companies, replaces hr_expense_invoice check, comparing each
        vendor bill with its expenses converted to the vendor bill currency."""
        ar_sheets = self.filtered(lambda x: x.company_id.country_id.code == "AR")
        super(HrExpenseSheet, self - ar_sheets)._validate_expense_invoice()
        expense_lines = ar_sheets.expense_line_ids.filtered("invoice_id")
        invoices = expense_lines.invoice_id
        if not invoices:
            return
        if invoices.filtered(lambda i: i.state != "posted"):
            raise UserError(self.env._("Vendor bill state must be Posted"))
        for invoice in invoices:
            expenses = expense_lines.filtered(lambda x, inv=invoice: x.invoice_id == inv)
            expense_amount = invoice._get_expense_amount_in_move_currency(expenses)
            if invoice.currency_id.compare_amounts(expense_amount, invoice.amount_total):
                raise UserError(
                    self.env._(
                        "Vendor bill amount mismatch!\nPlease make sure amount in "
                        "vendor bills equal to amount of its expense lines"
                    )
                )
