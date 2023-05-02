# -*- coding: utf-8 -*-

from odoo import models


class StockBackorderConfirmation(models.TransientModel):
    _inherit = 'stock.backorder.confirmation'

    def process_cancel_backorder(self):
        res = super().process_cancel_backorder()
        pickings_to_validate = self.env.context.get('button_validate_picking_ids')
        if pickings_to_validate:
            pickings_id = self.env['stock.picking'].browse(pickings_to_validate)
            for move_id in pickings_id.move_ids_without_package.filtered(
                    lambda move: move.state == 'cancel'
            ):
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

                # if move_id.purchase_line_id:
                #     pol_product_qty = move_id.purchase_line_id.product_qty - move_id.product_uom_qty
                #     move_id.purchase_line_id.write({'product_qty': pol_product_qty})
        return res
