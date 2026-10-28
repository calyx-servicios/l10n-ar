from copy import deepcopy

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # For AR companies, a draft vendor bill linked to expenses can be completed
    # freely (e.g. adding perceptions): hr_expense_invoice_calyx check runs when
    # posting.
    @api.constrains("amount_total")
    def _check_invoice_expense_ids(self):
        deferred = self.browse()
        if not self.env.context.get("expense_invoice_posting"):
            deferred = self.filtered(
                lambda x: x.state == "draft" and x.company_id.country_id.code == "AR"
            )
        return super(AccountMove, self - deferred)._check_invoice_expense_ids()

    def _match_expense_rounding(self):
        """hr_expense_invoice_calyx builds the vendor bill from the untaxed amount of
        its expenses, so the taxes can round to another total (100 with 21% VAT
        gives 82.64 + 17.35), and Odoo computes them again on every change of the
        bill. The expenses take the bill total, so the reference is their approved
        amount (hr_expense_invoice_ux). As when editing the taxes of a vendor bill,
        the difference goes to the first tax group. Bigger differences aren't
        rounding: they're checked when posting."""
        # sudo: whoever bills may not see the expenses; the bill is written as is
        for move_sudo in self.sudo().filtered(
            lambda x: x.state == "draft" and x.invoice_expense_ids
        ):
            move = move_sudo.with_env(self.env)
            expenses = move_sudo.invoice_expense_ids
            tax_lines = move.line_ids.filtered("tax_line_id")
            if not tax_lines or not all(expenses.mapped("approved_amount")):
                continue
            # The approved amount is in company currency
            expense_amount = sum(expenses.mapped("approved_amount"))
            if move.currency_id != move.company_currency_id:
                expense_amount *= move.invoice_currency_rate
            difference = move.currency_id.round(expense_amount - move.amount_total)
            if move.currency_id.is_zero(difference) or abs(
                difference
            ) > move.currency_id.rounding * (len(tax_lines) + 1):
                continue
            tax_totals = deepcopy(move.tax_totals)
            tax_group = tax_totals["subtotals"][0]["tax_groups"][0]
            tax_group["tax_amount_currency"] += difference
            move.tax_totals = tax_totals

    def write(self, vals):
        # Saving the vendor bill can compute its taxes again (e.g. when setting the
        # vendor), and the tax amounts sent by the form are applied at the end of
        # the save: the rounding is adjusted after it, once
        with self._disable_recursion({"records": self}, "expense_rounding") as disabled:
            res = super().write(vals)
            if not disabled:
                self.filtered(
                    lambda x: x.company_id.country_id.code == "AR"
                )._match_expense_rounding()
        return res

    def _post(self, soft=True):
        self.filtered(
            lambda x: x.company_id.country_id.code == "AR"
        )._match_expense_rounding()
        # Checked before posting, so nothing is done for a bill that doesn't match.
        # sudo: whoever posts the bill may not see its expenses (e.g. billing users)
        moves = self.sudo().filtered(
            lambda x: x.company_id.country_id.code == "AR" and x.invoice_expense_ids
        )
        # The expenses copy the bill total before the checks: computing it checks
        # the bill again, while the expense amount isn't there yet
        moves.invoice_expense_ids.flush_recordset(
            ["total_amount_currency", "total_amount"]
        )
        moves = moves.with_context(expense_invoice_posting=True)
        moves._check_invoice_expense_ids()
        moves.invoice_expense_ids._check_invoice_amount_approved()
        return super()._post(soft=soft)
