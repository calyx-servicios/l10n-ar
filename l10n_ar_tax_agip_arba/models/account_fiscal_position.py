import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountFiscalPositionL10nArTax(models.Model):
    _inherit = "account.fiscal.position.l10n_ar_tax"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _padron_parse_date_range(self, rows, raw_from_idx, raw_to_idx, date, to_date):
        """Return the first row whose date range covers [date, to_date].
        Raw date values in the DB are stored as integers in DDMMYYYY format.
        We reorder them to YYYYMMDD before comparing.
        """
        date_yyyymmdd = int(date.strftime("%Y%m%d"))
        to_date_yyyymmdd = int(to_date.strftime("%Y%m%d"))
        for row in rows:
            raw_from = str(row[raw_from_idx]).zfill(8)
            raw_to = str(row[raw_to_idx]).zfill(8)
            # Reorder DDMMYYYY → YYYYMMDD
            from_server = int(raw_from[4:8] + raw_from[2:4] + raw_from[0:2])
            to_server = int(raw_to[4:8] + raw_to[2:4] + raw_to[0:2])
            if from_server <= date_yyyymmdd and to_server >= to_date_yyyymmdd:
                return row
        return None

    @staticmethod
    def _padron_parse_alicuota(raw_value: str) -> float:
        """Convierte un valor de alícuota del padrón
           (string con formato numérico argentino, ej "2.5" o "3,0") a float.
        """
        return float(str(raw_value).replace(".", "").replace(",", "."))

    # ------------------------------------------------------------------
    # AGIP override
    # ------------------------------------------------------------------

    def _get_agip_data(self, partner, date, to_date):
        """Devuelve la alícuota de AGIP para el partner consultando la BD externa de Calyx.
        """
        # Guard para data demo — igual que el método original de adhoc
        if self.env.ref("base.user_demo", raise_if_not_found=False):
            return (
                2.5 if self.tax_type == "withholding" else 3.0,
                "VALOR DUMMY | dummy",
            )

        cuit = partner.vat
        if not cuit:
            _logger.warning(
                "AGIP: partner id=%s no tiene CUIT, se omite consulta.",
                partner.id,
            )
            return (None, None)

        cuit_clean = cuit.replace("-", "")
        company = self.fiscal_position_id.company_id
        conn = None

        try:
            conn = company.padron_connect()
            cur = conn.cursor()

            # col2=fecha_desde, col3=fecha_hasta, col4=CUIT,
            # col8=percepcion, col9=retencion
            cur.execute(
                "SELECT col2, col3, col8, col9 FROM agip WHERE col4 = %s",
                (cuit_clean,),
            )
            rows = cur.fetchall()

            if not rows:
                _logger.info(
                    "AGIP: CUIT %s no figura en el padrón.", cuit_clean
                )
                return (
                    None,
                    "CUIT %s no figura en padrón AGIP" % cuit_clean,
                )

            # fecha_desde=idx 0, fecha_hasta=idx 1
            matching = self._padron_parse_date_range(
                rows, 0, 1, date, to_date
            )
            if not matching:
                _logger.info(
                    "AGIP: CUIT %s existe pero sin vigencia para %s - %s.",
                    cuit_clean, date, to_date,
                )
                return (
                    None,
                    "CUIT %s sin vigencia en padrón AGIP para el período"
                    % cuit_clean,
                )

            # col8=percepcion (idx 2), col9=retencion (idx 3)
            alicuota_per = self._padron_parse_alicuota(matching[2])
            alicuota_ret = self._padron_parse_alicuota(matching[3])

            alicuota = (
                alicuota_ret
                if self.tax_type == "withholding"
                else alicuota_per
            )
            _logger.info(
                "AGIP: CUIT %s — retención=%.2f%% percepción=%.2f%%",
                cuit_clean, alicuota_ret, alicuota_per,
            )
            return (alicuota, "Alícuota padrón AGIP (BD externa)")

        except Exception as e:
            _logger.error(
                "AGIP: error consultando BD externa para CUIT %s: %s",
                cuit_clean, str(e),
            )
            # (None, None) → adhoc aplica default_tax_id sin interrumpir la op.
            return (None, None)

        finally:
            if conn:
                conn.close()

    # ------------------------------------------------------------------
    # ARBA override
    # ------------------------------------------------------------------

    def _get_arba_data(self, partner, date, to_date):
        """Devuelve la alícuota de ARBA para el partner, consultando la BD externa de Calyx.
        """
        # Guard para data demo
        if self.env.ref("base.user_demo", raise_if_not_found=False):
            return (
                2.5 if self.tax_type == "withholding" else 3.0,
                "VALOR DUMMY | dummy",
            )

        self.ensure_one()

        # 1. Intentar padrón local cargado en Odoo (comportamiento original
        #    de adhoc). Si hay ref significa que lo encontró → lo usamos.
        alicuot, ref = self._get_padron_data(partner, date, to_date)
        if ref:
            return alicuot, ref

        # 2. Sin padrón local → consultar BD externa de Calyx.
        cuit = partner.vat
        if not cuit:
            _logger.warning(
                "ARBA: partner id=%s no tiene CUIT, se omite consulta.",
                partner.id,
            )
            return (None, None)

        cuit_clean = cuit.replace("-", "")
        company = self.fiscal_position_id.company_id

        # ARBA usa tablas separadas según tipo: arbaret (retenciones) o
        # arbaper (percepciones). Layout: col3=desde, col4=hasta, col5=CUIT,
        # col9=alicuota.
        if self.tax_type == "withholding":
            table = "arbaret"
            ref_label = "Alícuota retención ARBA (BD externa)"
        else:
            table = "arbaper"
            ref_label = "Alícuota percepción ARBA (BD externa)"

        conn = None
        try:
            conn = company.padron_connect()
            cur = conn.cursor()

            cur.execute(
                "SELECT col3, col4, col9 FROM %s WHERE col5 = %%s" % table,
                (cuit_clean,),
            )
            rows = cur.fetchall()

            if not rows:
                _logger.info(
                    "ARBA: CUIT %s no figura en %s.", cuit_clean, table
                )
                return (
                    None,
                    "CUIT %s no figura en padrón ARBA" % cuit_clean,
                )

            # fecha_desde=idx 0, fecha_hasta=idx 1, alicuota=idx 2
            matching = self._padron_parse_date_range(
                rows, 0, 1, date, to_date
            )
            if not matching:
                _logger.info(
                    "ARBA: CUIT %s existe en %s pero sin vigencia para "
                    "%s - %s.",
                    cuit_clean, table, date, to_date,
                )
                return (
                    None,
                    "CUIT %s sin vigencia en padrón ARBA para el período"
                    % cuit_clean,
                )

            alicuota = self._padron_parse_alicuota(matching[2])
            _logger.info(
                "ARBA: CUIT %s — %s=%.2f%%",
                cuit_clean, self.tax_type, alicuota,
            )
            return (alicuota, ref_label)

        except Exception as e:
            _logger.error(
                "ARBA: error consultando BD externa para CUIT %s: %s",
                cuit_clean, str(e),
            )
            return (None, None)

        finally:
            if conn:
                conn.close()
