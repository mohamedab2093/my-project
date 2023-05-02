# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    # seller_id = fields.Many2one(
    #     related='product_id.seller_ids.name', string='supplier',
    #     domain=[('supplier_rank', '>', 0)],
    # )
    default_code = fields.Char('SKU', readonly=True)
