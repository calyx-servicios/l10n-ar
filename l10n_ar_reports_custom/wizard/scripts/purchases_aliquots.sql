/**
Libro IVA COMPRAS

Diseño de Registro Compras
LIBRO DE IVA DIGITAL

DENOMINACION DEL ARCHIVO: LIBRO_IVA_DIGITAL_COMPRAS_ALICUOTAS

**/
SELECT right('000' || coalesce(dc.code,'0'),3) || --1 - Tipo de comprobante: Según tabla Comprobantes
	   right('00000' || NULLIF(regexp_replace(am.sequence_prefix, '\D','','g'), '')::varchar,5) || --3 - Punto de venta
	   right('00000000000000000000' || coalesce(am.sequence_number::varchar,'0'),20) || --3 - Número de comprobante
	   right('00' || coalesce(max(lit.l10n_ar_afip_code)::varchar,'0'),2) || --4 - Código de documento del vendedor: Según tabla Documentos
	   right('00000000000000000000' || coalesce(max(rp.vat),'0'),20) || --5 - Número de identificación del vendedor: Completar con ceros a izquierda
	   right('000000000000000' || replace(abs(SUM(CASE WHEN ntg_base.l10n_ar_vat_afip_code IN ('4','5','6','8','9') THEN aml.amount_currency ELSE 0.00 END))::varchar,'.',''),15) || --6 - Importe neto gravado: 13 enteros 2 decimales sin punto decimal	   
	   right('0000' || replace(max(ntg_base.l10n_ar_vat_afip_code)::varchar,'.',''),4) || --7 - Alícuota de IVA: Según tabla Alícuotas
	   right('000000000000000' || replace(abs(sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '5' THEN aml.amount_currency ELSE 0.00 END))::varchar,'.',''),15) --8 - Impuesto Liquidado: 13 enteros 2 decimales sin punto decimal
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
