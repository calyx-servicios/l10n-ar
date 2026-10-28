from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        results = super()._prepare_product_base_line_for_taxes_computation(product_line)
        if self.company_id.country_id.code != "AR":
            return results
        # The exchange product is configured per company: use the move's one,
        # not the one of the company the user is working on
        exchange_product = self.company_id.exchange_difference_product
        if exchange_product and exchange_product in self.invoice_line_ids.product_id:
            if self.move_type in ("out_refund", "in_refund"):
                results["special_mode"] = "total_included"
            elif self.move_type in ("out_invoice", "in_invoice"):
                results["special_mode"] = "total_excluded"
        return results
