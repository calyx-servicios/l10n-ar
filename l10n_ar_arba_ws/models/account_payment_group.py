from odoo import models


class AccountPaymentGroup(models.Model):
    _inherit = "account.payment.group"

    def post(self):
        """Al confirmar el grupo de pago, si la compañia tiene modo automático
        para informar retenciones, y tiene líneas de retención ARBA entonces
        enviamos a ARBA. El resultado es que vamos a tener el campo certificado
        con el número asignado por ARBA para cada línea de retención informada.
        """
        res = super().post()
        for payment_group in self:
            # Solo si la compañia tiene modo automático de retenciones ARBA
            if payment_group.company_id.l10n_ar_arba_wh_mode != "automatic":
                continue

            # Filtramos solo las líneas de retención de ARBA (provincia Buenos Aires)
            # que no tengan número de certificado aún (no informadas).
            # Si el impuesto no tiene l10n_ar_state_id configurado, el filtro
            # simplemente no lo selecciona y pasa de largo sin error.
            state_ar_b = self.env.ref("base.state_ar_b")
            wh_lines = payment_group.l10n_ar_withholding_line_ids.filtered(
                lambda x: (x.tax_id.l10n_ar_state_id == state_ar_b and not x.l10n_ar_cert_number)
            )
            wh_lines.send_to_arba()
        return res
