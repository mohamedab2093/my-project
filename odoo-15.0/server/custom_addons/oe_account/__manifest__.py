# -*- coding: utf-8 -*-
{
    'name': 'OdooERP Invoicing',
    'version': '1.0.0',
    'summary': 'Invoices & Payments',
    'sequence': 1,
    'description': """
Invoicing & Payments
====================
1. external_layout_standard customization
2. Tax invoice
""",
    'category': 'Accounting/Accounting',
    'author': 'OdooERP.ae, tou-odoo',
    'website': 'https://odooerp.ae/',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/report_templates.xml',
        'views/report_invoice.xml',
        'views/account_move_views.xml',
        'views/pickup_point_views.xml',
        'views/purchase_order.xml',
        'data/report_paperformat_data.xml',

    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
