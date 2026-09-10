import logging

import psycopg2
from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Esquema y vistas que publica el equipo de la BD de padrones. El usuario de
# consulta tiene permiso de lectura sólo sobre estas dos vistas.
TUCUMAN_SCHEMA = "eg_tucuman"
TUCUMAN_VIEWS = {
    "perception": "v_percepciones_v1",
    "withholding": "v_retenciones_v1",
}

# La consulta corre en el camino de facturación: si la BD externa no responde,
# preferimos un error rápido antes que dejar al usuario esperando.
CONNECT_TIMEOUT = 10
STATEMENT_TIMEOUT_MS = 15000


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ar_tucuman_db_host = fields.Char(string="Host")
    l10n_ar_tucuman_db_port = fields.Char(string="Puerto", default="5432")
    l10n_ar_tucuman_db_name = fields.Char(string="Base de Datos")
    l10n_ar_tucuman_db_user = fields.Char(string="Usuario")
    l10n_ar_tucuman_db_password = fields.Char(string="Contraseña")
    l10n_ar_tucuman_db_sslmode = fields.Selection(
        selection=[
            ("disable", "Deshabilitado"),
            ("prefer", "Preferido"),
            ("require", "Requerido"),
        ],
        string="Modo SSL",
        default="disable",
        required=True,
        help="El servidor de padrones de Tucumán no admite conexiones TLS: el modo debe ser "
        "'Deshabilitado' y la conexión hacerse desde una red aprobada. Se deja configurable "
        "para el día que habiliten TLS.",
    )

    def l10n_ar_tucuman_connect(self) -> psycopg2.extensions.connection:
        """Abre y devuelve una conexión a la base de datos externa de padrones de Tucumán.

        La conexión es de sólo lectura: el usuario configurado sólo tiene acceso a las
        vistas de eg_tucuman.

        :returns: Una conexión psycopg2 abierta. Es responsabilidad de quien llama cerrarla.
        :raises UserError: Si falta algún dato de conexión.
        :raises psycopg2.Error: Si no se puede establecer la conexión.
        """
        self.ensure_one()
        missing = [
            label
            for field_name, label in [
                ("l10n_ar_tucuman_db_host", "Host"),
                ("l10n_ar_tucuman_db_name", "Base de Datos"),
                ("l10n_ar_tucuman_db_user", "Usuario"),
                ("l10n_ar_tucuman_db_password", "Contraseña"),
            ]
            if not getattr(self, field_name)
        ]
        if missing:
            raise UserError(
                self.env._(
                    "Faltan los siguientes datos de conexión de la BD de Padrones de Tucumán "
                    "en Ajustes / Contabilidad / Localización Argentina: %s"
                )
                % ", ".join(missing)
            )
        _logger.info(
            "Conectando a BD de Padrones Tucumán: %s:%s",
            self.l10n_ar_tucuman_db_host,
            self.l10n_ar_tucuman_db_port or "5432",
        )
        return psycopg2.connect(
            host=self.l10n_ar_tucuman_db_host,
            port=int(self.l10n_ar_tucuman_db_port or 5432),
            database=self.l10n_ar_tucuman_db_name,
            user=self.l10n_ar_tucuman_db_user,
            password=self.l10n_ar_tucuman_db_password,
            sslmode=self.l10n_ar_tucuman_db_sslmode or "disable",
            connect_timeout=CONNECT_TIMEOUT,
            # Corta consultas colgadas del lado del servidor y nos identifica en sus logs.
            options="-c statement_timeout=%s" % STATEMENT_TIMEOUT_MS,
            application_name="odoo-l10n_ar_tax_tucuman",
        )
