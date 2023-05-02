# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class AccountPaymentAddStatement(models.TransientModel):
    _name = "picking.assign.responsible"

    user_id = fields.Many2one('res.users', string="Responsible")

    def action_done(self):
        pickings = self.env['stock.picking'].search([
            ('id', 'in', self.env.context.get('active_ids'))
        ])
        if pickings:
            pickings.user_id = self.user_id.id