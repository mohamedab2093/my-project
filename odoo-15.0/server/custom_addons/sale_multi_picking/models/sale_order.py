# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_round
import logging

_logger = logging.getLogger(__name__)
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    fresh_type = fields.Selection(string="Fulfillment Type",related='product_id.fresh_type', store=True )

    def _prepare_procurement_values(self, group_id=False):
        res = super(SaleOrderLine, self)._prepare_procurement_values(group_id)
        if type(res) != list:
            res.update({
                'fresh_type': self.product_id.fresh_type,
            })
        return res
    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        if self.mapped('order_id').multi_deliver and not self.mapped('order_id').picking_ids:
            for x in self:
                precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
                procurements = []
                for line in x:
                    line = line.with_company(line.company_id)
                    if line.state != 'sale' or not line.product_id.type in ('consu','product'):
                        continue
                    qty = line._get_qty_procurement(previous_product_uom_qty)
                    if float_compare(qty, line.product_uom_qty, precision_digits=precision) == 0:
                        continue

                    group_id = line._get_procurement_group()
                    if not group_id:
                        group_id = self.env['procurement.group'].create(line._prepare_procurement_group_vals())
                        line.order_id.procurement_group_id = group_id
                    else:
                        # In case the procurement group is already created and the order was
                        # cancelled, we need to update certain values of the group.
                        updated_vals = {}
                        if group_id.partner_id != line.order_id.partner_shipping_id:
                            updated_vals.update({'partner_id': line.order_id.partner_shipping_id.id})
                        if group_id.move_type != line.order_id.picking_policy:
                            updated_vals.update({'move_type': line.order_id.picking_policy})
                        if updated_vals:
                            group_id.write(updated_vals)

                    values = line._prepare_procurement_values(group_id=group_id)
                    product_qty = line.product_uom_qty - qty

                    line_uom = line.product_uom
                    quant_uom = line.product_id.uom_id
                    product_qty, procurement_uom = line_uom._adjust_uom_quantities(product_qty, quant_uom)
                    procurements.append(self.env['procurement.group'].Procurement(
                        line.product_id, product_qty, procurement_uom,
                        line.order_id.partner_shipping_id.property_stock_customer,
                        line.name, line.order_id.name, line.order_id.company_id, values))
                if procurements:
                    self.env['procurement.group'].run(procurements)

                # This next block is currently needed only because the scheduler trigger is done by picking confirmation rather than stock.move confirmation
                orders = self.mapped('order_id')
                for order in orders:
                    pickings_to_confirm = order.picking_ids.filtered(lambda p: p.state not in ['cancel', 'done'])
                    if pickings_to_confirm:
                        # Trigger the Scheduler for Pickings
                        pickings_to_confirm.action_confirm()
            return True
        else:
            return super(SaleOrderLine, self)._action_launch_stock_rule(previous_product_uom_qty)

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    multi_deliver = fields.Boolean('Task Splitting', default=True)
    is_confirmed_order = fields.Boolean(string="Confirmed Order")
    payment_method = fields.Char(string="Payment Method")

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super(SaleOrder, self)._create_invoices(grouped=False, final=False, date=None)
        if moves:
            for move in moves:
                vals = {
                    'name': self.name,
                }
                if self.payment_method:
                    vals['payment_method'] = self.payment_method
                move.write(vals)
        return moves

    @api.constrains('is_confirmed_order')
    def check_is_confirmed_order(self):
        for rec in self:
            rec.action_confirm()
            invoice = rec._create_invoices()
            vals = {
                'name': rec.name
            }
            if rec.payment_method:
                vals['payment_method'] = rec.payment_method
            invoice.write(vals)
            invoice.post()


    @api.constrains('picking_ids')
    def compute_picking_ids_field(self):
        _logger.info("Picking Constrains Start ... ")
        for rec in self:
            for picking in rec.picking_ids:
                for move in picking.move_ids_without_package:
                    _logger.info("Picking Constrains Start ... {}".format(move.fresh_type))
                    if move.fresh_type == 'fresh':
                        picking.sudo().write({
                            'is_fresh': True,
                        })
                    if move.fresh_type == 'none_fresh':
                        picking.sudo().write({
                            'is_non_fresh': True,
                        })
                    break