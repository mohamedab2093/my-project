# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, Warning

class BarcodePlusTax1(models.Model):
    _name = "product.category"
    _inherit = "product.category"
