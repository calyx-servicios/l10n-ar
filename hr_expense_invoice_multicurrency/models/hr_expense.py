from odoo import api, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    def _prepare_invoice_values(self):
        vals = super()._prepare_invoice_values()
        if self.company_id.country_id.code != "AR":
            return vals
        vals["currency_id"] = self.currency_id.id
        if self.is_multiple_currency and self.currency_rate:
            # The expense rate goes from expense currency to company currency,
            # the vendor bill one goes the other way around.
            vals["invoice_currency_rate"] = 1 / self.currency_rate
        return vals

    @api.depends("invoice_id.amount_total_signed")
    def _compute_total_amount(self):
        res = super()._compute_total_amount()
        # hr_expense_invoice_calyx copies the vendor bill total to the expense but
        # not its company amount: take it from the bill, so both go with its rate
        for expense in self.filtered(
            lambda x: x.invoice_id
            and x.is_multiple_currency
            and x.company_id.country_id.code == "AR"
        ):
            expense.total_amount = abs(expense.invoice_id.amount_total_signed)
            # The rate is read from total_amount, but doesn't depend on it
            expense.invalidate_recordset(
                ["currency_rate", "label_currency_rate"], flush=False
            )
        return res

    def _compute_price_unit(self):
        res = super()._compute_price_unit()
        # hr_expense_invoice_calyx writes the vendor bill total as price_unit, but
        # price_unit is expressed in company currency. Same guard as the core
        # compute: submitted expenses keep their value
        for expense in self.filtered(
            lambda x: x.state == "draft"
            and x.invoice_id
            and x.is_multiple_currency
            and x.company_id.country_id.code == "AR"
        ):
            expense.price_unit = expense.total_amount
        return res

    def _prepare_transfer_move_lines_vals(self):
        lines_vals = super()._prepare_transfer_move_lines_vals()
        invoice = self.invoice_id
        if (
            self.company_id.country_id.code != "AR"
            or invoice.currency_id == invoice.company_currency_id
        ):
            return lines_vals
        ap_lines = invoice.line_ids.filtered(lambda x: x.display_type == "payment_term")
        amount_currency = -sum(ap_lines.mapped("amount_currency"))
        for command in lines_vals:
            line_vals = command[2]
            sign = 1 if line_vals.get("debit") else -1
            line_vals.update(
                {
                    "currency_id": invoice.currency_id.id,
                    "amount_currency": sign * amount_currency,
                }
            )
        return lines_vals
