# -*- coding: utf-8 -*-
from math import ceil

import requests
import base64
import random
import logging

_logger = logging.getLogger(__name__)
from odoo import http, SUPERUSER_ID, _
from odoo.http import request, Response
from odoo.exceptions import AccessDenied


class ForntierApis(http.Controller):

    def _check_token(self, token=None):
        """
            - Check if the token is exist in store.screen
        """
        user_token = request.env['res.users'].with_user(SUPERUSER_ID).search([('access_token', '=', token)], limit=1)
        return user_token or False

    def _check_required_values(self, data=None, keys=None):
        missing_data = []
        if keys and data:
            for key in keys:
                if not all([key in data, data.get(key)]):
                    missing_data.append(key)
        return missing_data or False

    @http.route('/api/user/singup', type='json', auth='public', methods=['POST'], sitemap=False, csrf=False)
    def user_signup(self, **kw):
        required_values = ['first_name', 'last_name', 'email', 'phone', 'image', 'news_letter', 'country_id', 'state',
                           'street', 'po_box', 'notes', 'username', 'password', 'type']
        if kw:
            missing_values = self._check_required_values(data=kw, keys=required_values)
            if missing_values:
                message = "Missing parameters: %s !" % ', '.join(missing_values)
                response = {'result': {'code': 400, 'message': message}}
                Response.status = "400"
                return response
        else:
            response = {"result": {"code": 400, "message": "All data are missing!"}}
            Response.status = "400"
            return response

        full_name = ' '.join([kw.get('first_name'), kw.get('last_name')])
        image = base64.b64encode(requests.get(kw.get('image').strip()).content).replace(b'\n', b'')

        created_partner = request.env['res.partner'].with_user(SUPERUSER_ID).create(
            {'name': full_name, 'email': kw.get('email'),
             'phone': kw.get('phone'), 'image_1920': image,
             'news_letter': kw.get('news_letter'),
             'country_id': kw.get('country_id'),
             'city': kw.get('state'), 'street': kw.get('street'),
             'zip': kw.get('po_box'), 'comment': kw.get('notes'),
             })

        default_user_ids = request.env['portal.wizard'].sudo().with_context(
            {'active_ids': [created_partner.id]})._default_user_ids()
        portal_user = request.env['portal.wizard'].sudo().with_context({'default_user_ids': default_user_ids}).create(
            {})
        portal_user.user_ids.write({'in_portal': True})
        portal_user.with_user(SUPERUSER_ID).action_apply()
        related_user = request.env['res.users'].with_user(SUPERUSER_ID).search(
            [('partner_id', '=', created_partner.id)])
        related_user.write({'login': kw.get('username'), 'password': kw.get('password'), 'user_type': kw.get('type')})
        related_user.generate_access_token()

        if related_user and created_partner:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "User Created successfully",
                                   "data": {"access_token": related_user.access_token}}}
            return response
        else:
            Response.status = "401"
            response = {"result": {"code": 401, "message": "Something went wrong during registration"}}
            return response

    @http.route('/api/user/singin', type='json', auth='public', methods=['POST'], sitemap=False, csrf=False)
    def user_signin(self, **kw):
        required_values = ['username', 'password']
        if kw:
            missing_values = self._check_required_values(data=kw, keys=required_values)
            if missing_values:
                message = "Missing parameters: %s !" % ', '.join(missing_values)
                response = {'result': {'code': 400, 'message': message}}
                Response.status = "400"
                return response
        else:
            response = {"result": {"code": 400, "message": "All data are missing!"}}
            Response.status = "400"
            return response

        try:
            user_env = request.env['res.users']
            user = user_env.with_user(SUPERUSER_ID).search([('login', '=', kw.get('username'))])
            user_env.with_user(user)._check_credentials(password=kw.get('password'),
                                                        user_agent_env={'interactive': False})
        except AccessDenied:
            response = {"result": {"code": 400, "message": "Either Username or Password is incorrect"}}
            Response.status = "400"
            return response

        Response.status = "200"
        response = {"result": {"code": 200, "message": "User Logged In successfully",
                               "data": {"name": user.partner_id.name, "email": user.partner_id.email,
                                        "phone": user.partner_id.phone,
                                        "news_letter": user.partner_id.news_letter,
                                        "access_token": user.access_token}}}
        return response

    @http.route('/api/user/get_reset_password_code', type='json', auth='public', methods=['POST'], sitemap=False,
                csrf=False)
    def get_reset_password_code(self, **kw):
        required_values = ['username', 'password']
        if kw:
            missing_values = self._check_required_values(data=kw, keys=required_values)
            if missing_values:
                message = "Missing parameters: %s !" % ', '.join(missing_values)
                response = {'result': {'code': 400, 'message': message}}
                Response.status = "400"
                return response
        else:
            response = {"result": {"code": 400, "message": "All data are missing!"}}
            Response.status = "400"
            return response

        try:
            user_env = request.env['res.users']
            user = user_env.with_user(SUPERUSER_ID).search([('login', '=', kw.get('username'))])
            user_env.with_user(user)._check_credentials(password=kw.get('password'),
                                                        user_agent_env={'interactive': False})
        except AccessDenied:
            response = {"result": {"code": 400, "message": "Either Username or Password is incorrect"}}
            Response.status = "400"
            return response

        if user:
            # TODO: Send Email with the verification code
            # FIXME: Remove "reset_password_code" from response
            user.sudo().write({'reset_password_code': random.randint(1000, 9999)})
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Verification Code has been sent to User's email",
                                   "data": {"reset_password_code": user.reset_password_code}}}
            return response

    @http.route('/api/verify_reset_password_code', type='json', auth='public', methods=['POST'], sitemap=False,
                csrf=False)
    def verify_reset_password_code(self, **kw):
        required_values = ['username', 'confirm_code']
        if kw:
            missing_values = self._check_required_values(data=kw, keys=required_values)
            if missing_values:
                message = "Missing parameters: %s !" % ', '.join(missing_values)
                response = {'result': {'code': 400, 'message': message}}
                Response.status = "400"
                return response
        else:
            response = {"result": {"code": 400, "message": "All data are missing!"}}
            Response.status = "400"
            return response
        sudo_user = request.env['res.users'].with_user(SUPERUSER_ID)
        user = sudo_user.search(
            [('login', '=', kw.get('username')), ('reset_password_code', '=', kw.get('confirm_code'))], limit=1)
        if user:
            Response.status = "200"
            return {
                'statue': True,
            }
        else:
            Response.status = "400"
            return {
                'statue': False,
                'error': "Either confirmation code or Email is not correct!"
            }

    @http.route('/api/reset_password', type='json', auth='public', methods=['POST'], sitemap=False, csrf=False)
    def reset_password(self, **kw):
        required_values = ['username', 'confirm_code', 'new_password', 'confirm_password']
        if kw:
            missing_values = self._check_required_values(data=kw, keys=required_values)
            if missing_values:
                message = "Missing parameters: %s !" % ', '.join(missing_values)
                response = {'result': {'code': 400, 'message': message}}
                Response.status = "400"
                return response
        else:
            response = {"result": {"code": 400, "message": "All data are missing!"}}
            Response.status = "400"
            return response

        if not kw.get('new_password') == kw.get('confirm_password'):
            response = {"result": {"code": 400, "message": "Passwords are not matching"}}
            Response.status = "400"
            return response

        sudo_user = request.env['res.users'].with_user(SUPERUSER_ID)
        user = sudo_user.search(
            [('login', '=', kw.get('username')), ('reset_password_code', '=', kw.get('confirm_code'))], limit=1)

        if user:
            user.with_user(SUPERUSER_ID).write({'password': kw.get('new_password'), 'reset_password_code': False})
            user.generate_access_token()
            Response.status = "200"
            return {
                'statue': True,
                'access_token': user.access_token
            }
        else:
            Response.status = "204"
            return {
                'statue': False,
                'error': "User is not found"
            }

    @http.route('/api/get_countries', type='json', auth='public', methods=['GET'], sitemap=False, csrf=False)
    def get_countries(self, **kw):
        # accepted_lang = request.httprequest.accept_languages.best
        # countries = request.env['res.country'].sudo().with_context(lang=accepted_lang).search_read(domain=[], fields=['name', 'phone_code'])
        countries = request.env['res.country'].sudo().search_read(domain=[], fields=['name', 'code', 'phone_code'])
        if countries:
            Response.status = "200"
            return {
                'statue': True,
                'data': countries
            }
        else:
            Response.status = "204"
            return {
                'error': 'No countries available'
            }

    @http.route(['/api/read/customer', '/api/read/customer/<int:customer_id>'], type='json', methods=['GET'],
                auth='public', sitemap=False, csrf=False)
    def read_customer(self, customer_id=False, **kw):
        """
        API to sync customers from Frontier Website -> Odoo
        :param kw:
        :return:
        """
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        domain = [('customer_rank', '>', 0)]
        if customer_id:
            domain.append(('id', '=', customer_id))

        fields = ['name', 'ref', 'lang', 'email', 'phone', 'mobile']

        if kw.get('image'):
            fields.append('image_1920')
        customers = request.env['res.partner'].with_user(user).search_read(domain, fields)

        if customers:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Data Retrieved successfully", "data": customers}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no customers"}}
            return response

    @http.route(['/api/update/vendor/', '/api/update/customer/', '/api/update/vendor/<int:partner_id>',
                 '/api/update/customer/<int:partner_id>'], type='json', methods=['PUT'],
                auth='public', sitemap=False, csrf=False)
    def update_customer(self, partner_id=False, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        partner_obj = False

        if partner_id:
            partner_obj = request.env['res.partner'].with_user(user).search([
                ('id', '=', partner_id)
            ], limit=1)
        else:
            Response.status = "401"
            response = {"result": {"code": 401, "message": "No Customer / Vendor ID provided"}}
            return response
        if partner_obj:
            allowed_fields = ['name', 'ref', 'lang', 'email', 'phone', 'mobile', 'bank_ids']
            update_values = {}
            update_lines_values = []
            for key, val in kw.items():
                if key in allowed_fields:
                    if key != 'bank_ids':
                        update_values.update({key: val})
                    else:
                        allowed_line_fields = ['bank_id', 'acc_number']
                        for line in kw.get('bank_ids'):
                            line_data = {}
                            for line_key, line_val in line.items():
                                if line_key in allowed_line_fields:
                                    line_data.update({line_key: line_val})
                            update_lines_values.append((0, 0, line_data))
                        partner_obj.with_user(user).write({
                            'bank_ids': [(5,0,0)]
                        })
                        update_values.update({key: update_lines_values})

            updated_partner = partner_obj.with_user(user).write(update_values)

            if updated_partner:
                Response.status = "200"
                response = {"result": {"code": 200, "message": "Customer Updated successfully"}}
                return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Customer"}}
            return response

    @http.route(['/api/read/vendor', '/api/read/vendor/<int:vendor_id>'], type='json', methods=['GET'], auth='public',
                sitemap=False, csrf=False)
    def read_vendor(self, vendor_id=False, **kw):
        """
        API to sync orders from Frontier Website -> Odoo
        :param kw:
        :return:
        """
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        domain = [('supplier_rank', '>', 0)]
        if vendor_id:
            domain.append(('id', '=', vendor_id))

        fields = ['name', 'ref', 'lang', 'email', 'phone', 'mobile']

        if kw.get('image'):
            fields.append('image_1920')

        vendors = request.env['res.partner'].with_user(user).search_read(domain, fields)

        if vendors:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Data Retrieved successfully", "data": vendors}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Vendors"}}
            return response

    @http.route(['/api/read/category', '/api/read/category/<int:categ_id>', '/api/read/category/page/<int:page>'],
                type='json', methods=['GET'], auth='public',
                sitemap=False, csrf=False)
    def read_product_category(self, categ_id=False, page=1, **kw):
        """
        API to sync orders from Frontier Website -> Odoo
        :param kw:
        :return:
        """
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response
        domain = []
        if categ_id:
            domain.append(('id', '=', categ_id))
        if kw.get('filters').get('title'):
            domain.append(('name', 'ilike', kw.get('filters').get('title')))
        if kw.get('filters').get('parent_categ'):
            domain.append(('parent_id.name', 'ilike', kw.get('filters').get('parent_categ')))

        fields = ['name', 'product_count', 'parent_id']
        env_product_category = request.env['product.category'].with_user(SUPERUSER_ID)

        categories = env_product_category.search_read(domain, fields, limit=15, offset=15 * (page - 1))
        total_categories = request.env['product.category'].with_user(SUPERUSER_ID).search_count(domain)
        total_pages = ceil(total_categories / 15)
        if categories:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Data Retrieved successfully", "total_pages": total_pages,
                                   "current_page": page, "data": categories}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Categories"}}
            return response

    @http.route(['/api/read/product', '/api/read/product/<int:product_id>', '/api/read/product/page/<int:page>'],
                type='json', methods=['GET'],
                auth='public',
                sitemap=False, csrf=False)
    def read_product(self, product_id=False, page=1, **kw):
        """
        API to sync orders from Frontier Website -> Odoo
        :param kw:
        :return:
        """
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        domain = [('sale_ok', '=', True)]
        if product_id:
            domain.append(('id', '=', product_id))
        if kw.get('filters'):
            filters_category = kw.get('filters').get('category')
            filters_sku = kw.get('filters').get('sku')
            filters_school = kw.get('filters').get('school_id')
            if filters_category:
                domain.append(('categ_id.name', 'ilike', filters_category))
            if filters_school:
                domain.append(('school_id', '=', filters_school))
            if filters_sku:
                domain.append('|')
                domain.append(('default_code', 'ilike', filters_sku))
                domain.append(('barcode', 'ilike', filters_sku))

        fields = ['name', 'barcode', 'default_code', 'description', 'description_sale', 'list_price', 'qty_available',
                  'seller_ids', 'attribute_line_ids', 'create_date', 'uom_id', 'image_1920', 'categ_id', 'sale_label',
                  'brand_id', 'school_id']

        if kw.get('image'):
            fields.append('image_1920')
        env_product_template = request.env['product.template'].with_user(SUPERUSER_ID)
        env_product_product = request.env['product.product'].with_user(SUPERUSER_ID)
        env_partner = request.env['res.partner'].with_user(SUPERUSER_ID)
        env_attribute_line = request.env['product.template.attribute.line'].with_user(SUPERUSER_ID)
        env_attribute_value = request.env['product.attribute.value'].with_user(SUPERUSER_ID)
        env_template_attribute_value = request.env['product.template.attribute.value'].with_user(SUPERUSER_ID)
        env_attachment = request.env['ir.attachment'].with_user(SUPERUSER_ID)
        env_config_parameter = request.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        products = env_product_template.search_read(domain, fields, limit=15, offset=15 * (page - 1))
        # Get Suppler Details
        for product in products:
            if product.get("seller_ids", False):
                suppliers = env_partner.search_read([('id', 'in', product.get('seller_ids'))],
                                                    fields=['name', 'email', 'phone', 'mobile', 'website'])
                product.update({"seller_ids": suppliers})
                product.update({"suppliers": product.pop('seller_ids')})

            if product.get('attribute_line_ids', False):
                attributes = env_attribute_line.search_read([('id', 'in', product.get('attribute_line_ids'))],
                                                            fields=['attribute_id', 'value_ids'])
                for attribute in attributes:
                    if attribute.get('value_ids', False):
                        values = env_attribute_value.search_read([('id', 'in', attribute.get('value_ids'))],
                                                                 fields=['name'])
                        attribute.update({'value_ids': values})
                product.update({'attribute_line_ids': attributes})

            if 'image_1920' in product and product.get('image_1920'):
                attachment_obj = env_attachment.search(
                    [('res_model', '=', 'product.template'), ('res_id', '=', product.get('id')),
                     ('res_field', '=', 'image_1920')], limit=1)
                if attachment_obj:
                    base_url = env_config_parameter.get_param('web.base.url')
                    product.update({'image': base_url + "/web/image/" + str(attachment_obj.id)})
                else:
                    product.update({'image': False})
                product.pop('image_1920')

            product_variants = env_product_product.search_read([('product_tmpl_id', '=', product.get('id'))],
                                                               fields=['name', 'barcode', 'default_code', 'lst_price',
                                                                       'brand_id', 'special_price',
                                                                       'product_template_attribute_value_ids'])
            for value in product_variants:
                if value.get('product_template_attribute_value_ids', False):
                    variant_values = env_template_attribute_value.search_read(
                        [('id', 'in', value.get('product_template_attribute_value_ids'))], fields=['display_name'])
                    value.update({"product_template_attribute_value_ids": variant_values})
            product.update({"variants": product_variants})

        total_products = env_product_template.search_count(domain)
        total_pages = ceil(total_products / 15)
        if products:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Data Retrieved successfully", "total_pages": total_pages,
                                   "current_page": page, "data": products}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Products"}}
            return response

    @http.route(['/api/update/product/', '/api/update/product/<int:product_id>'], type='json', methods=['PUT'],
                auth='public', sitemap=False, csrf=False)
    def update_product(self, product_id=False, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        product_obj = False

        if product_id:
            product_obj = request.env['product.product'].with_user(SUPERUSER_ID).search([
                ('id', '=', product_id)
            ], limit=1)
        else:
            Response.status = "401"
            response = {"result": {"code": 401, "message": "No Product ID provided"}}
            return response

        if product_obj:
            allowed_fields = ['name', 'barcode', 'default_code', 'description', 'description_sale', 'list_price']
            update_values = {}
            for key, val in kw.items():
                if key in allowed_fields:
                    update_values.update({key: val})

            updated_partner = product_obj.with_user(user).write(update_values)

            if updated_partner:
                Response.status = "200"
                response = {"result": {"code": 200, "message": "Product Updated successfully"}}
                return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Product"}}
            return response

    @http.route(['/api/read/order', '/api/read/order/<int:order_id>'], type='json', methods=['GET'], auth='public',
                sitemap=False, csrf=False)
    def read_order(self, order_id=False, **kw):
        """
        API to sync orders from Frontier Website -> Odoo
        :param kw:
        :return:
        """
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        domain = []
        if order_id:
            domain.append(('id', '=', order_id))
            domain.append(('partner_id', '=', user.partner_id.id))

        orders = request.env['sale.order'].with_user(user).search_read(domain,
                                                                       ['name', 'partner_id', 'state',
                                                                        'client_order_ref', 'origin', 'reference',
                                                                        'date_order', 'validity_date', 'note',
                                                                        'amount_untaxed', 'amount_tax', 'amount_total',
                                                                        'order_line'])

        for order in orders:
            if order.get('order_line'):
                line_domain = [('id', 'in', order.get('order_line'))]
                lines = request.env['sale.order.line'].with_user(user).search_read(line_domain,
                                                                                   ['product_id', 'order_id', 'name',
                                                                                    'price_unit', 'price_subtotal',
                                                                                    'price_tax', 'discount',
                                                                                    'product_uom_qty',
                                                                                    'qty_delivered', 'qty_invoiced', ])
                order.update({'order_line': lines})

        if orders:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Data Retrieved successfully", "data": orders}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Orders"}}
            return response

    @http.route(['/api/update/order', '/api/update/order/<int:order_line_id>'], type='json', methods=['PUT'],
                auth='public',
                sitemap=False, csrf=False)
    def update_order(self, order_line_id=False, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        order_line_obj = False

        if order_line_id:
            order_line_obj = request.env['sale.order.line'].with_user(user).search([
                ('id', '=', order_line_id)
            ], limit=1)
        else:
            Response.status = "401"
            response = {"result": {"code": 401, "message": "No Order Line ID provided"}}
            return response

        if order_line_obj:
            allowed_fields = ['product_id', 'name', 'price_unit', 'product_uom_qty', 'discount']
            update_values = {}
            for key, val in kw.items():
                if key in allowed_fields:
                    update_values.update({key: val})

            updated_partner = order_line_obj.with_user(user).write(update_values)

            if updated_partner:
                Response.status = "200"
                response = {"result": {"code": 200, "message": "Order Updated successfully"}}
                return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Orders"}}
            return response

    @http.route(['/api/read/brand', '/api/read/brand/<int:brand_id>'], type='json', methods=['GET'], auth='public',
                sitemap=False, csrf=False)
    def read_brand(self, brand_id=False, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        domain = []
        if brand_id:
            domain.append(('id', '=', brand_id))
        if kw.get('filters').get('title'):
            domain.append(('name', 'ilike', kw.get('filters').get('title')))
        if kw.get('filters').get('parent_categ'):
            domain.append(('parent_id.name', 'ilike', kw.get('filters').get('parent_categ')))

        fields = ['name']

        if kw.get('image'):
            fields.append('image_1920')

        brands = request.env['product.brand'].with_user(user).search_read(domain, fields)

        for brand in brands:
            if 'image_1920' in brand and brand.get('image_1920'):
                attachment_obj = request.env['ir.attachment'].with_user(SUPERUSER_ID).search(
                    [('res_model', '=', 'product.brand'), ('res_id', '=', brand.get('id')),
                     ('res_field', '=', 'image_1920')], limit=1)
                if attachment_obj:
                    base_url = request.env['ir.config_parameter'].with_user(SUPERUSER_ID).get_param('web.base.url')
                    brand.update({'image': base_url + "/web/image/" + str(attachment_obj.id)})
                else:
                    brand.update({'image': False})
                brand.pop('image_1920')

        if brands:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Data Retrieved successfully", "data": brands}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Vendors"}}
            return response

    @http.route('/api/create/customer', type='json', methods=['POST'],
                auth='public', sitemap=False, csrf=False)
    def create_customer(self, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response
        customer_env = request.env['res.partner']
        allowed_fields = ['name', 'phone', 'email', 'street', 'city', 'bank_ids']
        update_values = {
            'customer_rank': 1
        }
        update_lines_values = []
        for key, val in kw.items():
            if key in allowed_fields:
                if key != 'bank_ids':
                    update_values.update({key: val})
                else:
                    allowed_line_fields = ['bank_id', 'acc_number']
                    for line in kw.get('bank_ids'):
                        line_data = {}
                        for line_key, line_val in line.items():
                            if line_key in allowed_line_fields:
                                line_data.update({line_key: line_val})
                        update_lines_values.append((0, 0, line_data))
                    update_values.update({key: update_lines_values})

        if kw.get('email'):
            check = customer_env.with_user(SUPERUSER_ID).search([
                ('email', '=', kw.get('email'))
            ])
            if check:
                response = {'result': {'code': 401, 'message': "Email exist"}}
                Response.status = "401"
                return response
        if kw.get('phone'):
            check = customer_env.with_user(SUPERUSER_ID).search([
                ('phone', '=', kw.get('phone'))
            ])
            if check:
                response = {'result': {'code': 401, 'message': "Phone exist"}}
                Response.status = "401"
                return response

        create_obj = customer_env.with_user(user).create(update_values)

        if create_obj:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Order Updated successfully", "data": create_obj.read()}}
            return response

    @http.route('/api/create/vendor', type='json', methods=['POST'],
                auth='public', sitemap=False, csrf=False)
    def create_vendor(self, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response
        customer_env = request.env['res.partner']
        allowed_fields = ['name', 'phone', 'email', 'street', 'city', 'bank_ids']
        update_values = {
            'supplier_rank': 1
        }
        update_lines_values = []
        for key, val in kw.items():
            if key in allowed_fields:
                if key != 'bank_ids':
                    update_values.update({key: val})
                else:
                    allowed_line_fields = ['bank_id', 'acc_number']
                    for line in kw.get('bank_ids'):
                        line_data = {}
                        for line_key, line_val in line.items():
                            if line_key in allowed_line_fields:
                                line_data.update({line_key: line_val})
                        update_lines_values.append((0, 0, line_data))
                    update_values.update({key: update_lines_values})

        if kw.get('email'):
            check = customer_env.with_user(SUPERUSER_ID).search([
                ('email', '=', kw.get('email'))
            ])
            if check:
                response = {'result': {'code': 401, 'message': "Email exist"}}
                Response.status = "401"
                return response
        if kw.get('phone'):
            check = customer_env.with_user(SUPERUSER_ID).search([
                ('phone', '=', kw.get('phone'))
            ])
            if check:
                response = {'result': {'code': 401, 'message': "Phone exist"}}
                Response.status = "401"
                return response

        create_obj = customer_env.with_user(user).create(update_values)

        if create_obj:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Order Updated successfully", "data": create_obj.read()}}
            return response

    @http.route('/api/create/product', type='json', methods=['POST'],
                auth='public', sitemap=False, csrf=False)
    def create_product(self, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response
        product_env = request.env['product.product']
        allowed_fields = ['name', 'type', 'barcode', 'default_code', 'description', 'description_sale', 'list_price',
                          'categ_id']
        update_values = {}
        for key, val in kw.items():
            if key in allowed_fields:
                update_values.update({key: val})

        if kw.get('default_code'):
            check = product_env.with_user(SUPERUSER_ID).search([
                ('default_code', '=', kw.get('default_code'))
            ])
            if check:
                response = {'result': {'code': 401, 'message': "default_code exist"}}
                Response.status = "401"
                return response

        create_obj = product_env.with_user(SUPERUSER_ID).create(update_values)

        if create_obj:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Product Created successfully", "data": create_obj.read()}}
            return response

    @http.route('/api/create/order', type='json', methods=['POST'],
                auth='public', sitemap=False, csrf=False)
    def create_order(self, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response
        order_env = request.env['sale.order']
        allowed_fields = ['name', 'order_line', 'partner_id', 'state', 'pickup_point_id', 'commitment_date', 'payment_method', 'is_confirmed_order']
        update_values = {}
        update_lines_values = []
        for key, val in kw.items():
            if key in allowed_fields:
                if key != 'order_line':
                    update_values.update({key: val})
                else:
                    allowed_line_fields = ['product_id', 'name', 'product_uom_qty', 'price_unit']
                    for line in kw.get('order_line'):
                        line_data = {}
                        for line_key, line_val in line.items():
                            if line_key in allowed_line_fields:
                                line_data.update({line_key: line_val})
                        update_lines_values.append((0, 0, line_data))
                    update_values.update({key: update_lines_values})

        create_obj = order_env.with_user(user).create(update_values)
        # if kw.get('state') and kw.get('state') == 'sale':
        #     create_obj.state = 'draft'
        #     create_obj.action_confirm()
        #     invoice = create_obj._create_invoices()
        #     invoice.write({
        #         'name': create_obj.name
        #     })
        #     invoice.post()

        if create_obj:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Order Created successfully", "data": create_obj.read()}}
            return response

    @http.route('/api/create/purchase_order', type='json', methods=['POST'],
                auth='public', sitemap=False, csrf=False)
    def create_purchase_order(self, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response
        order_env = request.env['purchase.order']
        allowed_fields = ['order_line', 'partner_id', 'state']
        update_values = {}
        update_lines_values = []
        for key, val in kw.items():
            if key in allowed_fields:
                if key != 'order_line':
                    update_values.update({key: val})
                else:
                    allowed_line_fields = ['product_id', 'name', 'product_qty', 'price_unit']
                    for line in kw.get('order_line'):
                        line_data = {}
                        for line_key, line_val in line.items():
                            if line_key in allowed_line_fields:
                                line_data.update({line_key: line_val})
                        update_lines_values.append((0, 0, line_data))
                    update_values.update({key: update_lines_values})

        create_obj = order_env.with_user(user).create(update_values)

        if create_obj:
            Response.status = "200"
            response = {
                "result": {"code": 200, "message": "Purchase Order Created successfully", "data": create_obj.read()}}
            return response

    @http.route('/api/create/invoice', type='json', methods=['POST'],
                auth='public', sitemap=False, csrf=False)
    def create_invoice(self, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response
        order_env = request.env['account.move']
        allowed_fields = ['invoice_line_ids', 'partner_id', 'state', 'move_type', 'invoice_date']
        update_values = {
            'state': 'draft'
        }
        update_lines_values = []
        for key, val in kw.items():
            if key in allowed_fields:
                if key not in ['invoice_line_ids', 'state']:
                    update_values.update({key: val})
                if key == 'invoice_line_ids':
                    allowed_line_fields = ['product_id', 'name', 'quantity', 'price_unit']
                    for line in kw.get('invoice_line_ids'):
                        line_data = {}
                        for line_key, line_val in line.items():
                            if line_key in allowed_line_fields:
                                line_data.update({line_key: line_val})
                        update_lines_values.append((0, 0, line_data))
                    update_values.update({key: update_lines_values})
        create_obj = order_env.with_user(user).create(update_values)
        if create_obj:
            Response.status = "200"
        response = {"result": {"code": 200, "message": "Invoice Created successfully", "data": create_obj.read()}}

        if kw.get('move_type') == 'in_invoice' and kw.get('pay_invoice'):
            response = {'result': {'code': 401, 'message': "In Invoice cannot create payment for it"}}
            Response.status = "401"
            return response


        if kw.get('state') == 'posted' and not kw.get('pay_invoice'):
            create_obj.action_post()
        elif kw.get('pay_invoice'):
            create_obj.action_post()
            payment_obj = {
                'amount': create_obj.amount_total,
                'payment_date': create_obj.invoice_date,
                'payment_type': 'inbound' if create_obj.amount_total < 0.0 else 'outbound',
                'journal_id': create_obj.journal_id.id,
                'currency_id': create_obj.currency_id.id,
                'payment_method_line_id': request.env['account.payment.method.line'].with_user(SUPERUSER_ID).search([], limit=1).id,
            }
            if kw.get('payment_type') and kw.get('payment_type') == 'cash':
                payment_obj['journal_id'] = request.env.company.default_cash_journal.id
            if kw.get('payment_type') and kw.get('payment_type') == 'bank':
                payment_obj['journal_id'] = request.env.company.default_bank_journal.id
            payment_vals = request.env['account.payment.register'] \
                .with_user(SUPERUSER_ID).with_context(active_model='account.move', active_ids=create_obj.ids) \
                .create(payment_obj).action_create_payments()
            if create_obj:
                Response.status = "200"
            response = {"result": {"code": 200, "message": "Invoice Created successfully", "data": create_obj.read()}}
        return response

    @http.route('/api/create/bank', type='json', methods=['POST'],
                auth='public', sitemap=False, csrf=False)
    def create_bank(self, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response
        order_env = request.env['res.bank']
        allowed_fields = ['name', 'bic', 'phone', 'email', 'street']
        update_values = {}
        update_lines_values = []
        for key, val in kw.items():
            if key in allowed_fields:
                update_values.update({key: val})
        create_obj = order_env.with_user(user).create(update_values)
        if create_obj:
            Response.status = "200"
        response = {"result": {"code": 200, "message": "Bank Created successfully", "data": create_obj.read()}}

        return response

    @http.route(['/api/read/bank', '/api/read/bank/<int:bank_id>'], type='json', methods=['GET'],
                auth='public',
                sitemap=False, csrf=False)
    def read_bank(self, bank_id=False, **kw):
        """
        API to sync orders from Frontier Website -> Odoo
        :param kw:
        :return:
        """
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        domain = []
        if bank_id:
            domain.append(('id', '=', bank_id))

        orders = request.env['res.bank'].with_user(user).search_read(domain)

        if orders:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Data Retrieved successfully", "data": orders}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Banks"}}
            return response

    @http.route(['/api/update/bank', '/api/update/bank/<int:bank_id>'], type='json',
                methods=['PUT'],
                auth='public',
                sitemap=False, csrf=False)
    def update_bank(self, bank_id=False, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        bank_obj = False

        if bank_id:
            bank_obj = request.env['res.bank'].with_user(user).search([
                ('id', '=', bank_id)
            ], limit=1)
        else:
            Response.status = "401"
            response = {"result": {"code": 401, "message": "No Bank ID provided"}}
            return response
        if bank_obj:
            allowed_fields = ['name', 'bic', 'phone', 'email', 'street']
            update_values = {}
            for key, val in kw.items():
                if key in allowed_fields:
                    update_values.update({key: val})

            updated_partner = bank_obj.with_user(user).write(update_values)

            if updated_partner:
                Response.status = "200"
                response = {"result": {"code": 200, "message": "Bank Updated successfully"}}
                return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Bank"}}
            return response

    @http.route(['/api/read/purchase_order', '/api/read/purchase_order/<int:order_id>'], type='json', methods=['GET'],
                auth='public',
                sitemap=False, csrf=False)
    def read_purchase_order(self, order_id=False, **kw):
        """
        API to sync orders from Frontier Website -> Odoo
        :param kw:
        :return:
        """
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        domain = []
        if order_id:
            domain.append(('id', '=', order_id))
            domain.append(('partner_id', '=', user.partner_id.id))

        orders = request.env['purchase.order'].with_user(user).search_read(domain)

        for order in orders:
            if order.get('order_line'):
                line_domain = [('id', 'in', order.get('order_line'))]
                lines = request.env['purchase.order.line'].with_user(user).search_read(line_domain)
                order.update({'order_line': lines})

        if orders:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Data Retrieved successfully", "data": orders}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Orders"}}
            return response

    @http.route(['/api/update/purchase_order', '/api/update/purchase_order/<int:order_line_id>'], type='json',
                methods=['PUT'],
                auth='public',
                sitemap=False, csrf=False)
    def update_purchase_order(self, order_line_id=False, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        order_line_obj = False

        if order_line_id:
            order_line_obj = request.env['purchase.order.line'].with_user(user).search([
                ('id', '=', order_line_id)
            ], limit=1)
        else:
            Response.status = "401"
            response = {"result": {"code": 401, "message": "No Purchase Order Line ID provided"}}
            return response

        if order_line_obj:
            allowed_fields = ['product_id', 'name', 'price_unit', 'product_qty', 'discount']
            update_values = {}
            for key, val in kw.items():
                if key in allowed_fields:
                    update_values.update({key: val})

            updated_partner = order_line_obj.with_user(user).write(update_values)

            if updated_partner:
                Response.status = "200"
                response = {"result": {"code": 200, "message": "Order Updated successfully"}}
                return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Orders"}}
            return response

    @http.route(['/api/read/invoice', '/api/read/invoice/<int:order_id>'], type='json', methods=['GET'], auth='public',
                sitemap=False, csrf=False)
    def read_invoice(self, order_id=False, **kw):
        """
        API to sync orders from Frontier Website -> Odoo
        :param kw:
        :return:
        """
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        domain = []
        if order_id:
            domain.append(('id', '=', order_id))
            domain.append(('partner_id', '=', user.partner_id.id))

        orders = request.env['account.move'].with_user(user).search_read(domain)

        for order in orders:
            if order.get('invoice_line_ids'):
                line_domain = [('id', 'in', order.get('invoice_line_ids'))]
                lines = request.env['account.move.line'].with_user(user).search_read(line_domain)
                order.update({'invoice_line_ids': lines})

        if orders:
            Response.status = "200"
            response = {"result": {"code": 200, "message": "Data Retrieved successfully", "data": orders}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Orders"}}
            return response

    @http.route(['/api/update/invoice', '/api/update/invoice/<int:order_line_id>'], type='json', methods=['PUT'],
                auth='public',
                sitemap=False, csrf=False)
    def update_invoice(self, order_line_id=False, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {'result': {'code': 401, 'message': "No valid token provided"}}
            Response.status = "401"
            return response

        order_line_obj = False

        if order_line_id:
            order_line_obj = request.env['account.move.line'].with_user(user).search([
                ('id', '=', order_line_id)
            ], limit=1)
        else:
            Response.status = "401"
            response = {"result": {"code": 401, "message": "No Invoice Line ID provided"}}
            return response

        if order_line_obj:
            allowed_fields = ['product_id', 'name', 'price_unit', 'quantity']
            update_values = {}
            for key, val in kw.items():
                if key in allowed_fields:
                    update_values.update({key: val})

            updated_partner = order_line_obj.with_user(user).write(update_values)

            if updated_partner:
                Response.status = "200"
                response = {"result": {"code": 200, "message": "Order Updated successfully"}}
                return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Your search result has no Orders"}}
            return response

    @http.route(['/api/generate/invoice/<int:order_id>'], type='json', methods=['GET'], auth='public',
                sitemap=False, csrf=False)
    def generate_invoice_pdf(self, order_id=False):
        invoice = request.env['account.move'].with_user(SUPERUSER_ID).search([
            ('id', '=', order_id)
        ], limit=1)
        if invoice:
            Response.status = "200"
            odoo_url_host = request.env['ir.config_parameter'].with_user(SUPERUSER_ID).get_param('web.base.url')
            download_url = "%s/my/invoices/%s?report_type=pdf&download=true&access_token=%s" % (
                odoo_url_host, order_id, invoice._portal_ensure_token())
            # return request.make_response(download_url, [
            #     ('Content-Type', 'application/pdf'),
            #     ('Content-Length', len(download_url))
            # ])
            response = {"result": {"code": 200, "message": "Your PDf File is ready", "data": download_url}}
            return response
        else:
            Response.status = "404"
            response = {"result": {"code": 404, "message": "Not Found"}}
            return response
