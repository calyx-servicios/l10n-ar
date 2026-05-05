from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _compute_withholding(self):
        """Fallback to payment-group withholdings when payment linkage is missing."""
        super()._compute_withholding()

        fallback_lines = self.filtered(
            lambda line: (
                not line.withholding_id
                and line.tax_line_id
                and line.payment_group_id
            )
        )
        if not fallback_lines:
            return

        withholdings = self.env["l10n_ar.payment.withholding"].search(
            [
                ("payment_group_id", "in", fallback_lines.mapped("payment_group_id").ids),
                ("tax_id", "in", fallback_lines.mapped("tax_line_id").ids),
            ],
            order="id desc",
        )

        by_group_tax_name = {}
        by_group_tax = {}
        for withholding in withholdings:
            key_by_name = (
                withholding.payment_group_id.id,
                withholding.tax_id.id,
                withholding.name or False,
            )
            key_by_tax = (
                withholding.payment_group_id.id,
                withholding.tax_id.id,
            )
            by_group_tax_name.setdefault(key_by_name, withholding)
            by_group_tax.setdefault(key_by_tax, withholding)

        for line in fallback_lines:
            key_by_name = (
                line.payment_group_id.id,
                line.tax_line_id.id,
                line.name or False,
            )
            key_by_tax = (line.payment_group_id.id, line.tax_line_id.id)
            line.withholding_id = (
                by_group_tax_name.get(key_by_name)
                or by_group_tax.get(key_by_tax)
            )
