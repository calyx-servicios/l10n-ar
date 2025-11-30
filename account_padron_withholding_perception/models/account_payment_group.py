from odoo import models, _

class AccountPaymentGroup(models.Model):
    _inherit = "account.payment.group"

    def compute_withholdings(self):
        self.ensure_one()
        result = super(AccountPaymentGroup, self).compute_withholdings()

        # Get alicut
        arba_line = self._find_arba_alicuot()

        # Get padron type
        padron_type = self._find_padron_type(arba_line)

        # Search withholding payment line
        retention_line = self._search_line_retention(padron_type.account_tax_retention_id)

        # Get all debt lines
        to_pay_lines = self._get_all_to_pay_lines()

        total_debt_untaxed = sum(to_pay_lines.mapped('move_id.amount_untaxed'))
        total_alicuot = total_debt_untaxed * arba_line.alicuota_retencion / 100

        display_msg = False
        if retention_line:
            total_to_discount = self._total_amount_retention(
                padron_type.minimum_base_retention, arba_line.alicuota_retencion, padron_type.minimum_calcule_retention
            )
            if total_to_discount >= total_alicuot:
                display_msg = _(
                    'The minimum base/calculated withholding {} is higher or equal than the untaxed amount '
                    'in the invoice, so it is not applied in this payment'
                ).format(padron_type.minimum_base_retention)
                retention_line.unlink()
            else:
                if total_to_discount > 0:
                    display_msg = _(
                        'The minimum base/calculated withholding {} is higher than the untaxed amount '
                        'on some of the invoices, so the following discount {} is applied to '
                        'withholding on the total in this payment.'
                    ).format(padron_type.minimum_base_retention, total_to_discount)

                amount_retention = total_alicuot - total_to_discount
                self.create_retention(retention_line, amount_retention, total_debt_untaxed)

            if display_msg:
                self.message_post(body=display_msg)
        return result

    def _find_arba_alicuot(self):
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('to_date', '>=', self.payment_date),
            ('from_date', '<=', self.payment_date),
            ('company_id', '=', self.company_id.id),
        ]
        return self.env['res.partner.arba_alicuot'].search(domain, limit=1)

    def _find_padron_type(self, arba_line):
        return arba_line.padron_line_id.padron_type_id.filtered(
            lambda x: x.company_id.id == self.company_id.id
        )

    def _search_line_retention(self, tax):
        return self.payment_ids.filtered(lambda x: x.tax_withholding_id.id == tax.id)

    def _total_amount_retention(self, base_minimum_retention, percent_retention_arba, minimum_calcule_retention):
        """
        Calculate the total amount to be retained based on specified criteria.

        :param base_minimum_retention: Minimum base for retention.
        :param percent_retention_arba: ARBA retention percentage.
        :param minimum_calcule_retention: Minimum calculated retention amount.
        :return: Total amount to be retained.
        """
        total_to_discount = 0
        for move_line in self.to_pay_move_line_ids:
            if move_line.move_id.move_type in ["in_invoice", "in_refund"]:
                withholding_applied = (
                    move_line.move_id.amount_untaxed * percent_retention_arba / 100
                )
                if base_minimum_retention > move_line.move_id.amount_untaxed:
                    total_to_discount += withholding_applied
                else:
                    if minimum_calcule_retention > withholding_applied:
                        total_to_discount += withholding_applied
        return total_to_discount

    def _get_all_to_pay_lines(self):
        return self.to_pay_move_line_ids.filtered(lambda x: x.move_id.move_type in ["in_invoice", "in_refund"])

    def create_retention(self, obj_ret, amount_retention, base_retention):
        vals = {
            'withholding_base_amount': base_retention,
            'withholdable_invoiced_amount': base_retention,
            'computed_withholding_amount': amount_retention,
            'previous_withholding_amount': 0.0,
            'amount': amount_retention,
            'accumulated_amount': 0.0,
            'total_amount': base_retention,
            'withholdable_base_amount': base_retention,
            'period_withholding_amount': amount_retention,
        }
        obj_ret.write(vals)
