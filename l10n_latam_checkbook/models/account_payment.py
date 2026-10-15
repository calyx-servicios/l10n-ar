from odoo import _, api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_latam_use_checkbooks = fields.Boolean(related="journal_id.l10n_latam_use_checkbooks")
    l10n_latam_checkbook_id = fields.Many2one(
        "l10n_latam.checkbook",
        "Checkbook",
        store=True,
        compute="_compute_l10n_latam_checkbook",
        readonly=False,
    )

    @api.depends("payment_method_line_id.code", "journal_id.l10n_latam_use_checkbooks")
    def _compute_l10n_latam_checkbook(self):
        with_checkbooks = self.filtered(
            lambda x: x.payment_method_line_id.code == "own_checks"
            and x.journal_id.l10n_latam_use_checkbooks
        )
        (self - with_checkbooks).l10n_latam_checkbook_id = False
        for rec in with_checkbooks:
            checkbooks = rec.journal_id.l10n_latam_checkbook_ids
            if rec.l10n_latam_checkbook_id and rec.l10n_latam_checkbook_id in checkbooks:
                continue
            rec.l10n_latam_checkbook_id = checkbooks and checkbooks[0] or False

    @api.depends("l10n_latam_checkbook_id")
    def _compute_l10n_latam_check_warning_msg(self):
        return super()._compute_l10n_latam_check_warning_msg()

    def _get_blocking_l10n_latam_warning_msg(self):
        msgs = super()._get_blocking_l10n_latam_warning_msg()
        for rec in self.filtered(lambda x: x.state == "draft" and x.l10n_latam_checkbook_id):
            names = [name for name in rec.l10n_latam_new_check_ids.mapped("name") if name]
            used_numbers = {name for name in names if names.count(name) > 1}
            used_numbers |= set(self.env["l10n_latam.check"].search([
                ("payment_method_line_id", "=", rec.payment_method_line_id.id),
                ("outstanding_line_id", "!=", False),
                ("name", "in", names),
            ]).mapped("name"))
            for number in sorted(used_numbers):
                msgs.append(_("The check number %s is already used.", number))
            range_to = rec.l10n_latam_checkbook_id.range_to
            for number in names:
                if range_to and number.isdecimal() and int(number) > range_to:
                    msgs.append(_(
                        "The check number %(number)s is bigger than max number for checkbook"
                        " %(checkbook)s.",
                        number=number,
                        checkbook=rec.l10n_latam_checkbook_id.display_name,
                    ))
        return msgs

    def action_post(self):
        super().action_post()
        for rec in self.filtered("l10n_latam_checkbook_id"):
            numbers = [
                int(name) for name in rec.l10n_latam_new_check_ids.mapped("name")
                if name and name.isdecimal()
            ]
            checkbook = rec.l10n_latam_checkbook_id
            if numbers and max(numbers) + 1 > checkbook.next_number:
                checkbook.sequence_id.sudo().write({"number_next_actual": max(numbers) + 1})
