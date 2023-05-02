# -*- coding: utf-8 -*-
{
    'name': 'OdooERP Webhooks',
    'version': '15.0.1.0.0',
    'summary': 'OdooERP Webhooks',
    'sequence': 99,
    'description': """
OdooERP Webhooks
====================
""",
    'category': 'Extra Tools',
    'author': 'OdooERP.ae, tou-odoo',
    'website': 'https://odooerp.ae/',
    'depends': ['base_automation'],
    'data': [
        'data/mail_template_data.xml',
        'views/base_menus.xml',
        # 'views/ir_actions_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
