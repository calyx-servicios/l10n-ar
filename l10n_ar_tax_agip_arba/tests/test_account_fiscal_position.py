# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class TestPadronAlicuotaParsing(TransactionCase):
    def test_parse_alicuota_handles_comma_and_dot_formats(self):
        model = self.env["account.fiscal.position.l10n_ar_tax"]

        self.assertEqual(model._padron_parse_alicuota("2.5"), 2.5)
        self.assertEqual(model._padron_parse_alicuota("3,0"), 3.0)
        self.assertEqual(model._padron_parse_alicuota("1.234,56"), 1234.56)