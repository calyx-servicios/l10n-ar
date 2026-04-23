import logging
from datetime import date
from typing import List, Tuple

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import RedirectWarning

_logger = logging.getLogger(__name__)

# Combinaciones (webservice, tax_type) definidas en l10n_ar_tax_agip_arba.
_PADRON_COMBOS: List[Tuple[str, str]] = [
    ("agip", "withholding"),
    ("agip", "perception"),
    ("arba", "withholding"),
    ("arba", "perception"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _cron_update_padron_for_target_date(self, target_date):
        """Run padron cron for all active commercial partners."""
        execution_dt = fields.Datetime.now()
        partners = (
            self.search([("active", "=", True)])
            .mapped("commercial_partner_id")
            .filtered("active")
        )

        _logger.info(
            "Padrón CRON: inicio actualización. "
            "Fecha ejecución=%s, fecha objetivo=%s, partners=%s",
            execution_dt,
            target_date,
            len(partners),
        )

        for partner in partners:
            try:
                summary = partner._run_update_padron_for_date(target_date)
                result_label = "error" if summary["errors"] else "exito"
                body = _(
                    "Actualización automática de padrón\n"
                    "Fecha de ejecución: %(execution)s\n"
                    "Período consultado: %(period)s\n"
                    "Resultado: %(result)s\n"
                    "Cambios realizados: %(changes)s\n"
                    "Detalle: %(detail)s",
                    execution=fields.Datetime.to_string(execution_dt),
                    period=target_date.strftime("%Y-%m"),
                    result=result_label,
                    changes=summary["created"],
                    detail=summary["message"],
                )
                partner.message_post(body=body, subtype_xmlid="mail.mt_note")
            except Exception as exc:
                _logger.exception(
                    "Padrón CRON: error inesperado "
                    "procesando partner id=%s: %s",
                    partner.id,
                    str(exc),
                )
                error_body = _(
                    "Actualización automática de padrón\n"
                    "Fecha de ejecución: %(execution)s\n"
                    "Período consultado: %(period)s\n"
                    "Resultado: error\n"
                    "Cambios realizados: 0\n"
                    "Detalle: %(detail)s",
                    execution=fields.Datetime.to_string(execution_dt),
                    period=target_date.strftime("%Y-%m"),
                    detail=str(exc),
                )
                partner.message_post(
                    body=error_body,
                    subtype_xmlid="mail.mt_note",
                )

        _logger.info("Padrón CRON: fin actualización.")
        return True

    def _run_update_padron_for_date(self, target_date) -> dict:
        """Run padron update for a single partner on a target date.
        This is used by the monthly cron and reuses base-module logic.
        """
        self.ensure_one()
        partner = self.commercial_partner_id

        if not partner.vat:
            return {
                "created": 0,
                "errors": [],
                "notif_type": "warning",
                "message": _("El partner no tiene CUIT configurado."),
            }

        company = self.env.company
        fp_tax_model = self.env["account.fiscal.position.l10n_ar_tax"]

        # Count existing records before the operation to compute delta.
        count_before = self.env["l10n_ar.partner.tax"].search_count(
            [("partner_id", "=", partner.id)]
        )

        errors: List[str] = []
        cuit_clean = partner.vat.replace("-", "")

        # --- Paso 1: determinar combos faltantes sin usar BD externa ---
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

            # _padron_existing_domain comes from l10n_ar_tax_agip_arba.
            domain = self._padron_existing_domain(fp_tax, company, target_date)
            if fp_tax.tax_type == "perception":
                existing = (
                    partner.l10n_ar_partner_perception_ids
                    .filtered_domain(domain)
                )
            else:
                existing = (
                    partner.l10n_ar_partner_tax_ids
                    .filtered_domain(domain)
                )

            if existing:
                _logger.info(
                    "Padrón: %s/%s ya vigente para '%s' "
                    "en fecha %s — se omite.",
                    webservice, tax_type, partner.name, target_date,
                )
                continue

            pending.append((webservice, tax_type, fp_tax))

        # Si no hay nada pendiente, salir sin tocar la BD externa.
        if not pending:
            return {
                "created": 0,
                "errors": [],
                "notif_type": "info",
                "message": _(
                    "Todos los registros ya estaban vigentes "
                    "para el período consultado."
                ),
            }

        # --- Paso 2: prefetch con una sola conexión ---
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
                )._get_missing_taxes(partner, target_date)
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

        # If pending combos existed but no source rows were available,
        # it usually means the period padron is not published yet.
        pending_webservices = {webservice for webservice, _, _ in pending}
        has_prefetch_for_pending = any(
            (webservice == "agip" and bool(padron_prefetch.get("agip")))
            or (
                webservice == "arba"
                and bool(
                    padron_prefetch.get("arbaret")
                    or padron_prefetch.get("arbaper")
                )
            )
            for webservice in pending_webservices
        )
        padron_not_published_hint = (
            bool(pending) and not has_prefetch_for_pending
        )

        if errors:
            msg = _(
                "Se crearon %(n)d registro(s). "
                "Errores en: %(e)s",
                n=created,
                e=", ".join(errors),
            )
            notif_type = "warning"
        elif padron_not_published_hint:
            msg = _(
                "Se crearon %(n)d registro(s). Si el padrón del período "
                "%(period)s aún no fue publicado, ejecutá este cron "
                "manualmente más adelante.",
                n=created,
                period=target_date.strftime("%Y-%m"),
            )
            notif_type = "warning"
        elif created == 0:
            msg = _(
                "Todos los registros ya estaban vigentes "
                "para el período consultado."
            )
            notif_type = "info"
        else:
            msg = _("Se crearon %(n)d registro(s) de padrón.", n=created)
            notif_type = "success"

        return {
            "created": created,
            "errors": errors,
            "notif_type": notif_type,
            "message": msg,
        }

    @api.model
    def cron_update_padron_next_month(self, next_month=True):
        """Monthly cron for active partners and next-month padron data.
        Logs in partner chatter and continues on per-partner errors.
        """
        month_offset = 1 if next_month else 0
        target_date = fields.Date.context_today(self) + relativedelta(
            months=month_offset, day=1
        )
        return self._cron_update_padron_for_target_date(target_date)

    @api.model
    def cron_update_padron_selected_month(
        self, test_year=None, test_month=None
    ):
        """Manual test cron that allows selecting explicit year/month."""
        today = fields.Date.context_today(self)
        year = int(test_year or today.year)
        month = int(test_month or today.month)
        if month < 1 or month > 12:
            _logger.warning(
                "Padrón CRON test: mes inválido %s. Se usa mes actual.",
                month,
            )
            month = today.month
        target_date = date(year, month, 1)
        return self._cron_update_padron_for_target_date(target_date)
