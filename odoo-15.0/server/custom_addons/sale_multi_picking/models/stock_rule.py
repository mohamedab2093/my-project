# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from datetime import date, datetime, time, timedelta
from odoo.fields import Date, Datetime
from odoo.tools import float_compare
import odoo.addons.decimal_precision as dp


class StockRule(models.Model):
    _inherit = 'stock.rule'
    def _get_custom_move_fields(self):
        res = super(StockRule, self)._get_custom_move_fields()
        res += ['fresh_type']
        return res
