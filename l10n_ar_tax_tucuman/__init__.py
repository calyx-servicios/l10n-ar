from . import models
from . import wizard

from .models.account_chart_template import AR_CHART_TEMPLATES


def post_init_hook(env):
    """Crear la plantilla de base bruta en las compañías que ya tienen el plan cargado."""
    chart_template = env["account.chart.template"].sudo()
    companies = env["res.company"].sudo().search([("chart_template", "in", AR_CHART_TEMPLATES)])
    for company in companies:
        chart_template._l10n_ar_tucuman_add_bruto_tax(company)
