import re
from typing import Dict

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _l10n_ar_get_document_number_parts(
        self,
        document_number: str,
        document_type_code: str,
    ) -> Dict[str, int]:
        """Return document parts even when local numbers don't contain '-' separator."""
        cleaned_number = (document_number or "").split("(")[0].strip()
        if document_type_code in ["66", "67"]:
            return super()._l10n_ar_get_document_number_parts(
                cleaned_number,
                document_type_code,
            )

        if "-" in cleaned_number:
            pos_raw, invoice_raw = cleaned_number.split("-", 1)
            pos_digits = re.sub(r"\D", "", pos_raw or "")
            invoice_digits = re.sub(r"\D", "", invoice_raw or "")
            if pos_digits and invoice_digits:
                return {
                    "invoice_number": int(invoice_digits) or 1,
                    "point_of_sale": int(pos_digits) or 1,
                }

            try:
                return super()._l10n_ar_get_document_number_parts(
                    cleaned_number,
                    document_type_code,
                )
            except (TypeError, ValueError):
                pass

        digit_groups = re.findall(r"\d+", cleaned_number)
        if not digit_groups:
            return {"invoice_number": 1, "point_of_sale": 1}

        invoice_number = int(digit_groups[-1] or "0") or 1
        point_of_sale = 1
        if len(digit_groups) > 1:
            point_of_sale = int(digit_groups[-2] or "0") or 1

        return {
            "invoice_number": invoice_number,
            "point_of_sale": point_of_sale,
        }
