import csv
import io

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    settlement_tax = fields.Selection(
        selection_add=[
            ("retenciones_iva_simple", "TXT Retenciones/Percepciones Sufridas IVA SIMPLE"),
        ]
    )

    def retenciones_iva_simple_files_values(self, move_lines):
        self.ensure_one()
        move_lines = move_lines.sorted(lambda line: (line.date, line.id))
        retentions = move_lines.filtered("payment_id")
        perceptions = (move_lines - retentions).filtered(lambda line: line.move_id.is_invoice())

        retention_rows = [
            [
                "767",
                self._get_iva_simple_regimen(line),
                line.payment_id.partner_id.ensure_vat(),
                "",
                line.payment_id.date.isoformat(),
                "2",
                self._format_iva_simple_document_number(line.move_id),
                line.withholding_id.name or "",
                self._format_iva_simple_amount(line),
            ]
            for line in retentions
        ]
        perception_rows = [
            [
                self._get_iva_simple_regimen(line),
                line.move_id.partner_id.ensure_vat(),
                "",
                line.move_id.invoice_date.isoformat(),
                "1",
                self._format_iva_simple_document_number(line.move_id),
                self._format_iva_simple_amount(line),
            ]
            for line in perceptions
        ]
        return [
            {
                "txt_filename": "Retenciones_iva.csv",
                "txt_content": self._build_iva_simple_csv(retention_rows),
            },
            {
                "txt_filename": "Percepciones_iva.csv",
                "txt_content": self._build_iva_simple_csv(perception_rows),
            },
        ]

    def _get_iva_simple_regimen(self, line):
        regimen = line.tax_line_id.codigo_regimen
        if not regimen:
            raise ValidationError(
                _(
                    'No hay código de régimen en la configuración del impuesto "%s"',
                    line.tax_line_id.name,
                )
            )
        return regimen

    def _format_iva_simple_document_number(self, move):
        parts = move._l10n_ar_get_document_number_parts(
            move.l10n_latam_document_number, move.l10n_latam_document_type_id.code
        )
        return f"{parts['point_of_sale']:05d}-{parts['invoice_number']:08d}"

    def _format_iva_simple_amount(self, line):
        if line.balance <= 0:
            raise ValidationError(
                _(
                    'El importe del apunte de "%s" debe ser mayor a cero para IVA Simple',
                    line.move_id.display_name,
                )
            )
        return f"{line.balance:.2f}".replace(".", ",")

    def _build_iva_simple_csv(self, rows):
        stream = io.StringIO()
        csv.writer(stream, delimiter=";", lineterminator="\r\n").writerows(rows)
        return stream.getvalue()
