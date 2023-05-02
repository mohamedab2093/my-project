# -*- coding: utf-8 -*-

import requests

from odoo import api, fields, models

class ServerAction(models.Model):
    _inherit = 'ir.actions.server'

    is_webhook = fields.Boolean(string='Is Webhook', readonly=True)

    @api.model
    def _get_eval_context(self, action=None):
        eval_context = super(ServerAction, self)._get_eval_context(action)

        def make_request(*args, **kwargs):
            return requests.request(*args, **kwargs)

        eval_context["make_request"] = make_request
        return eval_context
