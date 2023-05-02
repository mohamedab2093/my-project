# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'author': 'mohamed abdallah',
    'email':'mohamedab2010@gmail.com'
    'name': 'lab',
    'category': 'Accounting/Accounting',
    'summary': 'Lab_Emp_Check',
    'description': "",
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'views/lab_emp.xml',
        'views/egy_com.xml',
        'views/sa_com.xml',
        'views/emp_job.xml',
        'views/labdoct.xml',
        'views/labreson.xml',
        'views/lab_result.xml',
        'views/sequence_lab.xml',
        'security/security.xml'


    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
