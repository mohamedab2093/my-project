# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class StockPickingInherit(models.Model):
    _inherit = "stock.picking"


    def action_responsible_to_picking_wizard(self):
        context = self.env.context
        view = self.env.ref('assign_picking_responsible.view_responsible_to_picking')
        action = {
            'name': _('Assign Responsible'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'picking.assign.responsible',
            'target': 'new',
            'view_id': view.id,
            # 'res_id': wiz.id,
            'context': context,
        }
        return action