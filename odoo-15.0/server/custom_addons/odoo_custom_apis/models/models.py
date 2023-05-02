# -*- coding: utf-8 -*-

from odoo import models, fields
import string
import random
import re


class Users(models.Model):
    _name = 'res.users'
    _inherit = 'res.users'

    reset_password_code = fields.Char(string="Reset Password Code", )
    access_token = fields.Char(string="Access Token")
    user_type = fields.Selection(string="User Type", selection=[('registered', 'Registered'), ('guest', 'Guest'), ],
                                 default='guest', )
    reset_password_code = fields.Integer(string="Reset Password Code", required=False, )

    def generate_access_token(self):
        self.access_token = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase +
                                            string.digits, k=16))
        if not bool(re.search(r'\d', self.access_token)):
            self.generate_access_token()


class Company(models.Model):
    _inherit = 'res.company'

    default_cash_journal = fields.Many2one('account.journal', string="Default Cash Journal", )
    default_bank_journal = fields.Many2one('account.journal', string="Default Bank Journal",)
    
class Partner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    frontier_ref = fields.Char(string="Frontier Ref", required=False, )
    news_letter = fields.Boolean(string="News Letter", )


class Product(models.Model):
    _name = 'product.product'
    _inherit = 'product.product'

    frontier_ref = fields.Char(string="Frontier Ref", required=False, )
    special_price = fields.Monetary(string="Special Price",  currency_field='cost_currency_id', default=0.0)
    brand_id = fields.Many2one(comodel_name="product.brand", string="Brand", default=lambda s: s.product_tmpl_id.brand_id.id)
    school_id = fields.Many2one(related="product_tmpl_id.school_id")


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = 'product.template'

    sale_label = fields.Selection(string="Sale Label", selection=[('trending', 'Trending'), ('hot_sale', 'Hot Sale'), ('spl_offer', 'SPL Offer')], required=False, )
    brand_id = fields.Many2one(comodel_name="product.brand", string="Brand", required=False, )
    school_id = fields.Many2one(comodel_name="res.partner", string="School", domain=[('is_company', '=', True)], )


class ProductBrand(models.Model):
    _name = 'product.brand'
    _rec_name = 'name'
    _description = 'Product Brand'
    _inherit = ['image.mixin']

    name = fields.Char(string="Brand Name", required=True, )
    image_1920 = fields.Image("Brand Image", max_width=1920, max_height=1920)
    active = fields.Boolean(string="Active", default=True)
