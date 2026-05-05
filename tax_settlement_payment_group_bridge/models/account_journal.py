import re

from odoo import fields, models
from odoo.exceptions import UserError, ValidationError


def _bridge_format_amount(amount, padding=15, decimals=2, sep=""):
    if amount < 0:
        template = "-{:0>%dd}" % (padding - 1 - len(sep))
    else:
        template = "{:0>%dd}" % (padding - len(sep))
    res = template.format(int(round(abs(amount) * 10**decimals, decimals)))
    if sep:
        res = "{0}{1}{2}".format(res[:-decimals], sep, res[-decimals:])
    return res


def _bridge_get_line_tax_base(move_line):
    return sum(
        move_line.move_id.line_ids.filtered(
            lambda candidate: move_line.tax_line_id in candidate.tax_ids
        ).mapped("balance")
    )


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _bridge_normalize_payment_group_lines(self, only_unsettled=False, line_ids=None):
        """Normalize payment-group withholding lines so standard settlement logic can use them."""
        self.ensure_one()
        tag_ids = self.settlement_account_tag_ids.ids
        if not tag_ids:
            return

        where_clauses = [
            "aml.company_id = %s",
            "aml.payment_group_id IS NOT NULL",
            "am.state = 'posted'",
            "atrl.repartition_type = 'tax'",
            "tag_rel.account_account_tag_id IN %s",
            "atrl.account_id = aml.account_id",
            "("
            "aml.tax_line_id IS NULL OR "
            "aml.tax_repartition_line_id IS NULL OR "
            "aml.payment_id IS NULL OR "
            "aml.tax_state IS NULL OR "
            "NOT EXISTS ("
            "SELECT 1 "
            "FROM account_account_tag_account_move_line_rel rel "
            "WHERE rel.account_move_line_id = aml.id "
            "AND rel.account_account_tag_id IN %s"
            ")"
            ")",
            "((apg.partner_type = 'supplier' AND "
            "atrl.document_type = 'invoice') OR "
            "(apg.partner_type = 'customer' AND "
            "atrl.document_type = 'refund'))",
        ]
        params = [self.company_id.id, tuple(tag_ids), tuple(tag_ids)]

        if line_ids:
            where_clauses.append("aml.id IN %s")
            params.append(tuple(line_ids))
        else:
            from_date = self._context.get("from_date")
            if from_date:
                where_clauses.append("aml.date >= %s")
                params.append(from_date)

            to_date = self._context.get("to_date")
            if to_date:
                where_clauses.append("aml.date <= %s")
                params.append(to_date)

        if only_unsettled:
            where_clauses.append("aml.tax_settlement_move_id IS NULL")

        candidates_cte = """
            WITH candidates AS (
                SELECT DISTINCT
                    aml.id AS aml_id,
                    w.tax_id AS tax_id,
                    atrl.id AS tax_repartition_line_id,
                    pay.id AS payment_id,
                    tag_rel.account_account_tag_id AS tag_id
                FROM account_move_line aml
                JOIN account_move am
                    ON am.id = aml.move_id
                JOIN account_payment_group apg
                    ON apg.id = aml.payment_group_id
                JOIN l10n_ar_payment_withholding w
                    ON w.payment_group_id = aml.payment_group_id
                   AND w.name = aml.name
                JOIN account_tax_repartition_line atrl
                    ON atrl.tax_id = w.tax_id
                   AND atrl.account_id = aml.account_id
                JOIN account_account_tag_account_tax_repartition_line_rel tag_rel
                    ON tag_rel.account_tax_repartition_line_id = atrl.id
                LEFT JOIN LATERAL (
                    SELECT p2.id
                    FROM account_payment p2
                    WHERE p2.payment_group_id = aml.payment_group_id
                    ORDER BY p2.id
                    LIMIT 1
                ) pay ON TRUE
                WHERE %s
            )
        """ % " AND ".join(where_clauses)

        update_sql = candidates_cte + """
            UPDATE account_move_line aml
            SET
                tax_line_id = COALESCE(aml.tax_line_id, cand.tax_id),
                tax_repartition_line_id = COALESCE(
                    aml.tax_repartition_line_id,
                    cand.tax_repartition_line_id
                ),
                payment_id = COALESCE(aml.payment_id, cand.payment_id),
                tax_state = CASE
                    WHEN aml.tax_state IS NULL
                     AND aml.tax_settlement_move_id IS NULL
                    THEN 'to_settle'
                    ELSE aml.tax_state
                END
            FROM (
                SELECT
                    aml_id,
                    MIN(tax_id) AS tax_id,
                    MIN(tax_repartition_line_id) AS tax_repartition_line_id,
                    MIN(payment_id) AS payment_id
                FROM candidates
                GROUP BY aml_id
            ) cand
            WHERE aml.id = cand.aml_id
        """
        self.env.cr.execute(update_sql, params)

        tag_insert_sql = candidates_cte + """
            INSERT INTO account_account_tag_account_move_line_rel (
                account_move_line_id,
                account_account_tag_id
            )
            SELECT DISTINCT
                cand.aml_id,
                cand.tag_id
            FROM candidates cand
            LEFT JOIN account_account_tag_account_move_line_rel rel
                ON rel.account_move_line_id = cand.aml_id
               AND rel.account_account_tag_id = cand.tag_id
            WHERE rel.account_move_line_id IS NULL
        """
        self.env.cr.execute(tag_insert_sql, params)

    def _get_tax_settlement_lines_domain_by_tags(self):
        """Normalize lines first, then rely on the standard tag domain."""
        if not self._context.get("bridge_skip_normalization"):
            self._bridge_normalize_payment_group_lines()
        return super()._get_tax_settlement_lines_domain_by_tags()

    def _get_tax_settlement_move_lines_by_tags(self):
        """Normalize unsettled lines first, then rely on the standard search."""
        self._bridge_normalize_payment_group_lines(only_unsettled=True)
        journal = self.with_context(bridge_skip_normalization=True)
        return super(AccountJournal, journal)._get_tax_settlement_move_lines_by_tags()

    def get_tax_settlement_files_values(self, move_lines):
        """Normalize selected lines before delegating to Adhoc TXT generators."""
        self.ensure_one()
        self._bridge_normalize_payment_group_lines(line_ids=move_lines.ids)
        return super().get_tax_settlement_files_values(move_lines)

    def _bridge_get_arba_retention_base(self, line, alicuota_retencion):
        """Return a consistent base amount for ARBA retention exports."""
        withholding = line.withholding_id
        if not withholding:
            raise ValidationError(
                "No se encontro la retencion asociada a la linea \"%s\" (id: %s)"
                % (line.name, line.id)
            )

        if withholding.base_amount:
            return withholding.base_amount
        if withholding.withholdable_base_amount:
            return withholding.withholdable_base_amount

        if alicuota_retencion:
            return withholding.amount / (alicuota_retencion / 100.0)

        return 0.0

    def iibb_aplicado_arba_desde_01032026(self, move_lines, act_7=None):
        """Harden ARBA TXT generation when document letter is missing on legacy moves."""
        self.ensure_one()
        ret = ""
        perc = ""

        for line in move_lines:
            move = line.move_id
            payment = line.payment_id
            doc_type = line.l10n_latam_document_type_id

            if doc_type:
                internal_type = doc_type.internal_type
                document_code = doc_type.code
            else:
                internal_type = {
                    "out_invoice": "invoice",
                    "in_invoice": "invoice",
                    "out_refund": "credit_note",
                    "in_refund": "credit_note",
                    "out_debit": "debit_note",
                    "in_debit": "debit_note",
                }.get(move.move_type)
                document_code = False

            line.partner_id.ensure_vat()

            # CUIT contribuyente Percibido (long 13, desde 1 hasta 13. Formato 99-99999999-9)
            content = line.partner_id.l10n_ar_formatted_vat
            # Fecha Percepción (long 10, desde 14 hasta 23. Formato dd/mm/aaaa)
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # solo para percepciones
            if not payment:
                # Tipo de Comprobante (long 1, desde 24 hasta 24)
                content += (
                    document_code in ["201", "206", "211"] and "E"
                    or document_code in ["203", "208", "213"]
                    and "H"
                    or document_code in ["202", "207", "212"]
                    and "I"
                    or internal_type == "invoice"
                    and "F"
                    or internal_type == "credit_note"
                    and "C"
                    or internal_type == "debit_note"
                    and "D"
                    or "R"
                )
                # Letra Comprobante (long 1, desde 25 hasta 25. Valores A,B,C, o blanco).
                content += (doc_type and doc_type.l10n_ar_letter) or " "

            move_doc_type = move.l10n_latam_document_type_id
            move_doc_type_code = (
                (move_doc_type and move_doc_type.code) or document_code
            )
            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number or move.name,
                move_doc_type_code,
            )
            pto_venta = "{:0>5d}".format(document_parts["point_of_sale"])[-5:]
            nro_documento = "{:0>8d}".format(document_parts["invoice_number"])[-8:]
            # Numero Sucursal (long 5, desde 26 hasta 30)
            content += str(pto_venta)
            # Numero Emisión (long 8, desde 31 a 38)
            content += str(nro_documento)

            tax = line.tax_line_id
            partner = line.partner_id
            alicuot_line = tax.get_partner_alicuot(partner, line.date)
            if not alicuot_line:
                raise ValidationError(
                    'No hay alicuota configurada en el partner "%s" (id: %s)'
                    % (partner.name, partner.id)
                )

            if payment:
                withholdable_base = self._bridge_get_arba_retention_base(
                    line, alicuot_line.alicuota_retencion
                )
                content += _bridge_format_amount(
                    withholdable_base,
                    14,
                    2,
                    ",",
                )
                content += "%05.2f" % alicuot_line.alicuota_retencion
            else:
                content += _bridge_format_amount(
                    -_bridge_get_line_tax_base(line), 14, 2, ","
                )
                content += "%05.2f" % alicuot_line.alicuota_percepcion

            # Importe de la percepción (long 13.2, desde 58 hasta 70)
            content += _bridge_format_amount(-line.balance, 13, 2, ",")

            if act_7 and not payment:
                # Fecha Emisión (long 10, desde 71 hasta 80)
                content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # Tipo Operación (A=Alta)
            content += "A"
            content += "\r\n"

            if payment:
                ret += content
            else:
                perc += content

        period = (
            move_lines
            and fields.Date.from_string(move_lines[0].date).strftime("%Y%mX")
            or ""
        )

        # AR-CUIT-PERIODO-ACTIVIDAD-LOTE_MD5
        perc_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat,
            period,
            "7",
        )

        # AR-CUIT-PERIODO-ACTIVIDAD-LOTE_MD5
        ret_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat,
            period,
            "6",
        )

        return [
            {
                "txt_filename": perc_txt_filename,
                "txt_content": perc,
            },
            {
                "txt_filename": ret_txt_filename,
                "txt_content": ret,
            },
        ]

    def iibb_alta_ret_aplicado_arba_por_lote_A_122R_01032026(self, move_lines):
        """Harden ARBA ER TXT generation and align retention base criteria."""
        self.ensure_one()
        content = ""
        for line in move_lines:
            content += re.sub(r"[^0-9]", "", str(line.name))[-20:].zfill(20)
            content += line.partner_id.ensure_vat()

            move = line.move_id
            move_doc_type = move.l10n_latam_document_type_id
            line_doc_type = line.l10n_latam_document_type_id
            document_code = (
                (move_doc_type and move_doc_type.code)
                or (line_doc_type and line_doc_type.code)
            )
            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number or move.name,
                document_code,
            )
            pto_venta = "{:0>5d}".format(document_parts["point_of_sale"])[-5:]
            content += str(pto_venta)

            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            tax = line.tax_line_id
            partner = line.partner_id
            alicuot_line = tax.get_partner_alicuot(partner, line.date)
            if not alicuot_line:
                raise UserError(
                    'No hay alicuota configurada para el impuesto "%s" en '
                    'el partner "%s" (id: %s) en la fecha %s'
                    % (tax.name, partner.name, partner.id, line.date)
                )
            alicuota_retencion = alicuot_line.alicuota_retencion
            content += "%05.2f" % alicuota_retencion

            withholdable_base = self._bridge_get_arba_retention_base(
                line, alicuota_retencion
            )
            content += "%016.2f" % withholdable_base

            content += "\r\n"

        period = (
            move_lines
            and fields.Date.from_string(move_lines[0].date).strftime("%Y%mX")
            or ""
        )

        filename = "ER-%s-%s-%s-LOTEXXXXX.txt" % (
            self.company_id.vat,
            period,
            "6",
        )

        return [
            {
                "txt_filename": filename,
                "txt_content": content,
            }
        ]
