import logging
from typing import List, Tuple

from dateutil.relativedelta import relativedelta
from odoo import _, fields, models
from odoo.exceptions import RedirectWarning

_logger = logging.getLogger(__name__)

# Combinaciones (webservice, tax_type) que este módulo provee via BD externa.
_PADRON_COMBOS: List[Tuple[str, str]] = [
    ("agip", "withholding"),
    ("agip", "perception"),
    ("arba", "withholding"),
    ("arba", "perception"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _padron_existing_domain(
        self,
        fp_tax,
        company,
        today,
    ) -> list:
        """Build the search domain to detect an existing vigente record.
        """
        domain = (
            self.env["l10n_ar.partner.tax"]
            ._check_company_domain(company)
        )
        domain += [
            ("tax_id.tax_group_id", "=",
             fp_tax.default_tax_id.tax_group_id.id),
        ]
        if fp_tax.tax_type == "withholding":
            domain += [
                ("tax_id.l10n_ar_state_id", "=",
                 fp_tax.default_tax_id.l10n_ar_state_id.id),
            ]
        domain += [
            "|", ("from_date", "<=", today), ("from_date", "=", False),
            "|", ("to_date", ">=", today), ("to_date", "=", False),
        ]
        return domain

    # ------------------------------------------------------------------
    # Button action
    # ------------------------------------------------------------------

    def action_update_padron(self) -> dict:
        """Fetch missing padron aliquots from the external DB for this
        partner and the current period.
        """
        self.ensure_one()
        # Always work on the commercial partner (where taxes are stored).
        partner = self.commercial_partner_id

        if not partner.vat:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Sin CUIT"),
                    "message": _(
                        "El partner no tiene CUIT configurado."
                    ),
                    "type": "warning",
                    "sticky": False,
                },
            }

        company = self.env.company
        today = fields.Date.today()
        fp_tax_model = self.env["account.fiscal.position.l10n_ar_tax"]

        # Count existing records before the operation to compute delta.
        count_before = self.env["l10n_ar.partner.tax"].search_count(
            [("partner_id", "=", partner.id)]
        )

        errors: List[str] = []
        cuit_clean = partner.vat.replace("-", "")

        # --- Paso 1: determinar qué combos faltan (sin conectar a BD externa) ---
        pending = []
        for webservice, tax_type in _PADRON_COMBOS:
            fp_tax = fp_tax_model.sudo().search(
                [
                    ("webservice", "=", webservice),
                    ("tax_type", "=", tax_type),
                    ("fiscal_position_id.company_id", "=", company.id),
                ],
                limit=1,
            )

            if not fp_tax:
                _logger.info(
                    "Padrón: no hay fp_tax para %s/%s en empresa '%s'.",
                    webservice, tax_type, company.name,
                )
                continue

            domain = self._padron_existing_domain(fp_tax, company, today)
            if fp_tax.tax_type == "perception":
                existing = partner.l10n_ar_partner_perception_ids.filtered_domain(domain)
            else:
                existing = partner.l10n_ar_partner_tax_ids.filtered_domain(domain)

            if existing:
                _logger.info(
                    "Padrón: %s/%s ya vigente para '%s' — se omite.",
                    webservice, tax_type, partner.name,
                )
                continue

            pending.append((webservice, tax_type, fp_tax))

        # Si no hay nada pendiente, salir sin tocar la BD externa.
        if not pending:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Actualizar Padrón"),
                    "message": _(
                        "Todos los registros ya estaban vigentes "
                        "para el período actual."
                    ),
                    "type": "info",
                    "sticky": False,
                },
            }

        # --- Paso 2: pre-fetch con UNA sola conexión para los combos pendientes ---
        padron_prefetch: dict = {}
        _conn = None
        try:
            _conn = company.padron_connect()
            _cur = _conn.cursor()
            _cur.execute(
                "SELECT col2, col3, col8, col9 FROM agip WHERE col4 = %s",
                (cuit_clean,),
            )
            padron_prefetch["agip"] = _cur.fetchall()
            _cur.execute(
                "SELECT col3, col4, col9 FROM arbaret WHERE col5 = %s",
                (cuit_clean,),
            )
            padron_prefetch["arbaret"] = _cur.fetchall()
            _cur.execute(
                "SELECT col3, col4, col9 FROM arbaper WHERE col5 = %s",
                (cuit_clean,),
            )
            padron_prefetch["arbaper"] = _cur.fetchall()
        except Exception as _exc:
            _logger.error(
                "Padrón: error en pre-fetch para CUIT %s: %s",
                cuit_clean, str(_exc),
            )
            padron_prefetch = {}
        finally:
            if _conn:
                _conn.close()

        # --- Paso 3: procesar solo los combos pendientes ---
        for webservice, tax_type, fp_tax in pending:
            try:
                fp_tax.sudo().with_context(
                    padron_prefetch=padron_prefetch
                )._get_missing_taxes(partner, today)
            except RedirectWarning:
                # Múltiples impuestos vigentes para el mismo grupo —
                # es un problema de datos, no bloqueamos el resto.
                _logger.warning(
                    "Padrón: múltiples impuestos vigentes en %s/%s "
                    "para '%s'.",
                    webservice, tax_type, partner.name,
                )
                errors.append("%s %s" % (webservice.upper(), tax_type))
            except Exception as exc:
                _logger.error(
                    "Padrón: error consultando %s/%s para '%s': %s",
                    webservice, tax_type, partner.name, str(exc),
                )
                errors.append("%s %s" % (webservice.upper(), tax_type))

        count_after = self.env["l10n_ar.partner.tax"].search_count(
            [("partner_id", "=", partner.id)]
        )
        created = count_after - count_before

        # Build user-facing message.
        if errors:
            msg = _(
                "Se crearon %(n)d registro(s). "
                "Errores en: %(e)s",
                n=created,
                e=", ".join(errors),
            )
            notif_type = "warning"
        elif created == 0:
            msg = _(
                "Todos los registros ya estaban vigentes "
                "para el período actual."
            )
            notif_type = "info"
        else:
            msg = _("Se crearon %(n)d registro(s) de padrón.", n=created)
            notif_type = "success"

        result = {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Actualizar Padrón"),
                "message": msg,
                "type": notif_type,
                "sticky": False,
            },
        }
        if created > 0:
            result["params"]["next"] = {
                "type": "ir.actions.act_window",
                "res_model": "res.partner",
                "res_id": partner.id,
                "views": [(False, "form")],
                "target": "current",
            }
        return result
