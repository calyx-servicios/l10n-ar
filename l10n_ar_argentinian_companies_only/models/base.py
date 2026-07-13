# -*- coding: utf-8 -*-
from odoo import api, models



class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id=view_id, view_type=view_type, **options)

        # Company selector sets allowed_company_ids in the context
        allowed = tuple(self.env.context.get("allowed_company_ids") or ())
        current_company_id = self.env.company.id

        return key + (current_company_id, allowed)
