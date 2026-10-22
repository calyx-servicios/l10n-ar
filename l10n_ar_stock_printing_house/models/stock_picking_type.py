##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models

from odoo.addons.l10n_ar_stock_ux.models.stock_picking_type import (
    StockPickingType as L10nArStockUxPickingType,
)


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    # En v18 la imprenta era un dato del talonario (stock.book). En v19 el talonario
    # es la secuencia de remitos que comparten varios tipos de operación, así que la
    # sincronizamos entre ellos igual que el CAI.
    _L10N_AR_SHARED_SEQUENCE_FIELDS = (
        *L10nArStockUxPickingType._L10N_AR_SHARED_SEQUENCE_FIELDS,
        "printing_house",
    )

    printing_house = fields.Char(
        string="Imprenta",
        help="Pie de imprenta que se imprime en el remito, debajo del código de barras.",
    )
