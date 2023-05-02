# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
import tempfile
import binascii
import xlrd
from datetime import date, datetime
from odoo.exceptions import Warning, UserError
from odoo import models, fields, exceptions, api, _
import logging

_logger = logging.getLogger(__name__)
import io

try:
    import csv
except ImportError:
    _logger.debug('Cannot `import csv`.')
try:
    import xlwt
except ImportError:
    _logger.debug('Cannot `import xlwt`.')
try:
    import cStringIO
except ImportError:
    _logger.debug('Cannot `import cStringIO`.')
try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')


class ImportLine(models.TransientModel):
    _name = "import.line"

    File_slect = fields.Binary(string="Select Excel File")

    def import_file(self):
        try:
            fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            fp.write(binascii.a2b_base64(self.File_slect))
            fp.seek(0)
            values = {}
            workbook = xlrd.open_workbook(fp.name)
            sheet = workbook.sheet_by_index(0)
        except:
            raise Warning(_("Invalid file!"))
        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')
        order_id = self.env[active_model].sudo().browse(active_id)
        lines = []
        for row_no in range(sheet.nrows):
            val = {}
            if row_no <= 0:
                fields = map(lambda row: row.value.encode('utf-8'), sheet.row(row_no))
            else:
                line = list(
                    map(lambda row: isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value),
                        sheet.row(row_no)))
                # uom_id = self.env['uom.uom'].search([('name', '=', line[3])])
                price = line[3]
                product_c = str(line[0]).split('.')[0] if '.' in line[0] else line[0]
                product_id = self.env['product.product'].search(['|', ('name', '=', line[0]), ('default_code', '=', product_c)])
                if not product_id:
                    raise exceptions.ValidationError(
                        'Wrong Product Value In Row [{}: {}]'.format(row_no, line[0]))
                # if not uom_id:
                #     raise exceptions.ValidationError(
                #         'Wrong Unit Of Measure Value In Row [{}: {}]'.format(row_no, line[3]))
                # if  line[2] == "":
                #     raise Warning(_('Description field cannot be empty.'))

                # if line[3] == 0:
                #     raise Warning(_('Quantity field cannot be empty.'))
                values.update({
                    'order_id': order_id.id,
                    'product_id': product_id.id,
                    'name': line[1],
                    'product_qty': line[2],
                    'product_uom': product_id.uom_id.id,
                    'price_unit': price,
                    'taxes_id': [(6,0,product_id.supplier_taxes_id.ids)]
                })


                self.env['purchase.order.line'].with_context(from_import=True).create(values)

                lines.append((0, 0, values))

