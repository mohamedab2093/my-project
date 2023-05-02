# -*- coding: utf-8 -*-
# This module and its content is copyright of Tamayozsoft.
# - © Tamayozsoft 2020. All rights reserved.

import logging

from odoo import fields, models, api, _
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)

# Next account_move_line class is temp code for >> Tamayoz TODO: Reconcile installment_move_line_id with prepaid wallet recharge payments and previous cashback credit note by installment_amount only
class account_move_line(models.Model):
    _inherit='account.move.line'
    deducted_from_wallet = fields.Boolean(default=False)

class website_wallet_transaction(models.Model):
    _inherit='website.wallet.transaction'
    
    request_id = fields.Many2one('smartpay_operations.request', 'Request')
    wallet_transaction_info = fields.Text(string='Wallet Transaction Info', copy=False, readonly=True)
    reference = fields.Selection(selection_add=[('request', 'Request'),('cashback', 'Cash Back')], track_visibility='onchange')
    label = fields.Text('Label')
    status = fields.Selection(selection_add=[('cancel', 'Cancel')], track_visibility='onchange')
    wallet_transaction_line = fields.One2many('website.wallet.transaction.line', 'wallet_transaction_id',
                                              string='Wallet Transaction Lines',
                                              readonly=True, copy=True, auto_join=True)
    statement_id = fields.Many2one('account.bank.statement', help="The statement used for provider wallet reconciliation", index=True, copy=False)
    wallet_balance_before = fields.Char(string='Wallet Balance Before', copy=False, readonly=True)
    wallet_balance_after = fields.Char(string='Wallet Balance After', copy=False, readonly=True)

    def auto_deduct_installment_from_customer_wallet(self):
        try:
            '''
            request_pool = self.env['smartpay_operations.request']
            request_hours = int(self.env['ir.config_parameter'].sudo().get_param("smartpay_operations.request_hours"))

            timeout_request_ids=request_pool.search([('stage_id','=',self.env.ref('smartpay_operations.stage_new').id),('create_date','<=',str(datetime.now() - timedelta(hours=request_hours)))])
            for request in timeout_request_ids:
                request.write({'stage_id': self.env.ref('smartpay_operations.stage_expired').id})
            '''
            receivable_account_ids = self.env['account.account'].sudo().search([('user_type_id', '=', self.env.ref('account.data_account_type_receivable').id)])
            installment_move_line_ids = self.env['account.move.line'].sudo().search([('account_id', 'in', receivable_account_ids.ids),
                                                                                     ('invoice_id', '!=', None),
                                                                                     ('invoice_id.origin', 'ilike', 'SO'),
                                                                                     # ('invoice_id.name', '=', None),
                                                                                     # ('name', '=', None),
                                                                                     ('amount_residual', '>', 0),
                                                                                     # Next line is temp code for >> Tamayoz TODO: Reconcile installment_move_line_id with prepaid wallet recharge payments and previous cashback credit note by installment_amount only
                                                                                     ('deducted_from_wallet', '=', False),
                                                                                     ('date_maturity', '<=', fields.Date.today())])
            _logger.info("@@@@@@@@@@@@@@@@@@@ Start Auto deduction from wallet for [%s] installments" % (len(installment_move_line_ids)))
            for installment_move_line_id in installment_move_line_ids:
                _logger.info("@@@@@@@@@@@@@@@@@@@ Auto deduction from wallet for installment [%s]" % (installment_move_line_id.display_name))
                installment_invoice_id = installment_move_line_id.invoice_id
                installment_amount = installment_move_line_id.amount_residual
                installment_partner_id = installment_move_line_id.partner_id
                # Tamayoz TODO: Reconcile installment_move_line_id with prepaid wallet recharge payments and previous cashback credit note by installment_amount only
                '''
                # Auto Reconcile installment invoice with prepaid wallet recharge payments and previous cashback credit note by installment_amount only
                domain = [('account_id', '=', installment_invoice_id.account_id.id),
                          ('partner_id', '=',
                           self.env['res.partner']._find_accounting_partner(installment_invoice_id.partner_id).id),
                          ('reconciled', '=', False),
                          '|',
                          '&', ('amount_residual_currency', '!=', 0.0), ('currency_id', '!=', None),
                          '&', ('amount_residual_currency', '=', 0.0), '&', ('currency_id', '=', None),
                          ('amount_residual', '!=', 0.0)]
                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                lines = self.env['account.move.line'].sudo().search(domain)
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == installment_invoice_id.currency_id:
                        amount_residual_currency = abs(line.amount_residual_currency)
                    else:
                        currency = line.company_id.currency_id
                        amount_residual_currency = currency._convert(abs(line.amount_residual),
                                                                     installment_invoice_id.currency_id,
                                                                     installment_invoice_id.company_id,
                                                                     line.date or fields.Date.today())
                    if float_is_zero(amount_residual_currency,
                                     precision_rounding=installment_invoice_id.currency_id.rounding):
                        continue

                    installment_invoice_id.assign_outstanding_credit(line.id)
                    if installment_invoice_id.state == 'paid':
                        break
                '''
                label = _('Collect payment for invoice [%s]') % (installment_invoice_id.number)
                wallet_transaction_sudo = self.env['website.wallet.transaction'].sudo()
                partner_id_wallet_balance = installment_partner_id.wallet_balance
                machine_wallet_create = wallet_transaction_sudo.create(
                    {'wallet_type': 'debit', 'partner_id': installment_partner_id.id, 'reference': 'manual',
                     'label': label, 'amount': installment_amount, 'currency_id': installment_invoice_id.currency_id.id,
                     'wallet_balance_before': partner_id_wallet_balance,
                     'wallet_balance_after': partner_id_wallet_balance - installment_amount,
                     'status': 'done'})
                # self.env.cr.commit()

                installment_partner_id.update(
                    {'wallet_balance': installment_partner_id.wallet_balance - installment_amount})

                # Next line is temp code for >> Tamayoz TODO: Reconcile installment_move_line_id with prepaid wallet recharge payments and previous cashback credit note by installment_amount only
                installment_move_line_id.update({'deducted_from_wallet': True})

                self.env.cr.commit()

                # Notify customer
                irc_param = self.env['ir.config_parameter'].sudo()
                wallet_pay_invoice_notify_mode = irc_param.get_param(
                    "smartpay_operations.wallet_pay_invoice_notify_mode")
                if wallet_pay_invoice_notify_mode == 'inbox':
                    self.env['mail.thread'].sudo().message_notify(
                        subject=label,
                        body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                            installment_amount, _(installment_invoice_id.currency_id.name)),
                        partner_ids=[(4, installment_partner_id.id)],
                    )
                elif wallet_pay_invoice_notify_mode == 'email':
                    machine_wallet_create.wallet_transaction_email_send()
                elif wallet_pay_invoice_notify_mode == 'sms' and installment_partner_id.mobile:
                    machine_wallet_create.sms_send_wallet_transaction(wallet_pay_invoice_notify_mode,
                                                                      'wallet_pay_invoice',
                                                                      # Tamayoz TODO: Add 'wallet_deduction' sms template
                                                                      installment_partner_id.mobile,
                                                                      installment_partner_id.name, label,
                                                                      '%s %s' % (installment_amount,
                                                                                 _(
                                                                                     installment_invoice_id.currency_id.name)),
                                                                      installment_partner_id.country_id.phone_code or '2')
        except Exception as e:
            _logger.error("%s", e)
            return "internal error"

