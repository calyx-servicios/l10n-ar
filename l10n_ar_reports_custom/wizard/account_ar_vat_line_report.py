from odoo.exceptions import ValidationError
from odoo import models, fields

class AccountArVatLine(models.TransientModel):
    _name = "account.ar.vat.line.report"
    _description = "Línea de IVA para análisis en localización argentina"

    company_id = fields.Many2one(
        string="Compania",
        comodel_name="res.company",
        default=lambda self: self.env.company
    )
    start_date = fields.Date(
        string="Fecha de inicio"
    )
    end_date = fields.Date(
        string="Fecha fin"
    )
    report_type = fields.Selection(
        string="Tipo",
        selection=[
            ("purchase", "Compras"),
            ("sale", "Ventas")
        ],
        required=True
    )
    file_data = fields.Binary()
    file_name = fields.Char()


    def _return_report(self, content):
        self.file_data = content
        if self.report_type == "purchase":
            file_name = "reporte_iva_compras_%s.txt"
        else:
            file_name = "reporte_iva_ventas_%s.txt"

        date = datetime.now().strftime('%Y_%m_%d')
        self.file_name = file_name % date
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/?model=asset.report&id={self.id}&field=file_data&filename_field=file_name&download=true",
            'target': 'new',
        }

    def action_report(self):
        self.validate_fields()
        query = self._get_query()
        cr = self.env.cr
        cr.execute(query)
        invoices = cr.dictfetchall()
        aliquots = self._get_aliquots(self, invoices)
        vouchers = self._get_vouchers(self, invoices, aliquots)
        file_data = self._get_content(res)

    def _get_content(self, recs):
        for rec in recs:
            import ipdb
            ipdb.set_trace()

    def validate_fields(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError(
                    "La fecha fin no puede ser menor a la fecha de inicio"
                )

    def _get_where_query(self):
        where_query = """
        (aml.tax_line_id is not null or btg.l10n_ar_vat_afip_code is not null)
        -- AND am.l10n_latam_document_type_id != NULL
        AND am.state = 'posted'
        """
        if self.report_type == "sale":
            where_query += """
                AND move_type in ('out_invoice', 'out_refund')
            """
        elif self.report_type == "purchase":
            where_query += """
                AND move_type in ('in_invoice', 'in_refund')
                -- AND lldt.code not in ('66', '30', '32')
            """
        if self.start_date:
            where_query += """
                AND date >= '%s'
            """ % self.start_date.isoformat()
        if self.end_date:
            where_query += """
                AND date <= '%s'
            """ % self.end_date.isoformat()
        return where_query

    def _get_query(self):
        query = """
        SELECT
            am.id,
        (CASE WHEN lit.l10n_ar_afip_code = '80' THEN rp.vat ELSE null END) as cuit,
        art.name as afip_responsibility_type_name,
        am.name as move_name,
        rp.name as partner_name,
        am.id as move_id,
        move_type,
        am.date,
        am.invoice_date,
        am.partner_id,
        am.journal_id,
        am.name,
        am.l10n_ar_afip_responsibility_type_id as afip_responsibility_type_id,
        am.l10n_latam_document_type_id as document_type_id,
        am.state,
        am.company_id,
        sum(CASE WHEN btg.l10n_ar_vat_afip_code = '5' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN btg.l10n_ar_vat_afip_code = '5' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as base_21,
        sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '5' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN ntg.l10n_ar_vat_afip_code = '5' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as vat_21,
        sum(CASE WHEN btg.l10n_ar_vat_afip_code = '4' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN btg.l10n_ar_vat_afip_code = '4' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as base_10,
        sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '4' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN ntg.l10n_ar_vat_afip_code = '4' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as vat_10,
        sum(CASE WHEN btg.l10n_ar_vat_afip_code = '6' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN btg.l10n_ar_vat_afip_code = '6' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as base_27,
        sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '6' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN ntg.l10n_ar_vat_afip_code = '6' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as vat_27,
        sum(CASE WHEN btg.l10n_ar_vat_afip_code = '9' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN btg.l10n_ar_vat_afip_code = '9' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as base_25,
        sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '9' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN ntg.l10n_ar_vat_afip_code = '9' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as vat_25,
        sum(CASE WHEN btg.l10n_ar_vat_afip_code = '8' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN btg.l10n_ar_vat_afip_code = '8' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as base_5,
        sum(CASE WHEN ntg.l10n_ar_vat_afip_code = '8' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN ntg.l10n_ar_vat_afip_code = '8' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as vat_5,
        sum(CASE WHEN btg.l10n_ar_vat_afip_code IN ('0', '1', '2', '3', '7') AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN btg.l10n_ar_vat_afip_code IN ('0', '1', '2', '3', '7') AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as not_taxed,
        sum(CASE WHEN ntg.l10n_ar_tribute_afip_code = '06' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN ntg.l10n_ar_tribute_afip_code = '06' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as vat_per,
        sum(CASE WHEN ntg.l10n_ar_vat_afip_code is null and ntg.l10n_ar_tribute_afip_code != '06' AND move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN ntg.l10n_ar_vat_afip_code is null and ntg.l10n_ar_tribute_afip_code != '06' AND move_type IN ('in_invoice',  'in_refund')  THEN aml.balance
                ELSE Null END) as other_taxes,
        sum(CASE WHEN move_type IN ('out_invoice', 'out_refund') THEN aml.balance*-1
                WHEN move_type IN ('in_invoice', 'in_refund') THEN aml.balance END) as total
        FROM
            account_move_line aml
        LEFT JOIN
            account_move as am
            ON aml.move_id = am.id
        LEFT JOIN
            -- nt = net tax
            account_tax AS nt
            ON aml.tax_line_id = nt.id
        LEFT JOIN
            account_move_line_account_tax_rel AS amltr
            ON aml.id = amltr.account_move_line_id
        LEFT JOIN
            -- bt = base tax
            account_tax AS bt
            ON amltr.account_tax_id = bt.id
        LEFT JOIN
            account_tax_group AS btg
            ON btg.id = bt.tax_group_id
        LEFT JOIN
            account_tax_group AS ntg
            ON ntg.id = nt.tax_group_id
        LEFT JOIN
            res_partner AS rp
            ON rp.id = am.partner_id
        LEFT JOIN
            l10n_latam_identification_type AS lit
            ON rp.l10n_latam_identification_type_id = lit.id
        LEFT JOIN
            l10n_ar_afip_responsibility_type AS art
            ON am.l10n_ar_afip_responsibility_type_id = art.id
        LEFT JOIN
            l10n_latam_document_type AS lldt
            ON am.l10n_latam_document_type_id = lldt.id
        WHERE
            %s
        GROUP BY
            am.id, art.name, rp.id, lit.id
        ORDER BY
            am.date, am.name
        """
        query = query % self._get_where_query()
        return query
