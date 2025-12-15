# Argentina - Percepciones Automáticas

## Descripción

Módulo que permite calcular y aplicar automáticamente percepciones en facturas de ventas para Argentina.

## Características

- Botón "Calcular Percepciones" en facturas de ventas
- Integración con padrones ARBA
- Cálculo automático de alícuotas de percepción
- Solo visible en facturas de cliente con fecha y líneas
- Verifica mínimos de base imponible y montos calculados
- Utiliza alícuotas específicas del partner o valores por defecto

## Dependencias

- account
- l10n_ar
- account_padron_withholding_perception

## Uso

1. Crear una factura de venta (cliente)
2. Establecer fecha de factura
3. Agregar líneas de productos/servicios
4. Hacer clic en "Calcular Percepciones"
5. El sistema aplicará automáticamente las percepciones correspondientes

## Configuración

### Requisitos previos

1. Tener configurados los tipos de padrón de percepción en:
   - Contabilidad → Configuración → ARBA → Tipos de Padrón

2. Configurar para cada tipo:
   - Impuesto de percepción (tipo venta)
   - Porcentaje por defecto (opcional)
   - Mínimo de base imponible (opcional)
   - Mínimo de percepción calculada (opcional)

3. Importar padrones ARBA con alícuotas de percepción por partner

## Funcionamiento

El módulo:

1. Valida que sea una factura de venta con fecha y líneas
2. Busca tipos de percepción configurados
3. Para cada tipo, verifica:
   - Si el partner tiene alícuota específica en el padrón
   - Si no, usa el porcentaje por defecto
4. Calcula la base imponible (suma de líneas sin impuestos)
5. Verifica mínimos de base y monto
6. Crea o actualiza las líneas de percepción
7. Recalcula los totales de la factura

## Autor

Calyx Servicios

## Licencia

LGPL-3
