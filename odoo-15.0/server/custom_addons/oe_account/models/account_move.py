# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from io import BytesIO
import base64
from odoo.exceptions import UserError

try:
    import qrcode
except ImportError:
    qrcode = None


class AccountMove(models.Model):
    _inherit = 'account.move'

    pickup_point_id = fields.Many2one('pickup.point', string='Pickup Point', ondelete='restrict')
    external_id = fields.Char(string="External ID", readonly=1)
    action_id = fields.Char(string="Action ID", readonly=1)
    qr_code = fields.Binary('QRcode', compute="_generate_qr")

    def _generate_qr(self):
        for rec in self:
            qr = qrcode.QRCode(
                version=2,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=5,
                border=0,
            )
            qr.add_data("{'external_order_id': ")
            qr.add_data(rec.external_id)
            qr.add_data(", 'action': '")
            qr.add_data(rec.action_id)
            qr.add_data("'}")
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            qr_image = base64.b64encode(temp.getvalue())
            rec.update({'qr_code': qr_image})

    def get_delivery_date(self):
        if self.invoice_line_ids:
            so_id = self.invoice_line_ids.mapped('sale_line_ids.order_id')
            if so_id and so_id.commitment_date:
                return so_id.commitment_date
        return False
