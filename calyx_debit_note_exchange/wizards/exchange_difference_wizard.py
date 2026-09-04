from odoo import api, fields, models


class ExchangeDifferenceWizard(models.TransientModel):
    _inherit = "account.exchange.difference.wizard"

    date = fields.Date(string="Date")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        move_line_ids = self.env.context.get("move_line_ids", [])
        move_lines = self.env["account.move.line"].browse(move_line_ids)
        if move_lines:
            if "date" in fields_list and not values.get("date"):
                values["date"] = (
                    move_lines[0].move_id.date
                    or fields.Date.context_today(self)
                )

            line_values = values.get("line_ids", [])
            grouped_dates = {
                partner_id: lines[0].move_id.date
                for partner_id, lines in move_lines.grouped(
                    lambda line: line.partner_id.id
                ).items()
            }
            values["line_ids"] = [
                (
                    command,
                    record_id,
                    {
                        **line_value,
                        "original_date": grouped_dates.get(
                            line_value.get("partner_id")
                        ),
                    },
                )
                for command, record_id, line_value in line_values
            ]
        return values


class ExchangeDifferenceWizardLine(models.TransientModel):
    _inherit = "account.exchange.difference.line.wizard"

    original_date = fields.Date(string="Original Date", readonly=True)

    def _get_effective_date(self):
        self.ensure_one()
        return (
            self.wizard_id.date
            or self.original_date
            or fields.Date.context_today(self)
        )

    def _prepare_reversal(self, journal, rec_account):
        values = super()._prepare_reversal(journal, rec_account)
        values["date"] = self._get_effective_date()
        return values

    def _prepare_debit_credit_note(self, exch_moves, journal, rec_account):
        values = super()._prepare_debit_credit_note(exch_moves, journal, rec_account)
        effective_date = self._get_effective_date()
        values.update(
            {
                "date": effective_date,
                "invoice_date": effective_date,
            }
        )
        return values