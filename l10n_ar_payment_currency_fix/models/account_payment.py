from odoo import models, api


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.depends(
        "amount", "other_currency", "force_amount_company_currency",
        "amount_company_currency_signed")
    def _compute_amount_company_currency(self):
        for rec in self:
            if not rec.other_currency:
                amount_company_currency = rec.amount
            elif rec.force_amount_company_currency:
                amount_company_currency = rec.force_amount_company_currency
            else:
                amount_company_currency = abs(
                    rec.amount_company_currency_signed) or rec.currency_id._convert(
                    rec.amount, rec.company_id.currency_id, rec.company_id, rec.date)
            rec.amount_company_currency = amount_company_currency

    @api.onchange("withholdings_amount")
    def _onchange_withholdings(self):
        check_codes = ["in_third_party_checks", "out_third_party_checks"]
        for rec in self.filtered(lambda x: x.payment_method_code not in check_codes):
            rec.amount += rec.payment_difference / (rec.exchange_rate or 1.0)

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        res = super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals, force_balance=force_balance)
        if not self._l10n_ar_payment_currency_fix_applies():
            return res
        counterpart_rate = self._l10n_ar_to_pay_lines_rate()
        if not counterpart_rate:
            return res
        valid_account_types = self._get_valid_payment_account_types()
        for line in res:
            account = self.env["account.account"].browse(line["account_id"])
            if account.account_type in valid_account_types:
                balance = line.get("debit", 0.0) - line.get("credit", 0.0)
                line["amount_currency"] = self.currency_id.round(balance / counterpart_rate)
        return res

    def _l10n_ar_payment_currency_fix_applies(self):
        self.ensure_one()
        return bool(
            self.company_id.use_payment_pro
            and self.other_currency
            and self.l10n_ar_withholding_line_ids
            and self.to_pay_move_line_ids)

    def _l10n_ar_to_pay_lines_rate(self):
        self.ensure_one()
        lines = self.to_pay_move_line_ids.filtered(
            lambda x: x.currency_id == self.currency_id and x.amount_residual_currency)
        residual = sum(lines.mapped("amount_residual"))
        residual_currency = sum(lines.mapped("amount_residual_currency"))
        if not residual_currency:
            return False
        return abs(residual / residual_currency)
