# -*- coding: utf-8 -*-
# This module and its content is copyright of Tamayozsoft.
# - © Tamayozsoft 2020. All rights reserved.

from odoo import api, fields, models
from odoo.exceptions import ValidationError

class AcquirerBase(models.Model):
    _inherit = 'payment.acquirer'

    sevice_provider = fields.Boolean('Sevice Provider', default=False)
    related_partner = fields.Many2one('res.partner', 'Partner', domain=[('supplier', '=', True)])
    debug_logging = fields.Boolean('Debug logging', help="Log requests in order to ease debugging")

    def toggle_debug(self):
        for c in self:
            c.debug_logging = not c.debug_logging

class AcquirerChannel(models.Model):
    _name = 'payment.acquirer.channel'
    _order = "sequence"

    name = fields.Char('Chennel Name', required=True, groups='base.group_user')
    type = fields.Selection([('internet', 'Internet'), ('machine', 'Machine'), ('mobile', 'Mobile')], string='Chennel Type', default='internet',
                            required=True, groups='base.group_user')
    acquirer_id = fields.Many2one('payment.acquirer', 'Payment Acquirer', ondelete='cascade', readonly=True)
    sequence = fields.Integer('Sequence', help="Gives the sequence order when displaying a list of payment acquirer channels.",
                              default=1)
    company_id = fields.Many2one('res.company', readonly=True, default=lambda self: self.env.user.company_id.id)

    @api.multi
    def _check_required_if_provider(self):
        """ If the field has 'required_if_provider="<provider>"' attribute, then it
        required if record.acquirer_id.provider is <provider>. """
        empty_field = []
        for channel in self:
            for k, f in channel._fields.items():
                if getattr(f, 'required_if_provider', None) == channel.acquirer_id.provider and not channel[k]:
                    empty_field.append(self.env['ir.model.fields'].search(
                        [('name', '=', k), ('model', '=', channel._name)]).field_description)
        if empty_field:
            raise ValidationError((', ').join(empty_field))
        return True

    _constraints = [
        (_check_required_if_provider, 'Required fields not filled', []),
    ]