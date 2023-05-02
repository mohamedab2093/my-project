# -*- coding: utf-8 -*-

from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def oe_send_mail(self, vals):
        if not vals.get('recipients'):
            return {
                'error': 'No recipients found!'
            }

        if not vals.get('body'):
            return {
                'error': 'Mail template not found!'
            }

        partners = self.env['res.partner'].search([('email', 'in', vals.get('recipients'))])
        if not partners:
            return {
                'error': 'No recipients found!'
            }

        for partner in partners:
            template = self.env.ref('oe_webhooks.oe_email_template_wegotwe')
            template.with_context(body=vals.get('body')).send_mail(
                partner.id,
                force_send=True,
                raise_exception=False,
                notif_layout="mail.mail_notification_light",
            )
        return {
            'msg': 'Mail sent!'
        }
