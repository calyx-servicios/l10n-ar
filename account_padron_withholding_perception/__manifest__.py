# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Import Padron Withholding and Perception",
    "summary": """
        Adds to the partner the possibility of importing Patterns
        of Withholdings and Perceptions.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["PerezGabriela", "leandro090685"],
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Account",
    "version": "15.0.4.9.4",
    "installable": True,
    "application": False,
    "depends": [
        'l10n_ar_ux',
        'account_payment_group',
        'account_withholding_automatic',
        'l10n_ar_account_withholding',
    ],
    "data": [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/account_import_padron_ret_perc_view.xml',
        'views/account_move_view.xml',
        'views/account_padron_retention_perception_type_view.xml',
        'views/res_partner_view.xml',
    ],
}
