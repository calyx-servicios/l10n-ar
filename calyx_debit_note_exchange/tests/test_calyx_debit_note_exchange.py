from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ar.tests.common import TestArCommon


@tagged("post_install", "-at_install")
class TestCalyxDebitNoteExchange(TestArCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env.user)
        cls.old_date = cls.today - timedelta(days=30)
        cls.recent_date = cls.today - timedelta(days=3)
        cls.exchange_product = cls.env["product.product"].create(
            {
                "name": "Exchange rate difference",
                "type": "service",
                "sale_ok": False,
                "purchase_ok": False,
                "taxes_id": False,
            }
        )
        cls.company_ri.exchange_difference_product = cls.exchange_product
        journal_vals = {
            "type": "sale",
            "company_id": cls.company_ri.id,
            "l10n_latam_use_documents": True,
            "l10n_ar_afip_pos_partner_id": cls.partner_ri.id,
        }
        cls.preprinted_journal = cls.env["account.journal"].create(
            {
                **journal_vals,
                "name": "Preprinted sales",
                "code": "PREP",
                "l10n_ar_afip_pos_number": 31,
                "l10n_ar_afip_pos_system": "II_IM",
            }
        )
        cls.electronic_journal = cls.env["account.journal"].create(
            {
                **journal_vals,
                "name": "Electronic sales",
                "code": "ELEC",
                "l10n_ar_afip_pos_number": 32,
                "l10n_ar_afip_pos_system": "RLI_RLM",
            }
        )
        cls.partner_a = cls.res_partner_adhoc
        cls.partner_b = cls.res_partner_gritti_mono

    @classmethod
    def _create_exchange_entry(cls, partner, amount, date, company=None):
        """Exchange difference entry as Odoo creates it when reconciling a
        payment in foreign currency, with a fixed date."""
        company = company or cls.company_ri
        receivable = partner.with_company(company).property_account_receivable_id
        exchange_account = (
            company.income_currency_exchange_account_id
            if amount > 0
            else company.expense_currency_exchange_account_id
        )
        move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": company.currency_exchange_journal_id.id,
                "date": date,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": receivable.id,
                            "partner_id": partner.id,
                            "debit": max(amount, 0.0),
                            "credit": max(-amount, 0.0),
                        }
                    ),
                    Command.create(
                        {
                            "account_id": exchange_account.id,
                            "partner_id": partner.id,
                            "debit": max(-amount, 0.0),
                            "credit": max(amount, 0.0),
                        }
                    ),
                ],
            }
        )
        move.action_post()
        return move.line_ids.filtered(lambda line: line.account_id == receivable)

    def _wizard(self, lines, journal=None, **vals):
        return (
            self.env["account.exchange.difference.wizard"]
            .with_context(move_line_ids=lines.ids)
            .create({"journal_id": (journal or self.preprinted_journal).id, **vals})
        )

    def _note(self, line):
        """Debit/credit note created for an exchange entry."""
        return line.move_id.exchange_reversal_id.exchange_reversal_id

    def test_partner_date_is_its_latest_entry(self):
        old = self._create_exchange_entry(self.partner_a, 100.0, self.old_date)
        recent = self._create_exchange_entry(self.partner_a, 50.0, self.recent_date)
        for lines in (old + recent, recent + old):
            wizard = self._wizard(self.env["account.move.line"].browse(lines.ids))
            self.assertFalse(wizard.date)
            self.assertEqual(wizard.line_ids.original_date, self.recent_date)

    def test_each_partner_keeps_its_date(self):
        line_a = self._create_exchange_entry(self.partner_a, 100.0, self.old_date)
        line_b = self._create_exchange_entry(self.partner_b, 50.0, self.recent_date)
        self._wizard(line_a + line_b).action_create_debit_credit_notes()
        for line, date in ((line_a, self.old_date), (line_b, self.recent_date)):
            self.assertEqual(line.move_id.exchange_reversal_id.date, date)
            self.assertEqual(self._note(line).invoice_date, date)
            self.assertEqual(self._note(line).date, date)

    def test_wizard_date_overrides_partner_dates(self):
        line_a = self._create_exchange_entry(self.partner_a, 100.0, self.old_date)
        line_b = self._create_exchange_entry(self.partner_b, 50.0, self.recent_date)
        self._wizard(line_a + line_b, date=self.today).action_create_debit_credit_notes()
        for line in line_a + line_b:
            self.assertEqual(line.move_id.exchange_reversal_id.date, self.today)
            self.assertEqual(self._note(line).invoice_date, self.today)
            self.assertEqual(self._note(line).date, self.today)

    def test_old_dates_are_left_to_arca(self):
        line = self._create_exchange_entry(self.partner_a, 100.0, self.old_date)
        self._wizard(line, self.electronic_journal).action_create_debit_credit_notes()
        self.assertEqual(self._note(line).invoice_date, self.old_date)

    def test_locked_period_is_rejected(self):
        line = self._create_exchange_entry(self.partner_a, 100.0, self.old_date)
        self.company_ri.fiscalyear_lock_date = self.old_date
        with self.assertRaisesRegex(UserError, self.partner_a.name):
            self._wizard(line).action_create_debit_credit_notes()
        self.assertFalse(line.move_id.exchange_reversal_id)
        # A date written in the wizard must be after the lock date too
        with self.assertRaisesRegex(UserError, self.partner_a.name):
            self._wizard(line, date=self.old_date).action_create_debit_credit_notes()
        self._wizard(
            line, date=self.old_date + timedelta(days=1)
        ).action_create_debit_credit_notes()
        self.assertEqual(self._note(line).invoice_date, self.old_date + timedelta(days=1))

    def test_processed_entries_are_not_billed_again(self):
        processed = self._create_exchange_entry(self.partner_a, 300.0, self.recent_date)
        self._wizard(processed).action_create_debit_credit_notes()
        billed = self._note(processed)
        pending = self._create_exchange_entry(self.partner_a, 100.0, self.old_date)
        lines = self.env["account.move.line"].browse((processed + pending).ids)
        wizard = self._wizard(lines)
        self.assertEqual(wizard.line_ids.original_date, self.old_date)
        wizard.action_create_debit_credit_notes()
        note = self._note(pending)
        self.assertNotEqual(note, billed)
        self.assertEqual(note.invoice_date, self.old_date)
        self.assertAlmostEqual(note.amount_total, 100.0)
        self.assertEqual(processed.move_id.exchange_reversal_id.exchange_reversal_id, billed)

    def test_non_ar_company_keeps_upstream_behaviour(self):
        company = self.setup_other_company(name="Non AR company")["company"]
        company.country_id = self.env.ref("base.us")
        company.exchange_difference_product = self.exchange_product
        env = self.env(context={"allowed_company_ids": [company.id]})
        journal = env["account.journal"].create(
            {"name": "Sales", "code": "NOAR", "type": "sale", "company_id": company.id}
        )
        line = self._create_exchange_entry(
            self.partner_a, 100.0, self.old_date, company=company
        )
        wizard = (
            env["account.exchange.difference.wizard"]
            .with_context(move_line_ids=line.ids)
            .create({"journal_id": journal.id, "date": self.old_date})
        )
        self.assertFalse(wizard.line_ids.original_date)
        wizard.action_create_debit_credit_notes()
        self.assertEqual(line.move_id.exchange_reversal_id.date, self.today)
        self.assertFalse(self._note(line).invoice_date)

    def _create_exchange_note(self, move_type, env=None):
        return (env or self.env)["account.move"].create(
            {
                "move_type": move_type,
                "company_id": self.company_ri.id,
                "journal_id": self.preprinted_journal.id,
                "partner_id": self.partner_a.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.exchange_product.id,
                            "price_unit": 100.0,
                            "tax_ids": [Command.set(self.tax_21.ids)],
                        }
                    )
                ],
            }
        )

    def test_debit_notes_add_vat_credit_notes_include_it(self):
        self.assertAlmostEqual(self._create_exchange_note("out_invoice").amount_total, 121.0)
        self.assertAlmostEqual(self._create_exchange_note("out_refund").amount_total, 100.0)

    def test_exchange_product_read_from_move_company(self):
        other_company = self.setup_other_company(name="Other company")["company"]
        env = self.env(context={"allowed_company_ids": [other_company.id, self.company_ri.id]})
        self.assertEqual(env.company, other_company)
        refund = self._create_exchange_note("out_refund", env)
        # Credit notes for exchange differences have the VAT included
        self.assertAlmostEqual(refund.amount_total, 100.0)
