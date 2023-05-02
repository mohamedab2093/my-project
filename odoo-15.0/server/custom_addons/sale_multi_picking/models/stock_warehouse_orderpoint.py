# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from datetime import date, datetime, time, timedelta
from odoo.fields import Date, Datetime
from odoo.tools import float_compare
import odoo.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    def cron_minimum_stock_notification(self):
        obj = []
        points = self.sudo().search([])
        users = self.env.ref('sale_multi_picking.group_notification_minimum_qty').users
        for point in points:
            qty = 0
            quant_check = self.env['stock.quant'].sudo().search([
                ('product_id', '=', point.product_id.id),
                ('location_id', '=', point.location_id.id),
            ])
            if quant_check:
                qty = sum(quant_check.mapped('quantity')) - sum(quant_check.mapped('reserved_quantity'))
            if qty <= point.product_min_qty:
                obj.append({
                    'product_id': point.product_tmpl_id.id,
                    'product_name': point.product_tmpl_id.name,
                    'current_stock': qty,
                    'min_stock': point.product_min_qty,
                })
        if users:
            for user in users:
                template = self.env.ref('sale_multi_picking.mail_minimum_stock_alert')
                template.with_context(
                    obj=obj
                ).send_mail(user.id, raise_exception=True, force_send=True)