class website_wallet_transaction_line(models.Model):
    _name = 'website.wallet.transaction.line'
    _order = 'id desc'

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('website.wallet.transaction.line') or 'New'
        res = super(website_wallet_transaction_line, self).create(vals)
        return res

    wallet_transaction_id = fields.Many2one('website.wallet.transaction', string='Wallet Transaction Reference',
                                            ondelete='restrict', index=True, copy=False)
    name = fields.Char('Name')
    wallet_type = fields.Selection([
        ('credit', 'Credit'),
        ('debit', 'Debit')
    ], string='Type', default='credit')
    partner_id = fields.Many2one('res.partner', 'Customer')
    # sale_order_id = fields.Many2one('sale.order', 'Sale Order')
    request_id = fields.Many2one('smartpay_operations.request', 'Request')
    # wallet_id = fields.Many2one('res.partner', 'Wallet')
    reference = fields.Selection([
        ('manual', 'Manual'),
        # ('sale_order', 'Sale Order'),
        ('request', 'Request')
    ], string='Reference', default='manual')
    label = fields.Text('Label')
    amount = fields.Char('Amount') # Tamayoz TODO: Convert its type and amount field type in website.wallet.transaction to float
    currency_id = fields.Many2one('res.currency', 'Currency')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancel'),
        ('done', 'Done')
    ], string='Status', readonly=True, default='draft')

    statement_line_id = fields.Many2one('account.bank.statement.line', index=True, string='Statement Line',
                                        help='statement line reconciled with provider refund', copy=False,
                                        readonly=True)
    statement_id = fields.Many2one('account.bank.statement', related='statement_line_id.statement_id',
                                   string='Statement', store=True,
                                   help="The statement used for provider wallet reconciliation", index=True, copy=False)

class Wallet(models.TransientModel):
    _register = False

    name = fields.Char(string='Reason', required=True)
    amount = fields.Float(string='Amount', digits=0, required=True)

    @api.multi
    def run(self):
        context = dict(self._context or {})
        active_model = context.get('active_model', False)
        active_ids = context.get('active_ids', [])

        records = self.env[active_model].browse(active_ids)

        return self._run(records)

    @api.multi
    def _run(self, records):
        for wallet in self:
            for record in records:
                wallet.create_wallet_transaction(record)
        return {}

    @api.one
    def create_wallet_transaction(self, record):
        self._create_wallet_transaction(record)

