import logging

from odoo import fields, models
from odoo.exceptions import UserError

from .res_company import TUCUMAN_SCHEMA, TUCUMAN_VIEWS

_logger = logging.getLogger(__name__)


class AccountFiscalPositionL10nArTax(models.Model):
    _inherit = "account.fiscal.position.l10n_ar_tax"

    webservice = fields.Selection(
        selection_add=[("tucuman", "Padrón Tucumán")],
        ondelete={"tucuman": "set null"},
    )

    def _get_webservice_for_state(self, state):
        """Tucumán es la jurisdicción 924."""
        if state and state.jurisdiction_code == "924":
            return "tucuman"
        return super()._get_webservice_for_state(state)

    @staticmethod
    def _l10n_ar_tucuman_cuit(partner):
        cuit = (partner.vat or "").replace("-", "").strip()
        return cuit if len(cuit) == 11 and cuit.isdigit() else False

    def _get_tucuman_data(self, partner, date, to_date):
        """Alícuota del padrón de Tucumán para un CUIT y un período.

        :return: (float|None, str) alícuota y referencia. None = sin alícuota en el padrón,
            se aplica el impuesto por defecto de la línea.
        """
        self.ensure_one()

        # Para bases demo, se devuelve un valor dummy.
        if self.env.ref("base.user_demo", raise_if_not_found=False):
            return (2.5 if self.tax_type == "withholding" else 3.0, "VALOR DUMMY | dummy")

        cuit = self._l10n_ar_tucuman_cuit(partner)
        if not cuit:
            return None, self.env._("Sin CUIT válido para consultar el padrón de Tucumán")

        periodo = date.strftime("%Y%m")
        row = self.env.context.get("l10n_ar_tucuman_row")
        if row is None:
            row = self._l10n_ar_tucuman_resolve(partner, periodo)[0]
        if not row:
            return None, self.env._(
                "CUIT %(cuit)s sin alícuota en el padrón de Tucumán %(periodo)s",
                cuit=cuit,
                periodo=periodo,
            )

        ref = self.env._(
            "Padrón Tucumán %(periodo)s | Alícuota %(alicuota)s",
            periodo=periodo,
            alicuota=row["alicuota"],
        )
        if self.tax_type == "withholding":
            ref += self.env._(" | Marca %s", row["marca"])
        return float(row["alicuota"]), ref

    def _l10n_ar_tucuman_resolve(self, partner, periodo):
        """(fila|None, publicado): la fila del padrón que aplica a esta línea."""
        self.ensure_one()
        tipo = "retención" if self.tax_type == "withholding" else "percepción"
        cuit = self._l10n_ar_tucuman_cuit(partner)
        if not cuit:
            _logger.info(
                "Padrón Tucumán %s: partner %s sin CUIT válido, se omite consulta.",
                tipo,
                partner.id,
            )
            return None, True

        rows, publicado = self._l10n_ar_tucuman_fetch(cuit, periodo)
        if not publicado:
            _logger.info("Padrón Tucumán %s: período %s todavía no publicado.", tipo, periodo)
            return None, False
        if not rows:
            _logger.info(
                "Padrón Tucumán %s: CUIT %s no figura en el padrón %s, "
                "se aplica el default de la posición fiscal.",
                tipo,
                cuit,
                periodo,
            )
            return None, True

        if self.tax_type == "withholding":
            row, marca, motivo = self._l10n_ar_tucuman_select_withholding(rows, partner)
            decision = "marca %s (%s)" % (marca, motivo)
        else:
            row, decision = rows[0], "fila única"

        if row:
            _logger.info(
                "Padrón Tucumán %s: CUIT %s período %s -> %s, alícuota %s (%s)",
                tipo,
                cuit,
                periodo,
                decision,
                row["alicuota"],
                "bruto" if row["bruto"] else "neto",
            )
        else:
            _logger.info(
                "Padrón Tucumán %s: CUIT %s período %s -> %s no existe en el padrón, "
                "se aplica el default de la posición fiscal.",
                tipo,
                cuit,
                periodo,
                decision,
            )
        return row, True

    def _l10n_ar_tucuman_select_withholding(self, rows, partner):
        """(fila|None, marca, motivo) según las reglas de retención de Tucumán."""
        by_marca = {row["marca"]: row for row in rows}
        tucuman = self.env.ref("base.state_ar_t")
        if tucuman not in self.fiscal_position_id.state_ids:
            marca, motivo = "CM", "posición fiscal sin Tucumán"
        elif "E" in by_marca:
            marca, motivo = "E", "exento en el padrón"
        elif "CL" in by_marca:
            marca, motivo = "CL", "contribuyente local en el padrón"
        elif partner.l10n_ar_gross_income_type == "multilateral" and tucuman in (
            partner.state_id | partner.gross_income_jurisdiction_ids
        ):
            marca, motivo = "CM", "partner multilateral con Tucumán"
        else:
            marca, motivo = "art2", "partner no multilateral con Tucumán"
        return by_marca.get(marca), marca, motivo

    def _l10n_ar_tucuman_fetch(self, cuit, periodo):
        """(filas, publicado): las filas del CUIT y si el período está publicado."""
        self.ensure_one()
        view = "%s.%s" % (TUCUMAN_SCHEMA, TUCUMAN_VIEWS[self.tax_type])
        company = self.fiscal_position_id.company_id
        conn = None
        try:
            conn = company.l10n_ar_tucuman_connect()
            cur = conn.cursor()
            cur.execute(
                f"SELECT marca, alicuota, bruto FROM {view} WHERE periodo = %s AND cuit = %s",
                (periodo, cuit),
            )
            rows = [
                {"marca": marca, "alicuota": alicuota, "bruto": bruto}
                for marca, alicuota, bruto in cur.fetchall()
            ]
            if rows:
                return rows, True
            cur.execute(f"SELECT 1 FROM {view} WHERE periodo = %s LIMIT 1", (periodo,))
            return [], bool(cur.fetchone())
        except UserError:
            raise
        except Exception as e:
            _logger.error(
                "Padrón Tucumán: error consultando CUIT %s período %s: %s", cuit, periodo, e
            )
            # No devolvemos el impuesto por defecto en silencio: sería percibir mal sin avisar.
            raise UserError(
                self.env._(
                    "No se pudo consultar el padrón de Tucumán.\n\n"
                    "Puede cargar la alícuota manualmente en la pestaña 'Contabilidad' "
                    "del contacto mientras se resuelve.\n\nDetalle: %s"
                )
                % str(e)
            ) from e
        finally:
            if conn:
                conn.close()

    def _get_tax_from_ws(self, partner, date):
        """Consulta el padrón una sola vez y deja la fila en contexto, para que
        _get_tax_domain y _ensure_tax elijan la variante de base que indica 'bruto'."""
        if self.webservice != "tucuman" or self.env.ref(
            "base.user_demo", raise_if_not_found=False
        ):
            return super()._get_tax_from_ws(partner, date)

        row, publicado = self._l10n_ar_tucuman_resolve(partner, date.strftime("%Y%m"))
        if not publicado:
            return self.default_tax_id

        rec = self.with_context(l10n_ar_tucuman_row=row or {})
        return super(AccountFiscalPositionL10nArTax, rec)._get_tax_from_ws(partner, date)

    def _get_tax_domain(self, filter_tax_group=True):
        domain = super()._get_tax_domain(filter_tax_group=filter_tax_group)
        row = self.env.context.get("l10n_ar_tucuman_row")
        if not row:
            return domain
        if self.tax_type == "withholding":
            tax_type = "iibb_total" if row["bruto"] else "iibb_untaxed"
            return domain + [("l10n_ar_tax_type", "=", tax_type)]
        return domain + [("computa_sobre_bruto", "=", bool(row["bruto"]))]

    def _ensure_tax(self, rate):
        # Red de seguridad: las plantillas de base bruta las crea el hook de instalación,
        # pero si no están, _ensure_tax copiaría la de base neta con un nombre repetido.
        row = self.env.context.get("l10n_ar_tucuman_row")
        if row and row["bruto"]:
            chart_template = self.env["account.chart.template"].sudo()
            chart_template._l10n_ar_tucuman_add_bruto_taxes(self.fiscal_position_id.company_id)
        return super()._ensure_tax(rate)
