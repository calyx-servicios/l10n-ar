import base64

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open


@tagged("post_install", "-at_install")
class TestCertificateCuitCheck(TransactionCase):
    """The certificate/company CUIT check of l10n_ar_edi_ux only applies in production."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ar_country = cls.env.ref("base.ar")
        key = cls.env["certificate.key"].create(
            {
                "name": "Test RSA Key",
                "content": base64.b64encode(file_open("l10n_ar_edi/tests/private_key.pem", "rb").read()),
            }
        )
        # test_cert1.crt has serialNumber = "CUIT 20313932975"
        certificate = cls.env["certificate.certificate"].create(
            {
                "name": "Test Cert (CUIT 20313932975)",
                "content": base64.b64encode(file_open("l10n_ar_edi/tests/test_cert1.crt", "rb").read()),
                "private_key_id": key.id,
            }
        )
        cls.company = cls.env["res.company"].create(
            {
                "name": "Company CUIT Mismatches Cert",
                "currency_id": cls.env.ref("base.ARS").id,
                "country_id": ar_country.id,
            }
        )
        cls.company.partner_id.write(
            {
                "l10n_latam_identification_type_id": cls.env.ref("l10n_ar.it_cuit").id,
                "vat": "30500439617",
                "l10n_ar_afip_responsibility_type_id": cls.env.ref("l10n_ar.res_IVARI").id,
                "country_id": ar_country.id,
            }
        )
        cls.company.write({"l10n_ar_afip_ws_crt_id": certificate.id})

    def test_mismatch_allowed_in_testing(self):
        self.company.l10n_ar_afip_ws_environment = "testing"
        self.company._check_match_between_certificate_and_company()

    def test_mismatch_raises_in_production(self):
        self.company.l10n_ar_afip_ws_environment = "production"
        with self.assertRaisesRegex(UserError, "30500439617"):
            self.company._check_match_between_certificate_and_company()
