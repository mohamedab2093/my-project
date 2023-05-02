# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_round
class Product(models.Model):
    _inherit = 'product.template'
    fresh_type = fields.Selection(string="Fulfillment Type", selection=[('fresh', 'Fresh'), ('none_fresh', 'Non-Fresh'), ], copy=True, )