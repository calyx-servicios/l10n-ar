from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date


class ExchangeDifferenceWizard(models.TransientModel):
    _inherit = "account.exchange.difference.wizard"

    date = fields.Date(
        help="If set, the entries and the debit/credit notes of every partner use "
        "this date instead of the partner's original date.",
    )
    country_code = fields.Char(related="company_id.country_code")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        company = self.env["res.company"].browse(values.get("company_id"))
        if company.country_id.code != "AR":
            return values
        move_lines = self._get_exchange_lines_to_process()
        if move_lines and values.get("line_ids"):
            # A note can't be dated before any of the differences it includes,
            # so each partner uses its latest exchange entry
            original_dates = {
                partner_id: max(lines.move_id.mapped("date"))
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
                        "original_date": original_dates.get(line_value.get("partner_id")),
                    },
                )
                for command, record_id, line_value in values["line_ids"]
            ]
        return values

    @api.model
    def _get_exchange_lines_to_process(self):
        """Same lines account_exchange_difference_invoice uses: entries already
        processed are skipped."""
        move_line_ids = self.env.context.get("move_line_ids") or []
        if not move_line_ids:
            return self.env["account.move.line"]
        return self.env["account.move.line"].search(
            [
                ("id", "in", move_line_ids),
                ("move_id.exchange_reversal_id", "=", False),
                ("move_id.exchange_reversed_move_ids", "=", False),
            ]
        )

    def action_create_debit_credit_notes(self):
        if self.company_id.country_id.code != "AR":
            return super().action_create_debit_credit_notes()
        # account_exchange_difference_invoice builds the notes from the raw ids
        # in the context, so an entry already processed would be billed again
        self = self.with_context(move_line_ids=self._get_exchange_lines_to_process().ids)
        self.line_ids._check_lock_dates(self.journal_id)
        return super(ExchangeDifferenceWizard, self).action_create_debit_credit_notes()


class ExchangeDifferenceWizardLine(models.TransientModel):
    _inherit = "account.exchange.difference.line.wizard"

    original_date = fields.Date(readonly=True)

    def _is_ar_company(self):
        return self.wizard_id.company_id.country_id.code == "AR"

    def _get_effective_date(self):
        self.ensure_one()
        return (
            self.wizard_id.date
            or self.original_date
            or fields.Date.context_today(self)
        )

    def _check_lock_dates(self, journal):
        """Odoo moves the accounting date out of a locked period, but AR notes
        need it to match the invoice date, so they couldn't be posted."""
        company = self.wizard_id.company_id
        locked = self.filtered(
            lambda line: line.balance
            and company._get_violated_lock_dates(
                line._get_effective_date(), True, journal
            )
        )
        if locked:
            raise UserError(
                self.env._(
                    "These partners would get a date in a locked period: "
                    "%(partners)s.\nSet a later date in the wizard.",
                    partners=", ".join(
                        f"{line.partner_id.display_name} "
                        f"({format_date(self.env, line._get_effective_date())})"
                        for line in locked
                    ),
                )
            )

    def _prepare_reversal(self, journal, rec_account):
        values = super()._prepare_reversal(journal, rec_account)
        if self._is_ar_company():
            values["date"] = self._get_effective_date()
        return values

    def _prepare_debit_credit_note(self, exch_moves, journal, rec_account):
        values = super()._prepare_debit_credit_note(exch_moves, journal, rec_account)
        if self._is_ar_company():
            effective_date = self._get_effective_date()
            values.update(
                {
                    "date": effective_date,
                    "invoice_date": effective_date,
                }
            )
        return values
