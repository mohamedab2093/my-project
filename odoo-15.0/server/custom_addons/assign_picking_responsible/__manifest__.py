# -*- coding: utf-8 -*-
{
    'name': "Assign Stock Picking Responsible",

    'summary': """
       Assign Stock Picking Responsible""",

    'description': """
        Assign Stock Picking Responsible
    """,

    'author': "Oakland ERP",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': '',
    'version': '0.1',

    # any module necessary for this one to work correctly

    'depends': ['base', 'stock'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/actions.xml',
        'views/assign_wizard.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
}
