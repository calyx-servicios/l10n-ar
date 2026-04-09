import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    padron_db_host = fields.Char(
        related="company_id.padron_db_host",
        readonly=False,
        string="Host",
    )
    padron_db_port = fields.Char(
        related="company_id.padron_db_port",
        readonly=False,
        string="Puerto",
    )
    padron_db_name = fields.Char(
        related="company_id.padron_db_name",
        readonly=False,
        string="Base de Datos",
    )
    padron_db_user = fields.Char(
        related="company_id.padron_db_user",
        readonly=False,
        string="Usuario",
    )
    padron_db_password = fields.Char(
        related="company_id.padron_db_password",
        readonly=False,
        string="Contraseña",
    )

    def padron_db_test(self):
        """Test the connection to the external padron database (AGIP and ARBA).

        Displays a success or error message to the user.
        """
        self.ensure_one()
        try:
            conn = self.company_id.padron_connect()
            conn.close()
        except UserError:
            raise
        except Exception as e:
            raise UserError(
                _("No se pudo conectar a la BD de Padrones: %s") % str(e)
            )
        raise UserError(_("Conexión exitosa a la BD de Padrones."))
