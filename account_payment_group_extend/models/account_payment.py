from odoo import models, fields, api

def get_field_id_name(self, field, rec_id):
    if not rec_id:
        return False
    record = getattr(self, field).browse(rec_id)
    return (record.id, record.display_name)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        context = self.env.context
        res["receiptbook_id"] = get_field_id_name(self, "receiptbook_id", context.get("receiptbook_id", False))
        res["retencion_ganancias"] = context.get("retencion_ganancias", False)
        res["regimen_ganancias_id"] = get_field_id_name(self, "regimen_ganancias_id", context.get("regimen_ganancias_id", False))
        return res

    def onchange(self, values, field_names, fields_spec):
        res = super().onchange(values, field_names, fields_spec)
        if res.get("value"):
            context = self.env.context
            res["value"]["receiptbook_id"] = get_field_id_name(self, "receiptbook_id", context.get("receiptbook_id", False))
            res["value"]["retencion_ganancias"] = context.get("retencion_ganancias", False)
            res["value"]["regimen_ganancias_id"] = get_field_id_name(self, "regimen_ganancias_id", context.get("regimen_ganancias_id", False))
        return res
