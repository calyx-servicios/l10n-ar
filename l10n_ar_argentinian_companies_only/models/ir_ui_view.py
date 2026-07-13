# -*- coding: utf-8 -*-
from odoo import api, models, tools


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    @api.model
    @tools.ormcache("self.env.cr.dbname", "modules_str_clean")
    def _ar_view_ids_for_modules(self, modules_str_clean):
        if not modules_str_clean:
            return ()

        modules = tuple(m for m in modules_str_clean.split(",") if m)
        if not modules:
            return ()

        return tuple(
            self.env["ir.model.data"].sudo().search([
                ("module", "in", modules),
                ("model", "=", "ir.ui.view"),
            ]).mapped("res_id")
        )

    @api.model
    def _get_inheriting_views_domain(self):
        domain = super()._get_inheriting_views_domain()

        company = self.env.company
        if company.country_id.code != "AR":
            param = self.env["ir.config_parameter"].sudo().get_param("ln10_ar_modules_views_only_ar_companies", "") or ""
            modules_str_clean = param.replace("\n", "").replace("\r", "").strip().replace(" ", "")

            ar_view_ids = self._ar_view_ids_for_modules(modules_str_clean)
            if ar_view_ids:
                domain += [("id", "not in", list(ar_view_ids))]

        return domain

