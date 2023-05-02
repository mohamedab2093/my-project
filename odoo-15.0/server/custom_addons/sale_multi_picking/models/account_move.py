# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_round

class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    payment_method = fields.Char(string="Payment Method")

