# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, api, SUPERUSER_ID, _
from dateutil.relativedelta import relativedelta
import datetime, logging

_logger = logging.getLogger(__name__)


class PadronUpdateCron(models.Model):
    _name = "padron.update.cron"
    _description = _("Patterns Update cron")

    @api.model
    def update_padron(self, next_month=None):
        def get_next_month(date_from):
            try:
                date_from = date_from.replace(month=date_from.month + 1)
            except ValueError:
                if date_from.month == 12:
                    date_from = date_from.replace(
                        year=date_from.year + 1, month=1)
            return date_from

        _logger.info("update_padron")
        now = datetime.datetime.now()
        date_from = datetime.date(now.year, now.month, 1)
        if next_month:
            date_from = get_next_month(date_from)
        date_to = (get_next_month(date_from) -
                   datetime.timedelta(days=1)).strftime('%Y %m %d %H:%M:%S')
        date_from = date_from.strftime('%Y %m %d %H:%M:%S')
        for padron in self.env['account.padron.retention.perception.type'].search([]):
            try:
                if padron.server_host and padron.server_database and padron.server_user \
                        and padron.server_password and padron.server_port and padron.type and padron.default_percentage_perception\
                        and padron.default_percentage_retention:
                    vals = {
                        'name': date_from,
                        'server_host': padron.server_host,
                        'server_database': padron.server_database,
                        'server_user': padron.server_user,
                        'server_password': padron.server_password,
                        'server_port': padron.server_port,
                        'type': padron.type,
                        'padron_type_id': padron.id,
                        'default_percentage_perception': padron.default_percentage_perception,
                        'default_percentage_retention': padron.default_percentage_retention,
                        'default_date_from': date_from,
                        'default_date_to': date_to,
                        'state': 'open',
                    }
                    _logger.info(vals)
                    self.env['account.import.padron.ret.perc'].search(
                        [('default_date_from', '>=', date_from), ('default_date_from', '<=', date_to), ('type', '=', padron.type)])
                    if not self.env['account.import.padron.ret.perc'].search([('default_date_from', '>=', date_from), ('default_date_from', '<=', date_to), ('type', '=', padron.type)]):
                        padron_ids = self.env[
                            'account.import.padron.ret.perc'].create(vals)
                        padron_ids.import_padron_server(context={})
            except (Exception) as error:
                _logger.info(error)
                user_id = self.env['res.users'].search([('id', '=', SUPERUSER_ID)])
                _logger.info(user_id)
                self.env['mail.message'].create({'message_type': "notification",
                                                 'body': error,
                                                 'subject': "Actualizacion de Padrones",
                                                 'subtype_id': self.env.ref('mail.mt_comment').id,
                                                 'needaction_partner_ids': [(4, user_id.partner_id.id)],
                                                 'author_id': user_id.partner_id.id,
                                                 'model': self._name,
                                                 'res_id': self.id,
                                                 })

    @api.model
    def close_padron(self):
        today = datetime.datetime.today()
        month = datetime.datetime(today.year, today.month, 1)
        limit = month + relativedelta(months=-1)
        for padron in self.env['account.import.padron.ret.perc'].search([('name', '<', limit)]):
            padron.write({'state': 'close'})

