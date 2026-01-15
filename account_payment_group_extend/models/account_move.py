from odoo import models, fields, api
from datetime import datetime

class AccountMove(models.Model):
    _inherit = 'account.move'

    uses_account_payment_group = fields.Boolean(
        related="company_id.uses_account_payment_group"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "journal_id" in vals:
                journal = self.env["account.journal"].browse(vals["journal_id"])
                code = journal.code
                sequence_id = journal.sequence
                sequence = self.env["ir.sequence"].browse(sequence_id).sudo()
                if not sequence.exists():
                    continue
                sequence.use_date_range = False
                if not sequence.use_date_range:
                    date = False
                    if "invoice_date" in vals:
                        date = vals["invoice_date"]
                    elif "date" in vals:
                        date = vals["date"]
                    if not date:
                        continue
                    sequence.prefix = code
                    if "name" not in vals:
                        vals["name"] = sequence.with_context(ir_sequence_date=date).next_by_id(sequence_id)
                    else:
                        try:
                            if vals["name"]  not in vals["name"]:
                                vals["name"] = sequence.with_context(ir_sequence_date=date).next_by_id(sequence_id)
                        except Exception:
                            pass
                    move = True
                    name = vals["name"]
                    try:
                        while move:
                            move = self.search([("name", "=", name), ("journal_id", "=", vals["journal_id"])])
                            if move:
                                name = sequence.with_context(ir_sequence_date=date).next_by_id(sequence_id)
                        vals["name"] = name
                    except Exception:
                        vals["name"] = name
        return super().create(vals_list)

    def _get_starting_sequence(self):
        # EXTENDS account sequence.mixin
        self.ensure_one()
        if not self.date:
            env = self.env
            model = env.context.get("params", {}).get('model', False)
            rec_id = env.context.get("params", {}).get('id', False)
            apg = "account.payment.group"
            if model and model == apg and rec_id:
                payment_group = env[apg].browse(rec_id)
                self.date = payment_group.payment_date
            else:
                self.date = datetime.now()
        if self.journal_id.type in ['sale', 'bank', 'cash']:
            starting_sequence = "%s/%04d/00000" % (self.journal_id.code, self.date.year)
        else:
            starting_sequence = "%s/%04d/%02d/0000" % (self.journal_id.code, self.date.year, self.date.month)
        if self.journal_id.refund_sequence and self.move_type in ('out_refund', 'in_refund'):
            starting_sequence = "R" + starting_sequence
        if self.journal_id.payment_sequence and self.payment_id:
            starting_sequence = "P" + starting_sequence
        return starting_sequence

    def _get_sequence_date_range(self, reset):
        if not self.date:
            env = self.env
            model = env.context.get("params", {}).get('model', False)
            rec_id = env.context.get("params", {}).get('id', False)
            apg = "account.payment.group"
            if model and model == apg and rec_id:
                payment_group = env[apg].browse(rec_id)
                self.date = payment_group.payment_date
            else:
                self.date = datetime.now()
        if reset == 'year_range':
            company = self.company_id
            return date_utils.get_fiscal_year(self.date, day=company.fiscalyear_last_day, month=int(company.fiscalyear_last_month))
        return super()._get_sequence_date_range(reset)
