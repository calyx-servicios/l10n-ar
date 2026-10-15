from odoo import _, api, fields, models


class L10nLatamCheckbook(models.Model):
    _name = "l10n_latam.checkbook"
    _description = "Checkbook"
    _rec_name = "range_to"

    sequence_id = fields.Many2one(
        "ir.sequence",
        "Sequence",
        copy=False,
        help="Checks numbering sequence.",
    )
    next_number = fields.Integer(
        "Next Number",
        related="sequence_id.number_next_actual",
        related_sudo=True,
        readonly=False,
    )
    type = fields.Selection(
        [("deferred", "Deferred"), ("currents", "Currents"), ("electronic", "Electronic")],
        string="Check type",
        required=True,
        default="deferred",
    )
    journal_id = fields.Many2one(
        "account.journal",
        "Journal",
        readonly=True,
        required=True,
        ondelete="cascade",
    )
    range_from = fields.Integer("From Number")
    range_to = fields.Integer("To Number")
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if not rec.sequence_id:
                rec._create_sequence(vals.get("next_number", 0))
        return records

    def _create_sequence(self, next_number):
        for rec in self:
            rec.sequence_id = rec.env["ir.sequence"].sudo().create({
                "name": "%s - %s" % (rec.journal_id.name, rec.display_name),
                "implementation": "no_gap",
                "padding": 8,
                "number_increment": 1,
                "code": "l10n_latam.checkbook",
                "number_next_actual": next_number,
                "company_id": rec.journal_id.company_id.id,
            })

    @api.depends("type", "range_to")
    def _compute_display_name(self):
        for rec in self:
            name = {
                "deferred": _("Deferred Checks"),
                "currents": _("Currents Checks"),
                "electronic": _("Electronic Checks"),
            }.get(rec.type, "")
            if rec.range_to:
                name += _(" up to %s", rec.range_to)
            rec.display_name = name

    def _get_next_available_number(self, payment_method_line, used_numbers):
        self.ensure_one()
        sequence = self.sudo().sequence_id
        used_numbers = set(used_numbers) | set(self.env["l10n_latam.check"].search([
            ("payment_method_line_id", "=", payment_method_line.id),
            ("outstanding_line_id", "!=", False),
            ("name", ">=", sequence.get_next_char(self.next_number)),
        ]).mapped("name"))
        number = self.next_number
        while sequence.get_next_char(number) in used_numbers:
            number += 1
        return sequence.get_next_char(number)
