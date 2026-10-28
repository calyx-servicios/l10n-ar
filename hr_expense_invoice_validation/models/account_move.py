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

    def _post(self, soft=True):
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
