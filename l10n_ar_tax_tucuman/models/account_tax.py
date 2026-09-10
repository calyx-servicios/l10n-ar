from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round


class AccountTax(models.Model):
    _inherit = "account.tax"

    computa_sobre_bruto = fields.Boolean(
        string="Computa sobre bruto",
        help="La base de esta percepción es el Neto + IVA en lugar del Neto. Equivale a lo que "
        "'WTH Tax' = 'IIBB Total Amount' resuelve en las retenciones sobre pagos.",
    )

    @api.constrains("computa_sobre_bruto", "amount_type", "price_include", "type_tax_use")
    def _check_computa_sobre_bruto(self):
        """Sin estas condiciones el flag no se aplica y el impuesto liquidaría sobre el neto en
        silencio."""
        for tax in self.filtered("computa_sobre_bruto"):
            if tax.type_tax_use != "sale":
                raise ValidationError(
                    self.env._(
                        "'Computa sobre bruto' sólo aplica a percepciones (impuestos de ventas). "
                        "Para retenciones use 'WTH Tax' = 'IIBB Total Amount'. Impuesto: %s",
                        tax.name,
                    )
                )
            if tax.amount_type != "percent" or tax.price_include or tax.include_base_amount:
                raise ValidationError(
                    self.env._(
                        "'Computa sobre bruto' requiere un impuesto porcentual, no incluido en el "
                        "precio y que no afecte la base de los siguientes. Impuesto: %s",
                        tax.name,
                    )
                )

    def _l10n_ar_is_perception_on_total(self):
        """Percepción de venta cuya base es Neto + IVA."""
        self.ensure_one()
        return bool(
            self.computa_sobre_bruto
            and self.country_code == "AR"
            and self.type_tax_use == "sale"
            and self.amount_type == "percent"
            and not self.price_include
            and not self.include_base_amount
        )

    @api.model
    def _add_tax_details_in_base_line(self, base_line, company, rounding_method=None):
        """Mismo punto de extensión que usa l10n_account_withholding_tax en el core.

        No se usa `include_base_amount` en el IVA porque es global: afectaría a todas las
        percepciones y no sólo a las que el padrón marca como de base bruta.
        """
        super()._add_tax_details_in_base_line(base_line, company, rounding_method=rounding_method)
        self._l10n_ar_apply_perception_on_total(base_line, company, rounding_method=rounding_method)

    @api.model
    def _l10n_ar_apply_perception_on_total(self, base_line, company, rounding_method=None):
        """Rehace base e importe de las percepciones sobre bruto de una línea base.

        La base se toma por línea: si la percepción está en todas, la suma da el total del
        comprobante; si no está en alguna, no debe percibirse sobre el IVA de esa línea.
        """
        tax_details = base_line["tax_details"]
        taxes_data = tax_details["taxes_data"]

        target = [td for td in taxes_data if td["tax"]._l10n_ar_is_perception_on_total()]
        if not target:
            return

        # IVA por código de tributo ARCA del grupo, igual que l10n_ar. Se excluye reverse
        # charge para no contar dos veces el mismo importe.
        vat_amount_currency = sum(
            td["raw_tax_amount_currency"]
            for td in taxes_data
            if td["tax"].tax_group_id.l10n_ar_vat_afip_code and not td.get("is_reverse_charge")
        )
        if not vat_amount_currency:
            return

        rate = base_line["rate"]
        currency = base_line["currency_id"]
        rounding_method = rounding_method or company.tax_calculation_rounding_method

        for tax_data in target:
            tax = tax_data["tax"]
            new_base_currency = tax_data["raw_base_amount_currency"] + vat_amount_currency
            new_tax_currency = new_base_currency * tax.amount / 100.0
            if rounding_method == "round_per_line":
                new_tax_currency = float_round(
                    new_tax_currency, precision_rounding=currency.rounding
                )

            new_base = new_base_currency / rate if rate else 0.0
            new_tax = new_tax_currency / rate if rate else 0.0
            if rounding_method == "round_per_line":
                new_base = company.currency_id.round(new_base)
                new_tax = company.currency_id.round(new_tax)

            # Se ajusta por diferencia: el resto de los impuestos ya está sumado en el total.
            tax_details["raw_total_included_currency"] += (
                new_tax_currency - tax_data["raw_tax_amount_currency"]
            )
            tax_details["raw_total_included"] += new_tax - tax_data["raw_tax_amount"]

            tax_data["base_amount"] = new_base_currency
            tax_data["tax_amount"] = new_tax_currency
            tax_data["raw_base_amount_currency"] = new_base_currency
            tax_data["raw_tax_amount_currency"] = new_tax_currency
            tax_data["raw_base_amount"] = new_base
            tax_data["raw_tax_amount"] = new_tax
