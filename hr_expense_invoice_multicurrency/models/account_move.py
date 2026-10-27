from odoo import api, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    # For AR companies, the vendor bill goes with the rate of its expenses even
    # if its date changes: it's the rate used when the date changes and when
    # refreshing it.
    @api.depends("expense_ids.total_amount", "expense_ids.total_amount_currency")
    def _compute_expected_currency_rate(self):
        res = super()._compute_expected_currency_rate()
        for move in self.filtered(
            lambda x: x.company_id.country_id.code == "AR"
            and x.currency_id != x.company_currency_id
        ):
            expenses = move.expense_ids.filtered(
                lambda x, move=move: x.currency_id == move.currency_id
            )
            company_amount = sum(expenses.mapped("total_amount"))
            if company_amount:
                move.expected_currency_rate = (
                    sum(expenses.mapped("total_amount_currency")) / company_amount
                )
        return res

    def _get_expense_amount_in_move_currency(self, expenses):
        """Return the total of ``expenses`` in the move currency.

        The vendor bill goes with the date and rate of its expense, so expenses
        in another currency are converted with their own rate (``total_amount``
        is in company currency), not with the rate of the day."""
        self.ensure_one()
        same_currency = expenses.filtered(lambda x: x.currency_id == self.currency_id)
        other_currency = expenses - same_currency
        return sum(same_currency.mapped("total_amount_currency")) + self.currency_id.round(
            sum(other_currency.mapped("total_amount")) * self.invoice_currency_rate
        )

    # For AR companies, replaces hr_expense_invoice check, which compares
    # amounts without considering the currency of the expense and the bill.
    @api.constrains("amount_total", "currency_id")
    def _check_expense_ids(self):
        ar_moves = self.filtered(lambda x: x.company_id.country_id.code == "AR")
        super(AccountMove, self - ar_moves)._check_expense_ids()
        for move in ar_moves.filtered("expense_ids"):
            expense_amount = move._get_expense_amount_in_move_currency(
                move.expense_ids
            )
            if move.currency_id.compare_amounts(expense_amount, move.amount_total):
                raise ValidationError(
                    self.env._(
                        "You can't change the total amount, as there's an expense "
                        "linked to this invoice."
                    )
                )
