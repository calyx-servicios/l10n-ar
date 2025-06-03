from odoo import models, fields, api

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
