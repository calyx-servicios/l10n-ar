from odoo import models, api, fields, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class AccountMove(models.Model):
    _inherit = 'account.move'


    def calculate_perceptions(self):
        """
        Calcula percepciones según padrón ARBA en facturas de ventas.
        """
        self.ensure_one()
        
        if not self.invoice_date:
            raise UserError(_('Debe establecer una fecha de factura.'))
        
        if not self.invoice_line_ids:
            raise UserError(_('La factura debe tener líneas.'))
        
        # Buscar el padrón desde account.import.padron.ret.perc
        padron = self.env['account.import.padron.ret.perc'].search([
            ('type', '=', 'arba'),
            ('default_date_from', '<=', self.invoice_date),
            ('default_date_to', '>=', self.invoice_date),
        ], limit=1)
        
        if not padron:
            message = _('No se encontró padrón ARBA configurado para la fecha %s.') % self.invoice_date
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
        
        arba_line = self._find_arba_alicuot_perception()
        
        if arba_line:
            # Usa la alícuota del partner si está definida (puede ser 0)
            if arba_line.alicuota_percepcion is not None:
                perception_percentage = arba_line.alicuota_percepcion
            # Toma el default_percentage_perception del padrón
            elif arba_line.padron_line_id and arba_line.padron_line_id.default_percentage_perception:
                perception_percentage = arba_line.padron_line_id.default_percentage_perception
        
        if perception_percentage is None:
            if padron.default_percentage_perception:
                perception_percentage = padron.default_percentage_perception
            else:
                message = _('No se encontró alícuota de percepción para el cliente "%s" en el padrón ARBA para la fecha %s y no hay porcentaje por defecto configurado.') % (
                    self.partner_id.name, 
                    self.invoice_date
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

        invoice_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )
 
        if not invoice_lines:
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
        
        total_invoice_untaxed = sum(line.price_subtotal for line in invoice_lines)        
        total_alicuot = total_invoice_untaxed * perception_percentage / 100
        
        total_to_discount = self._total_amount_perception(
            padron_type.minimum_base_perception, 
            perception_percentage, 
            padron_type.minimum_calcule_perception
        )
        
        display_msg = False
        if total_to_discount >= total_alicuot:
            display_msg = _(
                'El mínimo base/calculado de percepción {} es mayor o igual que el monto sin impuestos '
                'en la factura, por lo que no se aplica percepción.'
            ).format(padron_type.minimum_base_perception)
        else:
            if total_to_discount > 0:
                display_msg = _(
                    'El mínimo base/calculado de percepción {} es mayor que el monto sin impuestos '
                    'en algunas líneas, por lo que se aplica el siguiente descuento {} a la '
                    'percepción sobre el total en esta factura.'
                ).format(padron_type.minimum_base_perception, total_to_discount)
            
            amount_perception = total_alicuot - total_to_discount
            if amount_perception > 0:
                self._create_arba_perception_line(
                    padron_type.account_tax_perception_id,
                    amount_perception,
                    total_invoice_untaxed
                )
        
        if display_msg:
            self.message_post(body=display_msg)
        
        amount_perception_final = total_alicuot - total_to_discount if total_alicuot > total_to_discount else 0
        success_message = _('Percepciones calculadas correctamente.\n') + \
                         _('Porcentaje aplicado: %s%%\n') % perception_percentage + \
                         _('Base imponible: %s\n') % formatLang(self.env, total_invoice_untaxed, currency_obj=self.currency_id) + \
                         _('Monto de percepción: %s') % formatLang(self.env, amount_perception_final, currency_obj=self.currency_id)
        
        self.message_post(body=success_message)
        
        return False
    
    def _find_arba_alicuot_perception(self):
        """Busca la alícuota de percepción del partner en el padrón ARBA."""
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('to_date', '>=', self.invoice_date),
            ('from_date', '<=', self.invoice_date),
            ('company_id', '=', self.company_id.id),
            ('alicuota_percepcion', '>', 0),  # Solo buscar si tiene alícuota de percepción
        ]
        return self.env['res.partner.arba_alicuot'].search(domain, limit=1)
    
    def _find_padron_type_perception(self, arba_line):
        """Encuentra el tipo de padrón de percepción configurado para la compañía."""
        if not arba_line.padron_line_id or not arba_line.padron_line_id.padron_type_id:
            return False
        return arba_line.padron_line_id.padron_type_id.filtered(
            lambda x: x.company_id.id == self.company_id.id and x.account_tax_perception_id
        )
    
    def _total_amount_perception(self, base_minimum_perception, percent_perception_arba, minimum_calcule_perception):

        total_to_discount = 0
        for line in self.invoice_line_ids:
            # Solo procesar líneas de productos/servicios (excluir line_section y line_note)
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
    
    def _create_arba_perception_line(self, tax, amount_perception, base_perception):
        
        self.ensure_one()
        
        if not tax:
            message = _('No se pudo agregar el impuesto de percepción porque el impuesto es inválido.')
            self.message_post(body=message)
            raise UserError(message)
        
        if tax.type_tax_use != 'sale':
            message = _('El impuesto "%s" no es de tipo venta. Debe ser un impuesto de venta para aplicarse en facturas de cliente.') % tax.name
            self.message_post(body=message)
            raise UserError(message)
        
        perception_percentage = (amount_perception / base_perception * 100) if base_perception > 0 else 0
        
        lines_updated = 0
        invoice_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )
        
        # Agregar el impuesto a todas las líneas que no lo tengan
        for line in invoice_lines:
            if tax.id not in line.tax_ids.ids:
                line.write({
                    'tax_ids': [(4, tax.id)]
                })
                lines_updated += 1
        
        original_amount_type = tax.amount_type
        
        if tax.amount_type != 'partner_tax':
            tax.write({'amount_type': 'partner_tax'})
        
        invoice_date = self.invoice_date or self.date
        move_with_context = self.with_context(invoice_date=invoice_date, partner_id=self.partner_id.id if self.partner_id else None)
        
        invoice_lines_with_tax = move_with_context.invoice_line_ids.filtered(
            lambda l: (l.display_type in ('product', False) or not l.display_type) and tax.id in l.tax_ids.ids
        )
        
        move_with_context.invalidate_recordset(['line_ids', 'amount_tax', 'amount_total', 'tax_totals'])
        
        for line in invoice_lines_with_tax:
            line.invalidate_recordset(['price_subtotal', 'price_total', 'tax_ids'])
            _dummy_subtotal = line.price_subtotal
            _dummy_total = line.price_total
        
        _dummy_tax_totals = move_with_context.tax_totals
        _dummy_tax = move_with_context.amount_tax
        
        base_lines, _tax_lines = move_with_context._get_rounded_base_and_tax_lines()
        
        if self.id:
            tax_container = {
                'records': move_with_context,
                'base_lines': base_lines,
                'tax_lines': _tax_lines,
            }
            move_with_context._sync_tax_lines(tax_container)
        else:
            move_with_context.invalidate_recordset(['tax_totals', 'amount_tax', 'amount_total'])
            _dummy_tax_totals = move_with_context.tax_totals
            _dummy_tax = move_with_context.amount_tax

        _dummy_lines = self.line_ids
        tax_repartition_lines = tax.invoice_repartition_line_ids
        tax_lines_found = _dummy_lines.filtered(
            lambda l: l.tax_repartition_line_id and l.tax_repartition_line_id.id in tax_repartition_lines.ids
        )
        
        if lines_updated > 0:
            message = _('Se aplicó percepción "%s" (%s%%) a %d líneas de producto. Monto total: %s') % (
                tax.name,
                perception_percentage,
                lines_updated,
                formatLang(self.env, amount_perception, currency_obj=self.currency_id)
            )
            self.message_post(body=message)
    
    def _recalculate_tax_lines_with_padron_alicuot(self, tax, perception_percentage, base_perception):

        self.ensure_one()
        
        self.invalidate_recordset(['line_ids'])
        
        _dummy = self.amount_tax
        
        tax_lines = self.line_ids.filtered(
            lambda l: l.tax_line_id.id == tax.id and l.tax_repartition_line_id
        )
        
        if not tax_lines:
            # Invalidar nuevamente y forzar recálculo
            self.invalidate_recordset(['line_ids'])
            for line in self.invoice_line_ids.filtered(lambda l: tax.id in l.tax_ids.ids):
                _dummy_price = line.price_subtotal
            _dummy = self.amount_tax
            self.invalidate_recordset(['line_ids'])
            tax_lines = self.line_ids.filtered(
                lambda l: l.tax_line_id.id == tax.id and l.tax_repartition_line_id
            )
            if not tax_lines:
                return False
        
        total_recalculated = 0.0
        
        invoice_lines_with_tax = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note') and tax.id in l.tax_ids.ids
        )
        
        # Calcular el monto proporcional para cada línea de producto
        for line in invoice_lines_with_tax:
            line_base = line.price_subtotal
            line_perception = line_base * perception_percentage / 100.0
            total_recalculated += line_perception
        
        is_refund = self.move_type == 'out_refund'
        
        if len(tax_lines) == 1:
            tax_line = tax_lines[0]
            repartition_line = tax_line.tax_repartition_line_id
            repartition_type = repartition_line.repartition_type if repartition_line else 'tax'
            is_invoice_repartition = repartition_type == 'invoice'
            is_refund_repartition = repartition_type == 'refund'
            
            if is_refund:
                # Nota de crédito: amount_currency positivo, balance positivo
                amount_currency = abs(total_recalculated)
                balance_value = abs(total_recalculated)
            else:
                # Factura de venta: amount_currency NEGATIVO para que balance sea negativo
                # Esto hace que se sume al total (credit aumenta lo que el cliente debe)
                amount_currency = -abs(total_recalculated)
                balance_value = -abs(total_recalculated)
            
            debit_value = 0.0 if amount_currency < 0 else abs(amount_currency)
            credit_value = abs(amount_currency) if amount_currency < 0 else 0.0
            
            tax_line.with_context(
                skip_tax_recalculation=True,
                skip_account_move_synchronization=True,
                check_move_validity=False
            ).write({
                'amount_currency': amount_currency,
                'debit': debit_value,
                'credit': credit_value,
            })
            
            # Invalidar balance para forzar recálculo desde debit/credit
            tax_line.invalidate_recordset(['balance'])
            
            # Leer balance para forzar recálculo
            _dummy_balance = tax_line.balance
            
        else:
            total_factor = sum(tax_lines.mapped('tax_repartition_line_id.factor'))
            if total_factor > 0:
                for tax_line in tax_lines:
                    factor = tax_line.tax_repartition_line_id.factor / total_factor
                    line_amount = total_recalculated * factor
                    # Asegurar que sea positivo para facturas de venta
                    if is_refund:
                        amount_currency = -abs(line_amount)
                    else:
                        amount_currency = abs(line_amount)  # Asegurar que sea positivo
                    
                    # Actualizar usando SOLO amount_currency
                    # No tocar price_unit porque puede causar recálculos incorrectos
                    tax_line.with_context(skip_tax_recalculation=True).write({
                        'amount_currency': amount_currency,
                    })
                    
        self.invalidate_recordset(['amount_tax', 'amount_total', 'line_ids', 'amount_untaxed'])
        _dummy_tax = self.amount_tax
        _dummy_total = self.amount_total
        _dummy_untaxed = self.amount_untaxed
        
        return True
