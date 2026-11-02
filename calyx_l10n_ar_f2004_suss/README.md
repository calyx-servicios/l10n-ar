# Calyx - SUSS Aplicado TXT F2004

Módulo de Odoo 19 para reportar retenciones SUSS aplicadas a proveedores y
exportar el archivo `SUSS_F2004.txt`.

| Dato | Valor |
| --- | --- |
| Nombre técnico | `calyx_l10n_ar_f2004_suss` |
| Versión | `19.0.1.0.1` |
| Dependencia directa | `l10n_ar_account_reports` |
| Autor | Calyx Servicios S.A. |
| Licencia | AGPL-3 |

## Funcionalidad

- Extiende `account.tax.l10n_ar_tax_type` con la opción `suss` (**SUSS**).
- Crea el reporte **SUSS Aplicado F2004**, variante argentina de
  `account.generic_tax_report`, con columna **Balance**.
- Agrega el botón **SUSS Aplicado TXT F2004**.
- Crea el tipo de obligación **SUSS (Agente)** (`account.return.type`):
  periodicidad mensual, demora de vencimiento configurada en 5 días,
  generación automática desactivada y contacto de pago `l10n_ar.partner_afip`.

No crea un menú propio ni una aplicación independiente. No realiza envíos
automáticos al organismo fiscal.

## Instalación y uso

1. Incluir el módulo y sus dependencias en los directorios de addons de Odoo.
2. Actualizar la lista de aplicaciones e instalar el módulo.
3. Configurar impuestos de retención a proveedores de tipo **SUSS**, con código
   de régimen AFIP (`l10n_ar_code`).
4. Completar los CUIT de proveedores y compañías; registrar pagos con
   retenciones y publicar sus asientos.
5. Abrir la variante **SUSS Aplicado F2004** del reporte de impuestos,
   seleccionar compañías y período, y exportar con **SUSS Aplicado TXT F2004**.

La disponibilidad del reporte depende de los permisos y la configuración
contable del entorno.

## Selección de datos

El exportador consulta `l10n_ar.payment.withholding` con estas condiciones:

- `company_id` dentro de las compañías seleccionadas en el reporte.
- `tax_id.l10n_ar_withholding_payment_type = "supplier"`.
- `tax_id.l10n_ar_tax_type = "suss"` **o** nombre del grupo de impuestos que
  contenga `suss` mediante `ilike`.
- `payment_id.move_id.state = "posted"`.
- Fecha de pago mayor o igual a `date_from` y menor o igual a `date_to`,
  cuando se informan esos límites.

El orden de salida es `(payment_id.date, id)`.

La línea contable del reporte usa `-sum(...)` sobre apuntes cuyos impuestos
son argentinos (`country_code = "AR"`), de retención a proveedores y
coincidentes con la clasificación o grupo SUSS. El TXT utiliza los registros
de retenciones de pagos; no exporta directamente el saldo de esa línea.

## Diseño del archivo

Nombre de descarga: `SUSS_F2004.txt` (traducible).  
Codificación: ISO-8859-1, con omisión de caracteres no representables.  
Separador de registros: CRLF (`\r\n`), también al final del último registro.  
Sin cabecera ni totales; un registro por retención.

Las posiciones siguientes corresponden al diseño de 191 caracteres, sin
contar CRLF:

| Posiciones | Ancho | Contenido | Implementación |
| --- | ---: | --- | --- |
| 1-4 | 4 | Formulario | Fijo `2004` |
| 5-8 | 4 | Versión | Fijo `0100` |
| 9-18 | 10 | Trazabilidad | Espacios |
| 19-29 | 11 | CUIT agente | `company.vat`, solo dígitos, ceros a la izquierda |
| 30-32 | 3 | Impuesto | Fijo `353` |
| 33-35 | 3 | Régimen | `tax.l10n_ar_code`, solo dígitos, ceros a la izquierda |
| 36-46 | 11 | CUIT retenido | `partner.vat`, solo dígitos, ceros a la izquierda |
| 47-56 | 10 | Fecha de retención | Fecha del pago, `DD/MM/AAAA` |
| 57-58 | 2 | Tipo de comprobante | Fijo `04` |
| 59-68 | 10 | Fecha de comprobante | Fecha del pago, `DD/MM/AAAA` |
| 69-84 | 16 | Número de comprobante | `withholding.name`, espacios a la derecha y recorte a 16 |
| 85-98 | 14 | Importe de comprobante | `abs(withholding.base_amount)`, formato `014.2f` |
| 99-112 | 14 | Importe de retención | `abs(withholding.amount)`, formato `014.2f` |
| 113-137 | 25 | Número de certificado original | Espacios |
| 138-147 | 10 | Fecha de retención original | Espacios |
| 148-161 | 14 | Importe de certificado original | Espacios |
| 162-191 | 30 | Otros datos | Espacios |

