# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError, Warning


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = 'account.move'
   #einv_amount_discount_total = fields.Monetary(string="Amount discount total", compute="_compute_total", store='True',
                                               # help="")
 #  @api.depends('invoice_line_ids', 'amount_total')
  # def _compute_total(self):
      # for r in self:
         #  r.einv_amount_discount_total = sum(line.einv_amount_discount for line in r.invoice_line_ids)





class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = 'account.move.line'
#to get discount as float not percentage
    #inv_amount_discount = fields.Monetary(string="Amount discount", compute="_compute_amount_discount", store='True',
                            #              help="")



   #@api.depends('discount', 'quantity', 'price_unit')
   #def _compute_amount_discount(self):
      # for r in self:
          # r.einv_amount_discount = r.quantity * r.price_unit * (r.discount / 100)


