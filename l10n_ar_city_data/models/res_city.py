# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCity(models.Model):
    _inherit = 'res.city'

    unique_code = fields.Char(
        string='Unique Code',
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('res.city.unique.code'),
        help='Sequential unique identifier assigned automatically to every city as it is created.',
    )
    afip_code = fields.Char(
        string='AFIP Code',
        help='Official AFIP locality code, when the city comes from the AFIP locality table.',
    )

    _unique_code_uniq = models.Constraint(
        'UNIQUE(unique_code)',
        'The unique code of the city must be unique!',
    )
