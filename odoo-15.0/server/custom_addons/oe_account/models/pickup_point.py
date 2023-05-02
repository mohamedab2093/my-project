# -*- coding: utf-8 -*-

from odoo import models, fields


class PickupPoint(models.Model):
    _name = 'pickup.point'
    _inherit = ['mail.thread']
    _description = "Pickup Point"
    _order = "id desc"

    name = fields.Char(string='Name', required=1, tracking=1)
    address = fields.Char(string='Address', tracking=1)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The pickup point name must be unique !')
    ]
