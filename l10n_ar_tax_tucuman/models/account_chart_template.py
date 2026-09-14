import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

AR_CHART_TEMPLATES = ("ar_ri", "ar_ex", "ar_base")
# Impuestos de IIBB Tucumán que crean l10n_ar y l10n_ar_withholding con el plan de cuentas.
TUCUMAN_PERCEPTION_XMLID = "account.%s_ri_tax_percepcion_iibb_tn_aplicada"
TUCUMAN_WITHHOLDING_XMLID = "account.%s_ex_tax_withholding_iibb_t_applied"


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @api.model
    def _l10n_ar_tucuman_add_bruto_taxes(self, company):
        """Crea las variantes de base bruta de la percepción y la retención de Tucumán."""
        company.ensure_one()
        self._l10n_ar_tucuman_add_variant(
            company, TUCUMAN_PERCEPTION_XMLID, "computa_sobre_bruto", True
        )
        self._l10n_ar_tucuman_add_variant(
            company, TUCUMAN_WITHHOLDING_XMLID, "l10n_ar_tax_type", "iibb_total"
        )

    @api.model
    def _l10n_ar_tucuman_add_variant(self, company, xmlid, field, value):
        tax = self.env.ref(xmlid % company.id, raise_if_not_found=False)
        if not tax:
            return
        Tax = self.env["account.tax"].with_context(active_test=False)
        exists = Tax.search(
            [
                ("company_id", "=", company.id),
                ("tax_group_id", "=", tax.tax_group_id.id),
                ("type_tax_use", "=", tax.type_tax_use),
                (field, "=", value),
            ],
            limit=1,
        )
        if exists:
            return
        new_tax = tax.copy({"name": "%s s/bruto" % tax.name, field: value, "active": True})
        _logger.info(
            "Padrón Tucumán: creada plantilla de base bruta %s para %s",
            new_tax.name,
            company.name,
        )

    def _load(self, template_code, company, install_demo, force_create=True):
        res = super()._load(template_code, company, install_demo, force_create)
        company = company or self.env.company
        if company.chart_template in AR_CHART_TEMPLATES:
            self.sudo()._l10n_ar_tucuman_add_bruto_taxes(company)
        return res
