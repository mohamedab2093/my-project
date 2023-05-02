# -*- coding: utf-8 -*-
# This module and its content is copyright of Tamayozsoft.
# - © Tamayozsoft 2020. All rights reserved.

import functools
import json
import ast
import logging
import string
import random
import werkzeug
import datetime
from datetime import date
from datetime import datetime as date_time, timedelta
from psycopg2 import IntegrityError
from Crypto.Cipher import DES3
import base64
from collections import OrderedDict
import requests

from odoo import http, fields, _
from odoo.tools import float_is_zero
from odoo.exceptions import UserError, ValidationError, AccessDenied
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.restful.common import (
    extract_arguments,
    invalid_response,
    valid_response,
    default,
)
from odoo.addons.restful.controllers.main import (
    validate_token, APIController as restful_main
)
from odoo.addons.website_form.controllers.main import WebsiteForm
from odoo.addons.tm_base_gateway.common import (
    suds_to_json,
)
from odoo.addons.web.controllers.main import (
    ensure_db,
)

from odoo.http import request

_logger = logging.getLogger(__name__)

_REQUEST_TYPES_IDS = ['general_inquiry', 'recharge_wallet', 'service_bill_inquiry', 'pay_service_bill', 'pay_invoice', 'wallet_invitation']
SECRET_KEY = base64.b64decode('MfG6sLDTQIaS8QgOnkBS2THxurCw00CG')
UNPAD = lambda s: s[0:-s[-1]]

def validate_machine(func):
    """."""

    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        """."""
        access_token = request.httprequest.headers.get("access_token")
        machine_serial = request.httprequest.headers.get("machine_serial")
        if not machine_serial:
            return invalid_response(
                "machine_serial_not_found", _("missing machine serial in request header"), 400
            )

        access_token_data = (
            request.env["api.access_token"]
                .sudo()
                .search([("token", "=", access_token)], order="id DESC", limit=1)
        )
        user_id = access_token_data.user_id.id

        machine_serial_data = (
            request.env["res.users"]
            .sudo()
            .search([("x_machine_serial", "=", machine_serial), ("id", "=", user_id)], order="id DESC", limit=1)
        )
        if not machine_serial_data:
            return invalid_response(
                "machine_serial", _("machine serial invalid"), 400
            )

        request.session.uid = user_id
        request.uid = user_id
        return func(self, *args, **kwargs)

    return wrap


