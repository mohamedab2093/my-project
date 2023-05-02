# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_round

class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'
    fresh_type = fields.Selection([
        ('is_fresh', 'Fresh'),
        ('is_non_fresh', 'Non-Fresh'),
    ], string="Fulfillment Type")
    is_fresh = fields.Boolean(string="Fresh Picking")
    is_non_fresh = fields.Boolean(string="Non-Fresh Picking")

class Move(models.Model):
    _inherit = 'stock.move'
    fresh_type = fields.Selection(string="Fulfillment Type", selection=[('fresh', 'Fresh'), ('none_fresh', 'Non-Fresh'), ], copy=True, )

    @api.constrains('picking_id')
    def check_picking_id_from_move(self):
        for rec in self:
            if rec.picking_id:
                if rec.fresh_type == 'fresh':
                    # sequence = self.env['ir.sequence'].next_by_code('fresh.picking')
                    sequence = '%s/F' % rec.origin
                    rec.picking_id.sudo().write({
                        'fresh_type': 'is_fresh',
                        'name': sequence,
                    })
                if rec.fresh_type == 'none_fresh':
                    # sequence = self.env['ir.sequence'].next_by_code('nonfresh.picking')
                    sequence = '%s/NF' % rec.origin
                    rec.picking_id.sudo().write({
                        'fresh_type': 'is_non_fresh',
                        'name': sequence,
                    })
                if not rec.fresh_type:
                    sequence = '%s' % rec.origin
                    rec.picking_id.sudo().write({
                        'name': sequence,
                    })
    # def _search_picking_for_assignation_domain(self):
    #     domain = [
    #         ('group_id', '=', self.group_id.id),
    #         ('location_id', '=', self.location_id.id),
    #         ('location_dest_id', '=', self.location_dest_id.id),
    #         ('picking_type_id', '=', self.picking_type_id.id),
    #         ('printed', '=', False),
    #         ('immediate_transfer', '=', False),
    #         ('move_ids_without_package.fresh_type', '=', self.fresh_type),
    #         ('state', 'in', ['draft', 'confirmed', 'waiting', 'partially_available', 'assigned'])]
    #     if self.partner_id and (self.location_id.usage == 'transit' or self.location_dest_id.usage == 'transit'):
    #         domain += [('partner_id', '=', self.partner_id.id)]
    #     return domain
    def _search_picking_for_assignation(self):
        self.ensure_one()
        domain = self._search_picking_for_assignation_domain()
        picking = self.env['stock.picking'].search(domain)
        if not any(p.group_id.sale_id.multi_deliver for p in picking):
            picking = self.env['stock.picking'].search(domain,limit=1)
            return picking
        for pick in picking:
            if self.fresh_type in pick.move_ids_without_package.mapped('fresh_type'):
                return pick
        return self.env['stock.picking']