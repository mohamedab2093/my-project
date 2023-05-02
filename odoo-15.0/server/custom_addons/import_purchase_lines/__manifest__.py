# -*- coding: utf-8 -*-
{
    'name': 'Import Purchase Lines',
    'summary': 'Import Purchase Lines from CSV or Excel File',
    'description': '''Import  Purchase Lines from CSV or Excel File
	''',
    'website': '',
    'category': 'general',
    'version': '12.0.0.1',
    'depends': [
        'base',
        'purchase',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/import_lines.xml',
        'views/purchase.xml',
    ],

    'installable': True,
    'application': True,

}
