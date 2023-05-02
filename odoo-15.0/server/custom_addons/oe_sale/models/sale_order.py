# -*- coding: utf-8 -*-

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    pickup_point_id = fields.Many2one(
        'pickup.point', string='Pickup Point',
        required=1, ondelete='restrict',
    )
    external_id = fields.Char(string="External ID", readonly=1)
    action_id = fields.Char(string="Action ID", readonly=1)
    is_fresh = fields.Boolean(string='Is Fresh', compute='_fresh_and_non_fresh', store=True)
    is_non_fresh = fields.Boolean(string='Is Non-Fresh', compute='_fresh_and_non_fresh', store=True)

    @api.depends('order_line.product_id')
    def _fresh_and_non_fresh(self):
        for record in self:
            products = record.order_line.mapped('product_id')
            record.is_fresh = True if products.filtered(lambda prod: prod.fresh_type == 'fresh') else False
            record.is_non_fresh = True if products.filtered(lambda prod: prod.fresh_type == 'none_fresh') else False

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals['pickup_point_id'] = self.pickup_point_id.id
        invoice_vals['external_id'] = self.external_id
        invoice_vals['action_id'] = self.action_id
        return invoice_vals
