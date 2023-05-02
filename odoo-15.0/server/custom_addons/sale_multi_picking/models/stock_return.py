# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class StockPickingInherit(models.Model):
    _inherit = "stock.picking"

    origin_picking_id = fields.Many2one('stock.picking', string="Origin Picking")
    picking_return_name = fields.Char(string="Origin Picking Return Name")
    products_html = fields.Text(string="Products HTML", compute="_compute_products_text")

    @api.constrains('move_ids_without_package')
    def _compute_products_text(self):
        for rec in self:
            html = 'Products'
            for line in rec.move_ids_without_package:
                html += ',%s - Qty: %s' % (line.product_id.name,line.product_uom_qty)
            rec.products_html = html

    def generate_backorder_name(self, name):
        for seq in range(200):
            if seq == 0:
                continue
            c_name = '%s/B/%s' % (name,seq)
            check = self.env['stock.picking'].sudo().search([
                ('name', '=', c_name)
            ])
            if not check:
                return c_name

    @api.model
    def create(self, vals):
        print("HELLO {}".format(vals))
        if vals.get('picking_return_name'):
            vals['name'] = vals['picking_return_name']
        if vals.get('backorder_id'):
            get_picking = self.env['stock.picking'].sudo().browse(vals.get('backorder_id'))
            vals['name'] = self.generate_backorder_name(get_picking.name)

        return super(StockPickingInherit, self).create(vals)

    def write(self, vals):
        for rec in self:
            if rec.backorder_id:
                vals['name'] = self.generate_backorder_name(rec.backorder_id.name)
            if vals.get('name') and vals.get('name') == 'False':
                del vals['name']
            if vals.get('name') and rec.picking_return_name:
                del vals['name']
        return super(StockPickingInherit, self).write(vals)
        

class StockReturnPickingInherit(models.TransientModel):
    _inherit = 'stock.return.picking'


    def generate_return_name(self, name):
        for seq in range(200):
            if seq == 0:
                continue
            c_name = '%s/R/%s' % (name,seq)
            check = self.env['stock.picking'].sudo().search([
                ('name', '=', c_name)
            ])
            if not check:
                return c_name

    def _prepare_picking_default_values(self):
        res = super(StockReturnPickingInherit, self)._prepare_picking_default_values()
        res['origin_picking_id'] = self.picking_id.id
        res['picking_return_name'] = self.generate_return_name(self.picking_id.name)
        print(res)
        return res