class WalletIn(Wallet):
    _name = 'wallet.in'
    _description = 'Wallet In'

    ref = fields.Char('Reference')
    expense_account = fields.Many2one('account.account', string='Expense account', required=True, domain=[('deprecated', '=', False)])

    @api.multi
    def _create_wallet_transaction(self, record):
        wallet_transaction_sudo = self.env['website.wallet.transaction'].sudo()
        label = self.name
        customer_wallet_balance = record.wallet_balance
        customer_wallet_create = wallet_transaction_sudo.create(
            {'wallet_type': 'credit', 'partner_id': record.id, 'reference': 'manual', 'label': label,
             'amount': self.amount or 0.0, 'currency_id': self.env.user.company_id.currency_id.id,
             'wallet_balance_before': customer_wallet_balance,
             'wallet_balance_after': customer_wallet_balance + self.amount or 0.0,
             'status': 'done'})
        # self.env.cr.commit()

        record.update({'wallet_balance': record.wallet_balance + self.amount or 0.0})
        self.env.cr.commit()

        # Create journal entry for wallet in.
        receivable_account = record.property_account_receivable_id
        account_move = self.env['account.move'].sudo().create({
            'journal_id': self.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
        })
        self.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
            'name': record.name + ': Wallet In',
            'move_id': account_move.id,
            'account_id': self.expense_account.id,
            'debit': self.amount,
        })
        self.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
            'name': record.name + ': Wallet In',
            'move_id': account_move.id,
            'account_id': receivable_account.id,
            'partner_id': record.id,
            'credit': self.amount,
        })
        account_move.post()
        self.env.cr.commit()

        # Notify Customer
        irc_param = self.env['ir.config_parameter'].sudo()
        wallet_bouns_notify_mode = irc_param.get_param("smartpay_operations.wallet_bouns_notify_mode")
        if wallet_bouns_notify_mode == 'inbox':
            self.env['mail.thread'].sudo().message_notify(
                subject=label,
                body=_('<p>%s %s successfully added to your wallet.</p>') % (
                    self.amount or 0.0, _(self.env.user.company_id.currency_id.name)),
                partner_ids=[(4, record.id)],
            )
        elif wallet_bouns_notify_mode == 'email':
            customer_wallet_create.wallet_transaction_email_send()
        elif wallet_bouns_notify_mode == 'sms' and record.mobile:
            customer_wallet_create.sms_send_wallet_transaction(wallet_bouns_notify_mode,
                                                               'wallet_bouns',
                                                               record.mobile,
                                                               record.name, label,
                                                               '%s %s' % (self.amount or 0.0,
                                                                          _(self.env.user.company_id.currency_id.name)),
                                                               record.country_id.phone_code or '2')

class WalletOut(Wallet):
    _name = 'wallet.out'
    _description = 'Wallet Out'

    income_account = fields.Many2one('account.account', string='Income account', required=True, domain=[('deprecated', '=', False)])

    @api.multi
    def _create_wallet_transaction(self, record):
        label = self.name
        wallet_transaction_sudo = self.env['website.wallet.transaction'].sudo()
        partner_id_wallet_balance = record.wallet_balance
        machine_wallet_create = wallet_transaction_sudo.create(
            {'wallet_type': 'debit', 'partner_id': record.id, 'reference': 'manual', 'label': label,
             'amount': self.amount or 0.0, 'currency_id': self.env.user.company_id.currency_id.id,
             'wallet_balance_before': partner_id_wallet_balance,
             'wallet_balance_after': partner_id_wallet_balance - self.amount or 0.0,
             'status': 'done'})
        # self.env.cr.commit()

        record.update(
            {'wallet_balance': record.wallet_balance - self.amount or 0.0})
        self.env.cr.commit()

        # Create journal entry for wallet out.
        receivable_account = record.property_account_receivable_id
        account_move = self.env['account.move'].sudo().create({
            'journal_id': self.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
        })
        self.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
            'name': record.name + ': Wallet In',
            'move_id': account_move.id,
            'account_id': receivable_account.id,
            'partner_id': record.id,
            'debit': self.amount,
        })
        self.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
            'name': record.name + ': Wallet In',
            'move_id': account_move.id,
            'account_id': self.income_account.id,
            'credit': self.amount,
        })
        account_move.post()
        self.env.cr.commit()

        # Notify customer
        irc_param = self.env['ir.config_parameter'].sudo()
        wallet_pay_invoice_notify_mode = irc_param.get_param("smartpay_operations.wallet_pay_invoice_notify_mode")
        if wallet_pay_invoice_notify_mode == 'inbox':
            self.env['mail.thread'].sudo().message_notify(
                subject=label,
                body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                    self.amount or 0.0, _(self.env.user.company_id.currency_id.name)),
                partner_ids=[(4, record.id)],
            )
        elif wallet_pay_invoice_notify_mode == 'email':
            machine_wallet_create.wallet_transaction_email_send()
        elif wallet_pay_invoice_notify_mode == 'sms' and record.mobile:
            machine_wallet_create.sms_send_wallet_transaction(wallet_pay_invoice_notify_mode,
                                                              'wallet_pay_invoice', # Tamayoz TODO: Add 'wallet_deduction' sms template
                                                              record.mobile,
                                                              record.name, label,
                                                              '%s %s' % (self.amount or 0.0,
                                                                         _(self.env.user.company_id.currency_id.name)),
                                                              record.country_id.phone_code or '2')
