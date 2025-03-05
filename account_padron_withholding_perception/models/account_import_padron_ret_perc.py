# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging, csv, psycopg2

_logger = logging.getLogger(__name__)


class AccountImportPadronRetPerc(models.Model):
    _name = 'account.import.padron.ret.perc'
    _description = _("Account import patterns withholding and perception")

    name = fields.Date('Date', required=True)
    ubication_file_import = fields.Char(string='Location File Import')
    ubication_file_ret_import = fields.Char(string='Location File Import 2 Ret')
    ubication_file_perc_import = fields.Char(string='Location File Import 3 Perc')
    padron_type_id = fields.Many2one('account.padron.retention.perception.type', string="Type Padron")
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close')
    ], string='State', default='open')
    type = fields.Selection([
        ('agip', 'AGIP'),
        ('arba', 'ARBA'),
        ('other', 'Other')
    ], string='Type', default='other')
    import_line_ids = fields.One2many('account.padron.retention.perception.line',
                            'import_padron_id', string='Import Lines', readonly=False)
    default_date_from = fields.Date('Default Date From')
    default_date_to = fields.Date('Default Date To')
    default_percentage_perception = fields.Float(string='Default Percentage Perception')
    default_percentage_retention = fields.Float(string='Default Percentage Retention')
# server fields
    server_host = fields.Char(string='Server Host')
    server_database = fields.Char(string='Server Database')
    server_user = fields.Char(string='Server User')
    server_password = fields.Char(string='Server Password')
    server_port = fields.Char(string='Server Port')


    def open2close(self, context=None):
        for import_obj in self:
            import_obj.sudo().write({'state': 'close'})

    def import_padron_server(self, context=None):
        partner_dic = {}
        for import_obj in self:
            _logger.info("import_padron_server()--> for %s" % str(import_obj))
            if context and 'partner_dic' in context:
                partner_dic = context['partner_dic']
            else:
                for partner_obj in import_obj.padron_type_id.line_partner_ids:
                    if not partner_obj.vat:
                        raise ValidationError(_("Error: The contact {} with ID({}) does not have a VAT identification number.".format(partner_obj.name, partner_obj.id)))
                    if partner_obj.l10n_latam_identification_type_id.country_id.code != 'AR':
                        raise ValidationError(_("Error: The contact {} with ID({}) is not from Argentina.".format(partner_obj.name, partner_obj.id)))
                    partner_dic[partner_obj.vat] = partner_obj

            date_from = str(import_obj.default_date_from)[
                :4] + str(import_obj.default_date_from)[5:7] + str(import_obj.default_date_from)[8:10]
            date_to = str(import_obj.default_date_to)[
                :4] + str(import_obj.default_date_to)[5:7] + str(import_obj.default_date_to)[8:10]
            if import_obj.type == 'agip':
                self.search_table_agip(
                    import_obj, partner_dic, date_from, date_to)
            if import_obj.type == 'arba':
                self.search_table_arba(
                    import_obj, partner_dic, date_from, date_to)
            if import_obj.type == 'other':
                self.search_table_other(
                    import_obj, partner_dic, date_from, date_to)

    def search_table_other(self, import_obj, partner_dic, date_from, date_to):
        for line_dicc in partner_dic:
            if partner_dic[line_dicc] != None:
                flag = True
                for line_obj in self.import_line_ids:
                    line_date_from_int = int(str(line_obj.date_from)[
                                             0:4] + str(line_obj.date_from)[5:7] + str(line_obj.date_from)[8:10])
                    if line_obj.partner_id.id == partner_dic[line_dicc].id and line_date_from_int == int(date_from):
                        flag = False
                    line_obj.create_arba_perception_line()
                if flag:
                    vals = {
                        'import_padron_id': import_obj.id,
                        'padron_type_id': import_obj.padron_type_id.id,
                        'cuit': partner_dic[line_dicc].vat,
                        'partner_id': partner_dic[line_dicc].id,
                        'date_from': import_obj.default_date_from,
                        'date_to': import_obj.default_date_to,
                        'percentage_perception': import_obj.default_percentage_perception,
                        'percentage_retention': import_obj.default_percentage_retention,

                    }
                    new_line = self.env[
                        'account.padron.retention.perception.line'].sudo().create(vals)
                    new_line.create_arba_perception_line()

    def _get_conn(self, import_obj):
        _logger.info("_get_conn: ")
        return psycopg2.connect(host=import_obj.server_host, port=import_obj.server_port, database=import_obj.server_database, user=import_obj.server_user, password=import_obj.server_password)

    def search_table_arba(self, import_obj, partner_dic, date_from, date_to):
        _logger.info("search_table_arba")
        # armar primero el where segun la columna que corresponda con los partner y las fechas
        # realizar la consulta y procesarla para volver en un dic como clave el cuil
        # col3 from,
        # col4 to,
        # col5 cuit,
        # col9 monto,
        # xX;xx     ;from     ;to;    ; cuit      :x:x:x:monto;x
        # P;26032019;01042019;30042019;20000000028;D;N;N;6,00;25;
        # P;26032019;01042019;30042019;20000021742;D;S;N;0,00;01;

        # filtros de cuit
        where = ' where col5 in ('
        for partner in partner_dic:
            where += str(partner) + ','
        where = where[:-1] + ') '
        # filtros de fechas que se comenta hasta que este bien la base de datos
        # importada
        # if date_to and date_from:
        #     date_to_string = str(date_to)[8:10] + \
        #         str(date_to)[5:7] + str(date_to)[:4]
        #     date_from_string = str(date_from)[
        #         8:10] + str(date_from)[5:7] + str(date_from)[:4]
        #     where += ' and (col3<=%s and col4>=%s);' % (date_from_string,
        #                                                 date_to_string)
        conn = None
        flag_month = False
        #####################################################
        # PARA LAS RETENCIONES
        ######################################################
        consulta = 'select col3,col4,col5,col9 from arbaret' + where

        conn = self._get_conn(import_obj)
        cur = conn.cursor()
        cur.execute(consulta)
        for line in cur.fetchall():
            string_from = str(line[0])
            if len(string_from) < 8:
                string_from = '0' + string_from
            date_from_server = string_from[
                4:8] + string_from[2:4] + string_from[:2]

            string_to = str(line[1])
            if len(string_to) < 8:
                string_to = '0' + string_to
            date_to_server = string_to[4:8] + \
                string_to[2:4] + string_to[:2]

            if int(date_from) <= int(date_from_server) and int(date_to) >= int(date_to_server):
                flag_month = True
                flag = True
                for line_obj in self.import_line_ids:
                    line_date_from_int = int(str(line_obj.date_from)[
                                                0:4] + str(line_obj.date_from)[5:7] + str(line_obj.date_from)[8:10])
                    if line_obj.partner_id.id == partner_dic[str(line[2])].id and line_date_from_int == int(date_from):
                        flag = False
                        percentage_retention = (str(line[3]).replace('.', '')).replace(',', '.')
                        vals = {
                            'percentage_retention': percentage_retention,
                        }
                        line_obj.sudo().write(vals)
                if flag:
                    percentage_retention = (
                        str(line[3]).replace('.', '')).replace(',', '.')
                    if type(date_from) == str:
                        date_from_final = date_from[0:4] + '-' + date_from[4:6] + '-'  + date_from[6:8]
                    else:
                        date_from_final = date_from
                    if type(date_to) == str:
                        date_to_final = date_to[0:4] + '-' + date_to[4:6] + '-'  + date_to[6:8]
                    else:
                        date_to_final = date_to
                    vals = {
                        'import_padron_id': import_obj.id,
                        'padron_type_id': import_obj.padron_type_id.id,
                        'cuit': line[2],
                        'partner_id': partner_dic[str(line[2])].id,
                        'date_from': date_from_final,
                        'date_to': date_to_final,
                        'percentage_perception': import_obj.default_percentage_perception,
                        'percentage_retention': percentage_retention,
                    }
                    new_line = self.env[
                        'account.padron.retention.perception.line'].sudo().create(vals)
        cur.close()
        ######################################################
        # PARA LAS PERCEPCIONES
        ######################################################
        consulta = 'select col3,col4,col5,col9 from arbaper' + where
        conn = self._get_conn(import_obj)
        cur = conn.cursor()
        cur.execute(consulta)

        for line in cur.fetchall():
            string_from = str(line[0])
            if len(string_from) < 8:
                string_from = '0' + string_from
            date_from_server = string_from[
                4:8] + string_from[2:4] + string_from[:2]

            string_to = str(line[1])
            if len(string_to) < 8:
                string_to = '0' + string_to
            date_to_server = string_to[4:8] + \
                string_to[2:4] + string_to[:2]

            if int(date_from) <= int(date_from_server) and int(date_to) >= int(date_to_server):
                flag_month = True
                flag = True
                for line_obj in self.import_line_ids:
                    line_date_from_int = int(str(line_obj.date_from)[
                                                0:4] + str(line_obj.date_from)[5:7] + str(line_obj.date_from)[8:10])
                    if line_obj.partner_id.id == partner_dic[str(line[2])].id and line_date_from_int == int(date_from):
                        flag = False
                        percentage_perception = (
                            str(line[3]).replace('.', '')).replace(',', '.')
                        vals = {
                            'percentage_perception': percentage_perception,  # percentage_perception
                        }
                        line_obj.sudo().write(vals)
                if flag:
                    percentage_perception = (
                        str(line[3]).replace('.', '')).replace(',', '.')
                    vals = {
                        'import_padron_id': import_obj.id,
                        'padron_type_id': import_obj.padron_type_id.id,
                        'cuit': line[2],
                        'partner_id': partner_dic[str(line[2])].id,
                        'date_from': date_from_final,
                        'date_to': date_to_final,
                        'percentage_perception': percentage_perception,
                        'percentage_retention': import_obj.default_percentage_retention,
                    }
                    new_line = self.env[
                        'account.padron.retention.perception.line'].sudo().create(vals)
        cur.close()
        if conn is not None:
            conn.close()
        if flag_month:
            for line_dicc in partner_dic:
                if partner_dic[line_dicc] != None:
                    flag = True
                    for line_obj in self.import_line_ids:
                        line_date_from_int = int(str(line_obj.date_from)[
                                                 0:4] + str(line_obj.date_from)[5:7] + str(line_obj.date_from)[8:10])
                        if line_obj.partner_id.id == partner_dic[line_dicc].id and line_date_from_int == int(date_from):
                            flag = False
                        line_obj.create_arba_perception_line()
                    if flag:
                        vals = {
                            'import_padron_id': import_obj.id,
                            'padron_type_id': import_obj.padron_type_id.id,
                            'cuit': partner_dic[line_dicc].vat,
                            'partner_id': partner_dic[line_dicc].id,
                            'date_from': import_obj.default_date_from,
                            'date_to': import_obj.default_date_to,
                            'percentage_perception': import_obj.default_percentage_perception,
                            'percentage_retention': import_obj.default_percentage_retention,
                        }
                        new_line = self.env[
                            'account.padron.retention.perception.line'].sudo().create(vals)
                        new_line.create_arba_perception_line()
        else:
            date_to_string = str(date_to)[6:8]+"/"+str(date_to)[4:6]+"/"+str(date_to)[:4]
            date_from_string = str(date_from)[6:8]+"/"+str(date_from)[4:6]+"/"+str(date_from)[:4]
            msg = _("No records were found for ARBA Padron Type {} between the dates {} and {}".format(import_obj.padron_type_id.name, date_from_string, date_to_string))
            for partner in partner_dic.values():
                partner.process_partner_data(import_obj)
                partner.message_post(body=msg)

    # METODO DE TABLA AGIP
    def search_table_agip(self, import_obj, partner_dic, date_from, date_to):
        # armar primero el where segun la columna que corresponda con los partner y las fechas
        # realizar la consulta y procesarla para volver en un dic como clave el cuil
        # col2 from,
        # col3 to,
        # col4 cuit,
        # xxx;from;to;cuit;x;x;x;percep;retenc;x;x;nombre
        # 21032019;01042019;30042019;20000962997;C;S;N;3,00;3,00;00;00;FINCATI
        # MARIA DOLORES

        # filtros de cuit
        where = ' where col4 in ('
        for partner in partner_dic:
            where += str(partner) + ','
        where = where[:-1] + ') '
        # filtros de fechas
        if False:  # date_to and date_from:
            date_to_string = str(date_to)[8:10] + \
                str(date_to)[5:7] + str(date_to)[:4]
            date_from_string = str(date_from)[
                8:10] + str(date_from)[5:7] + str(date_from)[:4]
            where += ' and (col2<=%s and col3>=%s);' % (date_from_string,
                                                        date_to_string)

        conn = None
        flag_month = False
        consulta = 'select col2,col3,col4,col8,col9 from agip' + where
        conn = self._get_conn(import_obj)
        cur = conn.cursor()
        cur.execute(consulta)
        for line in cur.fetchall():
            string_from = str(line[0])
            if len(string_from) < 8:
                string_from = '0' + string_from
            date_from_server = string_from[
                4:8] + string_from[2:4] + string_from[:2]

            string_to = str(line[1])
            if len(string_to) < 8:
                string_to = '0' + string_to
            date_to_server = string_to[4:8] + \
                string_to[2:4] + string_to[:2]

            if int(date_from) <= int(date_from_server) and int(date_to) >= int(date_to_server):
                flag_month = True
                flag = True
                for line_obj in self.import_line_ids:
                    line_date_from_int = int(str(line_obj.date_from)[
                                                0:4] + str(line_obj.date_from)[5:7] + str(line_obj.date_from)[8:10])
                    if line_obj.partner_id.id == partner_dic[str(line[2])].id and line_date_from_int == int(date_from):
                        flag = False
                if flag:
                    percentage_perception = (
                        str(line[3]).replace('.', '')).replace(',', '.')
                    percentage_retention = (
                        str(line[4]).replace('.', '')).replace(',', '.')
                    if type(date_from) == str:
                        date_from_final = date_from[0:4] + '-' + date_from[4:6] + '-'  + date_from[6:8]
                    else:
                        date_from_final = date_from
                    if type(date_to) == str:
                        date_to_final = date_to[0:4] + '-' + date_to[4:6] + '-'  + date_to[6:8]
                    else:
                        date_to_final = date_to
                    vals = {
                        'import_padron_id': import_obj.id,
                        'padron_type_id': import_obj.padron_type_id.id,
                        'cuit': line[2],
                        'partner_id': partner_dic[str(line[2])].id,
                        'date_from': date_from_final,
                        'date_to': date_to_final,
                        'percentage_perception': percentage_perception,
                        'percentage_retention': percentage_retention,
                    }
                    move = self.env[
                        'account.padron.retention.perception.line'].sudo().create(vals)
                    move.create_arba_perception_line()
                    partner_dic[line[3]] = None
        cur.close()
        if conn is not None:
            conn.close()
        if flag_month:
            for line_dicc in partner_dic:
                if partner_dic[line_dicc] != None:
                    flag = True
                    for line_obj in self.import_line_ids:
                        line_date_from_int = int(str(line_obj.date_from)[
                                                 0:4] + str(line_obj.date_from)[5:7] + str(line_obj.date_from)[8:10])
                        if line_obj.partner_id.id == partner_dic[line_dicc].id and line_date_from_int == int(date_from):
                            flag = False
                    if flag:
                        vals = {
                            'import_padron_id': import_obj.id,
                            'padron_type_id': import_obj.padron_type_id.id,
                            'cuit': partner_dic[line_dicc].vat,
                            'partner_id': partner_dic[line_dicc].id,
                            'date_from': import_obj.default_date_from,
                            'date_to': import_obj.default_date_to,
                            'percentage_perception': import_obj.default_percentage_perception,
                            'percentage_retention': import_obj.default_percentage_retention,
                        }
                        move = self.env[
                            'account.padron.retention.perception.line'].sudo().create(vals)
                        move.create_arba_perception_line()
        else:
            date_to_string = str(date_to)[6:8]+"/"+str(date_to)[4:6]+"/"+str(date_to)[:4]
            date_from_string = str(date_from)[6:8]+"/"+str(date_from)[4:6]+"/"+str(date_from)[:4]
            msg = _("No records were found for AGIP Padron Type{} between the dates {} and {}".format(import_obj.padron_type_id.name, date_from_string, date_to_string))
            for partner in partner_dic.values():
                partner.process_partner_data(import_obj)
                partner.message_post(body=msg)

    ###########################################
    # PARA EL USO DE ARCHIVOS EN EL SERVIDOR
    ###########################################
    def import_padron_file(self, context=None):
        partner_dic = {}
        for import_obj in self:
            for partner_obj in import_obj.padron_type_id.line_partner_ids:
                partner_dic[partner_obj.vat] = partner_obj
            self.import_partner_file(partner_dic=partner_dic)

    def import_partner_file(self, context=None, partner_dic={}):
        """
        Importar los datos de los archivos en sus respectivas lineas
        """
        for import_obj in self:
            # PARA UN ARCHIVO SOLO..
            if import_obj.ubication_file_import:
                with open(import_obj.ubication_file_import, encoding="ISO-8859-1") as csvfile:
                    readCSV = csv.reader(csvfile, delimiter=';')
                    for row in readCSV:
                        if row[3] in partner_dic and partner_dic[row[3]]:
                            flag = True
                            # xxx;from;to;cuit;x;x;x;percep;retenc;x;x;nombre
                            # 21032019;01042019;30042019;20000962997;C;S;N;3,00;3,00;00;00;FINCATI
                            # MARIA DOLORES
                            percentage_perception = (
                                str(row[7]).replace('.', '')).replace(',', '.')
                            percentage_retention = (
                                str(row[8]).replace('.', '')).replace(',', '.')

                            date_from = str(row[1])[
                                :2] + '/' + str(row[1])[2:4] + '/' + str(row[1])[4:8]
                            date_to = str(row[2])[
                                :2] + '/' + str(row[2])[2:4] + '/' + str(row[2])[4:8]

                            line_obj_aux = None
                            for line_obj in self.import_line_ids.filtered(lambda line_obj: line_obj.partner_id.id == partner_dic[row[3]].id):
                                if line_obj.date_to == date_to:
                                    line_obj_aux = line_obj

                            if line_obj_aux:
                                flag = False
                                vals = {
                                    'import_padron_id': import_obj.id,
                                    'padron_type_id': import_obj.padron_type_id.id,
                                    'cuit': row[3],
                                    'partner_id': partner_dic[row[3]].id,
                                    'date_from': date_from,
                                    'date_to': date_to,
                                    'percentage_perception': percentage_perception,
                                    'percentage_retention': percentage_retention,
                                }
                                line_obj_aux.sudo().write(vals)
                                line_obj_aux.create_arba_perception_line()

                            if flag:
                                vals = {
                                    'import_padron_id': import_obj.id,
                                    'padron_type_id': import_obj.padron_type_id.id,
                                    'cuit': row[3],
                                    'partner_id': partner_dic[row[3]].id,
                                    'date_from': date_from,
                                    'date_to': date_to,
                                    'percentage_perception': percentage_perception,
                                    'percentage_retention': percentage_retention,
                                }
                                move = self.env[
                                    'account.padron.retention.perception.line'].create(vals)
                                move.create_arba_perception_line()
                            partner_dic[row[3]] = None

            # PARA AMBOS ARCHIVOS
            partner_dic_write_obj = {}
            partner_dic_write_data = {}
            partner_dic_create = {}

            if import_obj.ubication_file_ret_import:  # and import_obj.ubication_file_perc_import
                with open(import_obj.ubication_file_ret_import, encoding="ISO-8859-1") as csvfile:
                    readCSV = csv.reader(csvfile, delimiter=';')
                    for row in readCSV:
                        if row[4] in partner_dic and partner_dic[row[4]]:
                            flag = True
                            # xX;xx     ;from     ;to;    ; cuit      :x:x:x:monto;x
                            # P;26032019;01042019;30042019;20000000028;D;N;N;6,00;25;
                            # P;26032019;01042019;30042019;20000021742;D;S;N;0,00;01;
                            #percentage_perception = (str(row[9]).replace('.','')).replace(',','.')
                            percentage_retention = (
                                str(row[9]).replace('.', '')).replace(',', '.')

                            date_from = str(row[2])[
                                :2] + '/' + str(row[2])[2:4] + '/' + str(row[2])[4:8]
                            date_to = str(row[3])[
                                :2] + '/' + str(row[3])[2:4] + '/' + str(row[3])[4:8]

                            line_obj_aux = None
                            for line_obj in self.import_line_ids.filtered(lambda line_obj: line_obj.partner_id.id == partner_dic[row[4]].id):
                                if line_obj.date_to == date_to:
                                    line_obj_aux = line_obj

                            if line_obj_aux:
                                flag = False
                                row[4]
                                partner_dic_write_obj[row[4]] = line_obj_aux
                                vals = {
                                    'import_padron_id': import_obj.id,
                                    'padron_type_id': import_obj.padron_type_id.id,
                                    'cuit': row[4],
                                    'partner_id': partner_dic[row[4]].id,
                                    'date_from': date_from,
                                    'date_to': date_to,
                                    'percentage_retention': percentage_retention,
                                }
                                partner_dic_write_data[row[4]] = vals

                            if flag:
                                vals = {
                                    'import_padron_id': import_obj.id,
                                    'padron_type_id': import_obj.padron_type_id.id,
                                    'cuit': row[4],
                                    'partner_id': partner_dic[row[4]].id,
                                    'date_from': date_from,
                                    'date_to': date_to,
                                    'percentage_perception': import_obj.default_percentage_perception,
                                    'percentage_retention': percentage_retention,
                                }
                                partner_dic_create[row[4]] = vals

            if import_obj.ubication_file_perc_import:
                with open(import_obj.ubication_file_perc_import, encoding="ISO-8859-1") as csvfile:
                    readCSV = csv.reader(csvfile, delimiter=';')
                    for row in readCSV:
                        if row[4] in partner_dic and partner_dic[row[4]]:
                            flag = True
                            # xX;xx     ;from     ;to;    ; cuit      :x:x:x:monto;x
                            # P;26032019;01042019;30042019;20000000028;D;N;N;6,00;25;
                            # P;26032019;01042019;30042019;20000021742;D;S;N;0,00;01;
                            percentage_perception = (
                                str(row[9]).replace('.', '')).replace(',', '.')

                            date_from = str(row[2])[
                                :2] + '/' + str(row[2])[2:4] + '/' + str(row[2])[4:8]
                            date_to = str(row[3])[
                                :2] + '/' + str(row[3])[2:4] + '/' + str(row[3])[4:8]

                            line_obj_aux = None
                            for line_obj in self.import_line_ids.filtered(lambda line_obj: line_obj.partner_id.id == partner_dic[row[4]].id):
                                if line_obj.date_to == date_to:
                                    line_obj_aux = line_obj

                            if line_obj_aux:
                                flag = False
                                if row[4] in partner_dic_write_obj:
                                    partner_dic_write_obj[row[4]][
                                        'percentage_perception'] = percentage_perception
                                else:
                                    vals = {
                                        'import_padron_id': import_obj.id,
                                        'padron_type_id': import_obj.padron_type_id.id,
                                        'cuit': row[4],
                                        'partner_id': partner_dic[row[4]].id,
                                        'date_from': date_from,
                                        'date_to': date_to,
                                        'percentage_perception': percentage_perception,
                                    }
                                    partner_dic_write_obj[
                                        row[4]] = line_obj_aux
                                    partner_dic_write_data[row[4]] = vals

                            if flag:
                                if row[4] in partner_dic_create:
                                    partner_dic_create[row[4]][
                                        'percentage_perception'] = percentage_perception
                                else:
                                    vals = {
                                        'import_padron_id': import_obj.id,
                                        'padron_type_id': import_obj.padron_type_id.id,
                                        'cuit': row[4],
                                        'partner_id': partner_dic[row[4]].id,
                                        'date_from': date_from,
                                        'date_to': date_to,
                                        'percentage_perception': percentage_perception,
                                        'percentage_retention': import_obj.default_percentage_retention,
                                    }
                                    partner_dic_create[row[4]] = line_obj_aux
                                    partner_dic_create[row[4]] = vals

            for line_dicc in partner_dic_write_obj:
                partner_dic[line_dicc] = None
                partner_dic_write_obj[line_dicc].write(
                    partner_dic_write_data[line_dicc])
                partner_dic_write_obj[line_dicc].create_arba_perception_line()

            for line_dicc in partner_dic_create:
                partner_dic[line_dicc] = None
                move = self.env['account.padron.retention.perception.line'].sudo().create(
                    partner_dic_create[line_dicc])
                move.create_arba_perception_line()

            # FINAL PARA LOS MONTOS POR DEFAULTS
            for line_dicc in partner_dic:
                if partner_dic[line_dicc] != None:
                    flag = True
                    for line_obj in self.import_line_ids:
                        if line_obj.partner_id.id == partner_dic[line_dicc].id:
                            if line_obj.date_to == date_to:
                                flag = False
                    if flag:
                        vals = {
                            'import_padron_id': import_obj.id,
                            'padron_type_id': import_obj.padron_type_id.id,
                            'cuit': partner_dic[line_dicc].vat,
                            'partner_id': partner_dic[line_dicc].id,
                            'date_from': import_obj.default_date_from,
                            'date_to': import_obj.default_date_to,
                            'percentage_perception': import_obj.default_percentage_perception,
                            'percentage_retention': import_obj.default_percentage_retention,
                        }
                        move = self.env[
                            'account.padron.retention.perception.line'].sudo().create(vals)
                        move.create_arba_perception_line()
