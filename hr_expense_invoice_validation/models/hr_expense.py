from odoo import api, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    # For AR companies, a draft vendor bill can go over the approved amount of its
    # expenses (e.g. adding perceptions): hr_expense_invoice_ux check runs when
    # posting the bill (account.move._post).
    @api.constrains("invoice_id", "total_amount")
    def _check_invoice_amount_approved(self):
        deferred = self.browse()
        if not self.env.context.get("expense_invoice_posting"):
            deferred = self.filtered(
                lambda x: x.invoice_id.state == "draft"
                and x.company_id.country_id.code == "AR"
            )
        return super(HrExpense, self - deferred)._check_invoice_amount_approved()
