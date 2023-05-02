# -*- coding: utf-8 -*-
{
    'name': "sale_multi_picking",

    'summary': """
    sale_multi_picking
        """,
    'description': """
        sale_multi_picking
    """,
    'version': '1.0.0',
    'depends': ['base','stock','sale_stock','product', 'account'],

    'data': [
        'security/security.xml',
        'data/mail.xml',
        'data/sequence.xml',
        'data/ir_cron.xml',
        'views/sale_view.xml',
        'views/product.xml',
        'views/stock_picking.xml',
        'views/account_move.xml',
    ],
    'demo': [
        # 'demo/demo.xml',
    ],
}