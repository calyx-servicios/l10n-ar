import logging

from odoo import fields, models
from odoo.exceptions import UserError

from ..models.res_company import TUCUMAN_SCHEMA, TUCUMAN_VIEWS

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ar_tucuman_db_host = fields.Char(
        related="company_id.l10n_ar_tucuman_db_host",
        readonly=False,
        string="Host",
    )
    l10n_ar_tucuman_db_port = fields.Char(
        related="company_id.l10n_ar_tucuman_db_port",
        readonly=False,
        string="Puerto",
    )
    l10n_ar_tucuman_db_name = fields.Char(
        related="company_id.l10n_ar_tucuman_db_name",
        readonly=False,
        string="Base de Datos",
    )
    l10n_ar_tucuman_db_user = fields.Char(
        related="company_id.l10n_ar_tucuman_db_user",
        readonly=False,
        string="Usuario",
    )
    l10n_ar_tucuman_db_password = fields.Char(
        related="company_id.l10n_ar_tucuman_db_password",
        readonly=False,
        string="Contraseña",
    )
    l10n_ar_tucuman_db_sslmode = fields.Selection(
        related="company_id.l10n_ar_tucuman_db_sslmode",
        readonly=False,
        string="Modo SSL",
    )

    def l10n_ar_tucuman_db_test(self):
        """Verifica la conexión a la BD externa de padrones de Tucumán."""
        self.ensure_one()
        # Guardamos primero: sin esto el botón probaría los valores anteriores y no los
        # que el usuario acaba de tipear en el formulario.
        self.execute()

        conn = None
        try:
            conn = self.company_id.l10n_ar_tucuman_connect()
            cur = conn.cursor()
            cur.execute("SELECT version()")
            server_version = cur.fetchone()[0]

            readable, denied = [], []
            for view_name in TUCUMAN_VIEWS.values():
                qualified = "%s.%s" % (TUCUMAN_SCHEMA, view_name)
                try:
                    # Sólo verificamos el permiso de lectura.
                    cur.execute("SELECT 1 FROM %s LIMIT 1" % qualified)
                    cur.fetchall()
                    readable.append(qualified)
                except Exception as view_exc:
                    _logger.warning("Padrón Tucumán: no se pudo leer %s: %s", qualified, view_exc)
                    denied.append(qualified)
                    # Un error deja la transacción abortada: hay que limpiarla para
                    # poder probar la vista siguiente con el mismo cursor.
                    conn.rollback()
        except UserError:
            raise
        except Exception as e:
            raise UserError(
                self.env._("No se pudo conectar a la BD de Padrones de Tucumán:\n\n%s") % str(e)
            ) from e
        finally:
            if conn:
                conn.close()

        message = self.env._("Servidor: %s", server_version.split(" on ")[0])
        if readable:
            message += self.env._("\nVistas legibles: %s", ", ".join(readable))
        if denied:
            message += self.env._("\nSin permiso de lectura: %s", ", ".join(denied))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Padrón Tucumán")
                if not denied
                else self.env._("Conecta, pero faltan permisos"),
                "message": message,
                "type": "success" if not denied else "warning",
                "sticky": True,
            },
        }
