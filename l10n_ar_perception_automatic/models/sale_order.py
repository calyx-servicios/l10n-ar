from odoo import models, api, fields, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def calculate_perceptions(self):
        """
        Calcula percepciones según padrón ARBA en órdenes de venta.
        """
        self.ensure_one()
        
        if not self.date_order:
            raise UserError(_('Debe establecer una fecha de pedido.'))
        
        if not self.order_line:
            raise UserError(_('La orden de venta debe tener líneas.'))
        
        # Buscar el padrón desde account.import.padron.ret.perc
        order_date = fields.Date.to_date(self.date_order)
        padron = self.env['account.import.padron.ret.perc'].search([
            ('type', '=', 'arba'),
            ('default_date_from', '<=', order_date),
            ('default_date_to', '>=', order_date),
        ], limit=1)
        
        if not padron:
            message = _('No se encontró padrón ARBA configurado para la fecha %s.') % order_date
            self.message_post(body=message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Padrón ARBA'),
                    'message': message,
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        padron_type = None
        if padron.padron_type_id:
            padron_type = padron.padron_type_id.filtered(
                lambda x: x.company_id.id == self.company_id.id and x.account_tax_perception_id
            )
        
        if not padron_type:
            message = _('No hay tipo de padrón de percepción configurado para esta compañía.')
            self.message_post(body=message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Configuración de Padrón'),
                    'message': message,
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        if not padron_type.account_tax_perception_id:
            message = _('El tipo de padrón "%s" no tiene un impuesto de percepción configurado.') % padron_type.name
            self.message_post(body=message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Impuesto de Percepción'),
                    'message': message,
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        perception_percentage = None
        
        arba_line = self._find_arba_alicuot_perception(order_date)
        
        if arba_line:
            if arba_line.alicuota_percepcion is not None:
                perception_percentage = arba_line.alicuota_percepcion
            elif arba_line.padron_line_id and arba_line.padron_line_id.default_percentage_perception:
                perception_percentage = arba_line.padron_line_id.default_percentage_perception
        
        if perception_percentage is None:
            if padron.default_percentage_perception:
                perception_percentage = padron.default_percentage_perception
            else:
                message = _('No se encontró alícuota de percepción para el cliente "%s" en el padrón ARBA para la fecha %s y no hay porcentaje por defecto configurado.') % (
                    self.partner_id.name, 
                    order_date
                )
                self.message_post(body=message)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sin Percepción ARBA'),
                        'message': message,
                        'type': 'warning',
                        'sticky': True,
                    }
                }

        order_lines = self.order_line.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )
 
        if not order_lines:
            message = _('No hay líneas de productos para calcular la percepción.')
            self.message_post(body=message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Líneas de Productos'),
                    'message': message,
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        total_order_untaxed = sum(line.price_subtotal for line in order_lines)        
        total_alicuot = total_order_untaxed * perception_percentage / 100
        
        total_to_discount = self._total_amount_perception(
            padron_type.minimum_base_perception, 
            perception_percentage, 
            padron_type.minimum_calcule_perception
        )
        
        display_msg = False
        if total_to_discount >= total_alicuot:
            display_msg = _(
                'El mínimo base/calculado de percepción {} es mayor o igual que el monto sin impuestos '
                'en la orden, por lo que no se aplica percepción.'
            ).format(padron_type.minimum_base_perception)
        else:
            if total_to_discount > 0:
                display_msg = _(
                    'El mínimo base/calculado de percepción {} es mayor que el monto sin impuestos '
                    'en algunas líneas, por lo que se aplica el siguiente descuento {} a la '
                    'percepción sobre el total en esta orden.'
                ).format(padron_type.minimum_base_perception, total_to_discount)
            
            amount_perception = total_alicuot - total_to_discount
            if amount_perception > 0:
                # Crear línea de percepción en la orden
                self._create_arba_perception_line(
                    padron_type.account_tax_perception_id,
                    amount_perception,
                    total_order_untaxed,
                    order_date
                )
        
        if display_msg:
            self.message_post(body=display_msg)
        
        amount_perception_final = total_alicuot - total_to_discount if total_alicuot > total_to_discount else 0
        success_message = _('Percepciones calculadas correctamente.\n') + \
                         _('Porcentaje aplicado: %s%%\n') % perception_percentage + \
                         _('Base imponible: %s\n') % formatLang(self.env, total_order_untaxed, currency_obj=self.currency_id) + \
                         _('Monto de percepción: %s') % formatLang(self.env, amount_perception_final, currency_obj=self.currency_id)
        
        self.message_post(body=success_message)
        
        return False
    
    def _find_arba_alicuot_perception(self, order_date):
        """Busca la alícuota de percepción del partner en el padrón ARBA."""
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('to_date', '>=', order_date),
            ('from_date', '<=', order_date),
            ('company_id', '=', self.company_id.id),
            ('alicuota_percepcion', '>', 0),  # Solo buscar si tiene alícuota de percepción
        ]
        return self.env['res.partner.arba_alicuot'].search(domain, limit=1)
    
    def _total_amount_perception(self, base_minimum_perception, percent_perception_arba, minimum_calcule_perception):
        total_to_discount = 0
        for line in self.order_line:
            if line.display_type not in ('line_section', 'line_note'):
                perception_applied = (
                    line.price_subtotal * percent_perception_arba / 100
                )
                if base_minimum_perception and base_minimum_perception > line.price_subtotal:
                    total_to_discount += perception_applied
                else:
                    if minimum_calcule_perception and minimum_calcule_perception > perception_applied:
                        total_to_discount += perception_applied
        return total_to_discount
    
    def _create_arba_perception_line(self, tax, amount_perception, base_perception, order_date):
        self.ensure_one()
        
        if not tax:
            message = _('No se pudo agregar el impuesto de percepción porque el impuesto es inválido.')
            self.message_post(body=message)
            raise UserError(message)
        
        if tax.type_tax_use != 'sale':
            message = _('El impuesto "%s" no es de tipo venta. Debe ser un impuesto de venta para aplicarse en órdenes de venta.') % tax.name
            self.message_post(body=message)
            raise UserError(message)
        
        perception_percentage = (amount_perception / base_perception * 100) if base_perception > 0 else 0
                
        lines_updated = 0
        order_lines = self.order_line.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )
        
        for line in order_lines:
            if tax.id not in line.tax_id.ids:
                line.write({
                    'tax_id': [(4, tax.id)]
                })
                lines_updated += 1
        
        if tax.amount_type != 'partner_tax':
            tax.write({'amount_type': 'partner_tax'})
        order_with_context = self.with_context(
            invoice_date=order_date,
            partner_id=self.partner_id.id if self.partner_id else None,
            order_id=self.id
        )
        
        order_lines_with_tax = order_with_context.order_line.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note') and tax.id in l.tax_id.ids
        )
        
        for line in order_lines_with_tax:
            line_with_context = line.with_context(
                invoice_date=order_date,
                partner_id=self.partner_id.id if self.partner_id else None,
                order_id=self.id
            )
            line_with_context.invalidate_recordset(['price_subtotal', 'price_tax', 'price_total'])
            _dummy_subtotal = line_with_context.price_subtotal
            _dummy_tax = line_with_context.price_tax
            _dummy_total = line_with_context.price_total
        
        order_with_context.invalidate_recordset(['amount_untaxed', 'amount_tax', 'amount_total'])
        _dummy_untaxed = order_with_context.amount_untaxed
        _dummy_tax = order_with_context.amount_tax
        _dummy_total = order_with_context.amount_total
        
        if lines_updated > 0:
            message = _('Se aplicó percepción "%s" (%s%%) a %d líneas de producto. Monto total: %s') % (
                tax.name,
                perception_percentage,
                lines_updated,
                formatLang(self.env, amount_perception, currency_obj=self.currency_id)
            )
        else:
            message = _('La percepción "%s" (%s%%) ya estaba aplicada a las líneas de producto.') % (
                tax.name,
                perception_percentage
            )


