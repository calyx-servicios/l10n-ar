from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_price_total_and_subtotal(
            self, price_unit=None, quantity=None, discount=None, currency=None,
            product=None, partner=None, taxes=None, move_type=None):
        """
        Hereda _get_price_total_and_subtotal para pasar invoice_date y partner_id
        en el contexto para que el cálculo de impuestos use la alícuota correcta.
        """
        order = self.order_id
        if order:
            order_date = fields.Date.to_date(order.date_order) if order.date_order else fields.Date.context_today(self)
            context_dict = {
                'invoice_date': order_date,
                'order_id': order.id
            }
            if order.partner_id:
                context_dict['partner_id'] = order.partner_id.id
            self = self.with_context(**context_dict)
            _logger.info('SaleOrderLine._get_price_total_and_subtotal: Contexto actualizado con invoice_date=%s, partner_id=%s, order_id=%s',
                       context_dict.get('invoice_date'), context_dict.get('partner_id'), context_dict.get('order_id'))
        return super(SaleOrderLine, self)._get_price_total_and_subtotal(
            price_unit=price_unit, quantity=quantity, discount=discount, currency=currency,
            product=product, partner=partner, taxes=taxes, move_type=move_type)
    
    @api.depends('product_uom', 'product_uom_qty', 'price_unit', 'tax_id', 'discount')
    def _compute_price_subtotal(self):
        """
        Sobrescribe para asegurar que el contexto se pase correctamente
        cuando se calcula price_subtotal.
        """
        order = self.order_id
        if order:
            order_date = fields.Date.to_date(order.date_order) if order.date_order else fields.Date.context_today(self)
            context_dict = {
                'invoice_date': order_date,
                'order_id': order.id
            }
            if order.partner_id:
                context_dict['partner_id'] = order.partner_id.id
            self = self.with_context(**context_dict)
            _logger.info('SaleOrderLine._compute_price_subtotal: Contexto actualizado')
        return super(SaleOrderLine, self)._compute_price_subtotal()


