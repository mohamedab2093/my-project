# -*- coding: utf-8 -*-
import json
import time
from ast import literal_eval
from datetime import date, timedelta
from itertools import groupby
from operator import attrgetter, itemgetter
from collections import defaultdict

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_datetime
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.tools.misc import format_date


from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

# class StockMoveInherit(models.Model):
#     _inherit = 'stock.move'
#     @api.constrains('picking_id')
#     def check_picking_id_from_move(self):
#         for rec in self:
#             if rec.picking_id:
#                 if rec.fresh_type == 'fresh':
#                     # sequence = self.env['ir.sequence'].next_by_code('fresh.picking')
#                     sequence = '%s/F' % self.origin
#                     rec.picking_id.sudo().write({
#                         'is_fresh': True,
#                         'name': sequence,
#                     })
#                 if rec.fresh_type == 'none_fresh':
#                     # sequence = self.env['ir.sequence'].next_by_code('nonfresh.picking')
#                     sequence = '%s/NF' % self.origin
#                     rec.picking_id.sudo().write({
#                         'is_non_fresh': True,
#                         'name': sequence,
#                     })
#                 if not rec.fresh_type:
#                     sequence = '%s' % self.origin
#                     rec.picking_id.sudo().write({
#                         'name': sequence,
#                     })
class Stock_pickingType(models.Model):
    _inherit = "stock.picking.type"

    # count_picking_ready_waiting = fields.Integer(compute="_compute_picking_count")
    incoming_picking_ready_waiting = fields.Integer(compute="_compute_count")
    outgoing_picking_ready_waiting = fields.Integer(compute="_compute_count")
    internal_picking_ready_waiting = fields.Integer(compute="_compute_count")

    def _compute_count(self):
        stock_picking = self.env['stock.picking']
        for rec in self:
            rec.incoming_picking_ready_waiting = stock_picking.search_count([
                ('picking_type_code', '=', 'incoming'),
                ('state', 'in', ['assigned', 'confirmed'])
            ])
            rec.outgoing_picking_ready_waiting = stock_picking.search_count([
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'in', ['assigned', 'confirmed'])
            ])
            rec.internal_picking_ready_waiting = stock_picking.search_count([
                ('picking_type_code', '=', 'internal'),
                ('state', 'in', ['assigned', 'confirmed'])
            ])

    # def _compute_picking_count(self):
    #     domains = {
    #         'count_picking_draft': [('state', '=', 'draft')],
    #         'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting'))],
    #         'count_picking_ready_waiting': [('state', 'in', ('assigned', 'waiting'))],
    #         'count_picking_ready': [('state', '=', 'assigned')],
    #         'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed'))],
    #         'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed'))],
    #         'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting'))],
    #     }
    #     print("zzzzzzzzzzzzzzzzzzzzzzzzzzz")
    #     print(domains)
    #     for field in domains:
    #         data = self.env['stock.picking'].read_group(domains[field] +
    #             [('state', 'not in', ('done', 'cancel')), ('picking_type_id', 'in', self.ids)],
    #             ['picking_type_id'], ['picking_type_id'])
    #         data2 = self.env['stock.picking'].search([('state', 'in', ('assigned', 'waiting'))],)
    #         print(data2)
    #         count = {
    #             x['picking_type_id'][0]: x['picking_type_id_count']
    #             for x in data if x['picking_type_id']
    #         }
    #         for record in self:
    #             record[field] = count.get(record.id, 0)
