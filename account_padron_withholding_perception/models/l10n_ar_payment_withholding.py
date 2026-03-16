# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class L10nArPaymentWithholding(models.Model):
    _inherit = "l10n_ar.payment.withholding"

    def _tax_compute_all_helper(self):
        """Override para manejar impuestos con "Alicuota en el Contacto".

        La alícuota se obtiene del partner (según la etiqueta en la línea de
        repartición del impuesto y la fecha de pago) y la cuenta / línea de
        repartición se toman de invoice_repartition_line_ids.
        """
        self.ensure_one()
        tax = self._get_withholding_tax()

        if tax.amount_type != 'partner_tax':
            return super()._tax_compute_all_helper()

        # Importe base (refleja la rama de no ganancias en el padre)
        net_amount = max(0, self.base_amount - tax.l10n_ar_non_taxable_amount)

        # Buscar la alícuota desde arba_alicuot del partner
        partner = self.payment_id.partner_id.commercial_partner_id
        payment_date = self.payment_id.date or fields.Date.context_today(self)
        company = self.payment_id.company_id

        # La etiqueta en la línea de repartición de impuesto de la factura es el discriminador
        # que vincula un impuesto específico con la fila de alícuota correspondiente en el
        # partner (una fila por provincia/jurisdicción).
        rep_line = tax.invoice_repartition_line_ids.filtered(
            lambda r: r.repartition_type == 'tax'
        )[:1]
        tag = rep_line.tag_ids[:1]

        alicuot = partner.arba_alicuot_ids.filtered(
            lambda a: (not tag or a.tag_id == tag)
            and a.company_id == company
            and (not a.from_date or a.from_date <= payment_date)
            and (not a.to_date or a.to_date >= payment_date)
        )[:1]

        rate = alicuot.alicuota_retencion if alicuot else 0.0

        # Computar monto
        tax_amount = self.currency_id.round(net_amount * rate / 100)

        if tax.l10n_ar_minimum_threshold > tax_amount:
            tax_amount = 0.0

        f = self.currency_id.format
        ref = f"{f(net_amount)} x {rate / 100}"

        tax_account_id = rep_line.account_id.id
        tax_repartition_line_id = rep_line.id

        return tax_amount, tax_account_id, tax_repartition_line_id, ref
