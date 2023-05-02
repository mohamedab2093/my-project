# -*- coding: utf-8 -*-
# This module and its content is copyright of Tamayozsoft.
# - © Tamayozsoft 2020. All rights reserved.

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    request_id = fields.Many2one(
        comodel_name='smartpay_operations.request',
        string='Request',
        readonly=True, states={'draft': [('readonly', False)]},
    )

    def _prepare_invoice_line_from_request(self, request, name, qty, price_unit):
        invoice_line = self.env['account.invoice.line']
        date = self.date or self.date_invoice
        data = {
            'request_id': request.id,
            'name': name,
            'origin': request.name,
            'uom_id': request.product_id.uom_id.id,
            'product_id': request.product_id.id,
            'account_id': invoice_line.with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
            'price_unit': request.currency_id._convert(price_unit, self.currency_id, request.company_id, date or fields.Date.today(), round=False),
            'quantity': qty,
            'discount': 0.0,
            # 'account_analytic_id': request.account_analytic_id.id,
            # 'analytic_tag_ids': request.analytic_tag_ids.ids,
            # 'invoice_line_tax_ids': invoice_line_tax_ids.ids
        }
        account = invoice_line.get_invoice_line_account('in_invoice', request.product_id, False, self.env.user.company_id)
        if account:
            data['account_id'] = account.id
        return data

class AccountInvoiceLine(models.Model):
    """ Override AccountInvoice_line to add the link to the request it is related to"""
    _inherit = 'account.invoice.line'

    request_id = fields.Many2one(
        comodel_name='smartpay_operations.request',
        string='Request',
        readonly=True, states={'draft': [('readonly', False)]},
    )