Los importes usan punto decimal y no llevan signo.

## Validaciones y límites

Se lanza `UserError` si:

- Está activa la opción `all_entries` (incluir asientos no publicados).
- El proveedor de una retención no tiene `vat`.
- El impuesto de una retención no tiene `l10n_ar_code`.

Límites de la implementación actual:

- No valida CUIT por longitud o dígito verificador ni exige el CUIT de la
  compañía; un CUIT de compañía vacío se rellena con ceros.
- No controla la longitud final del registro. El ancho de CUIT, régimen e
  importes es mínimo, no máximo: valores excedidos pueden superar las
  191 posiciones previstas.
- El comprobante se trunca a 16 caracteres.
- No contempla un flujo específico para notas de crédito, anulaciones o
  certificados originales. Usa siempre comprobante `04`, fecha del pago e
  importes absolutos.
- No realiza conversión monetaria explícita.
- Sin retenciones coincidentes devuelve un archivo vacío, sin advertencia.
- No separa archivos por compañía en una selección multicompañía.
- La coincidencia por nombre de grupo puede incluir impuestos no clasificados
  explícitamente como SUSS; revisar esa configuración.
- No verifica aceptación fiscal ni actualiza el diseño según normativa externa.

## Estructura

| Archivo | Responsabilidad |
| --- | --- |
| [__manifest__.py](__manifest__.py) | Metadatos, dependencia y carga de datos. |
| [models/account_tax.py](models/account_tax.py) | Opción SUSS y política de desinstalación. |
| [models/f2004_suss_report.py](models/f2004_suss_report.py) | Handler `l10n_ar.f2004.suss.report.handler`, botón, búsqueda y generación del TXT. |
| [data/f2004_suss_report.xml](data/f2004_suss_report.xml) | Reporte, columna, línea contable y tipo de obligación. |

## Corrección de compatibilidad con Odoo 19 (22/10/2026)

La instalación fallaba porque la opción SUSS declaraba:

```python
ondelete={"suss": "set default"}
```

El campo base es opcional y no define un valor predeterminado. Odoo rechaza
esa combinación al inicializar los campos. Se corrigió a:

```python
ondelete={"suss": "set null"}
```

Al desinstalar el módulo, la política limpia la clasificación SUSS sin
eliminar los impuestos. No agrega un valor predeterminado ni modifica las
opciones previas o el exportador.

Se reprodujo la falla y se verificó la inicialización corregida con el campo
real en Odoo `19.0-20261015`, conservando opciones previas, `required=False` y
`default=None`. También se validaron sintaxis Python y limpieza del diff.
No se ejecutó una instalación completa ni una validación fiscal end-to-end.

Tras desplegar el cambio, reiniciar Odoo para recargar Python y reintentar
la instalación. En el entorno Docker de este proyecto, desde su raíz:

```bash
docker compose restart web
```

Coordinar la interrupción temporal del servicio.

## Control funcional recomendado

- Instalar el módulo sin el `AssertionError` de la política `ondelete`.
- Verificar la selección por tipo SUSS y por nombre de grupo.
- Comprobar filtros de compañías, fechas y estado publicado.
- Validar los mensajes por CUIT o régimen faltante.
- Contrastar las retenciones exportadas con los pagos y el reporte contable.
- Revisar posiciones, importes, CRLF y codificación con datos representativos.
- Confirmar la aceptación del archivo por el sistema fiscal de destino.
