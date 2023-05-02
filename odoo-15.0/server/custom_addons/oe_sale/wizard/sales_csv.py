# -*- coding: utf-8 -*-

import time
from datetime import date, datetime
import pytz
import json
import datetime
import io
from odoo import api, fields, models, _
from odoo.tools import date_utils
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class SaleOrderState(models.Model):
    _name = 'sale.order.state'
    _description = 'Sale Order State'

    name = fields.Char(string='Name')
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')


class SalesCSV(models.TransientModel):
    _name = 'sales.csv'
    _description = 'Export Sales xlsx'

    # from_date = fields.Date(
    #     'From Date', default=date.today(), required=1,
    # )
    # to_date = fields.Date(
    #     'To Date', default=date.today(), required=1,
    # )
    commitment_date = fields.Date('Delivery Date')
    so_state_ids = fields.Many2many('sale.order.state', string='Status')
    filter_by = fields.Selection(
        string="Filter By",
        selection=[('products', 'Products'), ('categories', 'Categories')],
        required=1, default='products',
    )
    product_ids = fields.Many2many('product.product', string='Products')
    category_ids = fields.Many2many('product.category', string="Categories")

    @api.onchange('filter_by')
    def onchange_filter_by(self):
        self.product_ids = self.category_ids = False

    def export_sales_csv(self):
        data = {
            'ids': self.ids,
            'model': self._name,
            # 'from_date': self.from_date,
            # 'to_date': self.to_date,
            'commitment_date': self.commitment_date,
            'so_state_ids': self.so_state_ids.ids,
            'filter_by': self.filter_by,
            'product_ids': self.product_ids.ids,
            'category_ids': self.category_ids.ids,
        }
        return {
            'type': 'ir.actions.report',
            'data': {
                'model': 'sales.csv',
                'options': json.dumps(data, default=date_utils.json_default),
                'output_format': 'xlsx',
                'report_name': 'Sales',
            },
            'report_type': 'sales_report_xlsx'
        }

    def _get_product_ids(self, vals):
        products = self.env['product.product'].search([])
        if vals.get('filter_by') == 'products':
            return vals.get('product_ids') if vals.get('product_ids') else products.ids
        elif vals.get('filter_by') == 'categories':
            products = products.search([
                ('categ_id', 'child_of', vals.get('category_ids')),
            ])
            if products:
                return products.ids

    def _get_so_status(self, vals):
        so_state_obj = self.env['sale.order.state'].search([('id', 'in', vals.get('so_state_ids'))])
        return [record.state for record in so_state_obj]

    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Sales Info')
        format10_c_b = workbook.add_format({'font_size': 10, 'align': 'center', 'bold': True, 'border': 1})
        format8_c = workbook.add_format({'font_size': 8, 'align': 'center'})
        format8_l = workbook.add_format({'font_size': 8, 'align': 'left'})

        sheet.write(4, 0, 'Product', format10_c_b)
        sheet.write(4, 1, 'SKU', format10_c_b)
        sheet.write(4, 2, 'Quantity', format10_c_b)
        sheet.write(4, 3, 'Supplier', format10_c_b)

        format0 = workbook.add_format({'font_size': 10, 'align': 'center', 'bold': True})
        sheet.merge_range(0, 1, 0, 2, 'Sales Report', format0)
        company_name = self.env.user.company_id.name
        sheet.merge_range(1, 1, 1, 2, company_name, format0)
        user = self.env['res.users'].browse(self.env.uid)
        tz = pytz.timezone(user.tz if user.tz else 'UTC')
        times = pytz.utc.localize(datetime.datetime.now()).astimezone(tz)
        sheet.merge_range('A3:D3', 'XLS Export Date: ' + str(times.strftime("%Y-%m-%d %H:%M %p")), format0)

        product_ids = self._get_product_ids(data)
        start_commitment_date = data.get('commitment_date') + ' 00:00:00'
        end_commitment_date = data.get('commitment_date') + ' 23:59:59'
        so_status = self._get_so_status(data)
        domain = [
            ('state', 'in', so_status),
            ('commitment_date', '>=', start_commitment_date),
            ('commitment_date', '<=', end_commitment_date),
        ]
        so = self.env['sale.order'].search(domain)
        sol = self.env['sale.order.line'].search([('order_id', 'in', so._ids)])
        row = 5
        col = 0
        for product in product_ids:
            sol_obj = sol.filtered(lambda line: line.product_id.id == product)
            if sol_obj:
                prod = sol_obj[0].product_id
                sheet.write(row, col, prod.name, format8_l)
                sheet.write(row, col + 1, prod.default_code if prod.default_code else '', format8_l)
                product_uom_qty = sum(sol_obj.mapped('product_uom_qty'))
                sheet.write(row, col + 2, product_uom_qty, format8_c)
                sheet.write(row, col + 3, prod.seller_ids[0].name.name if prod.seller_ids else '', format8_l)
                row += 1

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
