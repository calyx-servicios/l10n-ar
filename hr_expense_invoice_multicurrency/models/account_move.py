from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # For AR companies, a vendor bill linked to expenses keeps its rate (the
    # expense one when created from it) even if its date changes: it's the rate
    # used when the date changes and when refreshing it. It isn't read from the
    # expenses: their company amount comes from the bill
    # (hr.expense._compute_total_amount), which depends on this rate. Changing
    # the currency from the form still takes the rate of the day.
    @api.depends("invoice_currency_rate", "invoice_expense_ids")
    def _compute_expected_currency_rate(self):
        res = super()._compute_expected_currency_rate()
        for move in self.filtered(
            lambda x: x.company_id.country_id.code == "AR"
            and x.invoice_expense_ids
            and x.invoice_currency_rate
            and x.currency_id != x.company_currency_id
            and x.currency_id == x._origin.currency_id
        ):
            move.expected_currency_rate = move.invoice_currency_rate
        return res
