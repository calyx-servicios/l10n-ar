import logging

import psycopg2
from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    padron_db_host = fields.Char(string="Host")
    padron_db_port = fields.Char(string="Puerto", default="5432")
    padron_db_name = fields.Char(string="Base de Datos")
    padron_db_user = fields.Char(string="Usuario")
    padron_db_password = fields.Char(string="Contraseña")

    def padron_connect(self) -> psycopg2.extensions.connection:
        """Open and return a psycopg2 connection to the external padron database.

        The same database hosts all padron tables: agip, arbaret, arbaper.

        :returns: An open psycopg2 connection.
        :raises UserError: If any required credential is missing.
        :raises psycopg2.Error: If the connection cannot be established.
        """
        self.ensure_one()
        missing = [
            label
            for field_name, label in [
                ("padron_db_host", "Host"),
                ("padron_db_name", "Base de Datos"),
                ("padron_db_user", "Usuario"),
                ("padron_db_password", "Contraseña"),
            ]
            if not getattr(self, field_name)
        ]
        if missing:
            raise UserError(
                _(
                    "Faltan los siguientes datos de conexión de BD de Padrones "
                    "en la configuración de la empresa: %s"
                )
                % ", ".join(missing)
            )
        _logger.info(
            "Conectando a BD de Padrones: host=%s port=%s db=%s user=%s",
            self.padron_db_host,
            self.padron_db_port or "5432",
            self.padron_db_name,
            self.padron_db_user,
        )
        return psycopg2.connect(
            host=self.padron_db_host,
            port=int(self.padron_db_port or 5432),
            database=self.padron_db_name,
            user=self.padron_db_user,
            password=self.padron_db_password,
        )
