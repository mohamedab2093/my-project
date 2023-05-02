# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    pickup_point_id = fields.Many2one(
        'pickup.point', string='Pickup Point', ondelete='restrict',
        readonly=False, store=True, compute='_compute_pickup_point_id',
    )

    @api.depends('sale_id')
    def _compute_pickup_point_id(self):
        for picking in self:
            so_id = picking.sale_id
            if so_id:
                picking.pickup_point_id = so_id.pickup_point_id.id
            else:
                picking.pickup_point_id = False

    @api.model
    def oe_print_invoices(self):
        invoice_ids = []
        so_id = self.mapped('sale_id')
        if so_id:
            for invoice_id in so_id.invoice_ids:
                if invoice_id.state in ('draft', 'posted'):
                    invoice_ids.append(invoice_id.id)

        if not invoice_ids:
            raise UserError(_('Invoice report not found!'))
        return self.env.ref('account.account_invoices').report_action(invoice_ids)

    def action_cancel(self):
        res = super().action_cancel()
        for rec in self:
            for move_id in rec.move_ids_without_package:
                if move_id.sale_line_id:
                    sol_product_uom_qty = move_id.sale_line_id.product_uom_qty - move_id.product_uom_qty
                    move_id.sale_line_id.write({'product_uom_qty': sol_product_uom_qty})

                    so_id = move_id.sale_line_id.order_id
                    invoice_ids = so_id.invoice_ids.filtered(lambda inv: inv.state == 'posted')
                    for invoice in invoice_ids:
                        invoice.button_draft()
                        for line in invoice.invoice_line_ids:
                            if move_id.sale_line_id.product_id.id == line.product_id.id:
                                line.with_context(check_move_validity=False).write({
                                    'quantity': line.quantity - move_id.product_uom_qty
                                })
                        invoice.with_context(check_move_validity=False)._recompute_dynamic_lines(
                            recompute_all_taxes=True,
                            recompute_tax_base_amount=True,
                        )
                        invoice.action_post()
        return res
