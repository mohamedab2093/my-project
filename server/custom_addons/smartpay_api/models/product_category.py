import logging

from odoo import api, fields, models,_
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class ProductCategories(models.Model):
    _inherit = "product.category"

    tag_ids = fields.Many2many('product.tags', string='Tags', compute='compute_tags', store=True, readonly=1)

    # @api.depends('id', 'child_id')
    def compute_tags(self):
        for line in self:
            # child_id = line.child_id.ids
            product_ids = line.env['product.template'].search([('categ_id', 'child_of', line.id)])
            for product_id in product_ids:
                if not line.tag_ids:
                    line.tag_ids = product_id.tag_ids
                else:
                    line.tag_ids += product_id.tag_ids

class product_template(models.Model):
    _inherit = 'product.template'

    tag_ids = fields.Many2many('product.tags', string='Tags')

    @api.onchange('tag_ids')
    @api.multi
    def on_change_tag_ids(self):
        for product_id in self:
            if product_id.tag_ids:
                product_id.categ_id.tag_ids += product_id.tag_ids
            parent_categories = product_id.env['product.category'].search([('id', 'parent_of', product_id.categ_id.id)])
            for parent_category in parent_categories:
                parent_category.tag_ids += product_id.tag_ids