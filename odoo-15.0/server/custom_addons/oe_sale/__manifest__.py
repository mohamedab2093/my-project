# -*- coding: utf-8 -*-
{
    'name': 'OdooERP Sales',
    'version': '1.0.0',
    'summary': 'OdooERP Sales Extension',
    'sequence': 1,
    'description': """
OdooERP Sales
====================
1. Sales Analysis Report
""",
    'category': 'Sales/Sales',
    'author': 'OdooERP.ae, tou-odoo',
    'website': 'https://odooerp.ae/',
    'depends': ['oe_account', 'sale_multi_picking'],
    'data': [
        'security/ir.model.access.csv',
        'data/so_state.xml',
        'wizard/sales_csv_views.xml',
        'views/menu.xml',
        'views/sale_views.xml',
        # 'views/stock_picking_views.xml',
        'report/sale_report_views.xml',
        'report/report_invoice.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {
        'web.assets_backend': [
            'oe_sale/static/src/js/action_manager.js',
        ],
    },
    'license': 'LGPL-3',
}
