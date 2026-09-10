import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

AR_CHART_TEMPLATES = ("ar_ri", "ar_ex", "ar_base")
# Percepción de IIBB Tucumán aplicada, la que crea l10n_ar con el plan de cuentas.
TUCUMAN_PERCEPTION_XMLID = "account.%s_ri_tax_percepcion_iibb_tn_aplicada"


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @api.model
    def _l10n_ar_tucuman_add_bruto_tax(self, company):
        """Crea la variante de base bruta de la percepción de Tucumán.
        """
        company.ensure_one()
        tax = self.env.ref(TUCUMAN_PERCEPTION_XMLID % company.id, raise_if_not_found=False)
        if not tax:
            return
        Tax = self.env["account.tax"].with_context(active_test=False)
        exists = Tax.search(
            [
                ("company_id", "=", company.id),
                ("tax_group_id", "=", tax.tax_group_id.id),
                ("type_tax_use", "=", "sale"),
                ("computa_sobre_bruto", "=", True),
            ],
            limit=1,
        )
        if exists:
            return
        new_tax = tax.copy(
            {
                "name": "%s s/bruto" % tax.name,
                "computa_sobre_bruto": True,
                "active": True,
            }
        )
        _logger.info(
            "Padrón Tucumán: creada plantilla de base bruta %s para %s",
            new_tax.name,
            company.name,
        )

    def _load(self, template_code, company, install_demo, force_create=True):
        res = super()._load(template_code, company, install_demo, force_create)
        company = company or self.env.company
        if company.chart_template in AR_CHART_TEMPLATES:
            self.sudo()._l10n_ar_tucuman_add_bruto_tax(company)
        return res
