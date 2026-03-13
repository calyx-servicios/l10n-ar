from odoo.exceptions import ValidationError
from odoo import models, fields
from datetime import datetime
import io
import os
import zipfile
import base64
import xlsxwriter

def ws_write(ws, row, col, field, style=None):
    if style:
        ws.write(row, col, field, style)
    else:
        ws.write(row, col, field)
    if not hasattr(ws, "_col_widths"):
        ws._col_widths = {}
    width = len(str(field)) + 2
    if col not in ws._col_widths or width > ws._col_widths[col]:
        ws._col_widths[col] = width
        ws.set_column(col, col, width)


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


    def _return_report(self):
        if self.report_type == "purchase":
            file_name = "reporte_iva_compras_%s.zip"
        if self.report_type == "sale":
            file_name = "reporte_iva_ventas_%s.zip"

        date = datetime.now().strftime('%Y_%m_%d')
        self.file_name = file_name % date
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/?model=account.ar.vat.line.report&id={self.id}&field=file_data&filename_field=file_name&download=true",
            'target': 'new',
        }

    def action_report(self):
        self.validate_fields()
        if self.report_type == "purchase":
            reports = [
                {'name': 'purchases.txt', 'script': 'purchases_vouchers.sql'},
                {'name': 'purchases_aliquots.txt', 'script': 'purchases_aliquots.sql'}
            ]
        if self.report_type == "sale":
            reports = [
                {'name': 'sales.txt', 'script': 'sales_vouchers.sql'},
                {'name': 'sales_aliquots.txt', 'script': 'sales_aliquots.sql'}
            ]
        self.generate_reports(reports)
        return self._return_report()

    def action_report_xlsx(self):
        self.validate_fields()
        if self.report_type == "purchase":
            reports = [
                {'name': 'purchases.xls', 'script': 'purchases_vouchers.sql'},
                {'name': 'purchases_aliquots.xls', 'script': 'purchases_aliquots.sql'}
            ]
        if self.report_type == "sale":
            reports = [
                {'name': 'sales.xls', 'script': 'sales_vouchers.sql'},
                {'name': 'sales_aliquots.xls', 'script': 'sales_aliquots.sql'}
            ]
        self.generate_reports_xlsx(reports)
        return self._return_report()

    def validate_fields(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError(
                    "La fecha fin no puede ser menor a la fecha de inicio"
                )

    def generate_reports(self, reports):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for report in reports:
                zf.writestr(report['name'], self._get_report_content(report['script']))
        self.file_data = base64.b64encode(stream.getvalue())

    def generate_reports_xlsx(self, reports):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for report in reports:
                excel_buffer = self._get_xlsx_buffer(report)
                zf.writestr(report['name'], excel_buffer.getvalue())
        self.file_data = base64.b64encode(stream.getvalue())

    def _get_report_xlsx_cols(self, report):
        if report["script"] == 'purchases_vouchers.sql':
            cols_names = [
                "Fecha", "Tipo", "PV", "Nro Comp", "Despacho", "Cod.", "CUIT",
                "Nom.Apell", "Total", "No gravado", "Excento", "Perc.IVA", "Perc.Nac",
                "Perc.IIBB", "Perc.Muni", "Imp.Int", "Mon.", "TC", "Cant.Ali", "Cod.Op",
                "Cred.Comp", "Otros", "CUIT.Emi", "Denom.Emi", "IVA.Com"
            ]
            cols = [8,3,5,20,16,2,20,30,15,15,15,15,15,15,15,15,3,10,1,1,15,15,11,30,15]
        if report["script"] == "purchases_aliquots.sql":
            cols_names = [
                "Tipo", "PV", "Nro Comp", "Cod.", "CUIT", "Imp.Neto", "Alic.IVA", "Imp.Liq"
            ]
            cols = [3,5,20,2,20,15,4,15]
        if report["script"] == "sales_vouchers.sql":
            cols_names = [
                "Fecha", "Tipo", "PV", "Nro Comp", "Nro Comp Hasta", "Cod.", "CUIT",
                "Nom.Apell", "Total", "No gravado", "Perc.No.Categ", "Excento", "Perc.Nac",
                "Perc.IIBB", "Perc.Muni", "Imp.Int", "Mon", "TC", "Cant.Ali", "Cod.Op",
                "Otros", "Fecha.Vto"
            ]
            cols = [8,3,5,20,20,2,20,30,15,15,15,15,15,15,15,15,3,10,1,1,15,8]
        if report["script"] == "sales_aliquots.sql":
            cols_names = [
                "Tipo", "PV", "Nro Comp", "Imp.Neto.Grav", "Alic.IVA", "Imp.Liq"
            ]
            cols = [3,5,20,15,4,15]
        return cols_names, cols


    def _get_xlsx_buffer(self, report):
        cols_names, cols = self._get_report_xlsx_cols(report)
        len_cols = len(cols)
        if len(cols_names) != len_cols:
            raise ValidationError(
                "El num de columnas debe coincidir con el numero de nombres de columnas"
            )
        excel_buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(excel_buffer, {'in_memory': True})
        ws = workbook.add_worksheet(report["name"])
        title_style = workbook.add_format({
            'bold': True,
            'font_color': 'white',
            'align': 'center',
            'bg_color': 'blue',
            'border': 1
        })
        for i in range(len_cols):
            ws_write(ws, 0, i, cols_names[i], style=title_style)
        row_num = 1
        for line in self._get_report_content(report["script"]).decode('ISO-8859-1').split("\r\n"):
            fields = []
            pos = 0
            for size in cols:
                fields.append(line[pos:pos+size])
                pos += size
            for i in range(len_cols):
                ws_write(ws, row_num, i, fields[i])
            row_num += 1
        workbook.close()
        return excel_buffer

    def _get_report_content(self, script_name):
        where_query = self._get_where_query()
        query = self._get_query(script_name, where_query)
        cr = self.env.cr
        cr.execute(query)
        data = self.env.cr.fetchall()
        content = '\r\n'.join([v[0] for v in data if v])
        return content.encode('ISO-8859-1', 'ignore')

    def _get_query(self, script_name, where_query):
        base_path = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(base_path, 'scripts', script_name)
        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()
        return script_content % where_query

    def _get_where_query(self):
        where_query = ""
        if self.start_date:
            where_query += """
                AND am.date >= '%s'
            """ % self.start_date.isoformat()
        if self.end_date:
            where_query += """
                AND am.date <= '%s'
            """ % self.end_date.isoformat()
        if self.company_id:
            where_query += """
                AND am.company_id = '%s'
            """ % self.company_id.id
        return where_query
