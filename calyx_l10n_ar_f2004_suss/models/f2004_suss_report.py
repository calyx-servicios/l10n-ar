import re

from odoo import _, fields, models
from odoo.exceptions import UserError


class L10n_ArF2004SussReportHandler(models.AbstractModel):
    _name = "l10n_ar.f2004.suss.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian SUSS F2004 Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # Add export button
        txt_export_button = {
            "name": _("SUSS Aplicado TXT F2004"),
            "sequence": 30,
            "action": "export_file",
            "action_param": "suss_f2004_export_files_to_txt",
            "file_export_type": "TXT",
            "branch_allowed": True,
        }
        options["buttons"].append(txt_export_button)

    def suss_f2004_export_files_to_txt(self, options):
        """Export method that lets us export applied SUSS withholdings to the AFIP F2004 txt file."""
        return {
            "file_name": _("SUSS_F2004.txt"),
            "file_content": self._suss_f2004_get_txt_files(options),
            "file_type": "txt",
        }

    def _suss_f2004_get_txt_files(self, options):
        """Returns SUSS F2004 txt content."""
        withholdings = self._suss_f2004_get_withholdings(options)
        return "".join(self._get_suss_f2004_txt_content(withholdings)).encode("ISO-8859-1", "ignore")

    def _suss_f2004_get_withholdings(self, options):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        company_ids = self.env["account.report"].get_report_company_ids(options)
        domain = [
            ("company_id", "in", company_ids),
            ("tax_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            # Taxes not yet tagged with l10n_ar_tax_type='suss' are matched by tax group name.
            "|",
            ("tax_id.l10n_ar_tax_type", "=", "suss"),
            ("tax_id.tax_group_id.name", "ilike", "suss"),
            ("payment_id.move_id.state", "=", "posted"),
        ]
        date_from = options.get("date", {}).get("date_from")
        date_to = options.get("date", {}).get("date_to")
        if date_from:
            domain.append(("payment_id.date", ">=", date_from))
        if date_to:
            domain.append(("payment_id.date", "<=", date_to))
        return self.env["l10n_ar.payment.withholding"].search(domain)

    def _get_suss_f2004_txt_content(self, withholdings):
        """Returns the lines to be printed in the txt file, each one exactly 191 chars long."""
        lines = []
        for withholding in withholdings.sorted(key=lambda w: (w.payment_id.date, w.id)):
            payment = withholding.payment_id
            partner = payment.partner_id
            tax = withholding.tax_id
            company = withholding.company_id

            if not partner.vat:
                raise UserError(
                    _(
                        'The partner "%(partner_name)s" (id %(partner_id)s) does not have the vat set.',
                        partner_name=partner.name,
                        partner_id=partner.id,
                    )
                )
            if not tax.l10n_ar_code:
                raise UserError(
                    _(
                        'The tax "%(tax_name)s" does not have the AFIP regime code (l10n_ar_code) set.',
                        tax_name=tax.name,
                    )
                )

            payment_date = fields.Date.to_date(payment.date).strftime("%d/%m/%Y")

            content = ""
            # 1 - Formulario (fijo)                                [ 4]
            content += "2004"
            # 2 - Version (fijo)                                   [ 4]
            content += "0100"
            # 3 - Codigo de trazabilidad (uso no fiscal)           [10]
            content += "".ljust(10)
            # 4 - CUIT Agente                                      [11]
            content += f"{re.sub(r'[^0-9]', '', company.vat or ''):0>11}"
            # 5 - Impuesto (fijo)                                  [ 3]
            content += "353"
            # 6 - Regimen                                          [ 3]
            content += f"{re.sub(r'[^0-9]', '', str(tax.l10n_ar_code)):0>3}"
            # 7 - CUIT Retenido                                    [11]
            content += f"{re.sub(r'[^0-9]', '', partner.vat):0>11}"
            # 8 - Fecha de retencion                                [10]
            content += payment_date
            # 9 - Tipo de comprobante (MVP: 04 Recibo, sin NC)     [ 2]
            content += "04"
            # 10 - Fecha del comprobante (MVP: igual a fecha ret.) [10]
            content += payment_date
            # 11 - Nro de comprobante                              [16]
            content += (withholding.name or "").ljust(16)[:16]
            # 12 - Importe comprobante                             [14]
            content += f"{abs(withholding.base_amount):014.2f}"
            # 13 - Importe retencion                               [14]
            content += f"{abs(withholding.amount):014.2f}"
            # 14 - Certificado original nro (MVP: sin NC)          [25]
            content += "".ljust(25)
            # 15 - Certificado original fecha retencion (MVP)      [10]
            content += "".ljust(10)
            # 16 - Certificado original importe (MVP)              [14]
            content += "".ljust(14)
            # 17 - Otros datos                                     [30]
            content += "".ljust(30)

            content += "\r\n"
            lines.append(content)
        return lines