class APIController(http.Controller):
    """."""

    def __init__(self):
        self._model = "ir.model"

    class UsersApi(http.Controller):

        @http.route('/api/signup', type="http", auth="none", methods=["POST"], csrf=False)
        def auth_signup(self, *args, **kw):
            qcontext = AuthSignupHome().get_auth_signup_qcontext()
            qcontext.update({
                'name': kw.get('first_name') + " " + kw.get('last_name'),
                'login': kw.get('email'),
                'password': kw.get('password'),
                'confirm_password': kw.get('confirm_password'),
                'phone': kw.get('phone'),
            })

            if not qcontext.get('token') and not qcontext.get('signup_enabled'):
                raise werkzeug.exceptions.NotFound()

            if 'error' not in qcontext and request.httprequest.method == 'POST':
                try:
                    AuthSignupHome().do_signup(qcontext)
                    qcontext["message"] = _("Your account successfully created.")
                    # Send an account creation confirmation email
                    if qcontext.get('token'):
                        user_sudo = request.env['res.users'].sudo().search([('login', '=', qcontext.get('login'))])
                        template = request.env.ref('auth_signup.mail_template_user_signup_account_created',
                                                   raise_if_not_found=False)
                        if user_sudo and template:
                            template.sudo().with_context(
                                lang=user_sudo.lang,
                                auth_login=werkzeug.url_encode({'auth_login': user_sudo.email}),
                            ).send_mail(user_sudo.id, force_send=True)
                    # else:
                        # request.env["res.users"].with_context(create_user=True).sudo().reset_password(qcontext.get('login'))
                        # qcontext["message"] = _("Check your email to activate your account!")

                    return valid_response(qcontext['message'])
                except UserError as e:
                    qcontext['error'] = e.name or e.value
                except (SignupError, AssertionError) as e:
                    if request.env["res.users"].sudo().search([("login", "=", qcontext.get("login"))]):
                        qcontext["error"] = _("Another user is already registered using this email address.")
                    else:
                        _logger.error("%s", e)
                        qcontext['error'] = _("Could not create a new account.")

                return invalid_response("Error", qcontext['error'], 500)

        @validate_token
        @http.route('/api/reset_password', type="http", auth="none", methods=["POST"], csrf=False)
        def auth_reset_password(self, *args, **kw):
            qcontext = AuthSignupHome().get_auth_signup_qcontext()
            qcontext.update({
                'login': kw.get('login')
            })

            if not qcontext.get('token') and not qcontext.get('reset_password_enabled'):
                raise werkzeug.exceptions.NotFound()

            if 'error' not in qcontext and request.httprequest.method == 'POST':
                try:
                    if qcontext.get('token'):
                        AuthSignupHome().do_signup(qcontext)
                        #return self.web_login(*args, **kw)
                        qcontext['message'] = _("Signup successfully with the new token")
                        return valid_response(qcontext['message'])
                    else:
                        login = qcontext.get('login')
                        assert login, _("No login provided.")
                        _logger.info(
                            "Password reset attempt for <%s> by user <%s> from %s",
                            login, request.env.user.login, request.httprequest.remote_addr)
                        # request.env['res.users'].sudo().reset_password(login)
                        # qcontext['message'] = _("An email has been sent with credentials to reset your password")
                        # return valid_response(qcontext['message'])

                        # Reset password
                        is_updated = False
                        prefix = "RP_"
                        password_characters = string.ascii_letters + string.digits + string.punctuation
                        new_password = ''.join(random.choice(password_characters) for i in range(10))
                        user = request.env['res.users'].sudo().search([('id', '=', request.env.user.id)], limit=1)
                        if user:
                            is_updated = user.sudo().write({'password': prefix + new_password})
                        if is_updated:
                            return valid_response({"new_password": prefix + new_password})
                except UserError as e:
                    qcontext['error'] = e.name or e.value
                except SignupError:
                    qcontext['error'] = _("Could not reset your password")
                    _logger.exception('error when resetting password')
                except Exception as e:
                    qcontext['error'] = str(e)

                return invalid_response("Error", qcontext['error'], 500)

        @validate_token
        @http.route('/api/change_password', type="http", auth="none", methods=["POST"], csrf=False)
        def auth_change_password(self, *args, **kw):
            qcontext = AuthSignupHome().get_auth_signup_qcontext()
            qcontext.update({
                'login': kw.get('login'),
                'old_pwd': kw.get('old_pwd'),
                'new_password': kw.get('new_password'),
                'confirm_pwd': kw.get('confirm_pwd'),
                'db': kw.get('db'),
            })

            if not qcontext.get('token') and not qcontext.get('reset_password_enabled'):
                raise werkzeug.exceptions.NotFound()

            if 'error' not in qcontext and request.httprequest.method == 'POST':
                try:
                    if qcontext.get('token'):
                        AuthSignupHome().do_signup(qcontext)
                        # return self.web_login(*args, **kw)
                        qcontext['message'] = _("Signup successfully with the new token")
                        return valid_response(qcontext['message'])
                    else:
                        login = qcontext.get('login')
                        assert login, _("No login provided.")
                        _logger.info(
                            "Password change attempt for <%s> by user <%s> from %s",
                            login, request.env.user.login, request.httprequest.remote_addr)

                        old_password = qcontext.get('old_pwd')
                        new_password = qcontext.get('new_password')
                        confirm_password = qcontext.get('confirm_pwd')
                        db = qcontext.get('db')
                        if not (old_password.strip() and new_password.strip() and confirm_password.strip()):
                            return invalid_response("Error", _('You cannot leave any password empty.'), 400)
                        if new_password != confirm_password:
                            return invalid_response("Error", _('The new password and its confirmation must be identical.'), 400)

                        qcontext['error'] = _("Error, password not changed !")

                        # Login in odoo database:
                        request.session.authenticate(db, login, old_password)
                        uid = request.session.uid
                        # odoo login failed:
                        if not uid:
                            info = "authentication failed"
                            error = "authentication failed"
                            _logger.error(info)
                            return invalid_response(info, error, 401)

                        user = request.env['res.users'].sudo().search([('id', '=', uid)], limit=1)
                        if user and user.sudo().write({'password': new_password}):
                            qcontext['message'] = _("Password successfully changed.")
                            return valid_response(qcontext['message'])

                except UserError as e:
                    qcontext['error'] = e.name or e.value
                except AccessDenied as e:
                    qcontext['error'] = e.args[0]
                    if qcontext['error'] == AccessDenied().args[0]:
                        qcontext['error'] = _('The old password you provided is incorrect, your password was not changed.')
                except Exception as e:
                    qcontext['error'] = str(e)

                return invalid_response("Error", qcontext['error'], 500)

        @http.route('/api/create_user', type="http", auth="none", methods=["POST"], csrf=False)
        def create_user(self, **user_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Create User API")
            values = {
                'name': user_data.get('first_name') + " " + user_data.get('last_name'),
                'login': user_data.get('email'),
                'password': user_data.get('password'),
                'confirm_password': user_data.get('confirm_password'),
                'phone': user_data.get('phone')
            }
            try:
                if request.env["res.users"].sudo().search([("login", "=", values.get("login"))]):
                    return invalid_response("Error", _("Another user is already registered using this email address."), 400)
                # sudo_users = request.env["res.users"].with_context(create_user=True).sudo()
                # is_created = sudo_users.signup(values, values.get("token"))
                # sudo_users.reset_password(values.get("login"))
                # if is_created:
                    # return valid_response(_("Check your email to activate your account!"))
                # else:
                    # return invalid_response("Error", _("Could not create a new account."))

                # Wallet Invitation
                if (user_data.get("invitation_code")):
                    invitation_request = request.env["smartpay_operations.request"].sudo().search(
                        [('request_type', '=', 'wallet_invitation'), ('name', '=', user_data.get("invitation_code")),
                        ('mobile_number', '=', values.get("phone")), ("stage_id", "=", 1)], order="id DESC", limit=1)
                    if not invitation_request:
                        return invalid_response("request_not_found", _("Invitation Code (%s) for mobile number (%s) does not exist!") % (
                            user_data.get("invitation_code"), values.get("phone")), 400)

                AuthSignupHome().do_signup(values)

                if (user_data.get("invitation_code")):
                    invited_user = request.env['res.users'].sudo().search([("login", "=", values.get("login"))])

                    # Bonus for both inviter and invited user
                    wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()
                    irc_param = request.env['ir.config_parameter'].sudo()
                    wallet_bouns_notify_mode = irc_param.get_param("smartpay_operations.wallet_bouns_notify_mode")
                    bounce_expense_account_id = irc_param.get_param("smartpay_operations.bounce_expense_account_id")
                    bounce_expense_account = request.env['account.account'].sudo().browse(int(bounce_expense_account_id)).exists()

                    inviter_bonus = float(irc_param.get_param("smartpay_operations.inviter_bonus"))
                    if inviter_bonus > 0:
                        inviter_bonus_currency_id = int(irc_param.get_param("smartpay_operations.inviter_bonus_currency_id"))
                        label = _('Bonus for inviter user')
                        partner_id_wallet_balance = invitation_request.partner_id.wallet_balance
                        inviter_wallet_create = wallet_transaction_sudo.create(
                            {'wallet_type': 'credit', 'partner_id': invitation_request.partner_id.id,
                             'request_id': invitation_request.id,
                             'reference': 'request', 'label': label,
                             'amount': inviter_bonus, 'currency_id': inviter_bonus_currency_id,
                             'wallet_balance_before': partner_id_wallet_balance,
                             'wallet_balance_after': partner_id_wallet_balance + inviter_bonus,
                             'status': 'done'})
                        request.env.cr.commit()

                        invitation_request.partner_id.update(
                            {'wallet_balance': invitation_request.partner_id.wallet_balance + inviter_bonus})
                        request.env.cr.commit()

                        # Notify Inviter
                        if wallet_bouns_notify_mode == 'inbox':
                            request.env['mail.thread'].sudo().message_notify(
                                subject=label,
                                body=_('<p>%s %s successfully added to your wallet.</p>') % (inviter_bonus,_(inviter_bonus_currency_id.name)),
                                partner_ids=[(4, invitation_request.partner_id.id)],
                            )
                        elif wallet_bouns_notify_mode == 'email':
                            inviter_wallet_create.wallet_transaction_email_send()
                        elif wallet_bouns_notify_mode == 'sms' and invitation_request.partner_id.mobile:
                            inviter_wallet_create.sms_send_wallet_transaction(wallet_bouns_notify_mode, 'wallet_bouns',
                                                                              invitation_request.partner_id.mobile,
                                                                              invitation_request.partner_id.name, label,
                                                                              '%s %s' % (inviter_bonus,_(inviter_bonus_currency_id.name)),
                                                                              invitation_request.partner_id.country_id.phone_code or '2')

                    invited_user_bonus = float(irc_param.get_param("smartpay_operations.invited_user_bonus"))
                    if invited_user_bonus > 0:
                        invited_user_bonus_currency_id = int(irc_param.get_param("smartpay_operations.invited_user_bonus_currency_id"))
                        label = _('Bonus for invited user')
                        invited_wallet_create = wallet_transaction_sudo.create(
                            {'wallet_type': 'credit', 'partner_id': invited_user.partner_id.id,
                             'request_id': invitation_request.id,
                             'reference': 'request', 'label': label,
                             'amount': invited_user_bonus, 'currency_id': invited_user_bonus_currency_id,
                             'wallet_balance_before': 0.0,
                             'wallet_balance_after': invited_user_bonus,
                             'status': 'done'})
                        request.env.cr.commit()

                        invited_user.partner_id.update({'wallet_balance': invited_user_bonus})
                        request.env.cr.commit()
                        invitation_request.sudo().write({'wallet_transaction_id': invited_wallet_create.id})
                        request.env.cr.commit()

                        # Notify invited User
                        if wallet_bouns_notify_mode == 'inbox':
                            request.env['mail.thread'].sudo().message_notify(
                                subject=label,
                                body=_('<p>%s %s bonus successfully added to your wallet.</p>') % (invited_user_bonus,_(invited_user_bonus_currency_id.name)),
                                partner_ids=[(4, invited_user.partner_id.id)],
                            )
                        elif wallet_bouns_notify_mode == 'email':
                            invited_wallet_create.wallet_transaction_email_send()
                        elif wallet_bouns_notify_mode == 'sms' and invited_user.partner_id.mobile:
                            inviter_wallet_create.sms_send_wallet_transaction(wallet_bouns_notify_mode,
                                                                              'wallet_bouns',
                                                                              invited_user.partner_id.mobile,
                                                                              invited_user.name, label,
                                                                              '%s %s' % (invited_user_bonus,
                                                                                         _(invited_user_bonus_currency_id.name)),
                                                                              invited_user.partner_id.country_id.phone_code or '2')

                    if inviter_bonus > 0 or invited_user_bonus > 0:
                        # Create journal entry for increase AR balance for both inviter and invited user.
                        inviter_user_receivable_account = invitation_request.partner_id.property_account_receivable_id
                        invited_user_receivable_account = invited_user.partner_id.property_account_receivable_id
                        account_move = request.env['account.move'].sudo().create({
                            'journal_id': request.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
                        })

                        bonus_total_amount = 0
                        if inviter_bonus > 0:
                            bonus_total_amount += inviter_bonus
                            request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                                'name': invitation_request.name + ': Invitation Bouns',
                                'move_id': account_move.id,
                                'account_id': inviter_user_receivable_account.id,
                                'partner_id': invitation_request.partner_id.id,
                                'credit': inviter_bonus,
                            })
                        if invited_user_bonus > 0:
                            bonus_total_amount += invited_user_bonus
                            request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                                'name': invitation_request.name + ': Invitation Bouns',
                                'move_id': account_move.id,
                                'account_id': invited_user_receivable_account.id,
                                'partner_id': invited_user.partner_id.id,
                                'credit': invited_user_bonus,
                            })

                        request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                            'name': invitation_request.name + ': Invitation Bouns',
                            'move_id': account_move.id,
                            'account_id': bounce_expense_account.id,
                            'debit': bonus_total_amount,
                        })
                        account_move.post()

                    invitation_request.sudo().write({'stage_id': 5})

                return valid_response(_("Congratulation. Your Account successfully created."))
            except Exception as e:
                _logger.error("%s", e)
                return invalid_response("Error", _("Could not create a new account.") + " ==> " + str(e), 500)

        @validate_token
        @http.route('/api/get_user_profile', type="http", auth="none", methods=["POST"], csrf=False)
        def get_user_profile(self, **payload):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Get User Profile API")
            return restful_main().get('res.users', request.env.user.id, **payload)

        @validate_token
        @http.route('/api/update_user_profile', type="http", auth="none", methods=["POST"], csrf=False)
        def update_user_profile(self, **user_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Update User Profile API")
            return restful_main().put('res.users', request.env.user.id, **user_data)

        @validate_token
        @http.route('/api/deactive_user', type="http", auth="none", methods=["POST"], csrf=False)
        def deactive_user(self, **user_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Deactivate User API")
            is_updated = False
            user = request.env['res.users'].sudo().search([('id', '=', request.env.user.id)], limit=1)
            if user:
                is_updated = user.sudo().write({'active': False})

            if is_updated:
                return valid_response(_('User Deactivated Successfully'))
            else:
                return invalid_response("Error", _("The User didn't deactivated"), 500)

        @http.route('/api/test', type="http", auth="none", methods=["GET"], csrf=False)
        def test(self, **user_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Test API")
            return valid_response(_('Tested Successfully'))


    class RequestApiTemp(http.Controller):

        @validate_token
        @validate_machine
        @http.route('/api/create_machine_request', type="http", auth="none", methods=["POST"], csrf=False)
        def create_machine_request(self, **request_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Machine Request API")

            if not request_data.get('request_type') or request_data.get('request_type') not in _REQUEST_TYPES_IDS:
                return invalid_response("request_type", _("request type invalid"), 400)

            if request_data.get('request_type') == 'recharge_wallet':
                if not request_data.get('trans_number'):
                    return invalid_response("receipt_number_not_found", _("missing deposit receipt number in request data"), 400)
                if not request_data.get('trans_date'):
                    return invalid_response("date_not_found", _("missing deposit date in request data"), 400)
                if not request_data.get('trans_amount'):
                    return invalid_response("amount_not_found", _("missing deposit amount in request data"), 400)
                if not any(hasattr(field_value, 'filename') for field_name, field_value in request_data.items()):
                    return invalid_response("receipt_not_found", _("missing deposit receipt attachment in request data"), 400)

                open_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'recharge_wallet'), ("partner_id", "=", request.env.user.partner_id.id),
                     ("stage_id", "=", 1)], order="id DESC", limit=1)
                if open_request:
                    return invalid_response("request_already_exist",
                                            _("You have a wallet recharge request in progress with REQ Number (%s)") % (
                                                open_request.name), 400)

                request_data['product_id'] = request.env["product.product"].sudo().search([('name', '=', 'Wallet Recharge')]).id

            if not request_data.get('product_id') and request_data.get('request_type') not in ('general_inquiry', 'pay_invoice', 'wallet_invitation'):
                return invalid_response("service_not_found", _("missing service in request data"), 400)
            elif request_data.get('request_type') not in ('general_inquiry', 'pay_invoice', 'wallet_invitation'):
                service = request.env["product.product"].sudo().search([("id", "=", request_data.get('product_id')), ("type", "=", "service")],
                                                                       order="id DESC", limit=1)
                if not service:
                    return invalid_response("service", _("service invalid"), 400)

            if request_data.get('request_type') == 'wallet_invitation':
                if not request_data.get('mobile_number'):
                    return invalid_response("mobile_number_not_found", _("missing mobile number for invited user in request data"), 400)

                open_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'wallet_invitation'), ('mobile_number', '=', request_data.get('mobile_number')),
                     ('partner_id', '=', request.env.user.partner_id.id), ("stage_id", "=", 1)], order="id DESC", limit=1)
                if open_request:
                    return invalid_response("request_already_exist",
                                            _("You have a wallet invitation request in progress for mobile number (%s) with REQ Number (%s)") % (
                                                request_data.get('mobile_number'), open_request.name), 400)

                done_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'wallet_invitation'),
                     ('mobile_number', '=', request_data.get('mobile_number')), ("stage_id", "=", 5)],
                    order="id DESC", limit=1)
                if done_request:
                    return invalid_response("request_already_exist",
                                            _("The mobile number (%s) already has a wallet") % (
                                                request_data.get('mobile_number')), 400)

            if request_data.get('request_type') == 'pay_invoice':
                if not request_data.get('trans_amount'):
                    return invalid_response("amount_not_found", _("missing invoice amount in request data"), 400)

            if request_data.get('request_type') == 'service_bill_inquiry' or request_data.get('request_type') == 'pay_service_bill':
                if not request_data.get('billingAcct'):
                    return invalid_response("billingAcct_not_found", _("missing billing account in request data"), 400)

                if request_data.get('request_type') == 'pay_service_bill':
                    if not request_data.get('currency_id'):
                        return invalid_response("curCode_not_found",
                                                _("missing bill currency code in request data"), 400)
                    if not request_data.get('pmtMethod'):
                        return invalid_response("pmtMethod_not_found",
                                                _("missing payment method in request data"), 400)

                    provider_provider = request_data.get('provider')
                    if provider_provider == 'khales':
                        if not request_data.get('pmtType'):
                            return invalid_response("pmtType_not_found", _("missing payment type in request data"), 400)
                        '''
                        if not request_data.get('billerId'):
                            return invalid_response("billerId_not_found", _("missing biller id in request data"), 400)
                        '''
                        if not request_data.get('ePayBillRecID'):
                            return invalid_response("ePayBillRecID_not_found", _("missing ePay Bill Rec ID in request data"), 400)
                        # if not request_data.get('pmtId'):
                            # return invalid_response("pmtId_not_found", _("missing payment id in request data"), 400)
                        if not request_data.get('feesAmt'):
                            return invalid_response("feesAmt_not_found", _("missing fees amount in request data"), 400)
                        # if not request_data.get('pmtRefInfo'):
                            # return invalid_response("pmtRefInfo_not_found", _("missing payment Ref Info in request data"), 400)
                        payAmtTemp = float(request_data.get('trans_amount'))
                        payAmts = request_data.get('payAmts')
                        if payAmts:
                            payAmts = ast.literal_eval(payAmts)
                            for payAmt in payAmts:
                                payAmtTemp -= float(payAmt.get('AmtDue'))
                            if payAmtTemp != 0:
                                return invalid_response("payAmts_not_match",
                                                        _("The sum of payAmts must be equals trans_amount"), 400)
                        feesAmtTemp = request_data.get('feesAmt') or 0.00
                        feesAmts = request_data.get('feesAmts')
                        if feesAmts:
                            feesAmts = ast.literal_eval(feesAmts)
                            for feeAmt in feesAmts:
                                feesAmtTemp -= float(feeAmt.get('Amt'))
                            if feesAmtTemp != 0:
                                return invalid_response("feesAmts_not_match",
                                                        _("The sum of feesAmts must be equals feesAmt"), 400)

                    if ((provider_provider == 'fawry' and request_data.get('pmtType') == "POST") or provider_provider == 'khales') \
                            and not request_data.get('billRefNumber'):
                        return invalid_response("billRefNumber_not_found", _("missing bill reference number in request data"), 400)

                    # Provider is mandatory because the service fee is different per provider.
                    # So the user must send provider that own the bill inquiry request for prevent pay bill
                    # with total amount different of total amount in bill inquiry
                    if provider_provider:
                        provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                        if provider:
                            service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                                ('product_tmpl_id', '=', service.product_tmpl_id.id),
                                ('name', '=', provider.related_partner.id)
                            ])
                            if not service_providerinfo:
                                return invalid_response(
                                    "Incompatible_provider_service", _("%s is not a provider for (%s) service") % (
                                        provider_provider, service.name), 400)
                    else:
                        return invalid_response("provider_not_found",
                                                _("missing provider in request data"), 400)

                    trans_amount = float(request_data.get('trans_amount'))
                    if not trans_amount:
                        return invalid_response("amount_not_found",
                                                _("missing bill amount in request data"), 400)
                    else:
                        # Calculate Fees
                        provider_fees_calculated_amount = 0.0
                        provider_fees_actual_amount = 0.0
                        merchant_cashback_amount = 0.0
                        customer_cashback_amount = 0.0
                        extra_fees_amount = 0.0
                        commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                            domain=[('vendor', '=', service_providerinfo.name.id),
                                    ('vendor_product_code', '=', service_providerinfo.product_code)],
                            fields=['Amount_Range_From', 'Amount_Range_To',
                                    'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                    'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt',
                                    'Mer_Comm_Full_Fix_Amt', 'Cust_Comm_Full_Fix_Amt',
                                    'Bill_Merchant_Comm_Prc', 'Bill_Customer_Comm_Prc']
                        )
                        for commission in commissions:
                            if commission['Amount_Range_From'] <= trans_amount \
                                    and commission['Amount_Range_To'] >= trans_amount:
                                if commission['Mer_Comm_Full_Fix_Amt'] > 0:
                                    merchant_cashback_amount = commission['Mer_Comm_Full_Fix_Amt']
                                    customer_cashback_amount = commission['Cust_Comm_Full_Fix_Amt']
                                elif commission['Bill_Merchant_Comm_Prc'] > 0:
                                    merchant_cashback_amount = trans_amount * commission[
                                        'Bill_Merchant_Comm_Prc'] / 100
                                    customer_cashback_amount = trans_amount * commission[
                                        'Bill_Customer_Comm_Prc'] / 100
                                if commission['Extra_Fee_Amt'] > 0:
                                    extra_fees_amount = commission['Extra_Fee_Amt']
                                elif commission['Extra_Fee_Prc'] > 0:
                                    extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                                if commission['Mer_Fee_Amt'] > 0:
                                    provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                                elif commission['Mer_Fee_Prc'] > 0:
                                    # Fees amount = FA + [Percentage * Payment Amount]
                                    # Fees amount ====================> provider_fees_calculated_amount
                                    # FA =============================> provider_fees_calculated_amount
                                    # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                    provider_fees_prc_calculated_amount = trans_amount * commission[
                                        'Mer_Fee_Prc'] / 100
                                    if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                        provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                    elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                            and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                        provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                    provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                                elif provider_provider == 'khales':
                                    provider_fees_calculated_amount = float(request_data.get('feesAmt'))
                                break
                        calculated_payment_amount = trans_amount + provider_fees_calculated_amount + extra_fees_amount
                        machine_wallet_balance = request.env.user.partner_id.wallet_balance
                        if machine_wallet_balance < calculated_payment_amount:
                            return invalid_response("machine_balance_not_enough",
                                                    _("Machine Wallet Balance (%s) less than the payment amount (%s)") % (
                                                        machine_wallet_balance, calculated_payment_amount), 400)

            request_data['partner_id'] = request.env.user.partner_id.id
            model_name = 'smartpay_operations.request'
            model_record = request.env['ir.model'].sudo().search([('model', '=', model_name)])

            try:
                data = WebsiteForm().extract_data(model_record, request_data)
            # If we encounter an issue while extracting data
            except ValidationError as e:
                # I couldn't find a cleaner way to pass data to an exception
                return invalid_response("Error", _("Could not submit you request.") + " ==> " + str(e), 500)

            try:
                id_record = WebsiteForm().insert_record(request, model_record, data['record'], data['custom'], data.get('meta'))
                if id_record:
                    WebsiteForm().insert_attachment(model_record, id_record, data['attachments'])
                    request.env.cr.commit()
                    machine_request = model_record.env[model_name].sudo().browse(id_record)
                else:
                    return invalid_response("Error", _("Could not submit you request."), 500)

            # Some fields have additional SQL constraints that we can't check generically
            # Ex: crm.lead.probability which is a float between 0 and 1
            # TODO: How to get the name of the erroneous field ?
            except IntegrityError as e:
                return invalid_response("Error", _("Could not submit you request.") + " ==> " + str(e), 500)

            if request_data.get('request_type') == 'recharge_wallet':
                return valid_response({"message": _("Recharge your wallet request was submit successfully."),
                                        "request_number": machine_request.name
                                       })
            elif request_data.get('request_type') == 'wallet_invitation':
                return valid_response({"message": _("Wallet inivitation request for mobile number (%s) was submit successfully.") % (
                                                request_data.get('mobile_number')),
                                        "request_number": machine_request.name
                                       })
            elif request_data.get('request_type') == 'service_bill_inquiry':
                lang = request_data.get('lang')
                billingAcct = request_data.get('billingAcct')
                extraBillingAcctKeys = request_data.get('extraBillingAcctKeys')
                if extraBillingAcctKeys:
                    extraBillingAcctKeys = ast.literal_eval(extraBillingAcctKeys)

                provider_response = {}
                error = {}
                for provider_info in service.seller_ids:
                    provider = request.env['payment.acquirer'].sudo().search(
                        [("related_partner", "=", provider_info.name.id)])
                    if provider:
                        trans_amount = 0.0
                        provider_channel = False
                        machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                  ("type", "in", ("machine", "internet"))], limit=1)
                        if machine_channels:
                            provider_channel = machine_channels[0]
                        if provider.provider == "fawry":
                            provider_response = provider.get_fawry_bill_details(lang, provider_info.product_code,
                                                                                billingAcct, extraBillingAcctKeys, provider_channel)
                            if provider_response.get('Success'):
                                billRecType = provider_response.get('Success')
                                provider_response_json = suds_to_json(billRecType)
                                for BillSummAmt in billRecType['BillInfo']['BillSummAmt']:
                                    if BillSummAmt['BillSummAmtCode'] == 'TotalAmtDue':
                                        trans_amount += float(BillSummAmt['CurAmt']['Amt'])
                                        break
                        if provider.provider == "khales":
                            provider_response = {}
                            biller_info_json_dict = json.loads(provider_info.biller_info, strict=False)
                            bill_response = provider.get_khales_bill_details(lang, provider_info.product_code, biller_info_json_dict.get('Code'),
                                                                             billingAcct, extraBillingAcctKeys, provider_channel)
                            if bill_response.get('Success'):
                                billRecType = bill_response.get('Success')
                                payAmts = billRecType['BillInfo']['CurAmt']
                                if payAmts and isinstance(payAmts, OrderedDict):
                                    payAmts = [payAmts]
                                    billRecType['BillInfo']['CurAmt'] = payAmts
                                success_response = {'bill_response': suds_to_json(billRecType)}
                                # for payAmt in payAmts:
                                    # trans_amount += float(payAmt.get("AmtDue"))
                                trans_amount += float(payAmts[0].get("AmtDue"))
                                if biller_info_json_dict.get('PmtType') == 'POST':
                                    ePayBillRecID = billRecType['EPayBillRecID']
                                    fees_response = provider.get_khales_fees(lang, ePayBillRecID, payAmts[0], provider_channel)
                                    if fees_response.get('Success'):
                                        feeInqRsType = fees_response.get('Success')
                                        success_response.update({'fees_response': suds_to_json(feeInqRsType)})
                                provider_response = {'Success': success_response}

                                provider_response_json = provider_response.get('Success')
                            else:
                                provider_response = bill_response

                        if provider_response.get('Success'):
                            commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                                domain=[('vendor', '=', provider_info.name.id), ('vendor_product_code', '=', provider_info.product_code)],
                                fields=['Amount_Range_From', 'Amount_Range_To', 'Extra_Fee_Amt', 'Extra_Fee_Prc']
                            )
                            extra_fees_amount = 0.0
                            for commission in commissions:
                                if commission['Amount_Range_From'] <= trans_amount \
                                        and commission['Amount_Range_To'] >= trans_amount:
                                    if commission['Extra_Fee_Amt'] > 0:
                                        extra_fees_amount = commission['Extra_Fee_Amt']
                                    elif commission['Extra_Fee_Prc'] > 0:
                                        extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                                    break
                            machine_request.update(
                                {"provider_id": provider.id, "provider_response": provider_response_json,
                                 "trans_amount": trans_amount, "extra_fees_amount": extra_fees_amount,
                                 "extra_fees": commissions, "stage_id": 5})
                            request.env.cr.commit()
                            return valid_response(
                                {"message": _("Service Bill Inquiry request was submit successfully."),
                                 "request_number": machine_request.name,
                                 "provider": provider.provider,
                                 "provider_response": provider_response_json,
                                 "extra_fees_amount": extra_fees_amount,
                                 # "extra_fees": commissions
                                 })
                        else:
                            error.update({provider.provider + "_response": provider_response or ''})
                    else:
                        error.update({provider_info.name.name + "_response": _("%s is not a provider for (%s) service") % (
                        provider_info.name.name, service.name)})

                machine_request.update({
                    "provider_response": error or _("(%s) service has not any provider.") % (service.name),
                    "stage_id": 5
                })
                request.env.cr.commit()
                return invalid_response("Error", error or _("(%s) service has not any provider.") % (service.name), 400)

            elif request_data.get('request_type') == 'pay_service_bill':
                lang = request_data.get('lang')
                billingAcct = request_data.get('billingAcct')

                extraBillingAcctKeys = request_data.get('extraBillingAcctKeys')
                if extraBillingAcctKeys:
                    extraBillingAcctKeys = ast.literal_eval(extraBillingAcctKeys)

                notifyMobile = request_data.get('notifyMobile')
                billRefNumber = request_data.get('billRefNumber')
                billerId = request_data.get('billerId')
                pmtType = request_data.get('pmtType')

                trans_amount = request_data.get('trans_amount')
                curCode = request_data.get('currency_id')
                payAmts = request_data.get('payAmts')
                if payAmts:
                    payAmts = ast.literal_eval(payAmts)
                else:
                    payAmts = [{'Sequence': '1', 'AmtDue': trans_amount, 'CurCode': curCode}]
                pmtMethod = request_data.get('pmtMethod')

                ePayBillRecID = request_data.get('ePayBillRecID')
                pmtId = request_data.get('pmtId') or machine_request.name
                feesAmt = request_data.get('feesAmt') or 0.00
                feesAmts = request_data.get('feesAmts')
                if feesAmts:
                    feesAmts = ast.literal_eval(feesAmts)
                else:
                    feesAmts = [{'Amt': feesAmt, 'CurCode': curCode}]
                pmtRefInfo = request_data.get('pmtRefInfo')

                providers_info = []
                '''
                provider_provider = request_data.get('provider')
                if provider_provider:
                    provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                    if provider:
                        service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                            ('product_tmpl_id', '=', service.product_tmpl_id.id),
                            ('name', '=', provider.related_partner.id)
                        ])
                        if service_providerinfo:
                            providers_info.append(service_providerinfo)
                if not provider_provider or len(providers_info) == 0:
                    providers_info = service.seller_ids
                '''
                providers_info.append(service_providerinfo)

                provider_response = {}
                provider_response_json = {}
                '''
                provider_fees_calculated_amount = 0.0
                provider_fees_actual_amount = 0.0
                merchant_cashback_amount = 0.0
                customer_cashback_amount = 0.0
                extra_fees_amount = 0.0
                '''
                error = {}
                for provider_info in providers_info:
                    biller_info_json_dict = json.loads(provider_info.biller_info, strict=False)
                    '''
                    # Get Extra Fees
                    commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                        domain=[('vendor', '=', provider_info.name.id),
                                ('vendor_product_code', '=', provider_info.product_code)],
                        fields=['Amount_Range_From', 'Amount_Range_To',
                                'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt',
                                'Mer_Comm_Full_Fix_Amt', 'Cust_Comm_Full_Fix_Amt',
                                'Bill_Merchant_Comm_Prc', 'Bill_Customer_Comm_Prc']
                    )
                    for commission in commissions:
                        if commission['Amount_Range_From'] <= machine_request.trans_amount \
                                and commission['Amount_Range_To'] >= machine_request.trans_amount:
                            if commission['Mer_Comm_Full_Fix_Amt'] > 0:
                                merchant_cashback_amount = commission['Mer_Comm_Full_Fix_Amt']
                                customer_cashback_amount = commission['Cust_Comm_Full_Fix_Amt']
                            elif commission['Bill_Merchant_Comm_Prc'] > 0:
                                merchant_cashback_amount = machine_request.trans_amount * commission[
                                    'Bill_Merchant_Comm_Prc'] / 100
                                customer_cashback_amount = machine_request.trans_amount * commission[
                                    'Bill_Customer_Comm_Prc'] / 100
                            if commission['Extra_Fee_Amt'] > 0:
                                extra_fees_amount = commission['Extra_Fee_Amt']
                            elif commission['Extra_Fee_Prc'] > 0:
                                extra_fees_amount = machine_request.trans_amount * commission['Extra_Fee_Prc'] / 100
                            if commission['Mer_Fee_Amt'] > 0:
                                provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                            elif commission['Mer_Fee_Prc'] > 0:
                                # Fees amount = FA + [Percentage * Payment Amount]
                                # Fees amount ====================> provider_fees_calculated_amount
                                # FA =============================> provider_fees_calculated_amount
                                # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                provider_fees_prc_calculated_amount = machine_request.trans_amount * commission['Mer_Fee_Prc'] / 100
                                if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                        and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                            elif provider_provider == 'khales':
                                provider_fees_calculated_amount = float(request_data.get('feesAmt'))
                            break
                    calculated_payment_amount = machine_request.trans_amount + provider_fees_calculated_amount + extra_fees_amount
                    machine_wallet_balance = request.env.user.partner_id.wallet_balance
                    if machine_wallet_balance < calculated_payment_amount:
                        error.update({"machine_balance_not_enough":
                                                _("Machine Wallet Balance (%s) less than the payment amount (%s)") % (machine_wallet_balance,
                                                                                                                      calculated_payment_amount)})
                    '''

                    machine_request.update({'provider_fees_calculated_amount': provider_fees_calculated_amount})
                    request.env.cr.commit()
                    provider = request.env['payment.acquirer'].sudo().search([("related_partner", "=", provider_info.name.id)])
                    if provider:
                        try:
                            provider_channel = False
                            machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                      ("type", "in", ("machine", "internet"))], limit=1)
                            if machine_channels:
                                provider_channel = machine_channels[0]
                            if provider.provider == "fawry":
                                # Tamayoz TODO: Provider Server Timeout Handling
                                provider_response = provider.pay_fawry_bill(lang, provider_info.product_code,
                                                                            billingAcct, extraBillingAcctKeys,
                                                                            trans_amount, curCode, pmtMethod,
                                                                            notifyMobile, billRefNumber,
                                                                            billerId, pmtType, provider_channel)
                                if provider_response.get('Success'):
                                    provider_response_json = suds_to_json(provider_response.get('Success'))
                                    # Get Provider Fees
                                    provider_response_json_dict = json.loads(provider_response_json, strict=False)
                                    # provider_response_json_dict['PmtInfo']['CurAmt']['Amt'] == machine_request.trans_amount
                                    provider_fees_actual_amount = provider_response_json_dict['PmtInfo']['FeesAmt']['Amt']
                                    machine_request.update({'provider_fees_amount': provider_fees_actual_amount})
                                    request.env.cr.commit()
                                    # Get Provider Payment Trans ID
                                    for payment in provider_response_json_dict['PmtTransId']:
                                        if payment['PmtIdType'] == 'FCRN':
                                            provider_payment_trans_id = payment['PmtId']
                                            break
                            if provider.provider == "khales":
                                if not billerId:
                                    billerId = biller_info_json_dict.get('Code')
                                # Tamayoz TODO: Provider Server Timeout Handling
                                # Tamayoz TODO: Remove the next temporary line
                                pmtMethod = "CARD"  # TEMP CODE
                                provider_response = provider.pay_khales_bill(lang, billingAcct, billerId, ePayBillRecID,
                                                                             payAmts, pmtId, pmtType, feesAmts,
                                                                             billRefNumber, pmtMethod, pmtRefInfo,
                                                                             provider_channel)
                                if provider_response.get('Success'):
                                    provider_response_json = suds_to_json(provider_response.get('Success'))
                                    # Add required parameters for cancel payment scenario
                                    # parsing JSON string:
                                    provider_response_json_dict = json.loads(provider_response_json)
                                    pmtId = provider_response_json_dict['PmtRecAdviceStatus']['PmtTransId']['PmtId']
                                    # appending the data
                                    provider_response_json_dict.update({'billingAcct': billingAcct, 'billRefNumber': billRefNumber,
                                                                        'billerId': billerId, 'pmtType': pmtType, 'trans_amount': trans_amount,
                                                                        'curCode': curCode, 'pmtMethod': pmtMethod, 'ePayBillRecID': ePayBillRecID,
                                                                        'pmtId': pmtId, 'feesAmt': feesAmt, 'pmtRefInfo': pmtRefInfo})
                                    if payAmts:
                                        provider_response_json_dict.update({'payAmts': payAmts})
                                    if feesAmts:
                                        provider_response_json_dict.update({'feesAmts': feesAmts})
                                    # the result is a JSON string:
                                    provider_response_json = json.dumps(provider_response_json_dict)
                                    # Provider Fees
                                    provider_fees_actual_amount = float(feesAmt)
                                    machine_request.update({'provider_fees_amount': provider_fees_actual_amount})
                                    request.env.cr.commit()
                                    # Provider Payment Trans ID
                                    provider_payment_trans_id = pmtId

                            if provider_response.get('Success'):
                                try:
                                    provider_invoice_id = False
                                    refund = False
                                    customer_invoice_id = False
                                    credit_note = False
                                    machine_request_response = {"request_number": machine_request.name,
                                                                "request_datetime": machine_request.create_date + timedelta(hours=2),
                                                                "provider": provider.provider,
                                                                "provider_response": provider_response_json
                                                                }

                                    provider_actual_amount = machine_request.trans_amount + provider_fees_actual_amount
                                    customer_actual_amount = provider_actual_amount + extra_fees_amount

                                    # Deduct Transaction Amount from Machine Wallet Balance
                                    wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                                    label = _('Pay Service Bill for %s service') % (service.name)
                                    partner_id_wallet_balance = request.env.user.partner_id.wallet_balance
                                    machine_wallet_create = wallet_transaction_sudo.create(
                                        {'wallet_type': 'debit', 'partner_id': request.env.user.partner_id.id,
                                         'request_id': machine_request.id,
                                         'reference': 'request',
                                         'label': label,
                                         'amount': customer_actual_amount, 'currency_id': machine_request.currency_id.id,
                                         'wallet_balance_before': partner_id_wallet_balance,
                                         'wallet_balance_after': partner_id_wallet_balance - customer_actual_amount,
                                         'status': 'done'})
                                    request.env.cr.commit()

                                    request.env.user.partner_id.update(
                                        {'wallet_balance': request.env.user.partner_id.wallet_balance - customer_actual_amount})
                                    request.env.cr.commit()

                                    # Notify customer
                                    irc_param = request.env['ir.config_parameter'].sudo()
                                    wallet_pay_service_bill_notify_mode = irc_param.get_param("smartpay_operations.wallet_pay_service_bill_notify_mode")
                                    if wallet_pay_service_bill_notify_mode == 'inbox':
                                        request.env['mail.thread'].sudo().message_notify(
                                            subject=label,
                                            body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                                                customer_actual_amount, _(machine_request.currency_id.name)),
                                            partner_ids=[(4, request.env.user.partner_id.id)],
                                        )
                                    elif wallet_pay_service_bill_notify_mode == 'email':
                                        machine_wallet_create.wallet_transaction_email_send()
                                    elif wallet_pay_service_bill_notify_mode == 'sms' and request.env.user.partner_id.mobile:
                                        machine_wallet_create.sms_send_wallet_transaction(wallet_pay_service_bill_notify_mode,
                                                                                          'wallet_pay_service',
                                                                                          request.env.user.partner_id.mobile,
                                                                                          request.env.user.name, label,
                                                                                          '%s %s' % (customer_actual_amount,
                                                                                                     _(machine_request.currency_id.name)),
                                                                                          request.env.user.partner_id.country_id.phone_code or '2')

                                    payment_info = {"service": service.name, "provider": provider.provider,
                                                    "request_number": machine_request.name,
                                                    "request_datetime": machine_request.create_date + timedelta(hours=2),
                                                    "label": biller_info_json_dict.get("BillTypeAcctLabel"),
                                                    "billing_acct": billingAcct, "ref_number": provider_payment_trans_id,
                                                    "amount": trans_amount,
                                                    "fees": (provider_fees_actual_amount + extra_fees_amount),
                                                    "total": customer_actual_amount}

                                    machine_request.update(
                                        {'extra_fees_amount': extra_fees_amount,
                                         'wallet_transaction_id': machine_wallet_create.id,
                                         'trans_date': date.today(),
                                         'provider_id': provider.id,
                                         'provider_response': provider_response_json, "stage_id": 5})
                                    request.env.cr.commit()

                                    # VouchPIN Decryption if exist
                                    if provider_response_json_dict.get('VouchInfo'):
                                        decrypted_bytes = bytes(provider_response_json_dict['VouchInfo']['VouchPIN'],
                                                                encoding='utf-8')
                                        # text = base64.decodestring(decrypted_bytes) #
                                        text = base64.b64decode(decrypted_bytes)  #
                                        cipher = DES3.new(SECRET_KEY, DES3.MODE_ECB)
                                        VouchPIN = cipher.decrypt(text)
                                        VouchPIN = UNPAD(VouchPIN)
                                        VouchPIN = VouchPIN.decode('utf-8')  # unpad and decode bytes to str
                                        machine_request_response.update({'vouch_pin': VouchPIN})
                                        payment_info.update({"vouch_pin": VouchPIN,
                                                             "vouch_sn": provider_response_json_dict['VouchInfo']['VouchSN']})

                                    # Wallet Transaction Info with payment info
                                    machine_wallet_create.update({"wallet_transaction_info": json.dumps({"payment_info": payment_info}, default=default)})
                                    request.env.cr.commit()

                                    '''
                                    # Create Vendor (Provider) Invoices
                                    provider_invoice_ids = ()
                                    # 1- Create Vendor bill
                                    provider_journal_id = request.env['account.journal'].sudo().search([('type', '=', 'purchase'),
                                                                                              ('company_id', '=', request.env.user.company_id.id)], limit=1)
                                    name = provider.provider + ': [' + provider_info.product_code + '] ' + provider_info.product_name
                                    provider_invoice_vals = machine_request.with_context(name=name,
                                                                                         provider_payment_trans_id=provider_payment_trans_id,
                                                                                         journal_id=provider_journal_id.id,
                                                                                         invoice_date=date.today(),
                                                                                         invoice_type='in_invoice',
                                                                                         partner_id=provider_info.name.id)._prepare_invoice()
                                    provider_invoice_id = request.env['account.invoice'].sudo().create(provider_invoice_vals)
                                    invoice_line = provider_invoice_id._prepare_invoice_line_from_request(request=machine_request,
                                                                                                          name=name,
                                                                                                          qty=1,
                                                                                                          price_unit=provider_actual_amount)
                                    new_line = request.env['account.invoice.line'].sudo().new(invoice_line)
                                    new_line._set_additional_fields(provider_invoice_id)
                                    provider_invoice_id.invoice_line_ids += new_line
                                    provider_invoice_id.action_invoice_open()
                                    provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                    provider_invoice_id.pay_and_reconcile(request.env['account.journal'].sudo().search(
                                        [('type', '=', 'cash'),
                                         ('company_id', '=', request.env.user.company_id.id),
                                         ('provider_id', '=', provider.id)], limit=1),
                                        provider_actual_amount)
                                    request.env.cr.commit()
                                    # 2- Create Vendor Refund with commision amount
                                    if merchant_cashback_amount > 0:
                                        refund = request.env['account.invoice.refund'].with_context(
                                            active_ids=provider_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': name,
                                            'date': provider_invoice_id.date_invoice,
                                        })
                                        result = refund.invoice_refund()
                                        refund_id = result.get('domain')[1][2]
                                        refund = request.env['account.invoice'].sudo().browse(refund_id)
                                        refund.update({'reference': provider_payment_trans_id, 'request_id': machine_request.id})
                                        refund_line = refund.invoice_line_ids[0]
                                        refund_line.update({'price_unit': merchant_cashback_amount, 'request_id': machine_request.id})
                                        refund.refresh()
                                        refund.action_invoice_open()
                                        provider_invoice_ids += (tuple(refund.ids),)
                                    machine_request.update({'provider_invoice_ids': provider_invoice_ids})
                                    request.env.cr.commit()

                                    # Create Customer Invoices
                                    customer_invoice_ids = ()
                                    # 1- Create Customer Invoice
                                    customer_journal_id = request.env['account.journal'].sudo().search([('type', '=', 'sale'),
                                                                                              ('company_id', '=', request.env.user.company_id.id)], limit=1)
                                    customer_invoice_vals = machine_request.with_context(name=provider_payment_trans_id,
                                                                                         journal_id=customer_journal_id.id,
                                                                                         invoice_date=date.today(),
                                                                                         invoice_type='out_invoice',
                                                                                         partner_id=request.env.user.partner_id.id)._prepare_invoice()
                                    customer_invoice_id = request.env['account.invoice'].sudo().create(customer_invoice_vals)
                                    machine_request.invoice_line_create(invoice_id=customer_invoice_id.id, name=name,
                                                                        qty=1, price_unit=customer_actual_amount)
                                    customer_invoice_id.action_invoice_open()
                                    customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                    # Auto Reconcile customer invoice with prepaid wallet recharge payments and previous cashback credit note
                                    domain = [('account_id', '=', customer_invoice_id.account_id.id),
                                              ('partner_id', '=',
                                               customer_invoice_id.env['res.partner']._find_accounting_partner(customer_invoice_id.partner_id).id),
                                              ('reconciled', '=', False),
                                              '|',
                                              '&', ('amount_residual_currency', '!=', 0.0), ('currency_id', '!=', None),
                                              '&', ('amount_residual_currency', '=', 0.0), '&', ('currency_id', '=', None),
                                              ('amount_residual', '!=', 0.0)]
                                    domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                                    lines = customer_invoice_id.env['account.move.line'].sudo().search(domain)
                                    for line in lines:
                                        # get the outstanding residual value in invoice currency
                                        if line.currency_id and line.currency_id == customer_invoice_id.currency_id:
                                            amount_residual_currency = abs(line.amount_residual_currency)
                                        else:
                                            currency = line.company_id.currency_id
                                            amount_residual_currency = currency._convert(abs(line.amount_residual),
                                                                                         customer_invoice_id.currency_id,
                                                                                         customer_invoice_id.company_id,
                                                                                         line.date or fields.Date.today())
                                        if float_is_zero(amount_residual_currency, precision_rounding=customer_invoice_id.currency_id.rounding):
                                            continue

                                        customer_invoice_id.assign_outstanding_credit(line.id)
                                        if customer_invoice_id.state == 'paid':
                                            break
                                    request.env.cr.commit()

                                    # 2- Create Customer Credit Note with commision amount for only customers have commission
                                    if request.env.user.commission and customer_cashback_amount > 0:
                                        credit_note = request.env['account.invoice.refund'].with_context(
                                            active_ids=customer_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': provider_payment_trans_id,
                                            'date': customer_invoice_id.date_invoice,
                                        })
                                        result = credit_note.invoice_refund()
                                        credit_note_id = result.get('domain')[1][2]
                                        credit_note = request.env['account.invoice'].sudo().browse(credit_note_id)
                                        credit_note.update({'request_id': machine_request.id})
                                        credit_note_line = credit_note.invoice_line_ids[0]
                                        credit_note_line.update({'price_unit': customer_cashback_amount, 'request_id': machine_request.id})
                                        credit_note.refresh()
                                        """  Don't validate the customer credit note until the vendor refund reconciliation
                                        After vendor refund reconciliation, validate the customer credit note with
                                        the net amount of vendor refund sent in provider cashback statement then
                                        increase the customer wallet with the same net amount. """
                                        # credit_note.action_invoice_open()
                                        customer_invoice_ids += (tuple(credit_note.ids),)
                                    machine_request.update({'customer_invoice_ids': customer_invoice_ids})
                                    request.env.cr.commit()
                                    '''
                                    if provider.provider == "khales":
                                        # Add required parameters for cancel payment scenario
                                        machine_request_response.update({'billingAcct': billingAcct, 'billRefNumber': billRefNumber,
                                                                         'billerId': billerId, 'pmtType': pmtType, 'trans_amount': trans_amount,
                                                                         'curCode': curCode, 'pmtMethod': pmtMethod, 'ePayBillRecID': ePayBillRecID,
                                                                         'pmtId': pmtId, 'feesAmt': feesAmt, 'pmtRefInfo': pmtRefInfo})
                                        if payAmts:
                                            machine_request_response.update({'payAmts': payAmts})
                                        if feesAmts:
                                            machine_request_response.update({'feesAmts': feesAmts})
                                    machine_request_response.update({"message": _("Pay Service Bill request was submit successfully with amount %s %s. Your Machine Wallet Balance is %s %s")
                                                                            % (customer_actual_amount,
                                                                               machine_request.currency_id.name,
                                                                               request.env.user.partner_id.wallet_balance,
                                                                               machine_request.currency_id.name)})

                                    # Cancel
                                    # request_number = {"request_number": machine_request.name}
                                    # self.cancel_request(**request_number)

                                    return valid_response(machine_request_response)
                                except Exception as e:
                                    try:
                                        _logger.error("%s", e)
                                        machine_request_update = {'extra_fees_amount': extra_fees_amount,
                                                                  'trans_date': date.today(),
                                                                  'provider_id': provider.id,
                                                                  'provider_response': provider_response_json, "stage_id": 5,
                                                                  'description': _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e)}
                                        if machine_wallet_create:
                                            machine_request_update.update({'wallet_transaction_id': machine_wallet_create.id})
                                        provider_invoice_ids = ()
                                        if provider_invoice_id or refund:
                                            if provider_invoice_id:
                                                provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                            if refund:
                                                provider_invoice_ids += (tuple(refund.ids),)
                                            machine_request_update.update({'provider_invoice_ids': provider_invoice_ids})
                                        customer_invoice_ids = ()
                                        if customer_invoice_id or credit_note:
                                            if customer_invoice_id:
                                                customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                            if credit_note:
                                                customer_invoice_ids += (tuple(credit_note.ids),)
                                            machine_request_update.update({'customer_invoice_ids': customer_invoice_ids})
                                        machine_request.update(machine_request_update)
                                        request.env.cr.commit()
                                    except Exception as e1:
                                        _logger.error("%s", e1)
                                        if machine_request and not machine_request.description:
                                            machine_request.update({'description': _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e)})
                                            request.env.cr.commit()

                                    return invalid_response(machine_request_response, _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e),
                                                            500)
                            else:
                                error.update({provider.provider + "_response": provider_response or ''})
                        except Exception as e2:
                            _logger.error("%s", e2)
                            if machine_request and not machine_request.description:
                                machine_request.update({'description': _("Error is occur:") + " ==> " + str(e2)})
                                request.env.cr.commit()
                            return invalid_response("Error", _("Error is occur:") + " ==> " + str(e), 500)
                    else:
                        error.update({provider_info.name.name + "_response": _("%s is not a provider for (%s) service") % (
                            provider_info.name.name, service.name)})

                machine_request.update({
                    'provider_response': error or _('(%s) service has not any provider.') % (service.name),
                    'stage_id': 5
                })
                request.env.cr.commit()
                return invalid_response("Error", error or _("(%s) service has not any provider.") % (service.name), 400)

            elif request_data.get('request_type') == 'pay_invoice':
                return valid_response({"message": _("Pay invoice request was submit successfully."),
                                       "request_number": machine_request.name
                                       })
            else:
                return valid_response({"message": _("Your request was submit successfully."),
                                       "request_number":machine_request.name
                                       })

        @validate_token
        @http.route('/api/create_mobile_request', type="http", auth="none", methods=["POST"], csrf=False)
        def create_mobile_request(self, **request_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Mobile Request API")

            if not request_data.get('request_type') or request_data.get('request_type') not in _REQUEST_TYPES_IDS:
                return invalid_response("request_type", _("request type invalid"), 400)

            if request_data.get('request_type') == 'recharge_wallet':
                if not request_data.get('trans_amount'):
                    return invalid_response("amount_not_found", _("missing amount in request data"), 400)
                open_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'recharge_wallet'),("partner_id", "=", request.env.user.partner_id.id), ("stage_id", "=", 1)],
                    order="id DESC", limit=1)
                if open_request:
                    return invalid_response("request_already_exist", _("You have a wallet recharge request in progress with REQ Number (%s)")
                                            % (open_request.name), 400)
                request_data['product_id'] = request.env["product.product"].sudo().search([('name', '=', 'Wallet Recharge')]).id

            if not request_data.get('product_id') and request_data.get('request_type') not in ('general_inquiry', 'wallet_invitation'):
                return invalid_response("service_not_found", _("missing service in request data"), 400)
            elif request_data.get('request_type') not in ('general_inquiry', 'wallet_invitation'):
                service = request.env["product.product"].sudo().search([("id", "=", request_data.get('product_id')), ("type", "=", "service")],
                                                                       order="id DESC", limit=1)
                if not service:
                    return invalid_response("service", _("service invalid"), 400)

            if request_data.get('request_type') == 'wallet_invitation':
                if not request_data.get('mobile_number'):
                    return invalid_response("mobile_number_not_found", _("missing mobile number for invited user in request data"), 400)

                open_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'wallet_invitation'), ('mobile_number', '=', request_data.get('mobile_number')),
                     ('partner_id', '=', request.env.user.partner_id.id), ("stage_id", "=", 1)], order="id DESC", limit=1)
                if open_request:
                    return invalid_response("request_already_exist",
                                            _("You have a wallet invitation request in progress for mobile number (%s) with REQ Number (%s)") % (
                                                request_data.get('mobile_number'), open_request.name), 400)

                done_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'wallet_invitation'),
                     ('mobile_number', '=', request_data.get('mobile_number')), ("stage_id", "=", 5)],
                    order="id DESC", limit=1)
                if done_request:
                    return invalid_response("request_already_exist",
                                            _("The mobile number (%s) already has a wallet") % (
                                                request_data.get('mobile_number')), 400)

            if request_data.get('request_type') == 'service_bill_inquiry' or request_data.get('request_type') == 'pay_service_bill':
                if not request_data.get('billingAcct'):
                    return invalid_response("billingAcct_not_found", _("missing billing account in request data"), 400)

                if request_data.get('request_type') == 'pay_service_bill':
                    if not request_data.get('currency_id'):
                        return invalid_response("curCode_not_found",
                                                _("missing bill currency code in request data"), 400)
                    if not request_data.get('pmtMethod'):
                        return invalid_response("pmtMethod_not_found",
                                                _("missing payment method in request data"), 400)

                    provider_provider = request_data.get('provider')
                    if provider_provider == 'khales':
                        if not request_data.get('pmtType'):
                            return invalid_response("pmtType_not_found", _("missing payment type in request data"), 400)
                        '''
                        if not request_data.get('billerId'):
                            return invalid_response("billerId_not_found", _("missing biller id in request data"), 400)
                        '''
                        if not request_data.get('ePayBillRecID'):
                            return invalid_response("ePayBillRecID_not_found", _("missing ePay Bill Rec ID in request data"), 400)
                        if not request_data.get('pmtId'):
                            return invalid_response("pmtId_not_found", _("missing payment id in request data"), 400)
                        if not request_data.get('feesAmt'):
                            return invalid_response("feesAmt_not_found", _("missing fees amount in request data"), 400)
                        # if not request_data.get('pmtRefInfo'):
                            # return invalid_response("pmtRefInfo_not_found", _("missing payment Ref Info in request data"), 400)
                        payAmtTemp = float(request_data.get('trans_amount'))
                        payAmts = request_data.get('payAmts')
                        if payAmts:
                            payAmts = ast.literal_eval(payAmts)
                            for payAmt in payAmts:
                                payAmtTemp -= float(payAmt.get('AmtDue'))
                            if payAmtTemp != 0:
                                return invalid_response("payAmts_not_match",
                                                        _("The sum of payAmts must be equals trans_amount"), 400)

                        feesAmtTemp = request_data.get('feesAmt') or 0.00
                        feesAmts = request_data.get('feesAmts')
                        if feesAmts:
                            feesAmts = ast.literal_eval(feesAmts)
                            for feeAmt in feesAmts:
                                feesAmtTemp -= float(feeAmt.get('Amt'))
                            if feesAmtTemp != 0:
                                return invalid_response("feesAmts_not_match",
                                                        _("The sum of feesAmts must be equals feesAmt"), 400)

                    if ((provider_provider == 'fawry' and request_data.get('pmtType') == "POST") or provider_provider == 'khales') \
                            and not request_data.get('billRefNumber'):
                        return invalid_response("billRefNumber_not_found", _("missing bill reference number in request data"), 400)

                    # Provider is mandatory because the service fee is different per provider.
                    # So the user must send provider that own the bill inquiry request for prevent pay bill
                    # with total amount different of total amount in bill inquiry
                    if provider_provider:
                        provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                        if provider:
                            service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                                ('product_tmpl_id', '=', service.product_tmpl_id.id),
                                ('name', '=', provider.related_partner.id)
                            ])
                            if not service_providerinfo:
                                return invalid_response(
                                    "Incompatible_provider_service", _("%s is not a provider for (%s) service") % (
                                        provider_provider, service.name), 400)
                    else:
                        return invalid_response("provider_not_found",
                                                _("missing provider in request data"), 400)

                    trans_amount = float(request_data.get('trans_amount'))
                    if not trans_amount:
                        return invalid_response("amount_not_found",
                                                _("missing bill amount in request data"), 400)
                    else:
                        # Calculate Fees
                        provider_fees_calculated_amount = 0.0
                        provider_fees_actual_amount = 0.0
                        merchant_cashback_amount = 0.0
                        customer_cashback_amount = 0.0
                        extra_fees_amount = 0.0
                        commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                            domain=[('vendor', '=', service_providerinfo.name.id),
                                    ('vendor_product_code', '=', service_providerinfo.product_code)],
                            fields=['Amount_Range_From', 'Amount_Range_To',
                                    'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                    'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt',
                                    'Mer_Comm_Full_Fix_Amt', 'Cust_Comm_Full_Fix_Amt',
                                    'Bill_Merchant_Comm_Prc', 'Bill_Customer_Comm_Prc']
                        )
                        for commission in commissions:
                            if commission['Amount_Range_From'] <= trans_amount \
                                    and commission['Amount_Range_To'] >= trans_amount:
                                if commission['Mer_Comm_Full_Fix_Amt'] > 0:
                                    merchant_cashback_amount = commission['Mer_Comm_Full_Fix_Amt']
                                    customer_cashback_amount = commission['Cust_Comm_Full_Fix_Amt']
                                elif commission['Bill_Merchant_Comm_Prc'] > 0:
                                    merchant_cashback_amount = trans_amount * commission[
                                        'Bill_Merchant_Comm_Prc'] / 100
                                    customer_cashback_amount = trans_amount * commission[
                                        'Bill_Customer_Comm_Prc'] / 100
                                if commission['Extra_Fee_Amt'] > 0:
                                    extra_fees_amount = commission['Extra_Fee_Amt']
                                elif commission['Extra_Fee_Prc'] > 0:
                                    extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                                if commission['Mer_Fee_Amt'] > 0:
                                    provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                                elif commission['Mer_Fee_Prc'] > 0:
                                    # Fees amount = FA + [Percentage * Payment Amount]
                                    # Fees amount ====================> provider_fees_calculated_amount
                                    # FA =============================> provider_fees_calculated_amount
                                    # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                    provider_fees_prc_calculated_amount = trans_amount * commission[
                                        'Mer_Fee_Prc'] / 100
                                    if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                        provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                    elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                            and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                        provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                    provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                                elif provider_provider == 'khales':
                                    provider_fees_calculated_amount = float(request_data.get('feesAmt'))
                                break
                        calculated_payment_amount = trans_amount + provider_fees_calculated_amount + extra_fees_amount
                        mobile_wallet_balance = request.env.user.partner_id.wallet_balance
                        if mobile_wallet_balance < calculated_payment_amount:
                            return invalid_response("mobile_balance_not_enough",
                                                    _("Mobile Wallet Balance (%s) less than the payment amount (%s)") % (
                                                        mobile_wallet_balance, calculated_payment_amount), 400)

            request_data['partner_id'] = request.env.user.partner_id.id
            model_name = 'smartpay_operations.request'
            model_record = request.env['ir.model'].sudo().search([('model', '=', model_name)])

            try:
                data = WebsiteForm().extract_data(model_record, request_data)
            # If we encounter an issue while extracting data
            except ValidationError as e:
                # I couldn't find a cleaner way to pass data to an exception
                return invalid_response("Error", _("Could not submit you request.") + " ==> " + str(e), 500)

            try:
                id_record = WebsiteForm().insert_record(request, model_record, data['record'], data['custom'], data.get('meta'))
                if id_record:
                    WebsiteForm().insert_attachment(model_record, id_record, data['attachments'])
                    request.env.cr.commit()
                    user_request = model_record.env[model_name].sudo().browse(id_record)
                else:
                    return invalid_response("Error", _("Could not submit you request."), 500)

            # Some fields have additional SQL constraints that we can't check generically
            # Ex: crm.lead.probability which is a float between 0 and 1
            # TODO: How to get the name of the erroneous field ?
            except IntegrityError as e:
                return invalid_response("Error", _("Could not submit you request.") + " ==> " + str(e), 500)

            if request_data.get('request_type') == 'recharge_wallet':
                return valid_response({"message": _("Recharge your wallet request was submit successfully."),
                                       "request_number": user_request.name
                                       })
            elif request_data.get('request_type') == 'wallet_invitation':
                return valid_response({"message": _("Wallet inivitation request for mobile number (%s) was submit successfully.") % (
                                                request_data.get('mobile_number')),
                                        "request_number": user_request.name
                                       })

            elif request_data.get('request_type') == 'service_bill_inquiry':
                lang = request_data.get('lang')
                billingAcct = request_data.get('billingAcct')
                extraBillingAcctKeys = request_data.get('extraBillingAcctKeys')
                if extraBillingAcctKeys:
                    extraBillingAcctKeys = ast.literal_eval(extraBillingAcctKeys)

                provider_response = {}
                error = {}
                for provider_info in service.seller_ids:
                    provider = request.env['payment.acquirer'].sudo().search([("related_partner", "=", provider_info.name.id)])
                    if provider:
                        trans_amount = 0.0
                        provider_channel = False
                        machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                  ("type", "in", ("machine", "internet"))], limit=1)
                        if machine_channels:
                            provider_channel = machine_channels[0]

                        if provider.provider == "fawry":
                            provider_response = provider.get_fawry_bill_details(lang, provider_info.product_code,
                                                                                billingAcct, extraBillingAcctKeys, provider_channel)
                            if provider_response.get('Success'):
                                billRecType = provider_response.get('Success')
                                provider_response_json = suds_to_json(billRecType)
                                for BillSummAmt in billRecType['BillInfo']['BillSummAmt']:
                                    if BillSummAmt['BillSummAmtCode'] == 'TotalAmtDue':
                                        trans_amount += float(BillSummAmt['CurAmt']['Amt'])
                                        break
                        if provider.provider == "khales":
                            provider_response = {}
                            biller_info_json_dict = json.loads(provider_info.biller_info, strict=False)
                            bill_response = provider.get_khales_bill_details(lang, provider_info.product_code, biller_info_json_dict.get('Code'),
                                                                             billingAcct, extraBillingAcctKeys, provider_channel)
                            if bill_response.get('Success'):
                                billRecType = bill_response.get('Success')
                                payAmts = billRecType['BillInfo']['CurAmt']
                                if payAmts and isinstance(payAmts, OrderedDict):
                                    payAmts = [payAmts]
                                    billRecType['BillInfo']['CurAmt'] = payAmts
                                success_response = {'bill_response': suds_to_json(billRecType)}
                                # for payAmt in payAmts:
                                    # trans_amount += float(payAmt.get("AmtDue"))
                                trans_amount += float(payAmts[0].get("AmtDue"))
                                if biller_info_json_dict.get('PmtType') == 'POST':
                                    ePayBillRecID = billRecType['EPayBillRecID']
                                    fees_response = provider.get_khales_fees(lang, ePayBillRecID, payAmts[0], provider_channel)
                                    if fees_response.get('Success'):
                                        feeInqRsType = fees_response.get('Success')
                                        success_response.update({'fees_response': suds_to_json(feeInqRsType)})
                                provider_response = {'Success': success_response}

                                provider_response_json = provider_response.get('Success')
                            else:
                                provider_response = bill_response

                        if provider_response.get('Success'):
                            # if not provider_response_json:
                                # provider_response_json = suds_to_json(provider_response.get('Success'))
                            commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                                domain=[('vendor', '=', provider_info.name.id), ('vendor_product_code', '=', provider_info.product_code)],
                                fields=['Amount_Range_From', 'Amount_Range_To', 'Extra_Fee_Amt', 'Extra_Fee_Prc']
                            )
                            extra_fees_amount = 0.0
                            for commission in commissions:
                                if commission['Amount_Range_From'] <= trans_amount \
                                        and commission['Amount_Range_To'] >= trans_amount:
                                    if commission['Extra_Fee_Amt'] > 0:
                                        extra_fees_amount = commission['Extra_Fee_Amt']
                                    elif commission['Extra_Fee_Prc'] > 0:
                                        extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                                    break
                            user_request.update(
                                {"provider_id": provider.id, "provider_response": provider_response_json,
                                 "trans_amount": trans_amount, "extra_fees_amount": extra_fees_amount,
                                 "extra_fees": commissions, "stage_id": 5})
                            request.env.cr.commit()
                            return valid_response(
                                {"message": _("Service Bill Inquiry request was submit successfully."),
                                 "request_number": user_request.name,
                                 "provider": provider.provider,
                                 "provider_response": provider_response_json,
                                 "extra_fees_amount": extra_fees_amount,
                                 # "extra_fees": commissions
                                 })
                        else:
                            error.update({provider.provider + "_response": provider_response or ''})
                    else:
                        error.update({provider_info.name.name + "_response": _("%s is not a provider for (%s) service") % (
                            provider_info.name.name, service.name)})

                user_request.update({
                    "provider_response": error or _("(%s) service has not any provider.") % (service.name),
                    "stage_id": 5
                })
                request.env.cr.commit()
                return invalid_response("Error", error or _("(%s) service has not any provider.") % (service.name), 400)

            elif request_data.get('request_type') == 'pay_service_bill':
                lang = request_data.get('lang')
                billingAcct = request_data.get('billingAcct')

                extraBillingAcctKeys = request_data.get('extraBillingAcctKeys')
                if extraBillingAcctKeys:
                    extraBillingAcctKeys = ast.literal_eval(extraBillingAcctKeys)

                notifyMobile = request_data.get('notifyMobile')
                billRefNumber = request_data.get('billRefNumber')
                billerId = request_data.get('billerId')
                pmtType = request_data.get('pmtType')

                trans_amount = request_data.get('trans_amount')
                curCode = request_data.get('currency_id')
                payAmts = request_data.get('payAmts')
                if payAmts:
                    payAmts = ast.literal_eval(payAmts)
                else:
                    payAmts = [{'Sequence':'1', 'AmtDue':trans_amount, 'CurCode':curCode}]
                pmtMethod = request_data.get('pmtMethod')

                ePayBillRecID = request_data.get('ePayBillRecID')
                pmtId = request_data.get('pmtId') or user_request.name
                feesAmt = request_data.get('feesAmt') or 0.00
                feesAmts = request_data.get('feesAmts')
                if feesAmts:
                    feesAmts = ast.literal_eval(feesAmts)
                else:
                    feesAmts = [{'Amt': feesAmt, 'CurCode': curCode}]
                pmtRefInfo = request_data.get('pmtRefInfo')

                providers_info = []
                '''
                provider_provider = request_data.get('provider')
                if provider_provider:
                    provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                    if provider:
                        service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                            ('product_tmpl_id', '=', service.product_tmpl_id.id),
                            ('name', '=', provider.related_partner.id)
                        ])
                        if service_providerinfo:
                            providers_info.append(service_providerinfo)
                if not provider_provider or len(providers_info) == 0:
                    providers_info = service.seller_ids
                '''
                providers_info.append(service_providerinfo)

                provider_response = {}
                provider_response_json = {}
                '''
                provider_fees_calculated_amount = 0.0
                provider_fees_actual_amount = 0.0
                merchant_cashback_amount = 0.0
                customer_cashback_amount = 0.0
                extra_fees_amount = 0.0
                '''
                error = {}
                for provider_info in providers_info:
                    biller_info_json_dict = json.loads(provider_info.biller_info, strict=False)
                    '''
                    # Get Extra Fees
                    commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                        domain=[('vendor', '=', provider_info.name.id),
                                ('vendor_product_code', '=', provider_info.product_code)],
                        fields=['Amount_Range_From', 'Amount_Range_To',
                                'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt',
                                'Mer_Comm_Full_Fix_Amt', 'Cust_Comm_Full_Fix_Amt',
                                'Bill_Merchant_Comm_Prc', 'Bill_Customer_Comm_Prc']
                    )
                    for commission in commissions:
                        if commission['Amount_Range_From'] <= machine_request.trans_amount \
                                and commission['Amount_Range_To'] >= machine_request.trans_amount:
                            if commission['Mer_Comm_Full_Fix_Amt'] > 0:
                                merchant_cashback_amount = commission['Mer_Comm_Full_Fix_Amt']
                                customer_cashback_amount = commission['Cust_Comm_Full_Fix_Amt']
                            elif commission['Bill_Merchant_Comm_Prc'] > 0:
                                merchant_cashback_amount = machine_request.trans_amount * commission[
                                    'Bill_Merchant_Comm_Prc'] / 100
                                customer_cashback_amount = machine_request.trans_amount * commission[
                                    'Bill_Customer_Comm_Prc'] / 100
                            if commission['Extra_Fee_Amt'] > 0:
                                extra_fees_amount = commission['Extra_Fee_Amt']
                            elif commission['Extra_Fee_Prc'] > 0:
                                extra_fees_amount = machine_request.trans_amount * commission['Extra_Fee_Prc'] / 100
                            if commission['Mer_Fee_Amt'] > 0:
                                provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                            elif commission['Mer_Fee_Prc'] > 0:
                                # Fees amount = FA + [Percentage * Payment Amount]
                                # Fees amount ====================> provider_fees_calculated_amount
                                # FA =============================> provider_fees_calculated_amount
                                # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                provider_fees_prc_calculated_amount = machine_request.trans_amount * commission['Mer_Fee_Prc'] / 100
                                if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                        and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                            elif provider_provider == 'khales':
                                provider_fees_calculated_amount = float(request_data.get('feesAmt'))
                            break
                    calculated_payment_amount = machine_request.trans_amount + provider_fees_calculated_amount + extra_fees_amount
                    mobile_wallet_balance = request.env.user.partner_id.wallet_balance
                    if mobile_wallet_balance < calculated_payment_amount:
                        error.update({"mobile_balance_not_enough":
                                                _("Mobile Wallet Balance (%s) less than the payment amount (%s)") % (mobile_wallet_balance,
                                                                                                                      calculated_payment_amount)})
                    '''

                    user_request.update({'provider_fees_calculated_amount': provider_fees_calculated_amount})
                    request.env.cr.commit()
                    provider = request.env['payment.acquirer'].sudo().search([("related_partner", "=", provider_info.name.id)])
                    if provider:
                        try:
                            provider_channel = False
                            machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                      ("type", "in", ("mobile", "internet"))], limit=1)
                            if machine_channels:
                                provider_channel = machine_channels[0]
                            if provider.provider == "fawry":
                                # Tamayoz TODO: Provider Server Timeout Handling
                                provider_response = provider.pay_fawry_bill(lang, provider_info.product_code,
                                                                            billingAcct, extraBillingAcctKeys,
                                                                            trans_amount, curCode, pmtMethod,
                                                                            notifyMobile, billRefNumber,
                                                                            billerId, pmtType, provider_channel)
                                if provider_response.get('Success'):
                                    provider_response_json = suds_to_json(provider_response.get('Success'))
                                    # Get Provider Fees
                                    provider_response_json_dict = json.loads(provider_response_json, strict=False)
                                    # provider_response_json_dict['PmtInfo']['CurAmt']['Amt'] == user_request.trans_amount
                                    provider_fees_actual_amount = provider_response_json_dict['PmtInfo']['FeesAmt']['Amt']
                                    user_request.update({'provider_fees_amount': provider_fees_actual_amount})
                                    request.env.cr.commit()
                                    # Get Provider Payment Trans ID
                                    for payment in provider_response_json_dict['PmtTransId']:
                                        if payment['PmtIdType'] == 'FCRN':
                                            provider_payment_trans_id = payment['PmtId']
                                            break

                            if provider.provider == "khales":
                                if not billerId:
                                    billerId = biller_info_json_dict.get('Code')
                                # Tamayoz TODO: Provider Server Timeout Handling
                                # Tamayoz TODO: Remove the next temporary line
                                pmtMethod = "CARD"  # TEMP CODE
                                provider_response = provider.pay_khales_bill(lang, billingAcct, billerId, ePayBillRecID,
                                                                             payAmts, pmtId, pmtType, feesAmts,
                                                                             billRefNumber, pmtMethod, pmtRefInfo,
                                                                             provider_channel)
                                if provider_response.get('Success'):
                                    provider_response_json = suds_to_json(provider_response.get('Success'))
                                    # Add required parameters for cancel payment scenario
                                    # parsing JSON string:
                                    provider_response_json_dict = json.loads(provider_response_json)
                                    pmtId = provider_response_json_dict['PmtRecAdviceStatus']['PmtTransId']['PmtId']
                                    # appending the data
                                    provider_response_json_dict.update({'billingAcct': billingAcct, 'billRefNumber': billRefNumber,
                                                                        'billerId': billerId, 'pmtType': pmtType, 'trans_amount': trans_amount,
                                                                        'curCode': curCode, 'pmtMethod': pmtMethod, 'ePayBillRecID': ePayBillRecID,
                                                                        'pmtId': pmtId, 'feesAmt': feesAmt, 'pmtRefInfo': pmtRefInfo})
                                    if payAmts:
                                        provider_response_json_dict.update({'payAmts': payAmts})
                                    if feesAmts:
                                        provider_response_json_dict.update({'feesAmts': feesAmts})
                                    # the result is a JSON string:
                                    provider_response_json = json.dumps(provider_response_json_dict)
                                    # Provider Fees
                                    provider_fees_actual_amount = float(feesAmt)
                                    user_request.update({'provider_fees_amount': provider_fees_actual_amount})
                                    request.env.cr.commit()
                                    # Provider Payment Trans ID
                                    provider_payment_trans_id = pmtId

                            if provider_response.get('Success'):
                                try:
                                    provider_invoice_id = False
                                    refund = False
                                    customer_invoice_id = False
                                    credit_note = False
                                    user_request_response = {"request_number": user_request.name,
                                                             "request_datetime": user_request.create_date + timedelta(hours=2),
                                                             "provider": provider.provider,
                                                             "provider_response": provider_response_json
                                                             }

                                    provider_actual_amount = user_request.trans_amount + provider_fees_actual_amount
                                    customer_actual_amount = provider_actual_amount + extra_fees_amount

                                    # Deduct Transaction Amount from Mobile Wallet Balance
                                    wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                                    label = _('Pay Service Bill for %s service') % (service.name)
                                    partner_id_wallet_balance = request.env.user.partner_id.wallet_balance
                                    mobile_wallet_create = wallet_transaction_sudo.create(
                                        {'wallet_type': 'debit', 'partner_id': request.env.user.partner_id.id,
                                         'request_id': user_request.id,
                                         'reference': 'request',
                                         'label': label,
                                         'amount': customer_actual_amount, 'currency_id': user_request.currency_id.id,
                                         'wallet_balance_before': partner_id_wallet_balance,
                                         'wallet_balance_after': partner_id_wallet_balance - customer_actual_amount,
                                         'status': 'done'})
                                    request.env.cr.commit()

                                    request.env.user.partner_id.update(
                                        {'wallet_balance': request.env.user.partner_id.wallet_balance - customer_actual_amount})
                                    request.env.cr.commit()

                                    # Notify user
                                    irc_param = request.env['ir.config_parameter'].sudo()
                                    wallet_pay_service_bill_notify_mode = irc_param.get_param("smartpay_operations.wallet_pay_service_bill_notify_mode")
                                    if wallet_pay_service_bill_notify_mode == 'inbox':
                                        request.env['mail.thread'].sudo().message_notify(
                                            subject=label,
                                            body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                                                customer_actual_amount, _(user_request.currency_id.name)),
                                            partner_ids=[(4, request.env.user.partner_id.id)],
                                        )
                                    elif wallet_pay_service_bill_notify_mode == 'email':
                                        mobile_wallet_create.wallet_transaction_email_send()
                                    elif wallet_pay_service_bill_notify_mode == 'sms' and request.env.user.partner_id.mobile:
                                        mobile_wallet_create.sms_send_wallet_transaction(wallet_pay_service_bill_notify_mode,
                                                                                         'wallet_pay_service',
                                                                                         request.env.user.partner_id.mobile,
                                                                                         request.env.user.name, label,
                                                                                         '%s %s' % (customer_actual_amount,
                                                                                                    _(user_request.currency_id.name)),
                                                                                         request.env.user.partner_id.country_id.phone_code or '2')

                                    payment_info = {"service": service.name, "provider": provider.provider,
                                                    "request_number": user_request.name,
                                                    "request_datetime": user_request.create_date + timedelta(hours=2),
                                                    "label": biller_info_json_dict.get("BillTypeAcctLabel"),
                                                    "billing_acct": billingAcct, "ref_number": provider_payment_trans_id,
                                                    "amount": trans_amount,
                                                    "fees": (provider_fees_actual_amount + extra_fees_amount),
                                                    "total": customer_actual_amount}

                                    user_request.update(
                                        {'extra_fees_amount': extra_fees_amount,
                                         'wallet_transaction_id': mobile_wallet_create.id,
                                         'trans_date': date.today(),
                                         'provider_id': provider.id,
                                         'provider_response': provider_response_json, "stage_id": 5})
                                    request.env.cr.commit()

                                    # VouchPIN Decryption if exist
                                    if provider_response_json_dict.get('VouchInfo'):
                                        decrypted_bytes = bytes(provider_response_json_dict['VouchInfo']['VouchPIN'],
                                                                encoding='utf-8')
                                        # text = base64.decodestring(decrypted_bytes) #
                                        text = base64.b64decode(decrypted_bytes)  #
                                        cipher = DES3.new(SECRET_KEY, DES3.MODE_ECB)
                                        VouchPIN = cipher.decrypt(text)
                                        VouchPIN = UNPAD(VouchPIN)
                                        VouchPIN = VouchPIN.decode('utf-8')  # unpad and decode bytes to str
                                        user_request_response.update({'vouch_pin': VouchPIN})
                                        payment_info.update({"vouch_pin": VouchPIN,
                                                             "vouch_sn": provider_response_json_dict['VouchInfo']['VouchSN']})

                                    # Wallet Transaction Info with payment info
                                    mobile_wallet_create.update({"wallet_transaction_info": json.dumps({"payment_info": payment_info}, default=default)})
                                    request.env.cr.commit()

                                    '''
                                    # Create Vendor (Provider) Invoices
                                    provider_invoice_ids = ()
                                    # 1- Create Vendor bill
                                    provider_journal_id = request.env['account.journal'].sudo().search([('type', '=', 'purchase'),
                                                                                              ('company_id', '=', request.env.user.company_id.id)], limit=1)
                                    name = provider.provider + ': [' + provider_info.product_code + '] ' + provider_info.product_name
                                    provider_invoice_vals = user_request.with_context(name=name,
                                                                                      provider_payment_trans_id=provider_payment_trans_id,
                                                                                      journal_id=provider_journal_id.id,
                                                                                      invoice_date=date.today(),
                                                                                      invoice_type='in_invoice',
                                                                                      partner_id=provider_info.name.id)._prepare_invoice()
                                    provider_invoice_id = request.env['account.invoice'].sudo().create(provider_invoice_vals)
                                    invoice_line = provider_invoice_id._prepare_invoice_line_from_request(request=user_request,
                                                                                                          name=name,
                                                                                                          qty=1,
                                                                                                          price_unit=provider_actual_amount)
                                    new_line = request.env['account.invoice.line'].sudo().new(invoice_line)
                                    new_line._set_additional_fields(provider_invoice_id)
                                    provider_invoice_id.invoice_line_ids += new_line
                                    provider_invoice_id.action_invoice_open()
                                    provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                    provider_invoice_id.pay_and_reconcile(request.env['account.journal'].sudo().search(
                                        [('type', '=', 'cash'),
                                         ('company_id', '=', request.env.user.company_id.id),
                                         ('provider_id', '=', provider.id)], limit=1),
                                        provider_actual_amount)
                                    request.env.cr.commit()
                                    # 2- Create Vendor Refund with commision amount
                                    if merchant_cashback_amount > 0:
                                        refund = request.env['account.invoice.refund'].with_context(
                                            active_ids=provider_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': name,
                                            'date': provider_invoice_id.date_invoice,
                                        })
                                        result = refund.invoice_refund()
                                        refund_id = result.get('domain')[1][2]
                                        refund = request.env['account.invoice'].sudo().browse(refund_id)
                                        refund.update({'reference': provider_payment_trans_id, 'request_id': user_request.id})
                                        refund_line = refund.invoice_line_ids[0]
                                        refund_line.update({'price_unit': merchant_cashback_amount, 'request_id': user_request.id})
                                        refund.refresh()
                                        refund.action_invoice_open()
                                        provider_invoice_ids += (tuple(refund.ids),)
                                    user_request.update({'provider_invoice_ids': provider_invoice_ids})
                                    request.env.cr.commit()

                                    # Create Customer Invoices
                                    customer_invoice_ids = ()
                                    # 1- Create Customer Invoice
                                    customer_journal_id = request.env['account.journal'].sudo().search([('type', '=', 'sale'),
                                                                                              ('company_id', '=', request.env.user.company_id.id)], limit=1)
                                    customer_invoice_vals = user_request.with_context(name=provider_payment_trans_id,
                                                                                      journal_id=customer_journal_id.id,
                                                                                      invoice_date=date.today(),
                                                                                      invoice_type='out_invoice',
                                                                                      partner_id=request.env.user.partner_id.id)._prepare_invoice()
                                    customer_invoice_id = request.env['account.invoice'].sudo().create(customer_invoice_vals)
                                    user_request.invoice_line_create(invoice_id=customer_invoice_id.id, name=name,
                                                                        qty=1, price_unit=customer_actual_amount)
                                    customer_invoice_id.action_invoice_open()
                                    customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                    # Auto Reconcile customer invoice with prepaid wallet recharge payments and previous cashback credit note
                                    domain = [('account_id', '=', customer_invoice_id.account_id.id),
                                              ('partner_id', '=',
                                               customer_invoice_id.env['res.partner']._find_accounting_partner(
                                                   customer_invoice_id.partner_id).id),
                                              ('reconciled', '=', False),
                                              '|',
                                              '&', ('amount_residual_currency', '!=', 0.0), ('currency_id', '!=', None),
                                              '&', ('amount_residual_currency', '=', 0.0), '&', ('currency_id', '=', None),
                                              ('amount_residual', '!=', 0.0)]
                                    domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                                    lines = customer_invoice_id.env['account.move.line'].sudo().search(domain)
                                    for line in lines:
                                        # get the outstanding residual value in invoice currency
                                        if line.currency_id and line.currency_id == customer_invoice_id.currency_id:
                                            amount_residual_currency = abs(line.amount_residual_currency)
                                        else:
                                            currency = line.company_id.currency_id
                                            amount_residual_currency = currency._convert(abs(line.amount_residual),
                                                                                         customer_invoice_id.currency_id,
                                                                                         customer_invoice_id.company_id,
                                                                                         line.date or fields.Date.today())
                                        if float_is_zero(amount_residual_currency,
                                                         precision_rounding=customer_invoice_id.currency_id.rounding):
                                            continue

                                        customer_invoice_id.assign_outstanding_credit(line.id)
                                        if customer_invoice_id.state == 'paid':
                                            break
                                    request.env.cr.commit()

                                    # 2- Create Customer Credit Note with commision amount for only mobile users have commission
                                    if request.env.user.commission and customer_cashback_amount > 0:
                                        credit_note = request.env['account.invoice.refund'].with_context(
                                            active_ids=customer_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': provider_payment_trans_id,
                                            'date': customer_invoice_id.date_invoice,
                                        })
                                        result = credit_note.invoice_refund()
                                        credit_note_id = result.get('domain')[1][2]
                                        credit_note = request.env['account.invoice'].sudo().browse(credit_note_id)
                                        credit_note.update({'request_id': user_request.id})
                                        credit_note_line = credit_note.invoice_line_ids[0]
                                        credit_note_line.update({'price_unit': customer_cashback_amount, 'request_id': user_request.id})
                                        credit_note.refresh()
                                        """  Don't validate the customer credit note until the vendor refund reconciliation
                                        After vendor refund reconciliation, validate the customer credit note with
                                        the net amount of vendor refund sent in provider cashback statement then
                                        increase the customer wallet with the same net amount. """
                                        # credit_note.action_invoice_open()
                                        customer_invoice_ids += (tuple(credit_note.ids),)
                                    user_request.update({'customer_invoice_ids': customer_invoice_ids})
                                    request.env.cr.commit()
                                    '''

                                    if provider.provider == "khales":
                                        # Add required parameters for cancel payment scenario
                                        user_request_response.update({'billingAcct': billingAcct, 'billRefNumber': billRefNumber,
                                                                      'billerId': billerId, 'pmtType': pmtType, 'trans_amount': trans_amount,
                                                                      'curCode': curCode, 'pmtMethod': pmtMethod, 'ePayBillRecID': ePayBillRecID,
                                                                      'pmtId': pmtId, 'feesAmt': feesAmt, 'pmtRefInfo': pmtRefInfo})
                                        if payAmts:
                                            user_request_response.update({'payAmts': payAmts})
                                        if feesAmts:
                                            user_request_response.update({'feesAmts': feesAmts})
                                    user_request_response.update({"message": _("Pay Service Bill request was submit successfully with amount %s %s. Your Machine Wallet Balance is %s %s")
                                                                        % (customer_actual_amount,
                                                                           user_request.currency_id.name,
                                                                           request.env.user.partner_id.wallet_balance,
                                                                           user_request.currency_id.name)
                                                             })
                                    return valid_response(user_request_response)
                                except Exception as e:
                                    try:
                                        _logger.error("%s", e)
                                        user_request_update = {'extra_fees_amount': extra_fees_amount,
                                                               'trans_date': date.today(),
                                                               'provider_id': provider.id,
                                                               'provider_response': provider_response_json,"stage_id": 5,
                                                               'description': _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e)}
                                        if mobile_wallet_create:
                                            user_request_update.update({'wallet_transaction_id': mobile_wallet_create.id})
                                        provider_invoice_ids = ()
                                        if provider_invoice_id or refund:
                                            if provider_invoice_id:
                                                provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                            if refund:
                                                provider_invoice_ids += (tuple(refund.ids),)
                                            user_request_update.update({'provider_invoice_ids': provider_invoice_ids})
                                        customer_invoice_ids = ()
                                        if customer_invoice_id or credit_note:
                                            if customer_invoice_id:
                                                customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                            if credit_note:
                                                customer_invoice_ids += (tuple(credit_note.ids),)
                                            user_request_update.update({'customer_invoice_ids': customer_invoice_ids})
                                        user_request.update(user_request_update)
                                        request.env.cr.commit()
                                    except Exception as e1:
                                        _logger.error("%s", e1)
                                        if user_request and not user_request.description:
                                            user_request.update({'description': _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e)})
                                            request.env.cr.commit()

                                    return invalid_response(user_request_response, _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e),
                                                            500)
                            else:
                                error.update({provider.provider + "_response": provider_response or ''})
                        except Exception as e2:
                            _logger.error("%s", e2)
                            if user_request and not user_request.get('description'):
                                user_request.update({'description': _("Error is occur:") + " ==> " + str(e2)})
                                request.env.cr.commit()
                            return invalid_response("Error", _("Error is occur:") + " ==> " + str(e), 500)
                    else:
                        error.update({provider_info.name.name + "_response": _("%s is not a provider for (%s) service") % (
                            provider_info.name.name, service.name)})

                user_request.update({
                    'provider_response': error or _('(%s) service has not any provider.') % (service.name),
                    'stage_id': 5
                })
                request.env.cr.commit()
                return invalid_response("Error", error or _("(%s) service has not any provider.") % (service.name), 400)
            else:
                return valid_response({"message": _("Your request was submit successfully."),
                                       "request_number": user_request.name
                                       })

        @validate_token
        @http.route('/api/cancel_request', type="http", auth="none", methods=["PUT"], csrf=False)
        def cancel_request(self, **request_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Cancel Mobile Request API")
            user_request = False
            request_number = request_data.get('request_number')
            if request_number:
                user_request = request.env['smartpay_operations.request'].sudo().search([('name', '=', request_number)], limit=1)
            else: # elif request_data.get('provider') == 'khales':
                # if not request_data.get('ePayBillRecID'):
                    # return invalid_response("ePayBillRecID_request_number_not_found", _("missing Request Number or ePay Bill Rec ID in request data"), 400)
                user_request = request.env['smartpay_operations.request'].sudo().search([('request_type', '=', 'pay_service_bill'),
                                                                                         ('provider_response', 'like', request_data.get('ePayBillRecID'))],
                                                                                        limit=1)
                # _logger.info("@@@@@@@@@@@@@@@@@@@ " + '"EPayBillRecID": "%s"' % (request_data.get('ePayBillRecID')))
            if user_request:
                request_number = user_request.name
                try:
                    service = user_request.product_id
                    provider = user_request.provider_id

                    service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                        ('product_tmpl_id', '=', service.product_tmpl_id.id),
                        ('name', '=', provider.related_partner.id)
                    ])
                    biller_info_json_dict = json.loads(service_providerinfo.biller_info, strict=False)
                    isAllowCancel = biller_info_json_dict.get('IsAllowCancel', False)

                    if user_request.request_type == 'pay_service_bill' and user_request.stage_id.id == 5 and isAllowCancel:
                        lang = 'ar-eg'
                        partner = user_request.partner_id
                        # trans_date = user_request.trans_date
                        trans_amount = user_request.trans_amount
                        provider_fees_amount = user_request.provider_fees_amount
                        extra_fees_amount = user_request.extra_fees_amount
                        currency = user_request.currency_id

                        provider_pay_response = user_request.provider_response
                        provider_response_json = {}
                        provider_response_json['provider_pay_response'] = provider_pay_response
                        provider_pay_response_json = json.loads(provider_pay_response)
                        billingAcct = request_data.get('billingAcct') or provider_pay_response_json.get('billingAcct')
                        billRefNumber = request_data.get('billRefNumber') or provider_pay_response_json.get('billRefNumber')
                        billerId = request_data.get('billerId') or provider_pay_response_json.get('billerId')
                        pmtType = request_data.get('pmtType') or provider_pay_response_json.get('pmtType')
                        # trans_amount = request_data.get('trans_amount') or provider_pay_response_json.get('trans_amount')
                        curCode = request_data.get('currency_id') or provider_pay_response_json.get('curCode')
                        payAmts = request_data.get('payAmts')
                        if payAmts:
                            payAmts = ast.literal_eval(payAmts)
                        else:
                            payAmts = [{'Sequence': '1', 'AmtDue': trans_amount, 'CurCode': curCode}]
                        pmtMethod = request_data.get('pmtMethod') or provider_pay_response_json.get('pmtMethod')
                        ePayBillRecID = request_data.get('ePayBillRecID') or provider_pay_response_json.get('ePayBillRecID')
                        pmtId = request_data.get('pmtId') or provider_pay_response_json.get('pmtId')
                        feesAmt = request_data.get('feesAmt') or provider_pay_response_json.get('feesAmt')
                        feesAmts = request_data.get('feesAmts')
                        if feesAmts:
                            feesAmts = ast.literal_eval(feesAmts)
                        else:
                            feesAmts = [{'Amt': feesAmt, 'CurCode': curCode}]
                        pmtRefInfo = request_data.get('pmtRefInfo') or provider_pay_response_json.get('pmtRefInfo')
                        cancelReason = request_data.get('cancelReason') or '001'

                        error = {}

                        provider_channel = False
                        machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                  ("type", "in", ("machine", "internet"))], limit=1)
                        if machine_channels:
                            provider_channel = machine_channels[0]
                        if provider.provider == "khales":
                            provider_cancel_response = provider.cancel_khales_payment(lang, billingAcct, billerId, ePayBillRecID,
                                                                                      payAmts, pmtId, pmtType, feesAmts,
                                                                                      billRefNumber, pmtMethod, pmtRefInfo,
                                                                                      cancelReason,provider_channel)
                        if provider_cancel_response.get('Success'):
                            try:
                                provider_cancel_response_json = suds_to_json(provider_cancel_response.get('Success'))
                                provider_response_json['provider_cancel_response'] = provider_cancel_response_json

                                provider_actual_amount = trans_amount + provider_fees_amount
                                customer_actual_amount = provider_actual_amount + extra_fees_amount

                                # Refund Payment Amount to Customer Wallet Balance
                                wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                                label = _('Cancel Service Payment for %s service') % (service.name)
                                partner_id_wallet_balance = partner.wallet_balance
                                customer_wallet_create = wallet_transaction_sudo.create({'wallet_type': 'credit', 'partner_id': partner.id,
                                                                                         'request_id': user_request.id, 'reference': 'request',
                                                                                         'label': label, 'amount': customer_actual_amount,
                                                                                         'currency_id': currency.id,
                                                                                         'wallet_balance_before': partner_id_wallet_balance,
                                                                                         'wallet_balance_after': partner_id_wallet_balance + customer_actual_amount,
                                                                                         'status': 'done'})
                                request.env.cr.commit()

                                partner.update({'wallet_balance': partner.wallet_balance + customer_actual_amount})
                                request.env.cr.commit()

                                # Notify customer
                                irc_param = request.env['ir.config_parameter'].sudo()
                                wallet_canel_service_payment_notify_mode = irc_param.get_param("smartpay_operations.wallet_pay_service_bill_notify_mode")
                                if wallet_canel_service_payment_notify_mode == 'inbox':
                                    request.env['mail.thread'].sudo().message_notify(subject=label,
                                                                                  body=_('<p>%s %s successfully Added to your wallet.</p>') % (
                                                                                      customer_actual_amount, _(currency.name)),
                                                                                  partner_ids=[(4, partner.id)],
                                    )
                                elif wallet_canel_service_payment_notify_mode == 'email':
                                    customer_wallet_create.wallet_transaction_email_send()
                                elif wallet_canel_service_payment_notify_mode == 'sms' and partner.mobile:
                                    customer_wallet_create.sms_send_wallet_transaction(wallet_canel_service_payment_notify_mode, 'wallet_cancel_service_payment',
                                                                                       partner.mobile, partner.name, # request.env.user.name,
                                                                                       label, '%s %s' % (customer_actual_amount, _(currency.name)),
                                                                                       partner.country_id.phone_code or '2')

                                # Refund provider bill for reconciliation purpose
                                # Cancel provider refund (cashback), customer invoice and customer credit note (cashback)
                                refund = False
                                provider_invoice_ids = ()
                                for provider_invoice_id in user_request.provider_invoice_ids:
                                    provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                    # Refund Provider Bill
                                    if provider_invoice_id.type == 'in_invoice' and len(user_request.provider_invoice_ids) == 2:
                                        refund = request.env['account.invoice.refund'].with_context(
                                            active_ids=provider_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': provider_invoice_id.name,
                                            'date': provider_invoice_id.date_invoice,
                                        })
                                        result = refund.invoice_refund()
                                        refund_id = result.get('domain')[1][2]
                                        refund = request.env['account.invoice'].sudo().browse(refund_id)
                                        refund.update({'reference': pmtId, 'request_id': user_request.id})
                                        refund_line = refund.invoice_line_ids[0]
                                        refund_line.update({'request_id': user_request.id})
                                        refund.refresh()
                                        refund.action_invoice_open()
                                        refund.pay_and_reconcile(request.env['account.journal'].sudo().search(
                                            [('type', '=', 'cash'),
                                             ('company_id', '=', request.env.user.company_id.id),
                                             ('provider_id', '=', provider.id)], limit=1),
                                            provider_actual_amount)
                                        provider_invoice_ids += (tuple(refund.ids),)
                                    # Cancel provider refund (cashback)
                                    if provider_invoice_id.type == 'in_refund':
                                        if provider_invoice_id.state in ('in_payment', 'paid'):
                                            provider_invoice_id.action_invoice_re_open()
                                        provider_invoice_id.action_invoice_cancel()

                                user_request.update({'provider_invoice_ids': provider_invoice_ids})
                                request.env.cr.commit()

                                # customer_invoice_ids = ()
                                for customer_invoice_id in user_request.customer_invoice_ids:
                                    # customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                    # Cancel Customer Invoice and Customer Credit Note (cashback)
                                    if len(user_request.customer_invoice_ids) == 2:
                                        if customer_invoice_id.state in ('in_payment', 'paid'):
                                            customer_invoice_id.action_invoice_re_open()
                                        customer_invoice_id.action_invoice_cancel()

                                # user_request.update({'customer_invoice_ids': customer_invoice_ids})
                                # request.env.cr.commit()

                                user_request.update(
                                    {'wallet_transaction_id': customer_wallet_create.id,
                                     'provider_response': provider_response_json , # "stage_id": 4
                                     'description': _('Cancel Service Payment request (%s) was submit successfully @ %s') % (user_request.name, str(date_time.now() + timedelta(hours=2)))
                                     })
                                request.env.cr.commit()

                                return valid_response({"request_number": user_request.name, "provider": provider.provider,
                                                       "provider_response": provider_response_json,
                                                       "message":
                                                           _("Cancel Service Payment request (%s) was submit successfully. Your Machine Wallet Balance is %s %s")
                                                                  % (user_request.name,
                                                                     partner.wallet_balance,
                                                                     currency.name)
                                                       })
                            except Exception as e:
                                try:
                                    _logger.error("%s", e)
                                    user_request_update = {'provider_response': provider_response_json, # "stage_id": 4,
                                                              'description': _(
                                                                  "After the Cancel Service Payment Request submit successfuly with provider, Error is occur:") + " ==> " + str(
                                                                  e)}
                                    if customer_wallet_create:
                                        user_request_update.update({'wallet_transaction_id': customer_wallet_create.id})
                                    provider_invoice_ids = ()
                                    if provider_invoice_id or refund:
                                        if provider_invoice_id:
                                            provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                        if refund:
                                            provider_invoice_ids += (tuple(refund.ids),)
                                        user_request_update.update({'provider_invoice_ids': provider_invoice_ids})
                                    '''
                                    customer_invoice_ids = ()
                                    if customer_invoice_id or credit_note:
                                        if customer_invoice_id:
                                            customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                        if credit_note:
                                            customer_invoice_ids += (tuple(credit_note.ids),)
                                        user_request_update.update({'customer_invoice_ids': customer_invoice_ids})
                                    '''
                                    user_request.update(user_request_update)
                                    request.env.cr.commit()
                                except Exception as e1:
                                    _logger.error("%s", e1)
                                    if user_request and not user_request.description:
                                        user_request.update({'description': _(
                                                                  "After the Cancel Service Payment Request submit successfuly with provider, Error is occur:") + " ==> " + str(
                                                                  e)})
                                        request.env.cr.commit()

                                return invalid_response({"request_number": user_request.name, "provider": provider.provider,
                                                         "provider_response": provider_response_json,
                                                         "message":
                                                           _("Cancel Service Payment request (%s) was submit successfully. Your Machine Wallet Balance is %s %s")
                                                                  % (user_request.name,
                                                                     currency.name,
                                                                     partner.wallet_balance,
                                                                     currency.name)
                                                         }, _(
                                    "After the Cancel Service Payment Request submit successfuly with provider, Error is occur:") + " ==> " + str(e), 500)
                        else:
                            provider_response_json["provider_cancel_response"] = provider_cancel_response
                            error.update({provider.provider + "_response": provider_response_json or ''})

                        user_request.update({
                            'provider_response': error,
                            # 'stage_id': 5
                        })
                        request.env.cr.commit()
                        return invalid_response("Error", error, 400)

                    elif user_request.sudo().write({'stage_id': 4}):
                        return valid_response(_("Cancel REQ Number (%s) successfully!") % (request_number))
                except Exception as ex:
                    _logger.error("%s", ex)
            else:
                return invalid_response("request_not_found", _("Request does not exist!"), 400)

            return invalid_response("request_not_canceled", _("Could not cancel REQ Number (%s)") % (request_number), 400)

        @validate_token
        @http.route('/api/get_request', type="http", auth="none", methods=["POST"], csrf=False)
        def get_request(self, **payload):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Get Requests API")
            domain = payload.get("domain")
            if not domain or "name" not in domain:
                return invalid_response("request_number_missing", _("REQ Number is missing. Please Send REQ Number"), 400)
            return restful_main().get('smartpay_operations.request', None, **payload)

        @validate_token
        @http.route('/api/get_requests', type="http", auth="none", methods=["POST"], csrf=False)
        def get_requests(self, **payload):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Get Requests API")
            domain = []
            if payload.get("domain", None):
                domain = ast.literal_eval(payload.get("domain"))
            domain += [("partner_id.id", "=", request.env.user.partner_id.id)]
            if not any(item[0] == 'create_date' for item in domain):
                create_date = (datetime.date.today()+datetime.timedelta(days=-30)).strftime('%Y-%m-%d')
                domain += [("create_date", ">=", create_date)]
            payload.update({
                'domain': str(domain)
            })
            return restful_main().get('smartpay_operations.request', None, **payload)

        @validate_token
        @http.route('/api/get_service_fees', type="http", auth="none", methods=["POST"], csrf=False)
        def get_service_fees(self, **request_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Get Service Fees API")

            if not request_data.get('product_id'):
                return invalid_response("service_not_found", _("missing service in request data"), 400)
            else:
                service = request.env["product.product"].sudo().search(
                    [("id", "=", request_data.get('product_id')), ("type", "=", "service")],
                    order="id DESC", limit=1)
                if not service:
                    return invalid_response("service", _("service invalid"), 400)

            # Provider is mandatory because the service fee is different per provider.
            # So the user must send provider that own the bill inquiry request for prevent pay bill
            # with total amount different of total amount in bill inquiry
            provider_provider = request_data.get('provider')
            if provider_provider:
                provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                if provider:
                    service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                        ('product_tmpl_id', '=', service.product_tmpl_id.id),
                        ('name', '=', provider.related_partner.id)
                    ])
                    if not service_providerinfo:
                        return invalid_response(
                            "Incompatible_provider_service", _("%s is not a provider for (%s) service") % (
                                provider_provider, service.name), 400)
            else:
                return invalid_response("provider_not_found",
                                        _("missing provider in request data"), 400)

            trans_amount = float(request_data.get('trans_amount'))
            if not trans_amount:
                return invalid_response("amount_not_found",
                                        _("missing bill amount in request data"), 400)
            else:
                # Calculate Fees
                provider_fees_calculated_amount = 0.0
                extra_fees_amount = 0.0
                if provider_provider != 'khales':
                    commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                        domain=[('vendor', '=', service_providerinfo.name.id),
                                ('vendor_product_code', '=', service_providerinfo.product_code)],
                        fields=['Amount_Range_From', 'Amount_Range_To',
                                'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt']
                    )
                    for commission in commissions:
                        if commission['Amount_Range_From'] <= trans_amount \
                                and commission['Amount_Range_To'] >= trans_amount:
                            if commission['Extra_Fee_Amt'] > 0:
                                extra_fees_amount = commission['Extra_Fee_Amt']
                            elif commission['Extra_Fee_Prc'] > 0:
                                extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                            if commission['Mer_Fee_Amt'] > 0:
                                provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                            elif commission['Mer_Fee_Prc'] > 0:
                                # Fees amount = FA + [Percentage * Payment Amount]
                                # Fees amount ====================> provider_fees_calculated_amount
                                # FA =============================> provider_fees_calculated_amount
                                # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                provider_fees_prc_calculated_amount = trans_amount * commission[
                                    'Mer_Fee_Prc'] / 100
                                if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                        and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                            break
                # if provider_fees_calculated_amount == 0 and provider_provider == 'khales':
                else:
                    if not request_data.get('ePayBillRecID'):
                        return invalid_response("ePayBillRecID_not_found",
                                                _("missing ePayBillRecID in request data"), 400)
                    if not request_data.get('currency_id'):
                        return invalid_response("currency_not_found", _("missing currency in request data"), 400)

                    provider_channel = False
                    provider_channels = request.env['payment.acquirer.channel'].sudo().search(
                        [("acquirer_id", "=", provider.id)], limit=1)
                    if provider_channels:
                        provider_channel = provider_channels[0]

                    curCode = request_data.get('currency_id')
                    payAmts = request_data.get('payAmts')
                    if payAmts:
                        payAmts = ast.literal_eval(payAmts)
                        payAmtTemp = trans_amount
                        for payAmt in payAmts:
                            payAmtTemp -= float(payAmt.get('AmtDue'))
                        if payAmtTemp != 0:
                            return invalid_response("payAmts_not_match",
                                                    _("The sum of payAmts must be equals trans_amount"), 400)
                    else:
                        payAmts = [{'Sequence': '1', 'AmtDue': trans_amount, 'CurCode': curCode}]

                    fees_response = provider.get_khales_fees('', request_data.get('ePayBillRecID'), payAmts,
                                                             provider_channel)
                    if fees_response.get('Success'):
                        feeInqRsType = fees_response.get('Success')
                        provider_fees_calculated_amount = float(feeInqRsType['FeesAmt']['Amt'])

                calculated_payment_amount = trans_amount + provider_fees_calculated_amount + extra_fees_amount
                return valid_response(
                    {"message": _("Get Service Fees request was submit successfully."),
                     "provider": provider.provider,
                     "provider_service_code": service_providerinfo.product_code,
                     "provider_service_name": service_providerinfo.product_name,
                     "trans_amount": trans_amount,
                     "provider_fees_amount": provider_fees_calculated_amount,
                     "extra_fees_amount": extra_fees_amount
                     })

        @validate_token
        @http.route('/api/get_wallet_balance', type="http", auth="none", methods=["POST"], csrf=False)
        def get_wallet_balance(self, **payload):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Get Wallet Balance API")
            return restful_main().get('res.partner', request.env.user.partner_id.id, **payload)

        @validate_token
        @http.route('/api/get_wallet_trans', type="http", auth="none", methods=["POST"], csrf=False)
        def get_wallet_trans(self, **payload):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Get Wallet Transactions API")
            domain = []
            if payload.get("domain", None):
                domain = ast.literal_eval(payload.get("domain"))
            domain += [("partner_id.id", "=", request.env.user.partner_id.id)]
            if not any(item[0] == 'create_date' for item in domain):
                create_date = (datetime.date.today()+datetime.timedelta(days=-30)).strftime('%Y-%m-%d')
                domain += [("create_date", ">=", create_date)]

            payload.update({
                'domain': str(domain)
            })
            return restful_main().get('website.wallet.transaction', None, **payload)

        @validate_token
        @validate_machine
        @http.route('/api/recharge_mobile_wallet', type="http", auth="none", methods=["POST"], csrf=False)
        def recharge_mobile_wallet(self, **request_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Recharge Mobile Wallet Request API")
            if not request_data.get('request_number'):
                if request_data.get('transfer_to') and request_data.get('trans_amount'):
                    # current_user = request.env.user
                    # current_user_access_token = request.httprequest.headers.get("access_token")
                    # current_user_machine_serial = request.httprequest.headers.get("machine_serial")
                    # Create Recharge Mobile Wallet Request
                    transfer_to_user = request.env['res.users'].sudo().search(['|',
                                                                               ('login', '=', request_data.get('transfer_to')),
                                                                               ('ref', '=', request_data.get('transfer_to'))], limit=1)[0]
                    if not transfer_to_user:
                        return invalid_response("request_code_invalid", _("invalid transfer user in request data"), 400)
                    access_token = (
                        request.env["api.access_token"]
                            .sudo()
                            .search([("user_id", "=", transfer_to_user.id)], order="id DESC", limit=1)
                    )
                    if access_token:
                        access_token = access_token[0]
                        if access_token.has_expired():
                            return invalid_response("token_expired", _("transfer to user token expired"), 400)
                    else:
                        return invalid_response("account_deactivate", _("transfer to user account is deactivated"), 400)

                    base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    headers = {
                        'content-type': 'application/x-www-form-urlencoded',
                        'charset': 'utf-8',
                        'access_token': access_token.token
                    }
                    data = {
                        'request_type': 'recharge_wallet',
                        'trans_amount': request_data.get('trans_amount')
                    }

                    res = requests.post('{}/api/create_mobile_request'.format(base_url), headers=headers, data=data)
                    content = json.loads(res.content.decode('utf-8'))
                    # res = self.create_mobile_request(**data)
                    _logger.info("@@@@@@@@@@@@@@@@@@@ Recharge Mobile Wallet Response: " + str(content))
                    if content.get('data'):
                        request_number = content.get('data').get('request_number') #json.loads(res.response[0].decode('utf-8')).get('request_number')
                        if not request_number:
                            return res
                        request_data.update({'request_number': request_number})
                        request.env.cr.commit()
                    else:
                        return res
                    '''
                    request.httprequest.headers = {
                        'content-type': 'application/x-www-form-urlencoded',
                        'charset': 'utf-8',
                        'access_token': current_user_access_token,
                        'access_token': current_user_machine_serial
                    }
                    request.session.uid = current_user.id
                    request.uid = current_user.id
                    '''
                else:
                    return invalid_response("request_code_missing", _("missing request number in request data"), 400)
            user_request = request.env['smartpay_operations.request'].sudo().search(
                [('name', '=', request_data.get('request_number')), ('request_type', '=', "recharge_wallet")], limit=1)
            if user_request:
                if user_request.stage_id.id != 1:
                    return invalid_response("request_not_found",
                                            _("REQ Number (%s) invalid!") % (request_data.get('request_number')), 400)
                if request.env.user.partner_id.wallet_balance < user_request.trans_amount:
                    return invalid_response("machine_balance_not_enough",
                                            _("Machine Wallet Balance less than the request amount"), 400)

                # Transfer Balance from Machine Wallet to Mobile Wallet
                wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                label = _('Transfer wallet balance from %s') % (request.env.user.partner_id.name)
                partner_id_wallet_balance = user_request.partner_id.wallet_balance
                mobile_wallet_create = wallet_transaction_sudo.create(
                    {'wallet_type': 'credit', 'partner_id': user_request.partner_id.id, 'request_id': user_request.id,
                     'reference': 'request', 'label': label,
                     'amount': user_request.trans_amount, 'currency_id': user_request.currency_id.id,
                     'wallet_balance_before': partner_id_wallet_balance,
                     'wallet_balance_after': partner_id_wallet_balance + user_request.trans_amount,
                     'status': 'done'})
                request.env.cr.commit()

                user_request.partner_id.update(
                    {'wallet_balance': user_request.partner_id.wallet_balance + user_request.trans_amount})
                request.env.cr.commit()

                # Notify Mobile User
                irc_param = request.env['ir.config_parameter'].sudo()
                wallet_transfer_balance_notify_mode = irc_param.get_param("smartpay_operations.wallet_transfer_balance_notify_mode")
                if wallet_transfer_balance_notify_mode == 'inbox':
                    request.env['mail.thread'].sudo().message_notify(
                        subject=label,
                        body=_('<p>%s %s successfully added to your wallet.</p>') % (
                            user_request.trans_amount, _(user_request.currency_id.name)),
                        partner_ids=[(4, user_request.partner_id.id)],
                    )
                elif wallet_transfer_balance_notify_mode == 'email':
                    mobile_wallet_create.wallet_transaction_email_send()
                elif wallet_transfer_balance_notify_mode == 'sms' and user_request.partner_id.mobile:
                    mobile_wallet_create.sms_send_wallet_transaction(wallet_transfer_balance_notify_mode,
                                                                     'wallet_transfer_balance',
                                                                     user_request.partner_id.mobile,
                                                                     user_request.partner_id.name, label,
                                                                     '%s %s' % (user_request.trans_amount,
                                                                                _(user_request.currency_id.name)),
                                                                     user_request.partner_id.country_id.phone_code or '2')

                label = _('Transfer wallet balance to %s') % (user_request.partner_id.name)
                partner_id_wallet_balance = request.env.user.partner_id.wallet_balance
                machine_wallet_create = wallet_transaction_sudo.create(
                    {'wallet_type': 'debit', 'partner_id': request.env.user.partner_id.id, 'request_id': user_request.id,
                     'reference': 'request', 'label': label,
                     'amount': user_request.trans_amount, 'currency_id': user_request.currency_id.id,
                     'wallet_balance_before': partner_id_wallet_balance,
                     'wallet_balance_after': partner_id_wallet_balance - user_request.trans_amount,
                     'status': 'done'})
                request.env.cr.commit()

                request.env.user.partner_id.update(
                    {'wallet_balance': request.env.user.partner_id.wallet_balance - user_request.trans_amount})
                request.env.cr.commit()
                user_request.sudo().write({'wallet_transaction_id': machine_wallet_create.id, 'stage_id': 5})
                request.env.cr.commit()

                # Notify customer
                if wallet_transfer_balance_notify_mode == 'inbox':
                    request.env['mail.thread'].sudo().message_notify(
                        subject=label,
                        body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                            user_request.trans_amount, _(user_request.currency_id.name)),
                        partner_ids=[(4, request.env.user.partner_id.id)],
                    )
                elif wallet_transfer_balance_notify_mode == 'email':
                    machine_wallet_create.wallet_transaction_email_send()
                elif wallet_transfer_balance_notify_mode == 'sms' and request.env.user.partner_id.mobile:
                    machine_wallet_create.sms_send_wallet_transaction(wallet_transfer_balance_notify_mode,
                                                                      'wallet_transfer_balance',
                                                                      request.env.user.partner_id.mobile,
                                                                      request.env.user.name, label,
                                                                      '%s %s' % (user_request.trans_amount,
                                                                                 _(user_request.currency_id.name)),
                                                                      request.env.user.partner_id.country_id.phone_code or '2')

                # Create journal entry for transfer AR balance from machine customer to mobile user.
                machine_customer_receivable_account = request.env.user.partner_id.property_account_receivable_id
                mobile_user_receivable_account = user_request.partner_id.property_account_receivable_id
                account_move = request.env['account.move'].sudo().create({
                    'journal_id': request.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
                })
                request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                    'name': user_request.name + ': Transfer Wallet Balance',
                    'move_id': account_move.id,
                    'account_id': machine_customer_receivable_account.id,
                    'partner_id': request.env.user.partner_id.id,
                    'debit': user_request.trans_amount,
                })
                request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                    'name': user_request.name + ': Transfer Wallet Balance',
                    'move_id': account_move.id,
                    'account_id': mobile_user_receivable_account.id,
                    'partner_id': user_request.partner_id.id,
                    'credit': user_request.trans_amount,
                })
                account_move.post()

                return valid_response(_(
                    "Wallet for User (%s) recharged successfully with amount %s %s. Your Machine Wallet Balance is %s %s") %
                                      (user_request.partner_id.name, user_request.trans_amount,
                                       user_request.currency_id.name,
                                       request.env.user.partner_id.wallet_balance, user_request.currency_id.name))
            else:
                return invalid_response("request_not_found", _("REQ Number (%s) does not exist!") % (
                request_data.get('request_number')), 400)

        @validate_token
        @http.route('/api/pay_invoice', type="http", auth="none", methods=["POST"], csrf=False)
        def pay_invoice(self, **request_data):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Pay Invoice Request API")
            if not request_data.get('request_number'):
                return invalid_response("request_code_missing", _("missing request number in request data"), 400)
            customer_request = request.env['smartpay_operations.request'].sudo().search(
                [('name', '=', request_data.get('request_number')), ('request_type', '=', "pay_invoice")], limit=1)
            if customer_request:
                if customer_request.stage_id.id != 1:
                    return invalid_response("request_not_found",
                                            _("REQ Number (%s) invalid!") % (request_data.get('request_number')), 400)
                if request.env.user.partner_id.wallet_balance < customer_request.trans_amount:
                    return invalid_response("mobile_balance_not_enough",
                                            _("Mobile Wallet Balance less than the request amount"), 400)

                # Transfer Balance from Mobile Wallet to Machine Wallet
                wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                label = _('Collect invoice payment from %s') % (request.env.user.partner_id.name)
                partner_id_wallet_balance = customer_request.partner_id.wallet_balance
                machine_wallet_create = wallet_transaction_sudo.create(
                    {'wallet_type': 'credit', 'partner_id': customer_request.partner_id.id, 'request_id': customer_request.id,
                     'reference': 'request', 'label': label,
                     'amount': customer_request.trans_amount, 'currency_id': customer_request.currency_id.id,
                     'wallet_balance_before': partner_id_wallet_balance,
                     'wallet_balance_after': partner_id_wallet_balance + customer_request.trans_amount,
                     'status': 'done'})
                request.env.cr.commit()

                customer_request.partner_id.update(
                    {'wallet_balance': customer_request.partner_id.wallet_balance + customer_request.trans_amount})
                request.env.cr.commit()

                # Notify Customer
                irc_param = request.env['ir.config_parameter'].sudo()
                wallet_pay_invoice_notify_mode = irc_param.get_param("smartpay_operations.wallet_pay_invoice_notify_mode")
                if wallet_pay_invoice_notify_mode == 'inbox':
                    request.env['mail.thread'].sudo().message_notify(
                        subject=label,
                        body=_('<p>%s %s successfully added to your wallet.</p>') % (
                            customer_request.trans_amount, _(customer_request.currency_id.name)),
                        partner_ids=[(4, customer_request.partner_id.id)],
                    )
                elif wallet_pay_invoice_notify_mode == 'email':
                    machine_wallet_create.wallet_transaction_email_send()
                elif wallet_pay_invoice_notify_mode == 'sms' and customer_request.partner_id.mobile:
                    machine_wallet_create.sms_send_wallet_transaction(wallet_pay_invoice_notify_mode,
                                                                      'wallet_pay_invoice',
                                                                      customer_request.partner_id.mobile,
                                                                      customer_request.partner_id.name, label,
                                                                      '%s %s' % (customer_request.trans_amount,
                                                                                 _(customer_request.currency_id.name)),
                                                                      customer_request.partner_id.country_id.phone_code or '2')

                label = _('Pay invoice to %s') % (customer_request.partner_id.name)
                partner_id_wallet_balance = request.env.user.partner_id.wallet_balance
                mobile_wallet_create = wallet_transaction_sudo.create(
                    {'wallet_type': 'debit', 'partner_id': request.env.user.partner_id.id, 'request_id': customer_request.id,
                     'reference': 'request', 'label': label,
                     'amount': customer_request.trans_amount, 'currency_id': customer_request.currency_id.id,
                     'wallet_balance_before': partner_id_wallet_balance,
                     'wallet_balance_after': partner_id_wallet_balance - customer_request.trans_amount,
                     'status': 'done'})
                request.env.cr.commit()

                request.env.user.partner_id.update(
                    {'wallet_balance': request.env.user.partner_id.wallet_balance - customer_request.trans_amount})
                request.env.cr.commit()
                customer_request.sudo().write({'wallet_transaction_id': mobile_wallet_create.id, 'stage_id': 5})
                request.env.cr.commit()

                # Notify User
                if wallet_pay_invoice_notify_mode == 'inbox':
                    request.env['mail.thread'].sudo().message_notify(
                        subject=label,
                        body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                            customer_request.trans_amount, _(customer_request.currency_id.name)),
                        partner_ids=[(4, request.env.user.partner_id.id)],
                    )
                elif wallet_pay_invoice_notify_mode == 'email':
                    mobile_wallet_create.wallet_transaction_email_send()
                elif wallet_pay_invoice_notify_mode == 'sms' and request.env.user.partner_id.mobile:
                    mobile_wallet_create.sms_send_wallet_transaction(wallet_pay_invoice_notify_mode,
                                                                      'wallet_pay_invoice',
                                                                      request.env.user.partner_id.mobile,
                                                                      request.env.user.name, label,
                                                                      '%s %s' % (customer_request.trans_amount,
                                                                                 _(customer_request.currency_id.name)),
                                                                      request.env.user.partner_id.country_id.phone_code or '2')

                # Create journal entry for transfer AR balance from mobile user to machine customer.
                mobile_user_receivable_account = request.env.user.partner_id.property_account_receivable_id
                machine_customer_receivable_account = customer_request.partner_id.property_account_receivable_id
                account_move = request.env['account.move'].sudo().create({
                    'journal_id': request.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
                })
                request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                    'name': customer_request.name + ': Pay Invoice',
                    'move_id': account_move.id,
                    'account_id': mobile_user_receivable_account.id,
                    'partner_id': request.env.user.partner_id.id,
                    'debit': customer_request.trans_amount,
                })
                request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                    'name': customer_request.name + ': Pay Invoice',
                    'move_id': account_move.id,
                    'account_id': machine_customer_receivable_account.id,
                    'partner_id': customer_request.partner_id.id,
                    'credit': customer_request.trans_amount,
                })
                account_move.post()

                return valid_response(_(
                    "Invoice request (%s) paid successfully with amount %s %s. Your Mobile Wallet Balance is %s %s") %
                                      (customer_request.name, customer_request.trans_amount,
                                       customer_request.currency_id.name,
                                       request.env.user.partner_id.wallet_balance, customer_request.currency_id.name))
            else:
                return invalid_response("request_not_found", _("REQ Number (%s) does not exist!") % (
                    request_data.get('request_number')), 400)

        ###############################################
        ######### Fawry Integration Requests ##########
        ###############################################
        @validate_token
        @http.route('/api/get_sevice_categories', type="http", auth="none", methods=["POST"], csrf=False)
        def get_sevice_categories(self, **payload):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Get Sevice Category API")
            domain, fields, offset, limit, order = extract_arguments(payload)
            domain += [("parent_id", "=", request.env.ref("tm_base_gateway.product_category_services").id), ("product_count", "!=", 0)]

            lang = payload.get("lang", "en_US")
            ir_translation_sudo = request.env['ir.translation'].sudo()
            product_category_sudo = request.env['product.category'].sudo()
            '''
            service_categories = product_category_sudo.search_read(domain=domain,
                                                                     fields=fields,
                                                                     offset=offset,
                                                                     limit=limit,
                                                                     order=order,
                                                                     )
            '''
            service_categories = product_category_sudo.search(domain, offset=offset, limit=limit, order=order)
            categories = []
            if service_categories:
                for service_category in service_categories:
                    category = {
                        "id": service_category.id,
                        # "image": service_category.image_medium and service_category.image_medium.decode('ascii') or False,
                        # "name": service_category.name
                    }

                    if service_category.image_medium:
                        category.update({"image": "/web/image?model=%s&field=image_medium&id=%s" % ("product.category", service_category.id)})

                    '''
                    ir_translation_ids = ir_translation_sudo.search_read(
                        domain=[("name", "=", "product.category,name"), ("res_id", "=", service_category.id)],
                        fields=["lang", "source", "value"], order="res_id")
                    if ir_translation_ids:
                        category_trans = []
                        for ir_translation in ir_translation_ids:
                            category_trans.append({
                                "lang": ir_translation["lang"],
                                "name": ir_translation["value"]
                            })
                        category.update({"name_translate": category_trans})
                    '''

                    if lang == "en_US":
                        category.update({"name": service_category.name})
                    else:
                        ir_translation_id = ir_translation_sudo.search(
                            [("name", "=", "product.category,name"), ("res_id", "=", service_category.id), ("lang", "=", lang)],
                            limit=1)
                        if ir_translation_id:
                            category.update({"name": ir_translation_id.value})

                    categories.append(category)

            return valid_response(categories)
            # return invalid_response("service_categories_not_found",  _("Could not get Service Categories"), 400)

        @validate_token
        @http.route('/api/get_sevice_billers', type="http", auth="none", methods=["POST"], csrf=False)
        def get_sevice_billers(self, **payload):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Get Sevice Biller API")
            domain, fields, offset, limit, order = extract_arguments(payload)
            domain += [("product_count", "!=", 0)]

            lang = payload.get("lang", "en_US")
            ir_translation_sudo = request.env['ir.translation'].sudo()
            product_category_sudo = request.env['product.category'].sudo()
            '''
            service_billers = product_category_sudo.search_read(domain=domain,
                                                                     fields=fields,
                                                                     offset=offset,
                                                                     limit=limit,
                                                                     order=order,
                                                                     )
            '''
            service_billers = product_category_sudo.search(domain, offset=offset, limit=limit, order=order)
            billers = []
            if service_billers:
                for service_biller in service_billers:
                    biller = {
                        "id": service_biller.id,
                        "categ_id": service_biller.parent_id.id,
                        "categ_name": service_biller.parent_id.name,
                        # "image": service_biller.image_medium and service_biller.image_medium.decode('ascii') or False,
                        # "name": service_biller.name
                    }

                    if service_biller.image_medium:
                        biller.update({"image": "/web/image?model=%s&field=image_medium&id=%s" % ("product.category", service_biller.id)})

                    '''
                    ir_translation_ids = ir_translation_sudo.search_read(
                        domain=[("name", "=", "product.category,name"), ("res_id", "=", service_biller.id)],
                        fields=["lang", "source", "value"], order="res_id")
                    if ir_translation_ids:
                        biller_trans = []
                        for ir_translation in ir_translation_ids:
                            biller_trans.append({
                                "lang": ir_translation["lang"],
                                "name": ir_translation["value"]
                            })
                        biller.update({"name_translate": biller_trans})
                    '''

                    if lang == "en_US":
                        biller.update({"name": service_biller.name})
                    else:
                        ir_translation_id = ir_translation_sudo.search(
                            [("name", "=", "product.category,name"), ("res_id", "=", service_biller.id), ("lang", "=", lang)],
                            limit=1)
                        if ir_translation_id:
                            biller.update({"name": ir_translation_id.value})

                    billers.append(biller)

            return valid_response(billers)
            # return invalid_response("service_billers_not_found", _("Could not get Service Billers"), 400)

        @validate_token
        @http.route('/api/get_sevices', type="http", auth="none", methods=["POST"], csrf=False)
        def get_sevices(self, **payload):
            _logger.info("@@@@@@@@@@@@@@@@@@@ Calling Get Sevices API")
            domain, fields, offset, limit, order = extract_arguments(payload)

            lang = payload.get("lang", "en_US")
            biller_info_sudo = request.env['product.supplierinfo'].sudo()
            ir_translation_sudo = request.env['ir.translation'].sudo()
            product_template_sudo = request.env['product.template'].sudo()
            '''
            service_ids = product_template_sudo.search_read(domain=domain,
                                                                     fields=fields,
                                                                     offset=offset,
                                                                     limit=limit,
                                                                     order=order,
                                                                     )
            '''
            service_ids = product_template_sudo.search(domain, offset=offset, limit=limit, order=order)
            services = []
            if service_ids:
                for service_id in service_ids:
                    service = {
                        "id": service_id.product_variant_id.id,
                        "categ_id": service_id.categ_id.id,
                        "categ_name": service_id.categ_id.name,
                        # "image": service_id.image_medium and service_id.image_medium.decode('ascii') or False,
                        # "name": service_id.name
                    }

                    if service_id.image_medium:
                        service.update({"image": "/web/image?model=%s&field=image_medium&id=%s" % ("product.template", service_id.id)})

                    '''
                    ir_translation_ids = ir_translation_sudo.search_read(
                        domain=[("name", "=", "product.template,name"), ("res_id", "=", service_id.id)],
                        fields=["lang", "source", "value"], order="res_id")
                    if ir_translation_ids:
                        service_trans = []
                        for ir_translation in ir_translation_ids:
                            service_trans.append({
                                "lang": ir_translation["lang"],
                                "name": ir_translation["value"]
                            })
                        service.update({"name_translate": service_trans})
                    '''

                    biller_info_id = biller_info_sudo.search(
                        [("product_tmpl_id.type", "=", "service"),
                                ("product_tmpl_id.id", "=", service_id.id)],
                        limit=1)

                    if lang == "en_US":
                        service.update({"name": service_id.name})

                        if biller_info_id:
                            service.update({"biller_info": biller_info_id.biller_info})
                    else:
                        ir_translation_id = ir_translation_sudo.search(
                            [("name", "=", "product.template,name"), ("res_id", "=", service_id.id),
                                    ("lang", "=", lang)],
                            limit=1)
                        if ir_translation_id:
                            service.update({"name": ir_translation_id.value})

                        ir_translation_id = ir_translation_sudo.search(
                            [("name", "=", "product.supplierinfo,biller_info"), ("res_id", "=", biller_info_id.id),
                                    ("lang", "=", lang)],
                            limit=1)
                        if ir_translation_id:
                            service.update({"biller_info": ir_translation_id.value})

                    services.append(service)

            return valid_response(services)
            # return invalid_response("services_not_found", _("Could not get Services"), 400)

    class RequestApi(http.Controller):

        @validate_token
        @validate_machine
        @http.route('/api/createMachineRequest', type="http", auth="none", methods=["POST"], csrf=False)
        def createMachineRequest(self, **request_data):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Machine Request API")

            if not request_data.get('request_type') or request_data.get('request_type') not in _REQUEST_TYPES_IDS:
                return invalid_response("request_type", _("request type invalid"), 400)

            if request_data.get('request_type') == 'recharge_wallet':
                if not request_data.get('trans_number'):
                    return invalid_response("receipt_number_not_found", _("missing deposit receipt number in request data"), 400)
                if not request_data.get('trans_date'):
                    return invalid_response("date_not_found", _("missing deposit date in request data"), 400)
                if not request_data.get('trans_amount'):
                    return invalid_response("amount_not_found", _("missing deposit amount in request data"), 400)
                if not any(hasattr(field_value, 'filename') for field_name, field_value in request_data.items()):
                    return invalid_response("receipt_not_found", _("missing deposit receipt attachment in request data"), 400)

                open_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'recharge_wallet'), ("partner_id", "=", request.env.user.partner_id.id),
                     ("stage_id", "=", 1)], order="id DESC", limit=1)
                if open_request:
                    return invalid_response("request_already_exist",
                                            _("You have a wallet recharge request in progress with REQ Number (%s)") % (
                                                open_request.name), 400)

                request_data['product_id'] = request.env["product.product"].sudo().search([('name', '=', 'Wallet Recharge')]).id

            if not request_data.get('product_id') and (
                    request_data.get('request_type') in ('recharge_wallet', 'service_bill_inquiry') or
                    (request_data.get('request_type') == 'pay_service_bill' and not request_data.get('inquiry_request_number'))
            ):
                return invalid_response("service_not_found", _("missing service in request data"), 400)
            elif request_data.get('request_type') in ('recharge_wallet', 'service_bill_inquiry', 'pay_service_bill'):
                product_id = request_data.get('product_id')
                inquiry_request_number = request_data.get('inquiry_request_number')
                if not product_id and inquiry_request_number:
                    inquiry_request = request.env["smartpay_operations.request"].sudo().search(
                        [('name', '=', inquiry_request_number)], limit=1)
                    if inquiry_request:
                        product_id = inquiry_request.product_id.id
                    else:
                        return invalid_response("inquiry_request_not_found", _("Inquiry Request does not exist!"), 400)
                service = request.env["product.product"].sudo().search([("id", "=", product_id), ("type", "=", "service")],
                                                                       order="id DESC", limit=1)
                if not service:
                    return invalid_response("service", _("service invalid"), 400)

            if request_data.get('request_type') == 'wallet_invitation':
                if not request_data.get('mobile_number'):
                    return invalid_response("mobile_number_not_found", _("missing mobile number for invited user in request data"), 400)

                open_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'wallet_invitation'), ('mobile_number', '=', request_data.get('mobile_number')),
                     ('partner_id', '=', request.env.user.partner_id.id), ("stage_id", "=", 1)], order="id DESC", limit=1)
                if open_request:
                    return invalid_response("request_already_exist",
                                            _("You have a wallet invitation request in progress for mobile number (%s) with REQ Number (%s)") % (
                                                request_data.get('mobile_number'), open_request.name), 400)

                done_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'wallet_invitation'),
                     ('mobile_number', '=', request_data.get('mobile_number')), ("stage_id", "=", 5)],
                    order="id DESC", limit=1)
                if done_request:
                    return invalid_response("request_already_exist",
                                            _("The mobile number (%s) already has a wallet") % (
                                                request_data.get('mobile_number')), 400)

            if request_data.get('request_type') == 'pay_invoice':
                if not request_data.get('trans_amount'):
                    return invalid_response("amount_not_found", _("missing invoice amount in request data"), 400)

            if request_data.get('request_type') == 'service_bill_inquiry':
                if not request_data.get('billingAcct'):
                    return invalid_response("billingAcct_not_found", _("missing billing account in request data"), 400)
                # TODO: extraBillingAcctKeys required with condition
                # if not request_data.get('extraBillingAcctKeys'):
                    # return invalid_response("extraBillingAcctKeys_not_found", _("missing extra billing account keys in request data"), 400)

            if request_data.get('request_type') == 'pay_service_bill':
                # Common: provider billRefNumber trans_amount pmtType currency_id pmtMethod
                # Fawry: extraBillingAcctKeys notifyMobile
                # Khales: ePayBillRecID '''payAmts''' feesAmt pmtRefInfo
                if inquiry_request_number:
                    billingAcct = inquiry_request.billing_acct
                    ePayBillRecID = inquiry_request.e_pay_bill_rec_id
                    trans_amount = inquiry_request.trans_amount
                else:
                    lang = request_data.get('lang')
                    billingAcct = request_data.get('billingAcct') #

                    extraBillingAcctKeys = request_data.get('extraBillingAcctKeys')
                    if extraBillingAcctKeys:
                        extraBillingAcctKeys = ast.literal_eval(extraBillingAcctKeys)

                    notifyMobile = request_data.get('notifyMobile')
                    billRefNumber = request_data.get('billRefNumber')
                    billerId = request_data.get('billerId')
                    pmtType = request_data.get('pmtType')

                    trans_amount = request_data.get('trans_amount') #
                    curCode = request_data.get('currency_id')
                    payAmts = request_data.get('payAmts')
                    if payAmts:
                        payAmts = ast.literal_eval(payAmts)
                    else:
                        payAmts = [{'Sequence': '1', 'AmtDue': trans_amount, 'CurCode': curCode}]
                    pmtMethod = request_data.get('pmtMethod')

                    ePayBillRecID = request_data.get('ePayBillRecID') #
                    pmtId = request_data.get('pmtId')
                    feesAmt = request_data.get('feesAmt') or 0.00
                    feesAmts = request_data.get('feesAmts')
                    if feesAmts:
                        feesAmts = ast.literal_eval(feesAmts)
                    else:
                        feesAmts = [{'Amt': feesAmt, 'CurCode': curCode}]
                    pmtRefInfo = request_data.get('pmtRefInfo')

                if not billingAcct:
                    return invalid_response("billingAcct_not_found", _("missing billing account in request data"), 400)

                provider_provider = request_data.get('provider')
                if provider_provider == 'khales':
                    '''
                    if not request_data.get('billerId'):
                        return invalid_response("billerId_not_found", _("missing biller id in request data"), 400)
                    '''
                    if not ePayBillRecID:
                        return invalid_response("ePayBillRecID_not_found", _("missing ePay Bill Rec ID in request data"), 400)
                    # if not request_data.get('pmtId'):
                        # return invalid_response("pmtId_not_found", _("missing payment id in request data"), 400)
                    if not request_data.get('feesAmt'):
                        return invalid_response("feesAmt_not_found", _("missing fees amount in request data"), 400)
                    # if not request_data.get('pmtRefInfo'):
                        # return invalid_response("pmtRefInfo_not_found", _("missing payment Ref Info in request data"), 400)
                    payAmtTemp = float(request_data.get('trans_amount'))
                    payAmts = request_data.get('payAmts')
                    if payAmts:
                        payAmts = ast.literal_eval(payAmts)
                        for payAmt in payAmts:
                            payAmtTemp -= float(payAmt.get('AmtDue'))
                        if payAmtTemp != 0:
                            return invalid_response("payAmts_not_match",
                                                    _("The sum of payAmts must be equals trans_amount"), 400)
                    feesAmtTemp = request_data.get('feesAmt') or 0.00
                    feesAmts = request_data.get('feesAmts')
                    if feesAmts:
                        feesAmts = ast.literal_eval(feesAmts)
                        for feeAmt in feesAmts:
                            feesAmtTemp -= float(feeAmt.get('Amt'))
                        if feesAmtTemp != 0:
                            return invalid_response("feesAmts_not_match",
                                                    _("The sum of feesAmts must be equals feesAmt"), 400)

                if ((provider_provider == 'fawry' and request_data.get('pmtType') == "POST") or provider_provider == 'khales') \
                        and not request_data.get('billRefNumber'):
                    return invalid_response("billRefNumber_not_found", _("missing bill reference number in request data"), 400)

                # Provider is mandatory because the service fee is different per provider.
                # So the user must send provider that own the bill inquiry request for prevent pay bill
                # with total amount different of total amount in bill inquiry
                if provider_provider:
                    provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                    if provider:
                        service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                            ('product_tmpl_id', '=', service.product_tmpl_id.id),
                            ('name', '=', provider.related_partner.id)
                        ])
                        if not service_providerinfo:
                            return invalid_response(
                                "Incompatible_provider_service", _("%s is not a provider for (%s) service") % (
                                    provider_provider, service.name), 400)
                else:
                    return invalid_response("provider_not_found",
                                            _("missing provider in request data"), 400)

                trans_amount = float(request_data.get('trans_amount'))
                if not trans_amount:
                    return invalid_response("amount_not_found",
                                            _("missing bill amount in request data"), 400)
                else:
                    # Calculate Fees
                    provider_fees_calculated_amount = 0.0
                    provider_fees_actual_amount = 0.0
                    merchant_cashback_amount = 0.0
                    customer_cashback_amount = 0.0
                    extra_fees_amount = 0.0
                    commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                        domain=[('vendor', '=', service_providerinfo.name.id),
                                ('vendor_product_code', '=', service_providerinfo.product_code)],
                        fields=['Amount_Range_From', 'Amount_Range_To',
                                'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt',
                                'Mer_Comm_Full_Fix_Amt', 'Cust_Comm_Full_Fix_Amt',
                                'Bill_Merchant_Comm_Prc', 'Bill_Customer_Comm_Prc']
                    )
                    for commission in commissions:
                        if commission['Amount_Range_From'] <= trans_amount \
                                and commission['Amount_Range_To'] >= trans_amount:
                            if commission['Mer_Comm_Full_Fix_Amt'] > 0:
                                merchant_cashback_amount = commission['Mer_Comm_Full_Fix_Amt']
                                customer_cashback_amount = commission['Cust_Comm_Full_Fix_Amt']
                            elif commission['Bill_Merchant_Comm_Prc'] > 0:
                                merchant_cashback_amount = trans_amount * commission[
                                    'Bill_Merchant_Comm_Prc'] / 100
                                customer_cashback_amount = trans_amount * commission[
                                    'Bill_Customer_Comm_Prc'] / 100
                            if commission['Extra_Fee_Amt'] > 0:
                                extra_fees_amount = commission['Extra_Fee_Amt']
                            elif commission['Extra_Fee_Prc'] > 0:
                                extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                            if commission['Mer_Fee_Amt'] > 0:
                                provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                            elif commission['Mer_Fee_Prc'] > 0:
                                # Fees amount = FA + [Percentage * Payment Amount]
                                # Fees amount ====================> provider_fees_calculated_amount
                                # FA =============================> provider_fees_calculated_amount
                                # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                provider_fees_prc_calculated_amount = trans_amount * commission[
                                    'Mer_Fee_Prc'] / 100
                                if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                        and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                            elif provider_provider == 'khales':
                                provider_fees_calculated_amount = float(request_data.get('feesAmt'))
                            break
                    calculated_payment_amount = trans_amount + provider_fees_calculated_amount + extra_fees_amount
                    machine_wallet_balance = request.env.user.partner_id.wallet_balance
                    if machine_wallet_balance < calculated_payment_amount:
                        return invalid_response("machine_balance_not_enough",
                                                _("Machine Wallet Balance (%s) less than the payment amount (%s)") % (
                                                    machine_wallet_balance, calculated_payment_amount), 400)

            request_data['partner_id'] = request.env.user.partner_id.id
            model_name = 'smartpay_operations.request'
            model_record = request.env['ir.model'].sudo().search([('model', '=', model_name)])

            try:
                data = WebsiteForm().extract_data(model_record, request_data)
            # If we encounter an issue while extracting data
            except ValidationError as e:
                # I couldn't find a cleaner way to pass data to an exception
                return invalid_response("Error", _("Could not submit you request.") + " ==> " + str(e), 500)

            try:
                id_record = WebsiteForm().insert_record(request, model_record, data['record'], data['custom'], data.get('meta'))
                if id_record:
                    WebsiteForm().insert_attachment(model_record, id_record, data['attachments'])
                    request.env.cr.commit()
                    machine_request = model_record.env[model_name].sudo().browse(id_record)
                else:
                    return invalid_response("Error", _("Could not submit you request."), 500)

            # Some fields have additional SQL constraints that we can't check generically
            # Ex: crm.lead.probability which is a float between 0 and 1
            # TODO: How to get the name of the erroneous field ?
            except IntegrityError as e:
                return invalid_response("Error", _("Could not submit you request.") + " ==> " + str(e), 500)

            if request_data.get('request_type') == 'recharge_wallet':
                return valid_response({"message": _("Recharge your wallet request was submit successfully."),
                                        "request_number": machine_request.name
                                       })
            elif request_data.get('request_type') == 'wallet_invitation':
                return valid_response({"message": _("Wallet inivitation request for mobile number (%s) was submit successfully.") % (
                                                request_data.get('mobile_number')),
                                        "request_number": machine_request.name
                                       })
            elif request_data.get('request_type') == 'service_bill_inquiry':
                lang = request_data.get('lang')
                billingAcct = request_data.get('billingAcct')
                extraBillingAcctKeys = request_data.get('extraBillingAcctKeys')
                if extraBillingAcctKeys:
                    extraBillingAcctKeys = ast.literal_eval(extraBillingAcctKeys)

                provider_response = {}
                error = {}
                for provider_info in service.seller_ids:
                    provider = request.env['payment.acquirer'].sudo().search(
                        [("related_partner", "=", provider_info.name.id)])
                    if provider:
                        trans_amount = 0.0
                        provider_channel = False
                        machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                  ("type", "in", ("machine", "internet"))], limit=1)
                        if machine_channels:
                            provider_channel = machine_channels[0]
                        if provider.provider == "fawry":
                            provider_response = provider.get_fawry_bill_details(lang, provider_info.product_code,
                                                                                billingAcct, extraBillingAcctKeys, provider_channel)
                            if provider_response.get('Success'):
                                billRecType = provider_response.get('Success')
                                provider_response_json = suds_to_json(billRecType)
                                for BillSummAmt in billRecType['BillInfo']['BillSummAmt']:
                                    if BillSummAmt['BillSummAmtCode'] == 'TotalAmtDue':
                                        trans_amount += float(BillSummAmt['CurAmt']['Amt'])
                                        break
                        if provider.provider == "khales":
                            provider_response = {}
                            biller_info_json_dict = json.loads(provider_info.biller_info, strict=False)
                            bill_response = provider.get_khales_bill_details(lang, provider_info.product_code, biller_info_json_dict.get('Code'),
                                                                             billingAcct, extraBillingAcctKeys, provider_channel)
                            if bill_response.get('Success'):
                                billRecType = bill_response.get('Success')
                                payAmts = billRecType['BillInfo']['CurAmt']
                                if payAmts and isinstance(payAmts, OrderedDict):
                                    payAmts = [payAmts]
                                    billRecType['BillInfo']['CurAmt'] = payAmts
                                success_response = {'bill_response': suds_to_json(billRecType)}
                                # for payAmt in payAmts:
                                    # trans_amount += float(payAmt.get("AmtDue"))
                                trans_amount += float(payAmts[0].get("AmtDue"))
                                if biller_info_json_dict.get('PmtType') == 'POST':
                                    ePayBillRecID = billRecType['EPayBillRecID']
                                    fees_response = provider.get_khales_fees(lang, ePayBillRecID, payAmts[0], provider_channel)
                                    if fees_response.get('Success'):
                                        feeInqRsType = fees_response.get('Success')
                                        success_response.update({'fees_response': suds_to_json(feeInqRsType)})
                                provider_response = {'Success': success_response}

                                provider_response_json = provider_response.get('Success')
                            else:
                                provider_response = bill_response

                        if provider_response.get('Success'):
                            commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                                domain=[('vendor', '=', provider_info.name.id), ('vendor_product_code', '=', provider_info.product_code)],
                                fields=['Amount_Range_From', 'Amount_Range_To', 'Extra_Fee_Amt', 'Extra_Fee_Prc']
                            )
                            extra_fees_amount = 0.0
                            for commission in commissions:
                                if commission['Amount_Range_From'] <= trans_amount \
                                        and commission['Amount_Range_To'] >= trans_amount:
                                    if commission['Extra_Fee_Amt'] > 0:
                                        extra_fees_amount = commission['Extra_Fee_Amt']
                                    elif commission['Extra_Fee_Prc'] > 0:
                                        extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                                    break
                            machine_request.update(
                                {"provider_id": provider.id, "provider_response": provider_response_json,
                                 "trans_amount": trans_amount, "extra_fees_amount": extra_fees_amount,
                                 "extra_fees": commissions, "stage_id": 5})
                            request.env.cr.commit()
                            return valid_response(
                                {"message": _("Service Bill Inquiry request was submit successfully."),
                                 "request_number": machine_request.name,
                                 "provider": provider.provider,
                                 "provider_response": provider_response_json,
                                 "extra_fees_amount": extra_fees_amount,
                                 # "extra_fees": commissions
                                 })
                        else:
                            error.update({provider.provider + "_response": provider_response or ''})
                    else:
                        error.update({provider_info.name.name + "_response": _("%s is not a provider for (%s) service") % (
                        provider_info.name.name, service.name)})

                machine_request.update({
                    "provider_response": error or _("(%s) service has not any provider.") % (service.name),
                    "stage_id": 5
                })
                request.env.cr.commit()
                return invalid_response("Error", error or _("(%s) service has not any provider.") % (service.name), 400)

            elif request_data.get('request_type') == 'pay_service_bill':
                lang = request_data.get('lang')
                billingAcct = request_data.get('billingAcct')

                extraBillingAcctKeys = request_data.get('extraBillingAcctKeys')
                if extraBillingAcctKeys:
                    extraBillingAcctKeys = ast.literal_eval(extraBillingAcctKeys)

                notifyMobile = request_data.get('notifyMobile')
                billRefNumber = request_data.get('billRefNumber')
                billerId = request_data.get('billerId')
                pmtType = request_data.get('pmtType')

                trans_amount = request_data.get('trans_amount')
                curCode = request_data.get('currency_id')
                payAmts = request_data.get('payAmts')
                if payAmts:
                    payAmts = ast.literal_eval(payAmts)
                else:
                    payAmts = [{'Sequence': '1', 'AmtDue': trans_amount, 'CurCode': curCode}]
                pmtMethod = request_data.get('pmtMethod')

                ePayBillRecID = request_data.get('ePayBillRecID')
                pmtId = request_data.get('pmtId') or machine_request.name
                feesAmt = request_data.get('feesAmt') or 0.00
                feesAmts = request_data.get('feesAmts')
                if feesAmts:
                    feesAmts = ast.literal_eval(feesAmts)
                else:
                    feesAmts = [{'Amt': feesAmt, 'CurCode': curCode}]
                pmtRefInfo = request_data.get('pmtRefInfo')

                providers_info = []
                '''
                provider_provider = request_data.get('provider')
                if provider_provider:
                    provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                    if provider:
                        service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                            ('product_tmpl_id', '=', service.product_tmpl_id.id),
                            ('name', '=', provider.related_partner.id)
                        ])
                        if service_providerinfo:
                            providers_info.append(service_providerinfo)
                if not provider_provider or len(providers_info) == 0:
                    providers_info = service.seller_ids
                '''
                providers_info.append(service_providerinfo)

                provider_response = {}
                provider_response_json = {}
                '''
                provider_fees_calculated_amount = 0.0
                provider_fees_actual_amount = 0.0
                merchant_cashback_amount = 0.0
                customer_cashback_amount = 0.0
                extra_fees_amount = 0.0
                '''
                error = {}
                for provider_info in providers_info:
                    biller_info_json_dict = json.loads(provider_info.biller_info, strict=False)
                    '''
                    # Get Extra Fees
                    commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                        domain=[('vendor', '=', provider_info.name.id),
                                ('vendor_product_code', '=', provider_info.product_code)],
                        fields=['Amount_Range_From', 'Amount_Range_To',
                                'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt',
                                'Mer_Comm_Full_Fix_Amt', 'Cust_Comm_Full_Fix_Amt',
                                'Bill_Merchant_Comm_Prc', 'Bill_Customer_Comm_Prc']
                    )
                    for commission in commissions:
                        if commission['Amount_Range_From'] <= machine_request.trans_amount \
                                and commission['Amount_Range_To'] >= machine_request.trans_amount:
                            if commission['Mer_Comm_Full_Fix_Amt'] > 0:
                                merchant_cashback_amount = commission['Mer_Comm_Full_Fix_Amt']
                                customer_cashback_amount = commission['Cust_Comm_Full_Fix_Amt']
                            elif commission['Bill_Merchant_Comm_Prc'] > 0:
                                merchant_cashback_amount = machine_request.trans_amount * commission[
                                    'Bill_Merchant_Comm_Prc'] / 100
                                customer_cashback_amount = machine_request.trans_amount * commission[
                                    'Bill_Customer_Comm_Prc'] / 100
                            if commission['Extra_Fee_Amt'] > 0:
                                extra_fees_amount = commission['Extra_Fee_Amt']
                            elif commission['Extra_Fee_Prc'] > 0:
                                extra_fees_amount = machine_request.trans_amount * commission['Extra_Fee_Prc'] / 100
                            if commission['Mer_Fee_Amt'] > 0:
                                provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                            elif commission['Mer_Fee_Prc'] > 0:
                                # Fees amount = FA + [Percentage * Payment Amount]
                                # Fees amount ====================> provider_fees_calculated_amount
                                # FA =============================> provider_fees_calculated_amount
                                # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                provider_fees_prc_calculated_amount = machine_request.trans_amount * commission['Mer_Fee_Prc'] / 100
                                if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                        and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                            elif provider_provider == 'khales':
                                provider_fees_calculated_amount = float(request_data.get('feesAmt'))
                            break
                    calculated_payment_amount = machine_request.trans_amount + provider_fees_calculated_amount + extra_fees_amount
                    machine_wallet_balance = request.env.user.partner_id.wallet_balance
                    if machine_wallet_balance < calculated_payment_amount:
                        error.update({"machine_balance_not_enough":
                                                _("Machine Wallet Balance (%s) less than the payment amount (%s)") % (machine_wallet_balance,
                                                                                                                      calculated_payment_amount)})
                    '''

                    machine_request.update({'provider_fees_calculated_amount': provider_fees_calculated_amount})
                    request.env.cr.commit()
                    provider = request.env['payment.acquirer'].sudo().search([("related_partner", "=", provider_info.name.id)])
                    if provider:
                        try:
                            provider_channel = False
                            machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                      ("type", "in", ("machine", "internet"))], limit=1)
                            if machine_channels:
                                provider_channel = machine_channels[0]
                            if provider.provider == "fawry":
                                # Tamayoz TODO: Provider Server Timeout Handling
                                provider_response = provider.pay_fawry_bill(lang, provider_info.product_code,
                                                                            billingAcct, extraBillingAcctKeys,
                                                                            trans_amount, curCode, pmtMethod,
                                                                            notifyMobile, billRefNumber,
                                                                            billerId, pmtType, provider_channel)
                                if provider_response.get('Success'):
                                    provider_response_json = suds_to_json(provider_response.get('Success'))
                                    # Get Provider Fees
                                    provider_response_json_dict = json.loads(provider_response_json, strict=False)
                                    # provider_response_json_dict['PmtInfo']['CurAmt']['Amt'] == machine_request.trans_amount
                                    provider_fees_actual_amount = provider_response_json_dict['PmtInfo']['FeesAmt']['Amt']
                                    machine_request.update({'provider_fees_amount': provider_fees_actual_amount})
                                    request.env.cr.commit()
                                    # Get Provider Payment Trans ID
                                    for payment in provider_response_json_dict['PmtTransId']:
                                        if payment['PmtIdType'] == 'FCRN':
                                            provider_payment_trans_id = payment['PmtId']
                                            break
                            if provider.provider == "khales":
                                if not billerId:
                                    billerId = biller_info_json_dict.get('Code')
                                # Tamayoz TODO: Provider Server Timeout Handling
                                # Tamayoz TODO: Remove the next temporary line
                                pmtMethod = "CARD"  # TEMP CODE
                                provider_response = provider.pay_khales_bill(lang, billingAcct, billerId, ePayBillRecID,
                                                                             payAmts, pmtId, pmtType, feesAmts,
                                                                             billRefNumber, pmtMethod, pmtRefInfo,
                                                                             provider_channel)
                                if provider_response.get('Success'):
                                    provider_response_json = suds_to_json(provider_response.get('Success'))
                                    # Add required parameters for cancel payment scenario
                                    # parsing JSON string:
                                    provider_response_json_dict = json.loads(provider_response_json)
                                    pmtId = provider_response_json_dict['PmtRecAdviceStatus']['PmtTransId']['PmtId']
                                    # appending the data
                                    provider_response_json_dict.update({'billingAcct': billingAcct, 'billRefNumber': billRefNumber,
                                                                        'billerId': billerId, 'pmtType': pmtType, 'trans_amount': trans_amount,
                                                                        'curCode': curCode, 'pmtMethod': pmtMethod, 'ePayBillRecID': ePayBillRecID,
                                                                        'pmtId': pmtId, 'feesAmt': feesAmt, 'pmtRefInfo': pmtRefInfo})
                                    if payAmts:
                                        provider_response_json_dict.update({'payAmts': payAmts})
                                    if feesAmts:
                                        provider_response_json_dict.update({'feesAmts': feesAmts})
                                    # the result is a JSON string:
                                    provider_response_json = json.dumps(provider_response_json_dict)
                                    # Provider Fees
                                    provider_fees_actual_amount = float(feesAmt)
                                    machine_request.update({'provider_fees_amount': provider_fees_actual_amount})
                                    request.env.cr.commit()
                                    # Provider Payment Trans ID
                                    provider_payment_trans_id = pmtId

                            if provider_response.get('Success'):
                                try:
                                    provider_invoice_id = False
                                    refund = False
                                    customer_invoice_id = False
                                    credit_note = False
                                    machine_request_response = {"request_number": machine_request.name,
                                                                "request_datetime": machine_request.create_date + timedelta(hours=2),
                                                                "provider": provider.provider,
                                                                "provider_response": provider_response_json
                                                                }

                                    provider_actual_amount = machine_request.trans_amount + provider_fees_actual_amount
                                    customer_actual_amount = provider_actual_amount + extra_fees_amount

                                    # Deduct Transaction Amount from Machine Wallet Balance
                                    wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                                    label = _('Pay Service Bill for %s service') % (service.name)
                                    partner_id_wallet_balance = request.env.user.partner_id.wallet_balance
                                    machine_wallet_create = wallet_transaction_sudo.create(
                                        {'wallet_type': 'debit', 'partner_id': request.env.user.partner_id.id,
                                         'request_id': machine_request.id,
                                         'reference': 'request',
                                         'label': label,
                                         'amount': customer_actual_amount, 'currency_id': machine_request.currency_id.id,
                                         'wallet_balance_before': partner_id_wallet_balance,
                                         'wallet_balance_after': partner_id_wallet_balance - customer_actual_amount,
                                         'status': 'done'})
                                    request.env.cr.commit()

                                    request.env.user.partner_id.update(
                                        {'wallet_balance': request.env.user.partner_id.wallet_balance - customer_actual_amount})
                                    request.env.cr.commit()

                                    # Notify customer
                                    irc_param = request.env['ir.config_parameter'].sudo()
                                    wallet_pay_service_bill_notify_mode = irc_param.get_param("smartpay_operations.wallet_pay_service_bill_notify_mode")
                                    if wallet_pay_service_bill_notify_mode == 'inbox':
                                        request.env['mail.thread'].sudo().message_notify(
                                            subject=label,
                                            body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                                                customer_actual_amount, _(machine_request.currency_id.name)),
                                            partner_ids=[(4, request.env.user.partner_id.id)],
                                        )
                                    elif wallet_pay_service_bill_notify_mode == 'email':
                                        machine_wallet_create.wallet_transaction_email_send()
                                    elif wallet_pay_service_bill_notify_mode == 'sms' and request.env.user.partner_id.mobile:
                                        machine_wallet_create.sms_send_wallet_transaction(wallet_pay_service_bill_notify_mode,
                                                                                          'wallet_pay_service',
                                                                                          request.env.user.partner_id.mobile,
                                                                                          request.env.user.name, label,
                                                                                          '%s %s' % (customer_actual_amount,
                                                                                                     _(machine_request.currency_id.name)),
                                                                                          request.env.user.partner_id.country_id.phone_code or '2')

                                    payment_info = {"service": service.name, "provider": provider.provider,
                                                    "request_number": machine_request.name,
                                                    "request_datetime": machine_request.create_date + timedelta(hours=2),
                                                    "label": biller_info_json_dict.get("BillTypeAcctLabel"),
                                                    "billing_acct": billingAcct, "ref_number": provider_payment_trans_id,
                                                    "amount": trans_amount,
                                                    "fees": (provider_fees_actual_amount + extra_fees_amount),
                                                    "total": customer_actual_amount}

                                    machine_request.update(
                                        {'extra_fees_amount': extra_fees_amount,
                                         'wallet_transaction_id': machine_wallet_create.id,
                                         'trans_date': date.today(),
                                         'provider_id': provider.id,
                                         'provider_response': provider_response_json, "stage_id": 5})
                                    request.env.cr.commit()

                                    # VouchPIN Decryption if exist
                                    if provider_response_json_dict.get('VouchInfo'):
                                        decrypted_bytes = bytes(provider_response_json_dict['VouchInfo']['VouchPIN'],
                                                                encoding='utf-8')
                                        # text = base64.decodestring(decrypted_bytes) #
                                        text = base64.b64decode(decrypted_bytes)  #
                                        cipher = DES3.new(SECRET_KEY, DES3.MODE_ECB)
                                        VouchPIN = cipher.decrypt(text)
                                        VouchPIN = UNPAD(VouchPIN)
                                        VouchPIN = VouchPIN.decode('utf-8')  # unpad and decode bytes to str
                                        machine_request_response.update({'vouch_pin': VouchPIN})
                                        payment_info.update({"vouch_pin": VouchPIN,
                                                             "vouch_sn": provider_response_json_dict['VouchInfo']['VouchSN']})

                                    # Wallet Transaction Info with payment info
                                    machine_wallet_create.update({"wallet_transaction_info": json.dumps({"payment_info": payment_info}, default=default)})
                                    request.env.cr.commit()

                                    '''
                                    # Create Vendor (Provider) Invoices
                                    provider_invoice_ids = ()
                                    # 1- Create Vendor bill
                                    provider_journal_id = request.env['account.journal'].sudo().search([('type', '=', 'purchase'),
                                                                                              ('company_id', '=', request.env.user.company_id.id)], limit=1)
                                    name = provider.provider + ': [' + provider_info.product_code + '] ' + provider_info.product_name
                                    provider_invoice_vals = machine_request.with_context(name=name,
                                                                                         provider_payment_trans_id=provider_payment_trans_id,
                                                                                         journal_id=provider_journal_id.id,
                                                                                         invoice_date=date.today(),
                                                                                         invoice_type='in_invoice',
                                                                                         partner_id=provider_info.name.id)._prepare_invoice()
                                    provider_invoice_id = request.env['account.invoice'].sudo().create(provider_invoice_vals)
                                    invoice_line = provider_invoice_id._prepare_invoice_line_from_request(request=machine_request,
                                                                                                          name=name,
                                                                                                          qty=1,
                                                                                                          price_unit=provider_actual_amount)
                                    new_line = request.env['account.invoice.line'].sudo().new(invoice_line)
                                    new_line._set_additional_fields(provider_invoice_id)
                                    provider_invoice_id.invoice_line_ids += new_line
                                    provider_invoice_id.action_invoice_open()
                                    provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                    provider_invoice_id.pay_and_reconcile(request.env['account.journal'].sudo().search(
                                        [('type', '=', 'cash'),
                                         ('company_id', '=', request.env.user.company_id.id),
                                         ('provider_id', '=', provider.id)], limit=1),
                                        provider_actual_amount)
                                    request.env.cr.commit()
                                    # 2- Create Vendor Refund with commision amount
                                    if merchant_cashback_amount > 0:
                                        refund = request.env['account.invoice.refund'].with_context(
                                            active_ids=provider_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': name,
                                            'date': provider_invoice_id.date_invoice,
                                        })
                                        result = refund.invoice_refund()
                                        refund_id = result.get('domain')[1][2]
                                        refund = request.env['account.invoice'].sudo().browse(refund_id)
                                        refund.update({'reference': provider_payment_trans_id, 'request_id': machine_request.id})
                                        refund_line = refund.invoice_line_ids[0]
                                        refund_line.update({'price_unit': merchant_cashback_amount, 'request_id': machine_request.id})
                                        refund.refresh()
                                        refund.action_invoice_open()
                                        provider_invoice_ids += (tuple(refund.ids),)
                                    machine_request.update({'provider_invoice_ids': provider_invoice_ids})
                                    request.env.cr.commit()

                                    # Create Customer Invoices
                                    customer_invoice_ids = ()
                                    # 1- Create Customer Invoice
                                    customer_journal_id = request.env['account.journal'].sudo().search([('type', '=', 'sale'),
                                                                                              ('company_id', '=', request.env.user.company_id.id)], limit=1)
                                    customer_invoice_vals = machine_request.with_context(name=provider_payment_trans_id,
                                                                                         journal_id=customer_journal_id.id,
                                                                                         invoice_date=date.today(),
                                                                                         invoice_type='out_invoice',
                                                                                         partner_id=request.env.user.partner_id.id)._prepare_invoice()
                                    customer_invoice_id = request.env['account.invoice'].sudo().create(customer_invoice_vals)
                                    machine_request.invoice_line_create(invoice_id=customer_invoice_id.id, name=name,
                                                                        qty=1, price_unit=customer_actual_amount)
                                    customer_invoice_id.action_invoice_open()
                                    customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                    # Auto Reconcile customer invoice with prepaid wallet recharge payments and previous cashback credit note
                                    domain = [('account_id', '=', customer_invoice_id.account_id.id),
                                              ('partner_id', '=',
                                               customer_invoice_id.env['res.partner']._find_accounting_partner(customer_invoice_id.partner_id).id),
                                              ('reconciled', '=', False),
                                              '|',
                                              '&', ('amount_residual_currency', '!=', 0.0), ('currency_id', '!=', None),
                                              '&', ('amount_residual_currency', '=', 0.0), '&', ('currency_id', '=', None),
                                              ('amount_residual', '!=', 0.0)]
                                    domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                                    lines = customer_invoice_id.env['account.move.line'].sudo().search(domain)
                                    for line in lines:
                                        # get the outstanding residual value in invoice currency
                                        if line.currency_id and line.currency_id == customer_invoice_id.currency_id:
                                            amount_residual_currency = abs(line.amount_residual_currency)
                                        else:
                                            currency = line.company_id.currency_id
                                            amount_residual_currency = currency._convert(abs(line.amount_residual),
                                                                                         customer_invoice_id.currency_id,
                                                                                         customer_invoice_id.company_id,
                                                                                         line.date or fields.Date.today())
                                        if float_is_zero(amount_residual_currency, precision_rounding=customer_invoice_id.currency_id.rounding):
                                            continue

                                        customer_invoice_id.assign_outstanding_credit(line.id)
                                        if customer_invoice_id.state == 'paid':
                                            break
                                    request.env.cr.commit()

                                    # 2- Create Customer Credit Note with commision amount for only customers have commission
                                    if request.env.user.commission and customer_cashback_amount > 0:
                                        credit_note = request.env['account.invoice.refund'].with_context(
                                            active_ids=customer_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': provider_payment_trans_id,
                                            'date': customer_invoice_id.date_invoice,
                                        })
                                        result = credit_note.invoice_refund()
                                        credit_note_id = result.get('domain')[1][2]
                                        credit_note = request.env['account.invoice'].sudo().browse(credit_note_id)
                                        credit_note.update({'request_id': machine_request.id})
                                        credit_note_line = credit_note.invoice_line_ids[0]
                                        credit_note_line.update({'price_unit': customer_cashback_amount, 'request_id': machine_request.id})
                                        credit_note.refresh()
                                        """  Don't validate the customer credit note until the vendor refund reconciliation
                                        After vendor refund reconciliation, validate the customer credit note with
                                        the net amount of vendor refund sent in provider cashback statement then
                                        increase the customer wallet with the same net amount. """
                                        # credit_note.action_invoice_open()
                                        customer_invoice_ids += (tuple(credit_note.ids),)
                                    machine_request.update({'customer_invoice_ids': customer_invoice_ids})
                                    request.env.cr.commit()
                                    '''

                                    if provider.provider == "khales":
                                        # Add required parameters for cancel payment scenario
                                        machine_request_response.update({'billingAcct': billingAcct, 'billRefNumber': billRefNumber,
                                                                         'billerId': billerId, 'pmtType': pmtType, 'trans_amount': trans_amount,
                                                                         'curCode': curCode, 'pmtMethod': pmtMethod, 'ePayBillRecID': ePayBillRecID,
                                                                         'pmtId': pmtId, 'feesAmt': feesAmt, 'pmtRefInfo': pmtRefInfo})
                                        if payAmts:
                                            machine_request_response.update({'payAmts': payAmts})
                                        if feesAmts:
                                            machine_request_response.update({'feesAmts': feesAmts})
                                    machine_request_response.update({"message": _("Pay Service Bill request was submit successfully with amount %s %s. Your Machine Wallet Balance is %s %s")
                                                                            % (customer_actual_amount,
                                                                               machine_request.currency_id.name,
                                                                               request.env.user.partner_id.wallet_balance,
                                                                               machine_request.currency_id.name)})

                                    # Cancel
                                    # request_number = {"request_number": machine_request.name}
                                    # self.cancel_request(**request_number)

                                    return valid_response(machine_request_response)
                                except Exception as e:
                                    try:
                                        _logger.error("%s", e)
                                        machine_request_update = {'extra_fees_amount': extra_fees_amount,
                                                                  'trans_date': date.today(),
                                                                  'provider_id': provider.id,
                                                                  'provider_response': provider_response_json, "stage_id": 5,
                                                                  'description': _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e)}
                                        if machine_wallet_create:
                                            machine_request_update.update({'wallet_transaction_id': machine_wallet_create.id})
                                        provider_invoice_ids = ()
                                        if provider_invoice_id or refund:
                                            if provider_invoice_id:
                                                provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                            if refund:
                                                provider_invoice_ids += (tuple(refund.ids),)
                                            machine_request_update.update({'provider_invoice_ids': provider_invoice_ids})
                                        customer_invoice_ids = ()
                                        if customer_invoice_id or credit_note:
                                            if customer_invoice_id:
                                                customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                            if credit_note:
                                                customer_invoice_ids += (tuple(credit_note.ids),)
                                            machine_request_update.update({'customer_invoice_ids': customer_invoice_ids})
                                        machine_request.update(machine_request_update)
                                        request.env.cr.commit()
                                    except Exception as e1:
                                        _logger.error("%s", e1)
                                        if machine_request and not machine_request.description:
                                            machine_request.update({'description': _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e)})
                                            request.env.cr.commit()

                                    return invalid_response(machine_request_response, _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e),
                                                            500)
                            else:
                                error.update({provider.provider + "_response": provider_response or ''})
                        except Exception as e2:
                            _logger.error("%s", e2)
                            if machine_request and not machine_request.description:
                                machine_request.update({'description': _("Error is occur:") + " ==> " + str(e2)})
                                request.env.cr.commit()
                            return invalid_response("Error", _("Error is occur:") + " ==> " + str(e), 500)
                    else:
                        error.update({provider_info.name.name + "_response": _("%s is not a provider for (%s) service") % (
                            provider_info.name.name, service.name)})

                machine_request.update({
                    'provider_response': error or _('(%s) service has not any provider.') % (service.name),
                    'stage_id': 5
                })
                request.env.cr.commit()
                return invalid_response("Error", error or _("(%s) service has not any provider.") % (service.name), 400)

            elif request_data.get('request_type') == 'pay_invoice':
                return valid_response({"message": _("Pay invoice request was submit successfully."),
                                       "request_number": machine_request.name
                                       })
            else:
                return valid_response({"message": _("Your request was submit successfully."),
                                       "request_number":machine_request.name
                                       })

        @validate_token
        @http.route('/api/createMobileRequest', type="http", auth="none", methods=["POST"], csrf=False)
        def createMobileRequest(self, **request_data):
            _logger.info(">>>>>>>>>>>>>>>>>>> Calling Mobile Request API")

            if not request_data.get('request_type') or request_data.get('request_type') not in _REQUEST_TYPES_IDS:
                return invalid_response("request_type", _("request type invalid"), 400)

            if request_data.get('request_type') == 'recharge_wallet':
                if not request_data.get('trans_amount'):
                    return invalid_response("amount_not_found", _("missing amount in request data"), 400)
                open_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'recharge_wallet'),("partner_id", "=", request.env.user.partner_id.id), ("stage_id", "=", 1)],
                    order="id DESC", limit=1)
                if open_request:
                    return invalid_response("request_already_exist", _("You have a wallet recharge request in progress with REQ Number (%s)")
                                            % (open_request.name), 400)
                request_data['product_id'] = request.env["product.product"].sudo().search([('name', '=', 'Wallet Recharge')]).id

            if not request_data.get('product_id') and request_data.get('request_type') not in ('general_inquiry', 'wallet_invitation'):
                return invalid_response("service_not_found", _("missing service in request data"), 400)
            elif request_data.get('request_type') not in ('general_inquiry', 'wallet_invitation'):
                service = request.env["product.product"].sudo().search([("id", "=", request_data.get('product_id')), ("type", "=", "service")],
                                                                       order="id DESC", limit=1)
                if not service:
                    return invalid_response("service", _("service invalid"), 400)

            if request_data.get('request_type') == 'wallet_invitation':
                if not request_data.get('mobile_number'):
                    return invalid_response("mobile_number_not_found", _("missing mobile number for invited user in request data"), 400)

                open_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'wallet_invitation'), ('mobile_number', '=', request_data.get('mobile_number')),
                     ('partner_id', '=', request.env.user.partner_id.id), ("stage_id", "=", 1)], order="id DESC", limit=1)
                if open_request:
                    return invalid_response("request_already_exist",
                                            _("You have a wallet invitation request in progress for mobile number (%s) with REQ Number (%s)") % (
                                                request_data.get('mobile_number'), open_request.name), 400)

                done_request = request.env["smartpay_operations.request"].sudo().search(
                    [('request_type', '=', 'wallet_invitation'),
                     ('mobile_number', '=', request_data.get('mobile_number')), ("stage_id", "=", 5)],
                    order="id DESC", limit=1)
                if done_request:
                    return invalid_response("request_already_exist",
                                            _("The mobile number (%s) already has a wallet") % (
                                                request_data.get('mobile_number')), 400)

            if request_data.get('request_type') == 'service_bill_inquiry' or request_data.get('request_type') == 'pay_service_bill':
                if not request_data.get('billingAcct'):
                    return invalid_response("billingAcct_not_found", _("missing billing account in request data"), 400)

                if request_data.get('request_type') == 'pay_service_bill':
                    if not request_data.get('currency_id'):
                        return invalid_response("curCode_not_found",
                                                _("missing bill currency code in request data"), 400)
                    if not request_data.get('pmtMethod'):
                        return invalid_response("pmtMethod_not_found",
                                                _("missing payment method in request data"), 400)

                    provider_provider = request_data.get('provider')
                    if provider_provider == 'khales':
                        if not request_data.get('pmtType'):
                            return invalid_response("pmtType_not_found", _("missing payment type in request data"), 400)
                        '''
                        if not request_data.get('billerId'):
                            return invalid_response("billerId_not_found", _("missing biller id in request data"), 400)
                        '''
                        if not request_data.get('ePayBillRecID'):
                            return invalid_response("ePayBillRecID_not_found", _("missing ePay Bill Rec ID in request data"), 400)
                        if not request_data.get('pmtId'):
                            return invalid_response("pmtId_not_found", _("missing payment id in request data"), 400)
                        if not request_data.get('feesAmt'):
                            return invalid_response("feesAmt_not_found", _("missing fees amount in request data"), 400)
                        # if not request_data.get('pmtRefInfo'):
                            # return invalid_response("pmtRefInfo_not_found", _("missing payment Ref Info in request data"), 400)
                        payAmtTemp = float(request_data.get('trans_amount'))
                        payAmts = request_data.get('payAmts')
                        if payAmts:
                            payAmts = ast.literal_eval(payAmts)
                            for payAmt in payAmts:
                                payAmtTemp -= float(payAmt.get('AmtDue'))
                            if payAmtTemp != 0:
                                return invalid_response("payAmts_not_match",
                                                        _("The sum of payAmts must be equals trans_amount"), 400)

                        feesAmtTemp = request_data.get('feesAmt') or 0.00
                        feesAmts = request_data.get('feesAmts')
                        if feesAmts:
                            feesAmts = ast.literal_eval(feesAmts)
                            for feeAmt in feesAmts:
                                feesAmtTemp -= float(feeAmt.get('Amt'))
                            if feesAmtTemp != 0:
                                return invalid_response("feesAmts_not_match",
                                                        _("The sum of feesAmts must be equals feesAmt"), 400)

                    if ((provider_provider == 'fawry' and request_data.get('pmtType') == "POST") or provider_provider == 'khales') \
                            and not request_data.get('billRefNumber'):
                        return invalid_response("billRefNumber_not_found", _("missing bill reference number in request data"), 400)

                    # Provider is mandatory because the service fee is different per provider.
                    # So the user must send provider that own the bill inquiry request for prevent pay bill
                    # with total amount different of total amount in bill inquiry
                    if provider_provider:
                        provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                        if provider:
                            service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                                ('product_tmpl_id', '=', service.product_tmpl_id.id),
                                ('name', '=', provider.related_partner.id)
                            ])
                            if not service_providerinfo:
                                return invalid_response(
                                    "Incompatible_provider_service", _("%s is not a provider for (%s) service") % (
                                        provider_provider, service.name), 400)
                    else:
                        return invalid_response("provider_not_found",
                                                _("missing provider in request data"), 400)

                    trans_amount = float(request_data.get('trans_amount'))
                    if not trans_amount:
                        return invalid_response("amount_not_found",
                                                _("missing bill amount in request data"), 400)
                    else:
                        # Calculate Fees
                        provider_fees_calculated_amount = 0.0
                        provider_fees_actual_amount = 0.0
                        merchant_cashback_amount = 0.0
                        customer_cashback_amount = 0.0
                        extra_fees_amount = 0.0
                        commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                            domain=[('vendor', '=', service_providerinfo.name.id),
                                    ('vendor_product_code', '=', service_providerinfo.product_code)],
                            fields=['Amount_Range_From', 'Amount_Range_To',
                                    'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                    'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt',
                                    'Mer_Comm_Full_Fix_Amt', 'Cust_Comm_Full_Fix_Amt',
                                    'Bill_Merchant_Comm_Prc', 'Bill_Customer_Comm_Prc']
                        )
                        for commission in commissions:
                            if commission['Amount_Range_From'] <= trans_amount \
                                    and commission['Amount_Range_To'] >= trans_amount:
                                if commission['Mer_Comm_Full_Fix_Amt'] > 0:
                                    merchant_cashback_amount = commission['Mer_Comm_Full_Fix_Amt']
                                    customer_cashback_amount = commission['Cust_Comm_Full_Fix_Amt']
                                elif commission['Bill_Merchant_Comm_Prc'] > 0:
                                    merchant_cashback_amount = trans_amount * commission[
                                        'Bill_Merchant_Comm_Prc'] / 100
                                    customer_cashback_amount = trans_amount * commission[
                                        'Bill_Customer_Comm_Prc'] / 100
                                if commission['Extra_Fee_Amt'] > 0:
                                    extra_fees_amount = commission['Extra_Fee_Amt']
                                elif commission['Extra_Fee_Prc'] > 0:
                                    extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                                if commission['Mer_Fee_Amt'] > 0:
                                    provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                                elif commission['Mer_Fee_Prc'] > 0:
                                    # Fees amount = FA + [Percentage * Payment Amount]
                                    # Fees amount ====================> provider_fees_calculated_amount
                                    # FA =============================> provider_fees_calculated_amount
                                    # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                    provider_fees_prc_calculated_amount = trans_amount * commission[
                                        'Mer_Fee_Prc'] / 100
                                    if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                        provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                    elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                            and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                        provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                    provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                                elif provider_provider == 'khales':
                                    provider_fees_calculated_amount = float(request_data.get('feesAmt'))
                                break
                        calculated_payment_amount = trans_amount + provider_fees_calculated_amount + extra_fees_amount
                        mobile_wallet_balance = request.env.user.partner_id.wallet_balance
                        if mobile_wallet_balance < calculated_payment_amount:
                            return invalid_response("mobile_balance_not_enough",
                                                    _("Mobile Wallet Balance (%s) less than the payment amount (%s)") % (
                                                        mobile_wallet_balance, calculated_payment_amount), 400)

            request_data['partner_id'] = request.env.user.partner_id.id
            model_name = 'smartpay_operations.request'
            model_record = request.env['ir.model'].sudo().search([('model', '=', model_name)])

            try:
                data = WebsiteForm().extract_data(model_record, request_data)
            # If we encounter an issue while extracting data
            except ValidationError as e:
                # I couldn't find a cleaner way to pass data to an exception
                return invalid_response("Error", _("Could not submit you request.") + " ==> " + str(e), 500)

            try:
                id_record = WebsiteForm().insert_record(request, model_record, data['record'], data['custom'], data.get('meta'))
                if id_record:
                    WebsiteForm().insert_attachment(model_record, id_record, data['attachments'])
                    request.env.cr.commit()
                    user_request = model_record.env[model_name].sudo().browse(id_record)
                else:
                    return invalid_response("Error", _("Could not submit you request."), 500)

            # Some fields have additional SQL constraints that we can't check generically
            # Ex: crm.lead.probability which is a float between 0 and 1
            # TODO: How to get the name of the erroneous field ?
            except IntegrityError as e:
                return invalid_response("Error", _("Could not submit you request.") + " ==> " + str(e), 500)

            if request_data.get('request_type') == 'recharge_wallet':
                return valid_response({"message": _("Recharge your wallet request was submit successfully."),
                                       "request_number": user_request.name
                                       })
            elif request_data.get('request_type') == 'wallet_invitation':
                return valid_response({"message": _("Wallet inivitation request for mobile number (%s) was submit successfully.") % (
                                                request_data.get('mobile_number')),
                                        "request_number": user_request.name
                                       })

            elif request_data.get('request_type') == 'service_bill_inquiry':
                lang = request_data.get('lang')
                billingAcct = request_data.get('billingAcct')
                extraBillingAcctKeys = request_data.get('extraBillingAcctKeys')
                if extraBillingAcctKeys:
                    extraBillingAcctKeys = ast.literal_eval(extraBillingAcctKeys)

                provider_response = {}
                error = {}
                for provider_info in service.seller_ids:
                    provider = request.env['payment.acquirer'].sudo().search([("related_partner", "=", provider_info.name.id)])
                    if provider:
                        trans_amount = 0.0
                        provider_channel = False
                        machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                  ("type", "in", ("machine", "internet"))], limit=1)
                        if machine_channels:
                            provider_channel = machine_channels[0]

                        if provider.provider == "fawry":
                            provider_response = provider.get_fawry_bill_details(lang, provider_info.product_code,
                                                                                billingAcct, extraBillingAcctKeys, provider_channel)
                            if provider_response.get('Success'):
                                billRecType = provider_response.get('Success')
                                provider_response_json = suds_to_json(billRecType)
                                for BillSummAmt in billRecType['BillInfo']['BillSummAmt']:
                                    if BillSummAmt['BillSummAmtCode'] == 'TotalAmtDue':
                                        trans_amount += float(BillSummAmt['CurAmt']['Amt'])
                                        break
                        if provider.provider == "khales":
                            provider_response = {}
                            biller_info_json_dict = json.loads(provider_info.biller_info, strict=False)
                            bill_response = provider.get_khales_bill_details(lang, provider_info.product_code, biller_info_json_dict.get('Code'),
                                                                             billingAcct, extraBillingAcctKeys, provider_channel)
                            if bill_response.get('Success'):
                                billRecType = bill_response.get('Success')
                                payAmts = billRecType['BillInfo']['CurAmt']
                                if payAmts and isinstance(payAmts, OrderedDict):
                                    payAmts = [payAmts]
                                    billRecType['BillInfo']['CurAmt'] = payAmts
                                success_response = {'bill_response': suds_to_json(billRecType)}
                                # for payAmt in payAmts:
                                    # trans_amount += float(payAmt.get("AmtDue"))
                                trans_amount += float(payAmts[0].get("AmtDue"))
                                if biller_info_json_dict.get('PmtType') == 'POST':
                                    ePayBillRecID = billRecType['EPayBillRecID']
                                    fees_response = provider.get_khales_fees(lang, ePayBillRecID, payAmts[0], provider_channel)
                                    if fees_response.get('Success'):
                                        feeInqRsType = fees_response.get('Success')
                                        success_response.update({'fees_response': suds_to_json(feeInqRsType)})
                                provider_response = {'Success': success_response}

                                provider_response_json = provider_response.get('Success')
                            else:
                                provider_response = bill_response

                        if provider_response.get('Success'):
                            # if not provider_response_json:
                                # provider_response_json = suds_to_json(provider_response.get('Success'))
                            commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                                domain=[('vendor', '=', provider_info.name.id), ('vendor_product_code', '=', provider_info.product_code)],
                                fields=['Amount_Range_From', 'Amount_Range_To', 'Extra_Fee_Amt', 'Extra_Fee_Prc']
                            )
                            extra_fees_amount = 0.0
                            for commission in commissions:
                                if commission['Amount_Range_From'] <= trans_amount \
                                        and commission['Amount_Range_To'] >= trans_amount:
                                    if commission['Extra_Fee_Amt'] > 0:
                                        extra_fees_amount = commission['Extra_Fee_Amt']
                                    elif commission['Extra_Fee_Prc'] > 0:
                                        extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                                    break
                            user_request.update(
                                {"provider_id": provider.id, "provider_response": provider_response_json,
                                 "trans_amount": trans_amount, "extra_fees_amount": extra_fees_amount,
                                 "extra_fees": commissions, "stage_id": 5})
                            request.env.cr.commit()
                            return valid_response(
                                {"message": _("Service Bill Inquiry request was submit successfully."),
                                 "request_number": user_request.name,
                                 "provider": provider.provider,
                                 "provider_response": provider_response_json,
                                 "extra_fees_amount": extra_fees_amount,
                                 # "extra_fees": commissions
                                 })
                        else:
                            error.update({provider.provider + "_response": provider_response or ''})
                    else:
                        error.update({provider_info.name.name + "_response": _("%s is not a provider for (%s) service") % (
                            provider_info.name.name, service.name)})

                user_request.update({
                    "provider_response": error or _("(%s) service has not any provider.") % (service.name),
                    "stage_id": 5
                })
                request.env.cr.commit()
                return invalid_response("Error", error or _("(%s) service has not any provider.") % (service.name), 400)

            elif request_data.get('request_type') == 'pay_service_bill':
                lang = request_data.get('lang')
                billingAcct = request_data.get('billingAcct')

                extraBillingAcctKeys = request_data.get('extraBillingAcctKeys')
                if extraBillingAcctKeys:
                    extraBillingAcctKeys = ast.literal_eval(extraBillingAcctKeys)

                notifyMobile = request_data.get('notifyMobile')
                billRefNumber = request_data.get('billRefNumber')
                billerId = request_data.get('billerId')
                pmtType = request_data.get('pmtType')

                trans_amount = request_data.get('trans_amount')
                curCode = request_data.get('currency_id')
                payAmts = request_data.get('payAmts')
                if payAmts:
                    payAmts = ast.literal_eval(payAmts)
                else:
                    payAmts = [{'Sequence':'1', 'AmtDue':trans_amount, 'CurCode':curCode}]
                pmtMethod = request_data.get('pmtMethod')

                ePayBillRecID = request_data.get('ePayBillRecID')
                pmtId = request_data.get('pmtId') or user_request.name
                feesAmt = request_data.get('feesAmt') or 0.00
                feesAmts = request_data.get('feesAmts')
                if feesAmts:
                    feesAmts = ast.literal_eval(feesAmts)
                else:
                    feesAmts = [{'Amt': feesAmt, 'CurCode': curCode}]
                pmtRefInfo = request_data.get('pmtRefInfo')

                providers_info = []
                '''
                provider_provider = request_data.get('provider')
                if provider_provider:
                    provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                    if provider:
                        service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                            ('product_tmpl_id', '=', service.product_tmpl_id.id),
                            ('name', '=', provider.related_partner.id)
                        ])
                        if service_providerinfo:
                            providers_info.append(service_providerinfo)
                if not provider_provider or len(providers_info) == 0:
                    providers_info = service.seller_ids
                '''
                providers_info.append(service_providerinfo)

                provider_response = {}
                provider_response_json = {}
                '''
                provider_fees_calculated_amount = 0.0
                provider_fees_actual_amount = 0.0
                merchant_cashback_amount = 0.0
                customer_cashback_amount = 0.0
                extra_fees_amount = 0.0
                '''
                error = {}
                for provider_info in providers_info:
                    biller_info_json_dict = json.loads(provider_info.biller_info, strict=False)
                    '''
                    # Get Extra Fees
                    commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                        domain=[('vendor', '=', provider_info.name.id),
                                ('vendor_product_code', '=', provider_info.product_code)],
                        fields=['Amount_Range_From', 'Amount_Range_To',
                                'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt',
                                'Mer_Comm_Full_Fix_Amt', 'Cust_Comm_Full_Fix_Amt',
                                'Bill_Merchant_Comm_Prc', 'Bill_Customer_Comm_Prc']
                    )
                    for commission in commissions:
                        if commission['Amount_Range_From'] <= machine_request.trans_amount \
                                and commission['Amount_Range_To'] >= machine_request.trans_amount:
                            if commission['Mer_Comm_Full_Fix_Amt'] > 0:
                                merchant_cashback_amount = commission['Mer_Comm_Full_Fix_Amt']
                                customer_cashback_amount = commission['Cust_Comm_Full_Fix_Amt']
                            elif commission['Bill_Merchant_Comm_Prc'] > 0:
                                merchant_cashback_amount = machine_request.trans_amount * commission[
                                    'Bill_Merchant_Comm_Prc'] / 100
                                customer_cashback_amount = machine_request.trans_amount * commission[
                                    'Bill_Customer_Comm_Prc'] / 100
                            if commission['Extra_Fee_Amt'] > 0:
                                extra_fees_amount = commission['Extra_Fee_Amt']
                            elif commission['Extra_Fee_Prc'] > 0:
                                extra_fees_amount = machine_request.trans_amount * commission['Extra_Fee_Prc'] / 100
                            if commission['Mer_Fee_Amt'] > 0:
                                provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                            elif commission['Mer_Fee_Prc'] > 0:
                                # Fees amount = FA + [Percentage * Payment Amount]
                                # Fees amount ====================> provider_fees_calculated_amount
                                # FA =============================> provider_fees_calculated_amount
                                # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                provider_fees_prc_calculated_amount = machine_request.trans_amount * commission['Mer_Fee_Prc'] / 100
                                if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                        and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                            elif provider_provider == 'khales':
                                provider_fees_calculated_amount = float(request_data.get('feesAmt'))
                            break
                    calculated_payment_amount = machine_request.trans_amount + provider_fees_calculated_amount + extra_fees_amount
                    mobile_wallet_balance = request.env.user.partner_id.wallet_balance
                    if mobile_wallet_balance < calculated_payment_amount:
                        error.update({"mobile_balance_not_enough":
                                                _("Mobile Wallet Balance (%s) less than the payment amount (%s)") % (mobile_wallet_balance,
                                                                                                                      calculated_payment_amount)})
                    '''

                    user_request.update({'provider_fees_calculated_amount': provider_fees_calculated_amount})
                    request.env.cr.commit()
                    provider = request.env['payment.acquirer'].sudo().search([("related_partner", "=", provider_info.name.id)])
                    if provider:
                        try:
                            provider_channel = False
                            machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                      ("type", "in", ("mobile", "internet"))], limit=1)
                            if machine_channels:
                                provider_channel = machine_channels[0]
                            if provider.provider == "fawry":
                                # Tamayoz TODO: Provider Server Timeout Handling
                                provider_response = provider.pay_fawry_bill(lang, provider_info.product_code,
                                                                            billingAcct, extraBillingAcctKeys,
                                                                            trans_amount, curCode, pmtMethod,
                                                                            notifyMobile, billRefNumber,
                                                                            billerId, pmtType, provider_channel)
                                if provider_response.get('Success'):
                                    provider_response_json = suds_to_json(provider_response.get('Success'))
                                    # Get Provider Fees
                                    provider_response_json_dict = json.loads(provider_response_json, strict=False)
                                    # provider_response_json_dict['PmtInfo']['CurAmt']['Amt'] == user_request.trans_amount
                                    provider_fees_actual_amount = provider_response_json_dict['PmtInfo']['FeesAmt']['Amt']
                                    user_request.update({'provider_fees_amount': provider_fees_actual_amount})
                                    request.env.cr.commit()
                                    # Get Provider Payment Trans ID
                                    for payment in provider_response_json_dict['PmtTransId']:
                                        if payment['PmtIdType'] == 'FCRN':
                                            provider_payment_trans_id = payment['PmtId']
                                            break

                            if provider.provider == "khales":
                                if not billerId:
                                    billerId = biller_info_json_dict.get('Code')
                                # Tamayoz TODO: Provider Server Timeout Handling
                                # Tamayoz TODO: Remove the next temporary line
                                pmtMethod = "CARD"  # TEMP CODE
                                provider_response = provider.pay_khales_bill(lang, billingAcct, billerId, ePayBillRecID,
                                                                             payAmts, pmtId, pmtType, feesAmts,
                                                                             billRefNumber, pmtMethod, pmtRefInfo,
                                                                             provider_channel)
                                if provider_response.get('Success'):
                                    provider_response_json = suds_to_json(provider_response.get('Success'))
                                    # Add required parameters for cancel payment scenario
                                    # parsing JSON string:
                                    provider_response_json_dict = json.loads(provider_response_json)
                                    pmtId = provider_response_json_dict['PmtRecAdviceStatus']['PmtTransId']['PmtId']
                                    # appending the data
                                    provider_response_json_dict.update({'billingAcct': billingAcct, 'billRefNumber': billRefNumber,
                                                                        'billerId': billerId, 'pmtType': pmtType, 'trans_amount': trans_amount,
                                                                        'curCode': curCode, 'pmtMethod': pmtMethod, 'ePayBillRecID': ePayBillRecID,
                                                                        'pmtId': pmtId, 'feesAmt': feesAmt, 'pmtRefInfo': pmtRefInfo})
                                    if payAmts:
                                        provider_response_json_dict.update({'payAmts': payAmts})
                                    if feesAmts:
                                        provider_response_json_dict.update({'feesAmts': feesAmts})
                                    # the result is a JSON string:
                                    provider_response_json = json.dumps(provider_response_json_dict)
                                    # Provider Fees
                                    provider_fees_actual_amount = float(feesAmt)
                                    user_request.update({'provider_fees_amount': provider_fees_actual_amount})
                                    request.env.cr.commit()
                                    # Provider Payment Trans ID
                                    provider_payment_trans_id = pmtId

                            if provider_response.get('Success'):
                                try:
                                    provider_invoice_id = False
                                    refund = False
                                    customer_invoice_id = False
                                    credit_note = False
                                    user_request_response = {"request_number": user_request.name,
                                                             "request_datetime": str(user_request.create_date + timedelta(hours=2)),
                                                             "provider": provider.provider,
                                                             "provider_response": provider_response_json
                                                             }

                                    provider_actual_amount = user_request.trans_amount + provider_fees_actual_amount
                                    customer_actual_amount = provider_actual_amount + extra_fees_amount

                                    # Deduct Transaction Amount from Mobile Wallet Balance
                                    wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                                    label = _('Pay Service Bill for %s service') % (service.name)
                                    partner_id_wallet_balance = request.env.user.partner_id.wallet_balance
                                    mobile_wallet_create = wallet_transaction_sudo.create(
                                        {'wallet_type': 'debit', 'partner_id': request.env.user.partner_id.id,
                                         'request_id': user_request.id,
                                         'reference': 'request',
                                         'label': label,
                                         'amount': customer_actual_amount, 'currency_id': user_request.currency_id.id,
                                         'wallet_balance_before': partner_id_wallet_balance,
                                         'wallet_balance_after': partner_id_wallet_balance - customer_actual_amount,
                                         'status': 'done'})
                                    request.env.cr.commit()

                                    request.env.user.partner_id.update(
                                        {'wallet_balance': request.env.user.partner_id.wallet_balance - customer_actual_amount})
                                    request.env.cr.commit()

                                    # Notify user
                                    irc_param = request.env['ir.config_parameter'].sudo()
                                    wallet_pay_service_bill_notify_mode = irc_param.get_param("smartpay_operations.wallet_pay_service_bill_notify_mode")
                                    if wallet_pay_service_bill_notify_mode == 'inbox':
                                        request.env['mail.thread'].sudo().message_notify(
                                            subject=label,
                                            body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                                                customer_actual_amount, _(user_request.currency_id.name)),
                                            partner_ids=[(4, request.env.user.partner_id.id)],
                                        )
                                    elif wallet_pay_service_bill_notify_mode == 'email':
                                        mobile_wallet_create.wallet_transaction_email_send()
                                    elif wallet_pay_service_bill_notify_mode == 'sms' and request.env.user.partner_id.mobile:
                                        mobile_wallet_create.sms_send_wallet_transaction(wallet_pay_service_bill_notify_mode,
                                                                                         'wallet_pay_service',
                                                                                         request.env.user.partner_id.mobile,
                                                                                         request.env.user.name, label,
                                                                                         '%s %s' % (customer_actual_amount,
                                                                                                    _(user_request.currency_id.name)),
                                                                                         request.env.user.partner_id.country_id.phone_code or '2')

                                    payment_info = {"service": service.name, "provider": provider.provider,
                                                    "request_number": user_request.name,
                                                    "request_datetime": user_request.create_date + timedelta(hours=2),
                                                    "label": biller_info_json_dict.get("BillTypeAcctLabel"),
                                                    "billing_acct": billingAcct, "ref_number": provider_payment_trans_id,
                                                    "amount": trans_amount,
                                                    "fees": (provider_fees_actual_amount + extra_fees_amount),
                                                    "total": customer_actual_amount}

                                    user_request.update(
                                        {'extra_fees_amount': extra_fees_amount,
                                         'wallet_transaction_id': mobile_wallet_create.id,
                                         'trans_date': date.today(),
                                         'provider_id': provider.id,
                                         'provider_response': provider_response_json, "stage_id": 5})
                                    request.env.cr.commit()

                                    # VouchPIN Decryption if exist
                                    if provider_response_json_dict.get('VouchInfo'):
                                        decrypted_bytes = bytes(provider_response_json_dict['VouchInfo']['VouchPIN'],
                                                                encoding='utf-8')
                                        # text = base64.decodestring(decrypted_bytes) #
                                        text = base64.b64decode(decrypted_bytes)  #
                                        cipher = DES3.new(SECRET_KEY, DES3.MODE_ECB)
                                        VouchPIN = cipher.decrypt(text)
                                        VouchPIN = UNPAD(VouchPIN)
                                        VouchPIN = VouchPIN.decode('utf-8')  # unpad and decode bytes to str
                                        user_request_response.update({'vouch_pin': VouchPIN})
                                        payment_info.update({"vouch_pin": VouchPIN,
                                                             "vouch_sn": provider_response_json_dict['VouchInfo']['VouchSN']})

                                    # Wallet Transaction Info with payment info
                                    mobile_wallet_create.update({"wallet_transaction_info": json.dumps({"payment_info": payment_info}, default=default)})
                                    request.env.cr.commit()

                                    '''
                                    # Create Vendor (Provider) Invoices
                                    provider_invoice_ids = ()
                                    # 1- Create Vendor bill
                                    provider_journal_id = request.env['account.journal'].sudo().search([('type', '=', 'purchase'),
                                                                                              ('company_id', '=', request.env.user.company_id.id)], limit=1)
                                    name = provider.provider + ': [' + provider_info.product_code + '] ' + provider_info.product_name
                                    provider_invoice_vals = user_request.with_context(name=name,
                                                                                      provider_payment_trans_id=provider_payment_trans_id,
                                                                                      journal_id=provider_journal_id.id,
                                                                                      invoice_date=date.today(),
                                                                                      invoice_type='in_invoice',
                                                                                      partner_id=provider_info.name.id)._prepare_invoice()
                                    provider_invoice_id = request.env['account.invoice'].sudo().create(provider_invoice_vals)
                                    invoice_line = provider_invoice_id._prepare_invoice_line_from_request(request=user_request,
                                                                                                          name=name,
                                                                                                          qty=1,
                                                                                                          price_unit=provider_actual_amount)
                                    new_line = request.env['account.invoice.line'].sudo().new(invoice_line)
                                    new_line._set_additional_fields(provider_invoice_id)
                                    provider_invoice_id.invoice_line_ids += new_line
                                    provider_invoice_id.action_invoice_open()
                                    provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                    provider_invoice_id.pay_and_reconcile(request.env['account.journal'].sudo().search(
                                        [('type', '=', 'cash'),
                                         ('company_id', '=', request.env.user.company_id.id),
                                         ('provider_id', '=', provider.id)], limit=1),
                                        provider_actual_amount)
                                    request.env.cr.commit()
                                    # 2- Create Vendor Refund with commision amount
                                    if merchant_cashback_amount > 0:
                                        refund = request.env['account.invoice.refund'].with_context(
                                            active_ids=provider_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': name,
                                            'date': provider_invoice_id.date_invoice,
                                        })
                                        result = refund.invoice_refund()
                                        refund_id = result.get('domain')[1][2]
                                        refund = request.env['account.invoice'].sudo().browse(refund_id)
                                        refund.update({'reference': provider_payment_trans_id, 'request_id': user_request.id})
                                        refund_line = refund.invoice_line_ids[0]
                                        refund_line.update({'price_unit': merchant_cashback_amount, 'request_id': user_request.id})
                                        refund.refresh()
                                        refund.action_invoice_open()
                                        provider_invoice_ids += (tuple(refund.ids),)
                                    user_request.update({'provider_invoice_ids': provider_invoice_ids})
                                    request.env.cr.commit()

                                    # Create Customer Invoices
                                    customer_invoice_ids = ()
                                    # 1- Create Customer Invoice
                                    customer_journal_id = request.env['account.journal'].sudo().search([('type', '=', 'sale'),
                                                                                              ('company_id', '=', request.env.user.company_id.id)], limit=1)
                                    customer_invoice_vals = user_request.with_context(name=provider_payment_trans_id,
                                                                                      journal_id=customer_journal_id.id,
                                                                                      invoice_date=date.today(),
                                                                                      invoice_type='out_invoice',
                                                                                      partner_id=request.env.user.partner_id.id)._prepare_invoice()
                                    customer_invoice_id = request.env['account.invoice'].sudo().create(customer_invoice_vals)
                                    user_request.invoice_line_create(invoice_id=customer_invoice_id.id, name=name,
                                                                        qty=1, price_unit=customer_actual_amount)
                                    customer_invoice_id.action_invoice_open()
                                    customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                    # Auto Reconcile customer invoice with prepaid wallet recharge payments and previous cashback credit note
                                    domain = [('account_id', '=', customer_invoice_id.account_id.id),
                                              ('partner_id', '=',
                                               customer_invoice_id.env['res.partner']._find_accounting_partner(
                                                   customer_invoice_id.partner_id).id),
                                              ('reconciled', '=', False),
                                              '|',
                                              '&', ('amount_residual_currency', '!=', 0.0), ('currency_id', '!=', None),
                                              '&', ('amount_residual_currency', '=', 0.0), '&', ('currency_id', '=', None),
                                              ('amount_residual', '!=', 0.0)]
                                    domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                                    lines = customer_invoice_id.env['account.move.line'].sudo().search(domain)
                                    for line in lines:
                                        # get the outstanding residual value in invoice currency
                                        if line.currency_id and line.currency_id == customer_invoice_id.currency_id:
                                            amount_residual_currency = abs(line.amount_residual_currency)
                                        else:
                                            currency = line.company_id.currency_id
                                            amount_residual_currency = currency._convert(abs(line.amount_residual),
                                                                                         customer_invoice_id.currency_id,
                                                                                         customer_invoice_id.company_id,
                                                                                         line.date or fields.Date.today())
                                        if float_is_zero(amount_residual_currency,
                                                         precision_rounding=customer_invoice_id.currency_id.rounding):
                                            continue

                                        customer_invoice_id.assign_outstanding_credit(line.id)
                                        if customer_invoice_id.state == 'paid':
                                            break
                                    request.env.cr.commit()

                                    # 2- Create Customer Credit Note with commision amount for only mobile users have commission
                                    if request.env.user.commission and customer_cashback_amount > 0:
                                        credit_note = request.env['account.invoice.refund'].with_context(
                                            active_ids=customer_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': provider_payment_trans_id,
                                            'date': customer_invoice_id.date_invoice,
                                        })
                                        result = credit_note.invoice_refund()
                                        credit_note_id = result.get('domain')[1][2]
                                        credit_note = request.env['account.invoice'].sudo().browse(credit_note_id)
                                        credit_note.update({'request_id': user_request.id})
                                        credit_note_line = credit_note.invoice_line_ids[0]
                                        credit_note_line.update({'price_unit': customer_cashback_amount, 'request_id': user_request.id})
                                        credit_note.refresh()
                                        """  Don't validate the customer credit note until the vendor refund reconciliation
                                        After vendor refund reconciliation, validate the customer credit note with
                                        the net amount of vendor refund sent in provider cashback statement then
                                        increase the customer wallet with the same net amount. """
                                        # credit_note.action_invoice_open()
                                        customer_invoice_ids += (tuple(credit_note.ids),)
                                    user_request.update({'customer_invoice_ids': customer_invoice_ids})
                                    request.env.cr.commit()
                                    '''

                                    if provider.provider == "khales":
                                        # Add required parameters for cancel payment scenario
                                        user_request_response.update({'billingAcct': billingAcct, 'billRefNumber': billRefNumber,
                                                                      'billerId': billerId, 'pmtType': pmtType, 'trans_amount': trans_amount,
                                                                      'curCode': curCode, 'pmtMethod': pmtMethod, 'ePayBillRecID': ePayBillRecID,
                                                                      'pmtId': pmtId, 'feesAmt': feesAmt, 'pmtRefInfo': pmtRefInfo})
                                        if payAmts:
                                            user_request_response.update({'payAmts': payAmts})
                                        if feesAmts:
                                            user_request_response.update({'feesAmts': feesAmts})
                                    user_request_response.update({"message": _("Pay Service Bill request was submit successfully with amount %s %s. Your Machine Wallet Balance is %s %s")
                                                                        % (customer_actual_amount,
                                                                           user_request.currency_id.name,
                                                                           request.env.user.partner_id.wallet_balance,
                                                                           user_request.currency_id.name)
                                                             })
                                    return valid_response(user_request_response)
                                except Exception as e:
                                    try:
                                        _logger.error("%s", e)
                                        user_request_update = {'extra_fees_amount': extra_fees_amount,
                                                               'trans_date': date.today(),
                                                               'provider_id': provider.id,
                                                               'provider_response': provider_response_json,"stage_id": 5,
                                                               'description': _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e)}
                                        if mobile_wallet_create:
                                            user_request_update.update({'wallet_transaction_id': mobile_wallet_create.id})
                                        provider_invoice_ids = ()
                                        if provider_invoice_id or refund:
                                            if provider_invoice_id:
                                                provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                            if refund:
                                                provider_invoice_ids += (tuple(refund.ids),)
                                            user_request_update.update({'provider_invoice_ids': provider_invoice_ids})
                                        customer_invoice_ids = ()
                                        if customer_invoice_id or credit_note:
                                            if customer_invoice_id:
                                                customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                            if credit_note:
                                                customer_invoice_ids += (tuple(credit_note.ids),)
                                            user_request_update.update({'customer_invoice_ids': customer_invoice_ids})
                                        user_request.update(user_request_update)
                                        request.env.cr.commit()
                                    except Exception as e1:
                                        _logger.error("%s", e1)
                                        if user_request and not user_request.description:
                                            user_request.update({'description': _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e)})
                                            request.env.cr.commit()

                                    return invalid_response(user_request_response, _("After the Pay Service Request submit successfuly with provider, Error is occur:") + " ==> " + str(e),
                                                            500)
                            else:
                                error.update({provider.provider + "_response": provider_response or ''})
                        except Exception as e2:
                            _logger.error("%s", e2)
                            if user_request and not user_request.get('description'):
                                user_request.update({'description': _("Error is occur:") + " ==> " + str(e2)})
                                request.env.cr.commit()
                            return invalid_response("Error", _("Error is occur:") + " ==> " + str(e), 500)
                    else:
                        error.update({provider_info.name.name + "_response": _("%s is not a provider for (%s) service") % (
                            provider_info.name.name, service.name)})

                user_request.update({
                    'provider_response': error or _('(%s) service has not any provider.') % (service.name),
                    'stage_id': 5
                })
                request.env.cr.commit()
                return invalid_response("Error", error or _("(%s) service has not any provider.") % (service.name), 400)
            else:
                return valid_response({"message": _("Your request was submit successfully."),
                                       "request_number": user_request.name
                                       })

        @validate_token
        @http.route('/api/cancelRequest', type="http", auth="none", methods=["PUT"], csrf=False)
        def cancelRequest(self, **request_data):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Cancel Mobile Request API")
            user_request = False
            request_number = request_data.get('request_number')
            if request_number:
                user_request = request.env['smartpay_operations.request'].sudo().search([('name', '=', request_number)], limit=1)
            else: # elif request_data.get('provider') == 'khales':
                # if not request_data.get('ePayBillRecID'):
                    # return invalid_response("ePayBillRecID_request_number_not_found", _("missing Request Number or ePay Bill Rec ID in request data"), 400)
                user_request = request.env['smartpay_operations.request'].sudo().search([('request_type', '=', 'pay_service_bill'),
                                                                                         ('provider_response', 'like', request_data.get('ePayBillRecID'))],
                                                                                        limit=1)
                # _logger.info("@@@@@@@@@@@@@@@@@@@ " + '"EPayBillRecID": "%s"' % (request_data.get('ePayBillRecID')))
            if user_request:
                request_number = user_request.name
                try:
                    service = user_request.product_id
                    provider = user_request.provider_id

                    service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                        ('product_tmpl_id', '=', service.product_tmpl_id.id),
                        ('name', '=', provider.related_partner.id)
                    ])
                    biller_info_json_dict = json.loads(service_providerinfo.biller_info, strict=False)
                    isAllowCancel = biller_info_json_dict.get('IsAllowCancel', False)

                    if user_request.request_type == 'pay_service_bill' and user_request.stage_id.id == 5 and isAllowCancel:
                        lang = 'ar-eg'
                        partner = user_request.partner_id
                        # trans_date = user_request.trans_date
                        trans_amount = user_request.trans_amount
                        provider_fees_amount = user_request.provider_fees_amount
                        extra_fees_amount = user_request.extra_fees_amount
                        currency = user_request.currency_id

                        provider_pay_response = user_request.provider_response
                        provider_response_json = {}
                        provider_response_json['provider_pay_response'] = provider_pay_response
                        provider_pay_response_json = json.loads(provider_pay_response)
                        billingAcct = request_data.get('billingAcct') or provider_pay_response_json.get('billingAcct')
                        billRefNumber = request_data.get('billRefNumber') or provider_pay_response_json.get('billRefNumber')
                        billerId = request_data.get('billerId') or provider_pay_response_json.get('billerId')
                        pmtType = request_data.get('pmtType') or provider_pay_response_json.get('pmtType')
                        # trans_amount = request_data.get('trans_amount') or provider_pay_response_json.get('trans_amount')
                        curCode = request_data.get('currency_id') or provider_pay_response_json.get('curCode')
                        payAmts = request_data.get('payAmts')
                        if payAmts:
                            payAmts = ast.literal_eval(payAmts)
                        else:
                            payAmts = [{'Sequence': '1', 'AmtDue': trans_amount, 'CurCode': curCode}]
                        pmtMethod = request_data.get('pmtMethod') or provider_pay_response_json.get('pmtMethod')
                        ePayBillRecID = request_data.get('ePayBillRecID') or provider_pay_response_json.get('ePayBillRecID')
                        pmtId = request_data.get('pmtId') or provider_pay_response_json.get('pmtId')
                        feesAmt = request_data.get('feesAmt') or provider_pay_response_json.get('feesAmt')
                        feesAmts = request_data.get('feesAmts')
                        if feesAmts:
                            feesAmts = ast.literal_eval(feesAmts)
                        else:
                            feesAmts = [{'Amt': feesAmt, 'CurCode': curCode}]
                        pmtRefInfo = request_data.get('pmtRefInfo') or provider_pay_response_json.get('pmtRefInfo')
                        cancelReason = request_data.get('cancelReason') or '001'

                        error = {}

                        provider_channel = False
                        machine_channels = request.env['payment.acquirer.channel'].sudo().search([("acquirer_id", "=", provider.id),
                                                                                                  ("type", "in", ("machine", "internet"))], limit=1)
                        if machine_channels:
                            provider_channel = machine_channels[0]
                        if provider.provider == "khales":
                            provider_cancel_response = provider.cancel_khales_payment(lang, billingAcct, billerId, ePayBillRecID,
                                                                                      payAmts, pmtId, pmtType, feesAmts,
                                                                                      billRefNumber, pmtMethod, pmtRefInfo,
                                                                                      cancelReason,provider_channel)
                        if provider_cancel_response.get('Success'):
                            try:
                                provider_cancel_response_json = suds_to_json(provider_cancel_response.get('Success'))
                                provider_response_json['provider_cancel_response'] = provider_cancel_response_json

                                provider_actual_amount = trans_amount + provider_fees_amount
                                customer_actual_amount = provider_actual_amount + extra_fees_amount

                                # Refund Payment Amount to Customer Wallet Balance
                                wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                                label = _('Cancel Service Payment for %s service') % (service.name)
                                partner_id_wallet_balance = partner.wallet_balance
                                customer_wallet_create = wallet_transaction_sudo.create({'wallet_type': 'credit', 'partner_id': partner.id,
                                                                                         'request_id': user_request.id, 'reference': 'request',
                                                                                         'label': label, 'amount': customer_actual_amount,
                                                                                         'currency_id': currency.id,
                                                                                         'wallet_balance_before': partner_id_wallet_balance,
                                                                                         'wallet_balance_after': partner_id_wallet_balance + customer_actual_amount,
                                                                                         'status': 'done'})
                                request.env.cr.commit()

                                partner.update({'wallet_balance': partner.wallet_balance + customer_actual_amount})
                                request.env.cr.commit()

                                # Notify customer
                                irc_param = request.env['ir.config_parameter'].sudo()
                                wallet_canel_service_payment_notify_mode = irc_param.get_param("smartpay_operations.wallet_pay_service_bill_notify_mode")
                                if wallet_canel_service_payment_notify_mode == 'inbox':
                                    request.env['mail.thread'].sudo().message_notify(subject=label,
                                                                                  body=_('<p>%s %s successfully Added to your wallet.</p>') % (
                                                                                      customer_actual_amount, _(currency.name)),
                                                                                  partner_ids=[(4, partner.id)],
                                    )
                                elif wallet_canel_service_payment_notify_mode == 'email':
                                    customer_wallet_create.wallet_transaction_email_send()
                                elif wallet_canel_service_payment_notify_mode == 'sms' and partner.mobile:
                                    customer_wallet_create.sms_send_wallet_transaction(wallet_canel_service_payment_notify_mode, 'wallet_cancel_service_payment',
                                                                                       partner.mobile, partner.name, # request.env.user.name,
                                                                                       label, '%s %s' % (customer_actual_amount, _(currency.name)),
                                                                                       partner.country_id.phone_code or '2')

                                # Refund provider bill for reconciliation purpose
                                # Cancel provider refund (cashback), customer invoice and customer credit note (cashback)
                                refund = False
                                provider_invoice_ids = ()
                                for provider_invoice_id in user_request.provider_invoice_ids:
                                    provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                    # Refund Provider Bill
                                    if provider_invoice_id.type == 'in_invoice' and len(user_request.provider_invoice_ids) == 2:
                                        refund = request.env['account.invoice.refund'].with_context(
                                            active_ids=provider_invoice_id.ids).sudo().create({
                                            'filter_refund': 'refund',
                                            'description': provider_invoice_id.name,
                                            'date': provider_invoice_id.date_invoice,
                                        })
                                        result = refund.invoice_refund()
                                        refund_id = result.get('domain')[1][2]
                                        refund = request.env['account.invoice'].sudo().browse(refund_id)
                                        refund.update({'reference': pmtId, 'request_id': user_request.id})
                                        refund_line = refund.invoice_line_ids[0]
                                        refund_line.update({'request_id': user_request.id})
                                        refund.refresh()
                                        refund.action_invoice_open()
                                        refund.pay_and_reconcile(request.env['account.journal'].sudo().search(
                                            [('type', '=', 'cash'),
                                             ('company_id', '=', request.env.user.company_id.id),
                                             ('provider_id', '=', provider.id)], limit=1),
                                            provider_actual_amount)
                                        provider_invoice_ids += (tuple(refund.ids),)
                                    # Cancel provider refund (cashback)
                                    if provider_invoice_id.type == 'in_refund':
                                        if provider_invoice_id.state in ('in_payment', 'paid'):
                                            provider_invoice_id.action_invoice_re_open()
                                        provider_invoice_id.action_invoice_cancel()

                                user_request.update({'provider_invoice_ids': provider_invoice_ids})
                                request.env.cr.commit()

                                # customer_invoice_ids = ()
                                for customer_invoice_id in user_request.customer_invoice_ids:
                                    # customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                    # Cancel Customer Invoice and Customer Credit Note (cashback)
                                    if len(user_request.customer_invoice_ids) == 2:
                                        if customer_invoice_id.state in ('in_payment', 'paid'):
                                            customer_invoice_id.action_invoice_re_open()
                                        customer_invoice_id.action_invoice_cancel()

                                # user_request.update({'customer_invoice_ids': customer_invoice_ids})
                                # request.env.cr.commit()

                                user_request.update(
                                    {'wallet_transaction_id': customer_wallet_create.id,
                                     'provider_response': provider_response_json , # "stage_id": 4
                                     'description': _('Cancel Service Payment request (%s) was submit successfully @ %s') % (user_request.name, str(date_time.now() + timedelta(hours=2)))
                                     })
                                request.env.cr.commit()

                                return valid_response({"request_number": user_request.name, "provider": provider.provider,
                                                       "provider_response": provider_response_json,
                                                       "message":
                                                           _("Cancel Service Payment request (%s) was submit successfully. Your Machine Wallet Balance is %s %s")
                                                                  % (user_request.name,
                                                                     partner.wallet_balance,
                                                                     currency.name)
                                                       })
                            except Exception as e:
                                try:
                                    _logger.error("%s", e)
                                    user_request_update = {'provider_response': provider_response_json, # "stage_id": 4,
                                                              'description': _(
                                                                  "After the Cancel Service Payment Request submit successfuly with provider, Error is occur:") + " ==> " + str(
                                                                  e)}
                                    if customer_wallet_create:
                                        user_request_update.update({'wallet_transaction_id': customer_wallet_create.id})
                                    provider_invoice_ids = ()
                                    if provider_invoice_id or refund:
                                        if provider_invoice_id:
                                            provider_invoice_ids += (tuple(provider_invoice_id.ids),)
                                        if refund:
                                            provider_invoice_ids += (tuple(refund.ids),)
                                        user_request_update.update({'provider_invoice_ids': provider_invoice_ids})
                                    '''
                                    customer_invoice_ids = ()
                                    if customer_invoice_id or credit_note:
                                        if customer_invoice_id:
                                            customer_invoice_ids += (tuple(customer_invoice_id.ids),)
                                        if credit_note:
                                            customer_invoice_ids += (tuple(credit_note.ids),)
                                        user_request_update.update({'customer_invoice_ids': customer_invoice_ids})
                                    '''
                                    user_request.update(user_request_update)
                                    request.env.cr.commit()
                                except Exception as e1:
                                    _logger.error("%s", e1)
                                    if user_request and not user_request.description:
                                        user_request.update({'description': _(
                                                                  "After the Cancel Service Payment Request submit successfuly with provider, Error is occur:") + " ==> " + str(
                                                                  e)})

                                return invalid_response({"request_number": user_request.name, "provider": provider.provider,
                                                         "provider_response": provider_response_json,
                                                         "message":
                                                           _("Cancel Service Payment request (%s) was submit successfully. Your Machine Wallet Balance is %s %s")
                                                                  % (user_request.name,
                                                                     currency.name,
                                                                     partner.wallet_balance,
                                                                     currency.name)
                                                         }, _(
                                    "After the Cancel Service Payment Request submit successfuly with provider, Error is occur:") + " ==> " + str(e), 500)
                        else:
                            provider_response_json["provider_cancel_response"] = provider_cancel_response
                            error.update({provider.provider + "_response": provider_response_json or ''})

                        user_request.update({
                            'provider_response': error,
                            # 'stage_id': 5
                        })
                        return invalid_response("Error", error, 400)

                    elif user_request.sudo().write({'stage_id': 4}):
                        return valid_response(_("Cancel REQ Number (%s) successfully!") % (request_number))
                except Exception as ex:
                    _logger.error("%s", ex)
            else:
                return invalid_response("request_not_found", _("Request does not exist!"), 400)

            return invalid_response("request_not_canceled", _("Could not cancel REQ Number (%s)") % (request_number), 400)

        @validate_token
        @http.route('/api/getRequest', type="http", auth="none", methods=["POST"], csrf=False)
        def getRequest(self, **payload):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Get Requests API")
            domain = payload.get("domain")
            if not domain or "name" not in domain:
                return invalid_response("request_number_missing", _("REQ Number is missing. Please Send REQ Number"), 400)
            return restful_main().get('smartpay_operations.request', None, **payload)

        @validate_token
        @http.route('/api/getRequests', type="http", auth="none", methods=["POST"], csrf=False)
        def getRequests(self, **payload):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Get Requests API")
            domain = []
            if payload.get("domain", None):
                domain = ast.literal_eval(payload.get("domain"))
            domain += [("partner_id.id", "=", request.env.user.partner_id.id)]
            if not any(item[0] == 'create_date' for item in domain):
                create_date = (datetime.date.today()+datetime.timedelta(days=-30)).strftime('%Y-%m-%d')
                domain += [("create_date", ">=", create_date)]
            payload.update({
                'domain': str(domain)
            })
            return restful_main().get('smartpay_operations.request', None, **payload)

        @validate_token
        @http.route('/api/getServiceFees', type="http", auth="none", methods=["POST"], csrf=False)
        def getServiceFees(self, **request_data):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Get Service Fees API")

            if not request_data.get('product_id'):
                return invalid_response("service_not_found", _("missing service in request data"), 400)
            else:
                service = request.env["product.product"].sudo().search(
                    [("id", "=", request_data.get('product_id')), ("type", "=", "service")],
                    order="id DESC", limit=1)
                if not service:
                    return invalid_response("service", _("service invalid"), 400)

            # Provider is mandatory because the service fee is different per provider.
            # So the user must send provider that own the bill inquiry request for prevent pay bill
            # with total amount different of total amount in bill inquiry
            provider_provider = request_data.get('provider')
            if provider_provider:
                provider = request.env['payment.acquirer'].sudo().search([("provider", "=", provider_provider)])
                if provider:
                    service_providerinfo = request.env['product.supplierinfo'].sudo().search([
                        ('product_tmpl_id', '=', service.product_tmpl_id.id),
                        ('name', '=', provider.related_partner.id)
                    ])
                    if not service_providerinfo:
                        return invalid_response(
                            "Incompatible_provider_service", _("%s is not a provider for (%s) service") % (
                                provider_provider, service.name), 400)
            else:
                return invalid_response("provider_not_found",
                                        _("missing provider in request data"), 400)

            trans_amount = float(request_data.get('trans_amount'))
            if not trans_amount:
                return invalid_response("amount_not_found",
                                        _("missing bill amount in request data"), 400)
            else:
                # Calculate Fees
                provider_fees_calculated_amount = 0.0
                extra_fees_amount = 0.0
                if provider_provider != 'khales':
                    commissions = request.env['product.supplierinfo.commission'].sudo().search_read(
                        domain=[('vendor', '=', service_providerinfo.name.id),
                                ('vendor_product_code', '=', service_providerinfo.product_code)],
                        fields=['Amount_Range_From', 'Amount_Range_To',
                                'Extra_Fee_Amt', 'Extra_Fee_Prc',
                                'Mer_Fee_Amt', 'Mer_Fee_Prc', 'Mer_Fee_Prc_MinAmt', 'Mer_Fee_Prc_MaxAmt']
                    )
                    for commission in commissions:
                        if commission['Amount_Range_From'] <= trans_amount \
                                and commission['Amount_Range_To'] >= trans_amount:
                            if commission['Extra_Fee_Amt'] > 0:
                                extra_fees_amount = commission['Extra_Fee_Amt']
                            elif commission['Extra_Fee_Prc'] > 0:
                                extra_fees_amount = trans_amount * commission['Extra_Fee_Prc'] / 100
                            if commission['Mer_Fee_Amt'] > 0:
                                provider_fees_calculated_amount = commission['Mer_Fee_Amt']
                            elif commission['Mer_Fee_Prc'] > 0:
                                # Fees amount = FA + [Percentage * Payment Amount]
                                # Fees amount ====================> provider_fees_calculated_amount
                                # FA =============================> provider_fees_calculated_amount
                                # [Percentage * Payment Amount] ==> provider_fees_prc_calculated_amount
                                provider_fees_prc_calculated_amount = trans_amount * commission[
                                    'Mer_Fee_Prc'] / 100
                                if provider_fees_prc_calculated_amount < commission['Mer_Fee_Prc_MinAmt']:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MinAmt']
                                elif provider_fees_prc_calculated_amount > commission['Mer_Fee_Prc_MaxAmt'] \
                                        and commission['Mer_Fee_Prc_MaxAmt'] > 0:
                                    provider_fees_prc_calculated_amount = commission['Mer_Fee_Prc_MaxAmt']
                                provider_fees_calculated_amount += provider_fees_prc_calculated_amount
                            break
                # if provider_fees_calculated_amount == 0 and provider_provider == 'khales':
                else:
                    if not request_data.get('ePayBillRecID'):
                        return invalid_response("ePayBillRecID_not_found",
                                                _("missing ePayBillRecID in request data"), 400)
                    if not request_data.get('currency_id'):
                        return invalid_response("currency_not_found", _("missing currency in request data"), 400)

                    provider_channel = False
                    provider_channels = request.env['payment.acquirer.channel'].sudo().search(
                        [("acquirer_id", "=", provider.id)], limit=1)
                    if provider_channels:
                        provider_channel = provider_channels[0]

                    curCode = request_data.get('currency_id')
                    payAmts = request_data.get('payAmts')
                    if payAmts:
                        payAmts = ast.literal_eval(payAmts)
                        payAmtTemp = trans_amount
                        for payAmt in payAmts:
                            payAmtTemp -= float(payAmt.get('AmtDue'))
                        if payAmtTemp != 0:
                            return invalid_response("payAmts_not_match",
                                                    _("The sum of payAmts must be equals trans_amount"), 400)
                    else:
                        payAmts = [{'Sequence': '1', 'AmtDue': trans_amount, 'CurCode': curCode}]

                    fees_response = provider.get_khales_fees('', request_data.get('ePayBillRecID'), payAmts,
                                                             provider_channel)
                    if fees_response.get('Success'):
                        feeInqRsType = fees_response.get('Success')
                        provider_fees_calculated_amount = float(feeInqRsType['FeesAmt']['Amt'])

                calculated_payment_amount = trans_amount + provider_fees_calculated_amount + extra_fees_amount
                return valid_response(
                    {"message": _("Get Service Fees request was submit successfully."),
                     "provider": provider.provider,
                     "provider_service_code": service_providerinfo.product_code,
                     "provider_service_name": service_providerinfo.product_name,
                     "trans_amount": trans_amount,
                     "provider_fees_amount": provider_fees_calculated_amount,
                     "extra_fees_amount": extra_fees_amount
                     })

        @validate_token
        @http.route('/api/getWalletBalance', type="http", auth="none", methods=["POST"], csrf=False)
        def getWalletBalance(self, **payload):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Get Wallet Balance API")
            return restful_main().get('res.partner', request.env.user.partner_id.id, **payload)

        @validate_token
        @http.route('/api/getWalletTrans', type="http", auth="none", methods=["POST"], csrf=False)
        def getWalletTrans(self, **payload):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Get Wallet Transactions API")
            domain = []
            if payload.get("domain", None):
                domain = ast.literal_eval(payload.get("domain"))
            domain += [("partner_id.id", "=", request.env.user.partner_id.id)]
            if not any(item[0] == 'create_date' for item in domain):
                create_date = (datetime.date.today()+datetime.timedelta(days=-30)).strftime('%Y-%m-%d')
                domain += [("create_date", ">=", create_date)]
            payload.update({
                'domain': str(domain)
            })
            return restful_main().get('website.wallet.transaction', None, **payload)

        @validate_token
        @validate_machine
        @http.route('/api/rechargeMobileWallet', type="http", auth="none", methods=["POST"], csrf=False)
        def rechargeMobileWallet(self, **request_data):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Recharge Mobile Wallet Request API")
            if not request_data.get('request_number'):
                if request_data.get('transfer_to') and request_data.get('trans_amount'):
                    # current_user = request.env.user
                    # current_user_access_token = request.httprequest.headers.get("access_token")
                    # current_user_machine_serial = request.httprequest.headers.get("machine_serial")
                    # Create Recharge Mobile Wallet Request
                    transfer_to_user = request.env['res.users'].sudo().search(['|',
                                                                               ('login', '=', request_data.get('transfer_to')),
                                                                               ('ref', '=', request_data.get('transfer_to'))], limit=1)[0]
                    if not transfer_to_user:
                        return invalid_response("request_code_invalid", _("invalid transfer user in request data"), 400)
                    access_token = (
                        request.env["api.access_token"]
                            .sudo()
                            .search([("user_id", "=", transfer_to_user.id)], order="id DESC", limit=1)
                    )
                    if access_token:
                        access_token = access_token[0]
                        if access_token.has_expired():
                            return invalid_response("token_expired", _("transfer to user token expired"), 400)
                    else:
                        return invalid_response("account_deactivate", _("transfer to user account is deactivated"), 400)

                    base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    headers = {
                        'content-type': 'application/x-www-form-urlencoded',
                        'charset': 'utf-8',
                        'access_token': access_token.token
                    }
                    data = {
                        'request_type': 'recharge_wallet',
                        'trans_amount': request_data.get('trans_amount')
                    }

                    res = requests.post('{}/api/create_mobile_request'.format(base_url), headers=headers, data=data)
                    content = json.loads(res.content.decode('utf-8'))
                    # res = self.create_mobile_request(**data)
                    _logger.info("@@@@@@@@@@@@@@@@@@@ Recharge Mobile Wallet Response: " + str(content))
                    if content.get('data'):
                        request_number = content.get('data').get('request_number') #json.loads(res.response[0].decode('utf-8')).get('request_number')
                        if not request_number:
                            return res
                        request_data.update({'request_number': request_number})
                        request.env.cr.commit()
                    else:
                        return res
                    '''
                    request.httprequest.headers = {
                        'content-type': 'application/x-www-form-urlencoded',
                        'charset': 'utf-8',
                        'access_token': current_user_access_token,
                        'access_token': current_user_machine_serial
                    }
                    request.session.uid = current_user.id
                    request.uid = current_user.id
                    '''
                else:
                    return invalid_response("request_code_missing", _("missing request number in request data"), 400)
            user_request = request.env['smartpay_operations.request'].sudo().search(
                [('name', '=', request_data.get('request_number')), ('request_type', '=', "recharge_wallet")], limit=1)
            if user_request:
                if user_request.stage_id.id != 1:
                    return invalid_response("request_not_found",
                                            _("REQ Number (%s) invalid!") % (request_data.get('request_number')), 400)
                if request.env.user.partner_id.wallet_balance < user_request.trans_amount:
                    return invalid_response("machine_balance_not_enough",
                                            _("Machine Wallet Balance less than the request amount"), 400)

                # Transfer Balance from Machine Wallet to Mobile Wallet
                wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                label = _('Transfer wallet balance from %s') % (request.env.user.partner_id.name)
                partner_id_wallet_balance = user_request.partner_id.wallet_balance
                mobile_wallet_create = wallet_transaction_sudo.create(
                    {'wallet_type': 'credit', 'partner_id': user_request.partner_id.id, 'request_id': user_request.id,
                     'reference': 'request', 'label': label,
                     'amount': user_request.trans_amount, 'currency_id': user_request.currency_id.id,
                     'wallet_balance_before': partner_id_wallet_balance,
                     'wallet_balance_after': partner_id_wallet_balance + user_request.trans_amount,
                     'status': 'done'})
                request.env.cr.commit()

                user_request.partner_id.update(
                    {'wallet_balance': user_request.partner_id.wallet_balance + user_request.trans_amount})
                request.env.cr.commit()

                # Notify Mobile User
                irc_param = request.env['ir.config_parameter'].sudo()
                wallet_transfer_balance_notify_mode = irc_param.get_param("smartpay_operations.wallet_transfer_balance_notify_mode")
                if wallet_transfer_balance_notify_mode == 'inbox':
                    request.env['mail.thread'].sudo().message_notify(
                        subject=label,
                        body=_('<p>%s %s successfully added to your wallet.</p>') % (
                            user_request.trans_amount, _(user_request.currency_id.name)),
                        partner_ids=[(4, user_request.partner_id.id)],
                    )
                elif wallet_transfer_balance_notify_mode == 'email':
                    mobile_wallet_create.wallet_transaction_email_send()
                elif wallet_transfer_balance_notify_mode == 'sms' and user_request.partner_id.mobile:
                    mobile_wallet_create.sms_send_wallet_transaction(wallet_transfer_balance_notify_mode,
                                                                     'wallet_transfer_balance',
                                                                     user_request.partner_id.mobile,
                                                                     user_request.partner_id.name, label,
                                                                     '%s %s' % (user_request.trans_amount,
                                                                                _(user_request.currency_id.name)),
                                                                     user_request.partner_id.country_id.phone_code or '2')

                label = _('Transfer wallet balance to %s') % (user_request.partner_id.name)
                partner_id_wallet_balance = request.env.user.partner_id.wallet_balance
                machine_wallet_create = wallet_transaction_sudo.create(
                    {'wallet_type': 'debit', 'partner_id': request.env.user.partner_id.id, 'request_id': user_request.id,
                     'reference': 'request', 'label': label,
                     'amount': user_request.trans_amount, 'currency_id': user_request.currency_id.id,
                     'wallet_balance_before': partner_id_wallet_balance,
                     'wallet_balance_after': partner_id_wallet_balance - user_request.trans_amount,
                     'status': 'done'})
                request.env.cr.commit()

                request.env.user.partner_id.update(
                    {'wallet_balance': request.env.user.partner_id.wallet_balance - user_request.trans_amount})
                request.env.cr.commit()
                user_request.sudo().write({'wallet_transaction_id': machine_wallet_create.id, 'stage_id': 5})
                request.env.cr.commit()

                # Notify customer
                if wallet_transfer_balance_notify_mode == 'inbox':
                    request.env['mail.thread'].sudo().message_notify(
                        subject=label,
                        body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                            user_request.trans_amount, _(user_request.currency_id.name)),
                        partner_ids=[(4, request.env.user.partner_id.id)],
                    )
                elif wallet_transfer_balance_notify_mode == 'email':
                    machine_wallet_create.wallet_transaction_email_send()
                elif wallet_transfer_balance_notify_mode == 'sms' and request.env.user.partner_id.mobile:
                    machine_wallet_create.sms_send_wallet_transaction(wallet_transfer_balance_notify_mode,
                                                                      'wallet_transfer_balance',
                                                                      request.env.user.partner_id.mobile,
                                                                      request.env.user.name, label,
                                                                      '%s %s' % (user_request.trans_amount,
                                                                                 _(user_request.currency_id.name)),
                                                                      request.env.user.partner_id.country_id.phone_code or '2')

                # Create journal entry for transfer AR balance from machine customer to mobile user.
                machine_customer_receivable_account = request.env.user.partner_id.property_account_receivable_id
                mobile_user_receivable_account = user_request.partner_id.property_account_receivable_id
                account_move = request.env['account.move'].sudo().create({
                    'journal_id': request.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
                })
                request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                    'name': user_request.name + ': Transfer Wallet Balance',
                    'move_id': account_move.id,
                    'account_id': machine_customer_receivable_account.id,
                    'partner_id': request.env.user.partner_id.id,
                    'debit': user_request.trans_amount,
                })
                request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                    'name': user_request.name + ': Transfer Wallet Balance',
                    'move_id': account_move.id,
                    'account_id': mobile_user_receivable_account.id,
                    'partner_id': user_request.partner_id.id,
                    'credit': user_request.trans_amount,
                })
                account_move.post()

                return valid_response(_(
                    "Wallet for User (%s) recharged successfully with amount %s %s. Your Machine Wallet Balance is %s %s") %
                                      (user_request.partner_id.name, user_request.trans_amount,
                                       user_request.currency_id.name,
                                       request.env.user.partner_id.wallet_balance, user_request.currency_id.name))
            else:
                return invalid_response("request_not_found", _("REQ Number (%s) does not exist!") % (
                request_data.get('request_number')), 400)

        @validate_token
        @http.route('/api/payInvoice', type="http", auth="none", methods=["POST"], csrf=False)
        def payInvoice(self, **request_data):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Pay Invoice Request API")
            if not request_data.get('request_number'):
                return invalid_response("request_code_missing", _("missing request number in request data"), 400)
            customer_request = request.env['smartpay_operations.request'].sudo().search(
                [('name', '=', request_data.get('request_number')), ('request_type', '=', "pay_invoice")], limit=1)
            if customer_request:
                if customer_request.stage_id.id != 1:
                    return invalid_response("request_not_found",
                                            _("REQ Number (%s) invalid!") % (request_data.get('request_number')), 400)
                if request.env.user.partner_id.wallet_balance < customer_request.trans_amount:
                    return invalid_response("mobile_balance_not_enough",
                                            _("Mobile Wallet Balance less than the request amount"), 400)

                # Transfer Balance from Mobile Wallet to Machine Wallet
                wallet_transaction_sudo = request.env['website.wallet.transaction'].sudo()

                label = _('Collect invoice payment from %s') % (request.env.user.partner_id.name)
                partner_id_wallet_balance = customer_request.partner_id.wallet_balance
                machine_wallet_create = wallet_transaction_sudo.create(
                    {'wallet_type': 'credit', 'partner_id': customer_request.partner_id.id, 'request_id': customer_request.id,
                     'reference': 'request', 'label': label,
                     'amount': customer_request.trans_amount, 'currency_id': customer_request.currency_id.id,
                     'wallet_balance_before': partner_id_wallet_balance,
                     'wallet_balance_after': partner_id_wallet_balance + customer_request.trans_amount,
                     'status': 'done'})
                request.env.cr.commit()

                customer_request.partner_id.update(
                    {'wallet_balance': customer_request.partner_id.wallet_balance + customer_request.trans_amount})
                request.env.cr.commit()

                # Notify Customer
                irc_param = request.env['ir.config_parameter'].sudo()
                wallet_pay_invoice_notify_mode = irc_param.get_param("smartpay_operations.wallet_pay_invoice_notify_mode")
                if wallet_pay_invoice_notify_mode == 'inbox':
                    request.env['mail.thread'].sudo().message_notify(
                        subject=label,
                        body=_('<p>%s %s successfully added to your wallet.</p>') % (
                            customer_request.trans_amount, _(customer_request.currency_id.name)),
                        partner_ids=[(4, customer_request.partner_id.id)],
                    )
                elif wallet_pay_invoice_notify_mode == 'email':
                    machine_wallet_create.wallet_transaction_email_send()
                elif wallet_pay_invoice_notify_mode == 'sms' and customer_request.partner_id.mobile:
                    machine_wallet_create.sms_send_wallet_transaction(wallet_pay_invoice_notify_mode,
                                                                      'wallet_pay_invoice',
                                                                      customer_request.partner_id.mobile,
                                                                      customer_request.partner_id.name, label,
                                                                      '%s %s' % (customer_request.trans_amount,
                                                                                 _(customer_request.currency_id.name)),
                                                                      customer_request.partner_id.country_id.phone_code or '2')

                label = _('Pay invoice to %s') % (customer_request.partner_id.name)
                partner_id_wallet_balance = request.env.user.partner_id.wallet_balance
                mobile_wallet_create = wallet_transaction_sudo.create(
                    {'wallet_type': 'debit', 'partner_id': request.env.user.partner_id.id, 'request_id': customer_request.id,
                     'reference': 'request', 'label': label,
                     'amount': customer_request.trans_amount, 'currency_id': customer_request.currency_id.id,
                     'wallet_balance_before': partner_id_wallet_balance,
                     'wallet_balance_after': partner_id_wallet_balance - customer_request.trans_amount,
                     'status': 'done'})
                request.env.cr.commit()

                request.env.user.partner_id.update(
                    {'wallet_balance': request.env.user.partner_id.wallet_balance - customer_request.trans_amount})
                request.env.cr.commit()
                customer_request.sudo().write({'wallet_transaction_id': mobile_wallet_create.id, 'stage_id': 5})
                request.env.cr.commit()

                # Notify User
                if wallet_pay_invoice_notify_mode == 'inbox':
                    request.env['mail.thread'].sudo().message_notify(
                        subject=label,
                        body=_('<p>%s %s successfully deducted from your wallet.</p>') % (
                            customer_request.trans_amount, _(customer_request.currency_id.name)),
                        partner_ids=[(4, request.env.user.partner_id.id)],
                    )
                elif wallet_pay_invoice_notify_mode == 'email':
                    mobile_wallet_create.wallet_transaction_email_send()
                elif wallet_pay_invoice_notify_mode == 'sms' and request.env.user.partner_id.mobile:
                    mobile_wallet_create.sms_send_wallet_transaction(wallet_pay_invoice_notify_mode,
                                                                      'wallet_pay_invoice',
                                                                      request.env.user.partner_id.mobile,
                                                                      request.env.user.name, label,
                                                                      '%s %s' % (customer_request.trans_amount,
                                                                                 _(customer_request.currency_id.name)),
                                                                      request.env.user.partner_id.country_id.phone_code or '2')

                # Create journal entry for transfer AR balance from mobile user to machine customer.
                mobile_user_receivable_account = request.env.user.partner_id.property_account_receivable_id
                machine_customer_receivable_account = customer_request.partner_id.property_account_receivable_id
                account_move = request.env['account.move'].sudo().create({
                    'journal_id': request.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
                })
                request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                    'name': customer_request.name + ': Pay Invoice',
                    'move_id': account_move.id,
                    'account_id': mobile_user_receivable_account.id,
                    'partner_id': request.env.user.partner_id.id,
                    'debit': customer_request.trans_amount,
                })
                request.env['account.move.line'].with_context(check_move_validity=False).sudo().create({
                    'name': customer_request.name + ': Pay Invoice',
                    'move_id': account_move.id,
                    'account_id': machine_customer_receivable_account.id,
                    'partner_id': customer_request.partner_id.id,
                    'credit': customer_request.trans_amount,
                })
                account_move.post()

                return valid_response(_(
                    "Invoice request (%s) paid successfully with amount %s %s. Your Mobile Wallet Balance is %s %s") %
                                      (customer_request.name, customer_request.trans_amount,
                                       customer_request.currency_id.name,
                                       request.env.user.partner_id.wallet_balance, customer_request.currency_id.name))
            else:
                return invalid_response("request_not_found", _("REQ Number (%s) does not exist!") % (
                    request_data.get('request_number')), 400)

        ###############################################
        ######### Fawry Integration Requests ##########
        ###############################################
        @validate_token
        @http.route('/api/getServiceCategories', type="http", auth="none", methods=["POST"], csrf=False)
        def getServiceCategories(self, **payload):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Get Sevice Category API")
            domain, fields, offset, limit, order = extract_arguments(payload)
            domain += [("parent_id", "=", request.env.ref("tm_base_gateway.product_category_services").id), ("product_count", "!=", 0)]

            lang = payload.get("lang", "en_US")
            ir_translation_sudo = request.env['ir.translation'].sudo()
            product_category_sudo = request.env['product.category'].sudo()
            '''
            service_categories = product_category_sudo.search_read(domain=domain,
                                                                     fields=fields,
                                                                     offset=offset,
                                                                     limit=limit,
                                                                     order=order,
                                                                     )
            '''
            service_categories = product_category_sudo.search(domain, offset=offset, limit=limit, order=order)
            categories = []
            if service_categories:
                for service_category in service_categories:
                    category = {
                        "id": service_category.id,
                        # "image": service_category.image_medium and service_category.image_medium.decode('ascii') or False,
                        # "name": service_category.name
                    }

                    if service_category.image_medium:
                        category.update({"image": "/web/image?model=%s&field=image_medium&id=%s" % ("product.category", service_category.id)})

                    '''
                    ir_translation_ids = ir_translation_sudo.search_read(
                        domain=[("name", "=", "product.category,name"), ("res_id", "=", service_category.id)],
                        fields=["lang", "source", "value"], order="res_id")
                    if ir_translation_ids:
                        category_trans = []
                        for ir_translation in ir_translation_ids:
                            category_trans.append({
                                "lang": ir_translation["lang"],
                                "name": ir_translation["value"]
                            })
                        category.update({"name_translate": category_trans})
                    '''

                    if lang == "en_US":
                        category.update({"name": service_category.name})
                    else:
                        ir_translation_id = ir_translation_sudo.search(
                            [("name", "=", "product.category,name"), ("res_id", "=", service_category.id), ("lang", "=", lang)],
                            limit=1)
                        if ir_translation_id:
                            category.update({"name": ir_translation_id.value})

                    categories.append(category)

            return valid_response(categories)
            # return invalid_response("service_categories_not_found",  _("Could not get Service Categories"), 400)

        @validate_token
        @http.route('/api/getServiceBillers', type="http", auth="none", methods=["POST"], csrf=False)
        def getServiceBillers(self, **payload):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Get Sevice Biller API")
            domain, fields, offset, limit, order = extract_arguments(payload)
            domain += [("product_count", "!=", 0)]

            lang = payload.get("lang", "en_US")
            ir_translation_sudo = request.env['ir.translation'].sudo()
            product_category_sudo = request.env['product.category'].sudo()
            '''
            service_billers = product_category_sudo.search_read(domain=domain,
                                                                     fields=fields,
                                                                     offset=offset,
                                                                     limit=limit,
                                                                     order=order,
                                                                     )
            '''
            service_billers = product_category_sudo.search(domain, offset=offset, limit=limit, order=order)
            billers = []
            if service_billers:
                for service_biller in service_billers:
                    biller = {
                        "id": service_biller.id,
                        "categ_id": service_biller.parent_id.id,
                        "categ_name": service_biller.parent_id.name,
                        # "image": service_biller.image_medium and service_biller.image_medium.decode('ascii') or False,
                        # "name": service_biller.name
                    }

                    if service_biller.image_medium:
                        biller.update({"image": "/web/image?model=%s&field=image_medium&id=%s" % ("product.category", service_biller.id)})

                    '''
                    ir_translation_ids = ir_translation_sudo.search_read(
                        domain=[("name", "=", "product.category,name"), ("res_id", "=", service_biller.id)],
                        fields=["lang", "source", "value"], order="res_id")
                    if ir_translation_ids:
                        biller_trans = []
                        for ir_translation in ir_translation_ids:
                            biller_trans.append({
                                "lang": ir_translation["lang"],
                                "name": ir_translation["value"]
                            })
                        biller.update({"name_translate": biller_trans})
                    '''

                    if lang == "en_US":
                        biller.update({"name": service_biller.name})
                    else:
                        ir_translation_id = ir_translation_sudo.search(
                            [("name", "=", "product.category,name"), ("res_id", "=", service_biller.id), ("lang", "=", lang)],
                            limit=1)
                        if ir_translation_id:
                            biller.update({"name": ir_translation_id.value})

                    billers.append(biller)

            return valid_response(billers)
            # return invalid_response("service_billers_not_found", _("Could not get Service Billers"), 400)

        @validate_token
        @http.route('/api/getServices', type="http", auth="none", methods=["POST"], csrf=False)
        def getServices(self, **payload):
            _logger.info(">>>>>>>>>>>>>>>>>>>> Calling Get Sevices API")
            domain, fields, offset, limit, order = extract_arguments(payload)

            lang = payload.get("lang", "en_US")
            biller_info_sudo = request.env['product.supplierinfo'].sudo()
            ir_translation_sudo = request.env['ir.translation'].sudo()
            product_template_sudo = request.env['product.template'].sudo()
            '''
            service_ids = product_template_sudo.search_read(domain=domain,
                                                                     fields=fields,
                                                                     offset=offset,
                                                                     limit=limit,
                                                                     order=order,
                                                                     )
            '''
            service_ids = product_template_sudo.search(domain, offset=offset, limit=limit, order=order)
            services = []
            if service_ids:
                for service_id in service_ids:
                    service = {
                        "id": service_id.product_variant_id.id,
                        "categ_id": service_id.categ_id.id,
                        "categ_name": service_id.categ_id.name,
                        # "image": service_id.image_medium and service_id.image_medium.decode('ascii') or False,
                        # "name": service_id.name
                    }

                    if service_id.image_medium:
                        service.update({"image": "/web/image?model=%s&field=image_medium&id=%s" % ("product.template", service_id.id)})

                    '''
                    ir_translation_ids = ir_translation_sudo.search_read(
                        domain=[("name", "=", "product.template,name"), ("res_id", "=", service_id.id)],
                        fields=["lang", "source", "value"], order="res_id")
                    if ir_translation_ids:
                        service_trans = []
                        for ir_translation in ir_translation_ids:
                            service_trans.append({
                                "lang": ir_translation["lang"],
                                "name": ir_translation["value"]
                            })
                        service.update({"name_translate": service_trans})
                    '''

                    biller_info_id = biller_info_sudo.search(
                        [("product_tmpl_id.type", "=", "service"),
                                ("product_tmpl_id.id", "=", service_id.id)],
                        limit=1)

                    if lang == "en_US":
                        service.update({"name": service_id.name})

                        if biller_info_id:
                            service.update({"biller_info": biller_info_id.biller_info})
                    else:
                        ir_translation_id = ir_translation_sudo.search(
                            [("name", "=", "product.template,name"), ("res_id", "=", service_id.id),
                                    ("lang", "=", lang)],
                            limit=1)
                        if ir_translation_id:
                            service.update({"name": ir_translation_id.value})

                        ir_translation_id = ir_translation_sudo.search(
                            [("name", "=", "product.supplierinfo,biller_info"), ("res_id", "=", biller_info_id.id),
                                    ("lang", "=", lang)],
                            limit=1)
                        if ir_translation_id:
                            service.update({"biller_info": ir_translation_id.value})

                    services.append(service)

            return valid_response(services)
            # return invalid_response("services_not_found", _("Could not get Services"), 400)

    class AccessToken(http.Controller):
        """."""

        def __init__(self):

            self._token = request.env["api.access_token"]
            self._expires_in = request.env.ref("restful.access_token_expires_in").sudo().value

        @http.route("/api/auth/machine_token", methods=["POST"], type="http", auth="none", csrf=False)
        def machine_token(self, **post):
            """The token URL to be used for getting the access_token:

            Args:
                **post must contain login and password.
            Returns:

                returns https response code 404 if failed error message in the body in json format
                and status code 202 if successful with the access_token.
            Example:
               import requests

               headers = {'content-type': 'text/plain', 'charset':'utf-8', 'machine_serial': '123456ABCDEF'}

               data = {
                   'login': 'admin',
                   'password': 'admin',
                   'db': 'galago.ng'
                   'Machine_serial': '123456ABCDEF',
                }
               base_url = 'http://odoo.ng'
               eq = requests.post(
                   '{}/api/auth/token'.format(base_url), data=data, headers=headers)
               content = json.loads(req.content.decode('utf-8'))
               headers.update(access-token=content.get('access_token'))
            """
            _token = request.env["api.access_token"]
            params = ["db", "login", "password"]
            params = {key: post.get(key) for key in params if post.get(key)}
            db, username, password, machine_serial = (
                params.get("db"),
                params.get("login"),
                params.get("password"),
                params.get("machine_serial"),
            )
            _credentials_includes_in_body = all([db, username, password, machine_serial])
            if not _credentials_includes_in_body:
                # The request post body is empty the credetials maybe passed via the headers.
                headers = request.httprequest.headers
                db = headers.get("db")
                username = headers.get("login")
                password = headers.get("password")
                machine_serial = headers.get("machine_serial")
                _credentials_includes_in_headers = all([db, username, password, machine_serial])
                if not _credentials_includes_in_headers:
                    # Empty 'db' or 'username' or 'password' or 'machine_serial':
                    return invalid_response(
                        "missing error",
                        _("either of the following are missing [db, username, password, machine_serial]"),
                        403,
                    )
            # Login in odoo database:
            try:
                request.session.authenticate(db, username, password)
            except Exception as e:
                # Invalid database:
                info = "The database name is not valid {}".format((e))
                error = "invalid_database"
                _logger.error(info)
                return invalid_response(_("wrong database name", error, 403))

            uid = request.session.uid
            # odoo login failed:
            if not uid:
                info = _("authentication failed")
                error = "authentication failed"
                _logger.error(info)
                return invalid_response(401, error, info)

            # Validate machine serial
            machine_serial_data = (
                request.env["res.users"]
                    .sudo()
                    .search([("x_machine_serial", "=", machine_serial), ("id", "=", uid)], order="id DESC", limit=1)
            )
            if not machine_serial_data:
                info = _("machine serial invalid")
                error = "machine_serial"
                _logger.error(info)
                return invalid_response(401, error, info)

            # Change the current password
            prefix = "TP_"
            password_characters = string.ascii_letters + string.digits + string.punctuation
            new_password = ''.join(random.choice(password_characters) for i in range(10))
            user = request.env['res.users'].sudo().search([('id', '=', request.env.user.id)], limit=1)
            user.sudo().write({'password': prefix + new_password})

            # Delete existing token
            access_token = (
                self.env["api.access_token"]
                    .sudo()
                    .search([("user_id", "=", uid)], order="id DESC", limit=1)
            )
            if access_token:
                access_token.unlink()
            # Generate tokens
            access_token = _token.find_one_or_create_token(user_id=uid, create=True)
            # Successful response:
            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps(
                    {
                        "uid": uid,
                        "user_context": request.session.get_context() if uid else {},
                        "company_id": request.env.user.company_id.id if uid else None,
                        "access_token": access_token,
                        "expires_in": self._expires_in,
                    }
                ),
            )

        @validate_token
        @validate_machine
        @http.route("/api/auth/refresh_machine_token", methods=["PUT"], type="http", auth="none", csrf=False)
        def refresh_machine_token(self, **post):
            """."""
            _token = request.env["api.access_token"].sudo()
            access_token = request.httprequest.headers.get("access_token")
            access_token = _token.search([("token", "=", access_token)])
            user_id = access_token.user_id.id
            if not access_token:
                info = _("No access token was provided in request!")
                error = "no_access_token"
                _logger.error(info)
                return invalid_response(400, error, info)
            # Delete current token
            for token in access_token:
                token.unlink()

            # Generate new token
            access_token = _token.find_one_or_create_token(user_id=user_id, create=True)
            # Successful response:
            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps(
                    {
                        "uid": user_id,
                        "user_context": request.session.get_context() if user_id else {},
                        "company_id": request.env.user.company_id.id if user_id else None,
                        "access_token": access_token,
                        "expires_in": self._expires_in,
                    }
                ),
            )

        @validate_token
        @http.route("/api/auth/refresh_token", methods=["PUT"], type="http", auth="none", csrf=False)
        def refresh_token(self, **post):
            """."""
            _token = request.env["api.access_token"].sudo()
            access_token = request.httprequest.headers.get("access_token")
            access_token = _token.search([("token", "=", access_token)])
            user_id = access_token.user_id.id
            if not access_token:
                info = _("No access token was provided in request!")
                error = "no_access_token"
                _logger.error(info)
                return invalid_response(400, error, info)
            # Delete current tokens
            for token in access_token:
                token.unlink()

            # Generate new token
            access_token = _token.find_one_or_create_token(user_id=user_id, create=True)
            # Successful response:
            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps(
                    {
                        "uid": user_id,
                        "user_context": request.session.get_context() if user_id else {},
                        "company_id": request.env.user.company_id.id if user_id else None,
                        "access_token": access_token,
                        "expires_in": self._expires_in,
                    }
                ),
            )