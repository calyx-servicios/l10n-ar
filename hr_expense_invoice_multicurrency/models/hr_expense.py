from odoo import models


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

    def _set_price_unit_from_company_amount(self):
        """hr_expense_invoice writes the vendor bill total as price_unit, but
        price_unit is expressed in company currency."""
        for expense in self.filtered(
            lambda x: x.invoice_id
            and x.is_multiple_currency
            and x.company_id.country_id.code == "AR"
        ):
            expense.price_unit = expense.total_amount

    def action_expense_create_invoice(self):
        res = super().action_expense_create_invoice()
        self._set_price_unit_from_company_amount()
        return res

    def _compute_price_unit(self):
        res = super()._compute_price_unit()
        # Same guard as the core compute: submitted expenses keep their value
        self.filtered(
            lambda x: x.state in {"draft", "reported"}
        )._set_price_unit_from_company_amount()
        return res

    def _prepare_own_account_transfer_move_vals(self):
        vals = super()._prepare_own_account_transfer_move_vals()
        invoice = self.invoice_id
        if (
            self.company_id.country_id.code != "AR"
            or invoice.currency_id == invoice.company_currency_id
        ):
            return vals
        ap_lines = invoice.line_ids.filtered(lambda x: x.display_type == "payment_term")
        amount_currency = -sum(ap_lines.mapped("amount_currency"))
        for command in vals["line_ids"]:
            line_vals = command[2]
            sign = 1 if line_vals.get("debit") else -1
            line_vals.update(
                {
                    "currency_id": invoice.currency_id.id,
                    "amount_currency": sign * amount_currency,
                }
            )
        return vals
