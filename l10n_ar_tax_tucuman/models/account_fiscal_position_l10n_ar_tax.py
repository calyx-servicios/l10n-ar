import logging

from odoo import fields, models
from odoo.exceptions import UserError

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

        :return: (float|None, str) alícuota y referencia. None = no está en el padrón,
            se aplica el impuesto por defecto de la línea.
        """
        self.ensure_one()

        # Temporal: falta definir cómo se representan en Odoo los CUITs que en
        # v_retenciones_v1 traen dos filas (marcas CM y art2, con alícuotas distintas)
        # cuando Odoo admite una sola alícuota por régimen y contribuyente.
        if self.tax_type != "perception":
            raise UserError(
                self.env._("El padrón de Tucumán está implementado sólo para percepciones.")
            )

        # En bases demo no hay credenciales ni red para consultar el padrón (misma guarda
        # que _get_agip_data, _get_arba_data y _get_rentas_cordoba_data).
        if self.env.ref("base.user_demo", raise_if_not_found=False):
            return 3.0, "VALOR DUMMY | dummy"

        cuit = self._l10n_ar_tucuman_cuit(partner)
        if not cuit:
            _logger.info(
                "Padrón Tucumán: partner %s sin CUIT válido, se omite consulta.", partner.id
            )
            return None, self.env._("Sin CUIT válido para consultar el padrón de Tucumán")

        periodo = date.strftime("%Y%m")
        row = self.env.context.get("l10n_ar_tucuman_row")
        if row is None:
            row = self._l10n_ar_tucuman_fetch(cuit, periodo)[0]
        if not row:
            return None, self.env._(
                "CUIT %(cuit)s no figura en el padrón de Tucumán %(periodo)s",
                cuit=cuit,
                periodo=periodo,
            )

        _logger.info(
            "Padrón Tucumán: CUIT %s período %s -> alícuota %s (%s)",
            cuit,
            periodo,
            row["alicuota"],
            "bruto" if row["bruto"] else "neto",
        )
        ref = self.env._(
            "Padrón Tucumán %(periodo)s | Alícuota %(alicuota)s",
            periodo=periodo,
            alicuota=row["alicuota"],
        )
        return float(row["alicuota"]), ref

    def _l10n_ar_tucuman_fetch(self, cuit, periodo):
        """(dict|None, bool): la fila del CUIT y si el período está publicado.

        Sin fila puede ser que el contribuyente no esté en el padrón (respuesta real) o
        que ese período todavía no se haya publicado (no sabemos nada). Se distinguen
        porque tienen tratamientos distintos.
        """
        self.ensure_one()
        company = self.fiscal_position_id.company_id
        conn = None
        try:
            conn = company.l10n_ar_tucuman_connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT alicuota, bruto FROM eg_tucuman.v_percepciones_v1 "
                "WHERE periodo = %s AND cuit = %s LIMIT 1",
                (periodo, cuit),
            )
            row = cur.fetchone()
            if row:
                return {"alicuota": row[0], "bruto": row[1]}, True
            cur.execute(
                "SELECT 1 FROM eg_tucuman.v_percepciones_v1 WHERE periodo = %s LIMIT 1",
                (periodo,),
            )
            return None, bool(cur.fetchone())
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
        if self.webservice != "tucuman" or self.tax_type != "perception":
            return super()._get_tax_from_ws(partner, date)
        if self.env.ref("base.user_demo", raise_if_not_found=False):
            return super()._get_tax_from_ws(partner, date)

        periodo = date.strftime("%Y%m")
        cuit = self._l10n_ar_tucuman_cuit(partner)
        row, publicado = self._l10n_ar_tucuman_fetch(cuit, periodo) if cuit else (None, True)

        if not row and not publicado:
            _logger.info("Padrón Tucumán: período %s todavía no publicado.", periodo)
            return self.default_tax_id

        rec = self.with_context(l10n_ar_tucuman_row=row or {})
        return super(AccountFiscalPositionL10nArTax, rec)._get_tax_from_ws(partner, date)

    def _get_tax_domain(self, filter_tax_group=True):
        domain = super()._get_tax_domain(filter_tax_group=filter_tax_group)
        row = self.env.context.get("l10n_ar_tucuman_row")
        if row:
            domain += [("computa_sobre_bruto", "=", bool(row["bruto"]))]
        return domain

    def _ensure_tax(self, rate):
        # Red de seguridad: la plantilla de base bruta la crea el hook de instalación,
        # pero si no está, _ensure_tax copiaría la de base neta con un nombre repetido.
        row = self.env.context.get("l10n_ar_tucuman_row")
        if row and row["bruto"]:
            chart_template = self.env["account.chart.template"].sudo()
            chart_template._l10n_ar_tucuman_add_bruto_tax(self.fiscal_position_id.company_id)
        return super()._ensure_tax(rate)
