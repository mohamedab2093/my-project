# -*- coding: utf-8 -*-
# This module and its content is copyright of Tamayozsoft.
# - © Tamayozsoft 2020. All rights reserved.

from odoo import api, fields, models, tools

class ProductCategory(models.Model):
    _inherit = 'product.category'

    provider_ids = fields.One2many('product_category.providerinfo', 'product_categ_id', 'Providers', help="Define product category providers.")

    # image: all image fields are base64 encoded and PIL-supported
    image = fields.Binary(
        "Image", attachment=True,
        help="This field holds the image used as image for the product, limited to 1024x1024px.")
    image_medium = fields.Binary(
        "Medium-sized image", attachment=True,
        help="Medium-sized image of the product. It is automatically "
             "resized as a 128x128px image, with aspect ratio preserved, "
             "only when the image exceeds one of those sizes. Use this field in form views or some kanban views.")
    image_small = fields.Binary(
        "Small-sized image", attachment=True,
        help="Small-sized image of the product. It is automatically "
             "resized as a 64x64px image, with aspect ratio preserved. "
             "Use this field anywhere a small image is required.")

    @api.model
    def create(self, vals):
        tools.image_resize_images(vals)
        return super(ProductCategory, self).create(vals)

    @api.multi
    def write(self, vals):
        tools.image_resize_images(vals)
        return super(ProductCategory, self).write(vals)

class ProviderInfo(models.Model):
    _name = "product_category.providerinfo"
    _description = "Service Category Provider"
    _order = 'sequence'

    provider_id = fields.Many2one('payment.acquirer', 'Provider',
                           domain=[('sevice_provider', '=', True)], required=True, help="Provider of this service category")
    product_categ_name = fields.Char('Provider Service Category Name')
    product_categ_code = fields.Char('Provider Service Category Code')
    sequence = fields.Integer('Sequence', default=1, help="Assigns the priority to the list of service category provider.")
    product_categ_id = fields.Many2one('product.category', 'Service Category', ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.user.company_id.id, index=1)
