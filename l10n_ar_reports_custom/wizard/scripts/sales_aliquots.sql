/**
Libro IVA VENTAS

Diseño de Registro Ventas - Cabecera
LIBRO DE IVA DIGITAL

DENOMINACION DEL ARCHIVO: LIBRO_IVA_DIGITAL_VENTAS_ALICUOTAS

**/
SELECT right('000' || coalesce(dc.code,'0'),3) || --1 - Tipo de comprobante: Según tabla Comprobantes
	   right('00000' || coalesce(aj.l10n_ar_afip_pos_number,'0'),5) || --2 - Punto de venta
	   right('00000000000000000000' || coalesce(am.sequence_number::varchar,'0'),20) || --3 - Número de comprobante
	   right('000000000000000' || replace(abs(SUM(CASE WHEN ntg_base.l10n_ar_vat_afip_code IN ('4','5','6','8','9') THEN aml.amount_currency ELSE 0.00 END))::varchar,'.',''),15) || --4 - Importe neto gravado: 13 enteros 2 decimales sin punto decimal	   
	   right('0000' || replace(max(ntg_base.l10n_ar_vat_afip_code)::varchar,'.',''),4) || --5 - Alícuota de IVA: Según tabla Alícuotas
	   right('000000000000000' || replace(abs(sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '5' THEN aml.amount_currency ELSE 0.00 END))::varchar,'.',''),15) --6 - Impuesto Liquidado: 13 enteros 2 decimales sin punto decimal
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
 INNER JOIN account_journal aj
    ON aj.id = am.journal_id
  --account_tax vat afip	
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
 WHERE am.move_type in ('out_invoice', 'out_refund')
	and am.state = 'posted'
    %s
GROUP BY
    am.invoice_date, aj.l10n_ar_afip_pos_number,am.sequence_number,dc.code
ORDER BY
	am.invoice_date, aj.l10n_ar_afip_pos_number,am.sequence_number    
