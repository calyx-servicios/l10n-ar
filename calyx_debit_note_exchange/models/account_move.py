from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        results = super()._prepare_product_base_line_for_taxes_computation(product_line)
        exchange_invoice = self.filtered(
            lambda x: x.line_ids.mapped("product_id")
            and self.env.company.exchange_difference_product.id in x.line_ids.mapped("product_id").ids
        )
        if exchange_invoice:
            if self.move_type in ['out_refund', 'in_refund']:
                results["special_mode"] = "total_included"
            elif self.move_type in ['out_invoice', 'in_invoice']:
                results["special_mode"] = "total_excluded"
        return results
