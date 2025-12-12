from odoo import models, fields, api


class AccountTax(models.Model):
    _inherit = 'account.tax'
    
    def _compute_amount(self, base_amount, price_unit, quantity=1.0, product=None, partner=None, fixed_multiplicator=1):
        # Si el tax tiene amount_type == 'partner_tax', usar la alícuota del partner
        if self.amount_type == 'partner_tax' and self.type_tax_use == 'sale':
            
            date = self._context.get('invoice_date', fields.Date.context_today(self))
            
            if not partner:
                if self._context.get('partner_id'):
                    partner = self.env['res.partner'].browse(self._context.get('partner_id'))
                elif self._context.get('default_partner_id'):
                    partner = self.env['res.partner'].browse(self._context.get('default_partner_id'))
                elif self._context.get('move_id'):
                    move = self.env['account.move'].browse(self._context.get('move_id'))
                    partner = move.partner_id if move else None
            
            partner = partner and partner.sudo()
            
            alicuota = self.sudo().get_partner_alicuota_percepcion(partner, date)
            result = base_amount * alicuota
            return result
        
        return super(AccountTax, self)._compute_amount(
            base_amount, price_unit, quantity, product, partner, fixed_multiplicator
        )
    
    def _eval_tax_amount_price_excluded(self, batch, raw_base, evaluation_context):
        if self.amount_type == 'partner_tax' and self.type_tax_use == 'sale':
            date = evaluation_context.get('invoice_date') or self._context.get('invoice_date') or fields.Date.context_today(self)

            partner = None
            if evaluation_context.get('partner_id'):
                partner = self.env['res.partner'].browse(evaluation_context['partner_id'])
            elif self._context.get('partner_id'):
                partner = self.env['res.partner'].browse(self._context.get('partner_id'))
            elif self._context.get('default_partner_id'):
                partner = self.env['res.partner'].browse(self._context.get('default_partner_id'))
            elif self._context.get('move_id'):
                move = self.env['account.move'].browse(self._context.get('move_id'))
                partner = move.partner_id if move else None
            elif self._context.get('order_id'):
                order = self.env['sale.order'].browse(self._context.get('order_id'))
                partner = order.partner_id if order else None
            
            partner = partner and partner.sudo()
            alicuota = self.sudo().get_partner_alicuota_percepcion(partner, date)
            
            result = raw_base * alicuota
            return result
        
        return super(AccountTax, self)._eval_tax_amount_price_excluded(batch, raw_base, evaluation_context)
    
    def _eval_tax_amount_price_included(self, batch, raw_base, evaluation_context):
        """ Sobrescribe para manejar amount_type == 'partner_tax' en Odoo 18 """
        if self.amount_type == 'partner_tax' and self.type_tax_use == 'sale':
            
            date = self._context.get('invoice_date', fields.Date.context_today(self))
            
            partner = None
            if evaluation_context.get('partner_id'):
                partner = self.env['res.partner'].browse(evaluation_context['partner_id'])
            elif self._context.get('partner_id'):
                partner = self.env['res.partner'].browse(self._context.get('partner_id'))
            elif self._context.get('default_partner_id'):
                partner = self.env['res.partner'].browse(self._context.get('default_partner_id'))
            elif self._context.get('move_id'):
                move = self.env['account.move'].browse(self._context.get('move_id'))
                partner = move.partner_id if move else None
            elif self._context.get('order_id'):
                order = self.env['sale.order'].browse(self._context.get('order_id'))
                partner = order.partner_id if order else None
            
            partner = partner and partner.sudo()
            
            alicuota = self.sudo().get_partner_alicuota_percepcion(partner, date)
            
            total_percentage = alicuota * 100.0  # Convertir fracción a porcentaje
            to_price_excluded_factor = 1 / (1 + total_percentage) if total_percentage != -1 else 0.0
            result = raw_base * to_price_excluded_factor * total_percentage / 100.0
            
            return result
        
        return super(AccountTax, self)._eval_tax_amount_price_included(batch, raw_base, evaluation_context)
    
    def get_partner_alicuota_percepcion(self, partner, date):
        if not partner or not date:
            return 0.0
        
        if self.type_tax_use != 'sale':
            return 0.0
        
        # Buscar alícuota de percepción de ARBA para la fecha
        arba_line = partner.arba_alicuot_ids.filtered(
            lambda x: x.to_date >= date
            and x.from_date <= date
            and x.company_id.id == self.company_id.id
            and x.alicuota_percepcion > 0
        )
        
        if arba_line:
            return arba_line[0].alicuota_percepcion / 100.0
        
        padron = self.env['account.import.padron.ret.perc'].search([
            ('type', '=', 'arba'),
            ('default_date_from', '<=', date),
            ('default_date_to', '>=', date),
        ], limit=1)
        
        if padron and padron.default_percentage_perception:
            return padron.default_percentage_perception / 100.0
        
        return 0.0
    
    def _get_tax_details(self, *args, **kwargs):
        """ Hereda _get_tax_details para agregar partner_id al evaluation_context """
        result = super(AccountTax, self)._get_tax_details(*args, **kwargs)
        
        if 'evaluation_context' in result:
            if not result['evaluation_context'].get('partner_id'):
                if self._context.get('partner_id'):
                    result['evaluation_context']['partner_id'] = self._context.get('partner_id')
                elif self._context.get('default_partner_id'):
                    result['evaluation_context']['partner_id'] = self._context.get('default_partner_id')
                elif self._context.get('move_id'):
                    move = self.env['account.move'].browse(self._context.get('move_id'))
                    if move and move.partner_id:
                        result['evaluation_context']['partner_id'] = move.partner_id.id
                elif self._context.get('order_id'):
                    order = self.env['sale.order'].browse(self._context.get('order_id'))
                    if order and order.partner_id:
                        result['evaluation_context']['partner_id'] = order.partner_id.id
                
                if self._context.get('invoice_date'):
                    result['evaluation_context']['invoice_date'] = self._context.get('invoice_date')
                elif self._context.get('order_id'):
                    order = self.env['sale.order'].browse(self._context.get('order_id'))
                    if order and order.date_order:
                        from odoo import fields
                        order_date = fields.Date.to_date(order.date_order)
                        result['evaluation_context']['invoice_date'] = order_date
        
        return result
    
    def _add_tax_details_in_base_line(self, base_line, company, rounding_method=None):
        """ Hereda _add_tax_details_in_base_line para pasar partner_id e invoice_date al contexto """
        context_updates = {}
        if base_line.get('partner_id'):
            partner = base_line['partner_id']
            context_updates['partner_id'] = partner.id if hasattr(partner, 'id') else partner
        
        if base_line.get('record'):
            record = base_line['record']
            if hasattr(record, 'move_id') and record.move_id:
                if record.move_id.invoice_date:
                    context_updates['invoice_date'] = record.move_id.invoice_date
                if record.move_id.partner_id and not context_updates.get('partner_id'):
                    context_updates['partner_id'] = record.move_id.partner_id.id
            elif hasattr(record, 'order_id') and record.order_id:
                if record.order_id.date_order:
                    from odoo import fields
                    order_date = fields.Date.to_date(record.order_id.date_order)
                    context_updates['invoice_date'] = order_date
                if record.order_id.partner_id and not context_updates.get('partner_id'):
                    context_updates['partner_id'] = record.order_id.partner_id.id
            elif hasattr(record, 'invoice_date') and record.invoice_date:
                context_updates['invoice_date'] = record.invoice_date
            elif hasattr(record, 'date') and record.date:
                context_updates['invoice_date'] = record.date
        
        if context_updates:
            self = self.with_context(**context_updates)
            if base_line.get('tax_ids'):
                base_line['tax_ids'] = base_line['tax_ids'].with_context(**context_updates)
        
        return super(AccountTax, self)._add_tax_details_in_base_line(base_line, company, rounding_method=rounding_method)
