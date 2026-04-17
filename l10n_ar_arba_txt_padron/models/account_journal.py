from odoo import models, fields, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.l10n_ar_account_tax_settlement.models.account_journal import (
    format_amount,
    get_line_tax_base,
)
import re


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def iibb_aplicado_arba_desde_01032026(self, move_lines, act_7=None):
        self.ensure_one()
        ret = ''
        perc = ''

        for line in move_lines:
            move = line.move_id
            payment = line.payment_id
            internal_type = line.l10n_latam_document_type_id.internal_type
            document_code = line.l10n_latam_document_type_id.code

            line.partner_id.ensure_vat()

            content = line.partner_id.l10n_ar_formatted_vat
            content += fields.Date.from_string(line.date).strftime('%d/%m/%Y')

            if not payment:
                content += (
                    document_code in ['201', '206', '211'] and 'E' or
                    document_code in ['203', '208', '213'] and 'H' or
                    document_code in ['202', '207', '212'] and 'I' or
                    internal_type == 'invoice' and 'F' or
                    internal_type == 'credit_note' and 'C' or
                    internal_type == 'debit_note' and 'D' or 'R')
                content += line.l10n_latam_document_type_id.l10n_ar_letter

            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number, move.l10n_latam_document_type_id.code)
            pto_venta = "{:0>5d}".format(document_parts['point_of_sale'])[-5:]
            nro_documento = "{:0>8d}".format(document_parts['invoice_number'])[-8:]
            content += str(pto_venta)
            content += str(nro_documento)

            tax = line.tax_line_id
            partner = line.partner_id
            alicuot_line = tax.get_partner_alicuot(partner, line.date)
            if not alicuot_line:
                raise ValidationError(_('No hay alicuota configurada en el partner "%s" (id: %s)') % (
                    partner.name, partner.id))

            if payment:
                alicuota = alicuot_line.alicuota_retencion
                withholdable_base = payment.amount / (alicuota / 100) if alicuota else 0.0
                content += format_amount(withholdable_base, 14, 2, ',')
                content += '%05.2f' % alicuota
            else:
                content += format_amount(-get_line_tax_base(line), 14, 2, ',')
                content += '%05.2f' % alicuot_line.alicuota_percepcion

            content += format_amount(-line.balance, 13, 2, ',')

            if act_7 and not payment:
                content += fields.Date.from_string(line.date).strftime('%d/%m/%Y')

            content += 'A'
            content += '\r\n'

            if payment:
                ret += content
            else:
                perc += content

        period = move_lines and \
            fields.Date.from_string(move_lines[0].date).strftime('%Y%mX') or ""

        perc_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat, period, "7")

        ret_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat, period, "6")

        return [
            {'txt_filename': perc_txt_filename, 'txt_content': perc},
            {'txt_filename': ret_txt_filename, 'txt_content': ret},
        ]

    def iibb_alta_ret_aplicado_arba_por_lote_A_122R_01032026(self, move_lines):
        self.ensure_one()
        content = ''
        for line in move_lines:
            content += re.sub(r'[^0-9]', '', str(line.name))[-20:].zfill(20)
            content += line.partner_id.ensure_vat()

            move = line.move_id
            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number, move.l10n_latam_document_type_id.code)
            pto_venta = "{:0>5d}".format(document_parts['point_of_sale'])[-5:]
            content += str(pto_venta)
            content += fields.Date.from_string(line.date).strftime('%d/%m/%Y')

            tax = line.tax_line_id
            partner = line.partner_id
            alicuot_line = tax.get_partner_alicuot(partner, line.date)
            if not alicuot_line:
                raise UserError(_('No hay alícuota configurada para el impuesto "%s" en el partner "%s" (id: %s) en la fecha %s') % (
                    tax.name, partner.name, partner.id, line.date))
            content += '%05.2f' % alicuot_line.alicuota_retencion

            alicuota = alicuot_line.alicuota_retencion
            withholdable_base = line.payment_id.amount / (alicuota / 100) if alicuota else 0.0
            content += '%016.2f' % withholdable_base

            content += '\r\n'

        period = move_lines and \
            fields.Date.from_string(move_lines[0].date).strftime('%Y%mX') or ""

        filename = "ER-%s-%s-%s-LOTEXXXXX.txt" % (
            self.company_id.vat, period, "6")

        return [{'txt_filename': filename, 'txt_content': content}]
