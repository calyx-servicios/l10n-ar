/**
Libro COMPRAS

Diseño de Registro Compras - Cabecera
LIBRO DE IVA DIGITAL

DENOMINACION DEL ARCHIVO: LIBRO_IVA_DIGITAL_COMPRAS_CBTE

**/
SELECT right('00000000' || to_char(am.invoice_date,'YYYYMMDD'),8) || --1 - Fecha de comprobante o fecha de oficialización: AAAAMMDD
	   right('000' || coalesce(dc.code,'0'),3) || --2 - Tipo de comprobante: Según tabla Comprobantes Compras
	   right('00000' || NULLIF(regexp_replace(am.sequence_prefix, '\D','','g'), '')::varchar,5) || --3 - Punto de venta 
	   right('00000000000000000000' || coalesce(am.sequence_number::varchar,'0'),20) || --4 - Número de comprobante
	   right('                ' || '',16)  || --5 - Despacho de importación ????????????????
	   right('00' || coalesce(max(lit.l10n_ar_afip_code)::varchar,'0'),2) || --6 - Código de documento del vendedor: Según tabla Documentos
	   right('00000000000000000000' || coalesce(max(rp.vat),'0'),20) || --7 - Número de identificación del vendedor: Completar con ceros a izquierda
	   UPPER(left(trim(rp.name) || '                              ',30)) || --8 - Apellido y nombre o denominación del vendedor
	   right('000000000000000' || replace(coalesce(am.amount_total::varchar,'0'),'.',''),15) || --9 - Importe total de la operación: 13 enteros 2 decimales sin punto decimal
	   right('000000000000000' || replace(SUM(CASE WHEN ntg_base.l10n_ar_vat_afip_code IN ('1','3','0') THEN aml.balance ELSE 0.00 END)::varchar,'.',''),15) || --10 - Importe total de conceptos que no integran el precio neto gravado: 13 enteros 2 decimales sin punto decimal
	   right('000000000000000' || replace(SUM(CASE WHEN ntg_base.l10n_ar_vat_afip_code IN ('2') THEN aml.balance ELSE 0.00 END)::varchar,'.',''),15) || --11 - Importe de operaciones exentas: 13 enteros 2 decimales sin punto decimal
	   right('000000000000000' || replace(sum(CASE WHEN ntg.l10n_ar_vat_afip_code IS NULL AND ntg.l10n_ar_tribute_afip_code IN ('06') THEN aml.balance ELSE 0.00 END)::varchar,'.',''),15) || --12 - Importe de percepciones o pagos a cuenta del Impuesto al Valor Agregado: 13 enteros 2 decimales sin punto decimal
	   right('000000000000000' || replace(0.00::varchar,'.',''),15) || --13 - Importe de percepciones o pagos a cuenta de otros impuestos Nacionales: 13 enteros 2 decimales sin punto decimal
	   right('000000000000000' || replace(sum(CASE WHEN ntg.l10n_ar_vat_afip_code IS NULL AND ntg.l10n_ar_tribute_afip_code IN ('07') THEN aml.balance ELSE 0.00 END)::varchar,'.',''),15) || --14 - Importe de percepciones de Ingresos Brutos: 13 enteros 2 decimales sin punto decimal
	   right('000000000000000' || replace(0.00::varchar,'.',''),15) || --15 - Importe de percepciones impuestos Municipales: 13 enteros 2 decimales sin punto decimal
	   right('000000000000000' || replace(sum(CASE WHEN ntg.l10n_ar_vat_afip_code IS NULL AND ntg.l10n_ar_tribute_afip_code IN ('04') THEN aml.balance ELSE 0.00 END)::varchar,'.',''),15) || --16 - Importe impuestos internos: 13 enteros 2 decimales sin punto decimal
	   right('000' || coalesce(rc.l10n_ar_afip_code,'0'),3) || --17 - Código de moneda: Según tabla Tipo de Monedas
	   right('0000000000' || replace(coalesce(l10n_ar_currency_rate::decimal(10,6)::varchar,'0'),'.',''),10) || --18 - Tipo de cambio: 4 enteros 6 decimales sin punto decimal
	   '1' || --19 - Cantidad de alícuotas de IVA
	   CASE WHEN max(ntg_base.l10n_ar_vat_afip_code) IN ('1','2','3','0') THEN 'N' WHEN max(ntg_base.l10n_ar_vat_afip_code) IN ('4') THEN 'E' ELSE ' ' END || --20 - Código de operación: Según tabla Código de Operación 
	   right('000000000000000' || replace(sum(CASE WHEN ntg.l10n_ar_vat_afip_code IN ('4','5') THEN aml.balance ELSE 0.00 END)::varchar,'.',''),15) || --21 - Crédito Fiscal Computable
	   right('000000000000000' || replace(sum(CASE WHEN ntg.l10n_ar_vat_afip_code IS NULL AND ntg.l10n_ar_tribute_afip_code IN ('99') THEN aml.balance ELSE 0.00 END)::varchar,'.',''),15) || --22 - Otros Tributos
	   right('00000000000' || '',11) || --23 - CUIT emisor/corredor
	   UPPER(left('' || '                              ',30))  || --24 - Denominación del emisor/corredor
	   right('000000000000000' || replace(0.00::varchar,'.',''),15)--25 - IVA comisión
  FROM account_move_line aml
 INNER JOIN account_move as am
    ON aml.move_id = am.id 
 INNER JOIN res_partner AS rp
    ON rp.id = am.partner_id
 INNER JOIN l10n_latam_identification_type as lit
    ON lit.id = rp.l10n_latam_identification_type_id
 INNER JOIN l10n_ar_afip_responsibility_type AS art
    ON am.l10n_ar_afip_responsibility_type_id = art.id	
 INNER JOIN res_currency rc
    ON rc.id = am.currency_id
 INNER JOIN l10n_latam_document_type dc
    ON dc.id = am.l10n_latam_document_type_id	
  LEFT JOIN account_tax AS nt
    ON nt.id = aml.tax_line_id	
  LEFT JOIN account_move_line_account_tax_rel AS amltr
    ON amltr.account_move_line_id = aml.id	
  LEFT JOIN account_tax_group AS ntg
    ON ntg.id = nt.tax_group_id
  LEFT JOIN account_tax AS nt_base
    ON nt_base.id = amltr.account_tax_id
  LEFT JOIN account_tax_group AS ntg_base
    ON ntg_base.id = nt_base.tax_group_id	
  WHERE am.move_type in ('in_invoice', 'in_refund')
	and am.state = 'posted'
    %s
	--30	"Facturas de proveedores ARS"
	--47	"Cartera Propia Compras con Documentos"
	--48	"Boletos de 3ros - Compra"
	--51	"Gastos bancarios"
	--85	"Facturas de proveedores USD"
	--174	"Compras tarjeta corporativa Santander (ARS) NO USAR"
	--176	"Pagos debitados via mercados"
	--220	"Compras tarjeta corporativa Bind (Ars) NO USAR"
	--and am.sequence_number = 199323	
GROUP BY
    am.id, am.invoice_date, rp.name, art.name, rp.vat, aml.move_name, rc.l10n_ar_afip_code, dc.code,lit.l10n_ar_afip_code
ORDER BY
    am.invoice_date, rp.name, art.name, rp.vat, aml.move_name;
