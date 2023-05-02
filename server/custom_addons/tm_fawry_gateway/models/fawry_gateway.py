# -*- coding: utf-8 -*-
# This module and its content is copyright of Tamayozsoft.
# - © Tamayozsoft 2020. All rights reserved.

import logging
import psycopg2

from odoo import api, fields, models, registry, SUPERUSER_ID, tools, _
from odoo.exceptions import UserError, ValidationError

from .fawry_request import FAWRYRequest #, Package
from odoo.addons.tm_base_gateway.common import (
    suds_to_json,
)

_logger = logging.getLogger(__name__)

class AcquirerFawryChannel(models.Model):
    _name = 'payment.acquirer.channel'
    _order = "sequence"

    name = fields.Char('Chennel Name', required_if_provider='fawry', groups='base.group_user')
    type = fields.Selection([('internet', 'Internet'), ('machine', 'Machine'), ('mobile', 'Mobile')], string='Chennel Type', default='machine',
                             required_if_provider='fawry', groups='base.group_user')
    fawry_sender = fields.Char('Sender', required_if_provider='fawry', groups='base.group_user')                              # sender: SmartPay2_MOB
    fawry_receiver = fields.Char('Receiver', required_if_provider='fawry', groups='base.group_user')                          # receiver: SmartPay2
    fawry_originatorCode = fields.Char('Originator Code', required_if_provider='fawry', groups='base.group_user')             # originatorCode: SmartPay2
    fawry_terminalId = fields.Char('Terminal ID', required_if_provider='fawry', groups='base.group_user')                     # terminalId: 104667
    fawry_posSerialNumber = fields.Char('POS Serial Number', groups='base.group_user')                                        # SerialNumber: 332-491-1222
    fawry_deliveryMethod = fields.Char('Delivery Method', required_if_provider='fawry', groups='base.group_user')             # DeliveryMethod: MOB
    fawry_profileCode = fields.Char('Profile Code', required_if_provider='fawry', groups='base.group_user')                   # ProfileCode: 22013
    fawry_bankId = fields.Char('Bank ID', required_if_provider='fawry', groups='base.group_user')                             # bankId: SmartPay2
    fawry_acctId = fields.Char('Account ID', required_if_provider='fawry', groups='base.group_user')                          # acctId: 104667
    fawry_acctType = fields.Char("Account Type", required_if_provider='fawry', groups='base.group_user', default='SDA')       # acctType: SDA
    fawry_acctKey = fields.Char('Account Key', required_if_provider='fawry', groups='base.group_user')                        # acctKey: 1234
    fawry_secureAcctKey = fields.Char('Secure Account Key', required_if_provider='fawry', groups='base.group_user')           # secureAcctKey: gdyb21LQTcIANtvYMT7QVQ==
    fawry_acctCur = fields.Many2one("res.currency", string='Account Currency', required_if_provider='fawry',
                                    groups='base.group_user', default=lambda self: self.env.user.company_id.currency_id)      # acctCur: EGP

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

class AcquirerFawry(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('fawry', 'Fawry')])

    # fawry_sender = fields.Char('Sender', required_if_provider='fawry', groups='base.group_user')                              # sender: SmartPay2_MOB                        ==> Per Channel
    # fawry_receiver = fields.Char('Receiver', required_if_provider='fawry', groups='base.group_user')                          # receiver: SmartPay2
    fawry_version =  fields.Char("Interface Version", required_if_provider='fawry', default='V1.0')                           # version: V1.0
    # fawry_originatorCode = fields.Char('Originator Code', required_if_provider='fawry', groups='base.group_user')             # originatorCode: SmartPay2
    # fawry_terminalId = fields.Char('Terminal ID', required_if_provider='fawry', groups='base.group_user')                     # terminalId: 104667                           ==> Per Channel
    # fawry_deliveryMethod = fields.Char('Delivery Method', required_if_provider='fawry', groups='base.group_user')             # DeliveryMethod: MOB                          ==> Per Channel
    # fawry_profileCode = fields.Char('Profile Code', required_if_provider='fawry', groups='base.group_user')                   # ProfileCode: 22013                           ==> Per Channel
    # fawry_posSerialNumber = fields.Char('POS Serial Number', required_if_provider='fawry', groups='base.group_user')          # posSerialNumber: 332-491-1222
    # fawry_bankId = fields.Char('Bank ID', required_if_provider='fawry', groups='base.group_user')                             # bankId: SmartPay2
    # fawry_acctId = fields.Char('Account ID', required_if_provider='fawry', groups='base.group_user')                          # acctId: 104667                               ==> Per Channel
    # fawry_acctType = fields.Char("Account Type", required_if_provider='fawry', groups='base.group_user', default='SDA')       # acctType: SDA
    # fawry_acctKey = fields.Char('Account Key', required_if_provider='fawry', groups='base.group_user')                        # acctKey: 1234
    # fawry_secureAcctKey = fields.Char('Secure Account Key', required_if_provider='fawry', groups='base.group_user')           # secureAcctKey: gdyb21LQTcIANtvYMT7QVQ==
    # fawry_acctCur = fields.Many2one("res.currency", string='Account Currency', required_if_provider='fawry',
    #                                 groups='base.group_user', default=lambda self: self.env.user.company_id.currency_id)      # acctCur: EGP

    fawry_test_url = fields.Char("Test url", required_if_provider='fawry',
                                 default='http://gw.fawrystaging.com:9081/CoreWeb/ApplicationBusinessFacadeService/')
    fawry_prod_url = fields.Char("Production url", required_if_provider='fawry',
                                 default='http://gw.fawrystaging.com:9081/CoreWeb/ApplicationBusinessFacadeService/')

    fawry_channel_ids = fields.One2many('payment.acquirer.channel', 'acquirer_id', string='Fawry Channels', copy=False)

    def log_xml(self, xml_string, func):
        self.ensure_one()

        if self.debug_logging:
            db_name = self._cr.dbname

            # Use a new cursor to avoid rollback that could be caused by an upper method
            try:
                db_registry = registry(db_name)
                with db_registry.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    IrLogging = env['ir.logging']
                    IrLogging.sudo().create({'name': 'payment.acquirer',
                              'type': 'server',
                              'dbname': db_name,
                              'level': 'DEBUG',
                              'message': xml_string,
                              'path': self.provider,
                              'func': func,
                              'line': 1})
            except psycopg2.Error:
                pass

    def get_fawry_biller_details(self, fawry_channel=None):
        superself = self.sudo()

        if not fawry_channel and superself.fawry_channel_ids:
            fawry_channel = superself.fawry_channel_ids[0]
        elif not fawry_channel and not superself.fawry_channel_ids:
            raise ValidationError(_('The fetch of fawry biller details cannot be processed because the fawry has not any chennel in confiquration!'))

        # Production and Testing url
        endurl = superself.fawry_prod_url
        suppressEcho = False
        if superself.environment == "test":
            endurl = superself.fawry_test_url
            suppressEcho = True

        '''
            sender, receiver, version, originatorCode, terminalId, deliveryMethod,  # msgCode: BillerInqRq, BillInqRq and PmtAddRq
            profileCode,                                                            # msgCode: BillerInqRq ==> Optional
            bankId,                                                                 # msgCode: BillInqRq and PmtAddRq
            acctId, acctType, acctKey, secureAcctKey, acctCur, posSerialNumber      # msgCode: PmtAddRq
        '''
        # _logger.info("endurl             >>>>>>>>>>>>>>>>>>>>> " + endurl)
        # _logger.info("sender             >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_sender)
        # _logger.info("receiver           >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_receiver)
        # _logger.info("version            >>>>>>>>>>>>>>>>>>>>> " + superself.fawry_version)
        # _logger.info("originatorCode     >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_originatorCode)
        # _logger.info("terminalId         >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_terminalId)
        # _logger.info("deliveryMethod     >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_deliveryMethod)
        srm = FAWRYRequest(debug_logger=self.log_xml, endurl=endurl, sender=fawry_channel.fawry_sender, receiver=fawry_channel.fawry_receiver, version=superself.fawry_version,
                           originatorCode=fawry_channel.fawry_originatorCode, terminalId=fawry_channel.fawry_terminalId, deliveryMethod=fawry_channel.fawry_deliveryMethod)

        result = {}
        # Tamayoz TODO: Loop for Fawry custLangPref enum
        for custLangPref in ['en-gb', 'ar-eg']:
            result_biller = srm.get_biller_details(custLangPref, suppressEcho)
            if result_biller.get('billerRecTypes'):
                result['billerRecTypes_'+custLangPref] = result_biller['billerRecTypes']
            else:
                result = result_biller

        return result

    def auto_fetch_fawry_biller_details(self):
        fawry = self.env['payment.acquirer'].sudo().search([("provider", "=", "fawry")])
        result = fawry.get_fawry_biller_details()
        fetch_success = False

        # Tamayoz TODO: Loop for Fawry custLangPref enum
        for custLangPref in ['en-gb', 'ar-eg']:
            billerRecTypes = result.get('billerRecTypes_'+custLangPref)
            if billerRecTypes:
                fetch_success = True
                for billerRecType in billerRecTypes:
                    _logger.info(" ====================================== Biller Fetch Data Begin " + billerRecType.BillerId + ": " + custLangPref + " =========================================")
                    billerId = billerRecType.BillerId
                    billerName = billerRecType.BillerName
                    # billerNameLanguage = billerRecType.BillerNameLang
                    billerLogo = False
                    if "BillerLogo" in billerRecType:
                        billerLogo = billerRecType.BillerLogo
                    billerStatus = billerRecType.BillerStatus

                    billerInfoTypes = billerRecType.BillerInfo
                    if billerInfoTypes:
                        for billerInfoType in billerInfoTypes:
                            # _logger.info(" ===== billerInfoType Json >>>>> " + suds_to_json(billerInfoType) + " =====")
                            serviceType = billerInfoType.ServiceType
                            serviceName = billerInfoType.ServiceName
                            serviceTypeLogo = False
                            if "ServiceTypeLogo" in billerInfoType:
                                serviceTypeLogo = billerRecType.ServiceTypeLogo

                            # Fetch Fawry Service Category
                            service_categ_providerinfo = self.env['product_category.providerinfo'].sudo().search([
                                ('product_categ_code', '=', serviceType), ('provider_id', '=', fawry.id)
                            ])
                            if not service_categ_providerinfo:
                                service_category_vals = {
                                    'name': serviceName,
                                    'parent_id': self.env.ref("tm_base_gateway.product_category_services").id,
                                    'property_cost_method': 'standard',
                                    'provider_ids': [(0, 0, {
                                        'product_categ_code': serviceType,
                                        'product_categ_name': serviceName,
                                        'provider_id': fawry.id,
                                    })],
                                }
                                if serviceTypeLogo:
                                    service_category_vals.update({
                                        'image': serviceTypeLogo,
                                        'image_medium': serviceTypeLogo,
                                        'image_small': serviceTypeLogo,
                                    })
                                    tools.image_resize_images(service_category_vals)
                                service_category = self.env['product.category'].sudo().create(service_category_vals)
                                service_categ_providerinfo = service_category.provider_ids[0]
                                # service_category_providerinfo = self.env['product_category.providerinfo'].sudo().create({
                                #     'product_categ_code': serviceType,
                                #     'product_categ_name': serviceName,
                                #     'provider_id': fawry.id,
                                #     'product_categ_id': service_category.id
                                # })

                                service_provider_vals = {
                                    'name': billerName,
                                    'parent_id': service_category.id,
                                    'property_cost_method': 'standard',
                                    'provider_ids': [(0, 0, {
                                        'product_categ_code': billerId,
                                        'product_categ_name': billerName,
                                        'provider_id': fawry.id,
                                    })],
                                }
                                if billerLogo:
                                    service_provider_vals.update({
                                        'image': billerLogo,
                                        'image_medium': billerLogo,
                                        'image_small': billerLogo,
                                    })
                                    tools.image_resize_images(service_provider_vals)
                                service_provider = self.env['product.category'].sudo().create(service_provider_vals)
                                service_provider_providerinfo = service_provider.provider_ids[0]
                                # service_provider_providerinfo = self.env['product_category.providerinfo'].sudo().create({
                                #     'product_categ_code': billerId,
                                #     'product_categ_name': billerName,
                                #     'provider_id': fawry.id,
                                #     'product_categ_id': service_provider.id
                                # })
                            else:
                                if custLangPref == 'en-gb':
                                    service_categ_providerinfo.sudo().write({'product_categ_name': serviceName})
                                elif custLangPref == 'ar-eg':
                                    serviceName_translate = self.env['ir.translation'].sudo().search([
                                        ('type', '=', 'model'),
                                        ('name', '=', 'product.category,name'),
                                        ('module', '=', 'product'),
                                        ('lang', '=', 'ar_AA'),
                                        ('res_id', '=', service_categ_providerinfo.product_categ_id.id),
                                        ('state', '=', 'translated')
                                    ])

                                    if not serviceName_translate:
                                        serviceName_translate = self.env['ir.translation'].sudo().create({
                                            'type': 'model',
                                            'name': 'product.category,name',
                                            'module': 'product',
                                            'lang': 'ar_AA',
                                            'res_id': service_categ_providerinfo.product_categ_id.id,
                                            'value': serviceName,
                                            'state': 'translated',
                                        })
                                    else:
                                        serviceName_translate.sudo().write({"value": serviceName})

                                # Fetch Fawry Service Provider
                                service_provider_providerinfo = self.env['product_category.providerinfo'].sudo().search([
                                    ('product_categ_code', '=', billerId),
                                    ('provider_id', '=', fawry.id),
                                    ('product_categ_id.parent_id', '=', service_categ_providerinfo.product_categ_id.id)
                                ])
                                if not service_provider_providerinfo:
                                    service_provider_vals = {
                                        'name': billerName,
                                        'parent_id': service_categ_providerinfo.product_categ_id.id,
                                        'property_cost_method': 'standard',
                                        'provider_ids': [(0, 0, {
                                            'product_categ_code': billerId,
                                            'product_categ_name': billerName,
                                            'provider_id': fawry.id,
                                        })],
                                    }
                                    if billerLogo:
                                        service_provider_vals.update({
                                            'image': billerLogo,
                                            'image_medium': billerLogo,
                                            'image_small': billerLogo,
                                        })
                                        tools.image_resize_images(service_provider_vals)
                                    service_provider = self.env['product.category'].sudo().create(service_provider_vals)
                                    service_provider_providerinfo = service_provider.provider_ids[0]
                                    # service_provider_providerinfo = self.env[
                                    #     'product_category.providerinfo'].sudo().create({
                                    #     'product_categ_code': billerId,
                                    #     'product_categ_name': billerName,
                                    #     'provider_id': fawry.id,
                                    #     'product_categ_id': service_provider.id
                                    # })
                                else:
                                    if custLangPref == 'en-gb':
                                        service_provider_providerinfo.sudo().write({"product_categ_name": billerName})
                                    elif custLangPref == 'ar-eg':
                                        serviceName_translate = self.env['ir.translation'].sudo().search([
                                            ('type', '=', 'model'),
                                            ('name', '=', 'product.category,name'),
                                            ('module', '=', 'product'),
                                            ('lang', '=', 'ar_AA'),
                                            ('res_id', '=', service_provider_providerinfo.product_categ_id.id),
                                            ('state', '=', 'translated')
                                        ])

                                        if not serviceName_translate:
                                            serviceName_translate = self.env['ir.translation'].sudo().create({
                                                'type': 'model',
                                                'name': 'product.category,name',
                                                'module': 'product',
                                                'lang': 'ar_AA',
                                                'res_id': service_provider_providerinfo.product_categ_id.id,
                                                'value': billerName,
                                                'state': 'translated',
                                            })
                                        else:
                                            serviceName_translate.sudo().write({"value": billerName})

                            billTypeCode = billerInfoType.BillTypeCode
                            billerServiceName = billerInfoType.Name
                            # billerServiceNameLanguage = billerInfoType.NameLang
                            billTypeLogo = False
                            if "BillTypeLogo" in billerInfoType:
                                billTypeLogo = billerInfoType.BillTypeLogo
                            billTypeStatus = billerInfoType.BillTypeStatus

                            # Fetch Fawry Service
                            service_providerinfo = self.env['product.supplierinfo'].sudo().search([
                                ('product_code', '=', billTypeCode),
                                ('name', '=', fawry.related_partner.id),
                                ('product_tmpl_id.categ_id', '=', service_provider_providerinfo.product_categ_id.id)
                            ])
                            if not service_providerinfo:
                                service_vals = {
                                    'name': billerServiceName,
                                    'type': 'service',
                                    'categ_id': service_provider_providerinfo.product_categ_id.id,
                                    'seller_ids': [(0, 0, {
                                        'name': fawry.related_partner.id,
                                        'product_code': billTypeCode,
                                        'product_name': billerServiceName,
                                        'biller_info': suds_to_json(billerInfoType),
                                    })],
                                    'taxes_id': False,
                                    'supplier_taxes_id': False,
                                    'sale_ok': True,
                                    'purchase_ok': True,
                                    'invoice_policy': 'order',
                                    'lst_price': 0, #Do not set a high value to avoid issue with coupon code
                                    'uom_id': self.env.ref("uom.product_uom_unit").id,
                                    'uom_po_id': self.env.ref("uom.product_uom_unit").id
                                }
                                if billTypeLogo:
                                    service_vals.update({
                                        'image': billTypeLogo,
                                        'image_medium': billTypeLogo,
                                        'image_small': billTypeLogo,
                                    })
                                    tools.image_resize_images(service_vals)
                                service = self.env['product.product'].sudo().create(service_vals)
                                service_providerinfo = service.seller_ids[0]
                                # service_providerinfo = self.env['product.supplierinfo'].sudo().create({
                                #     'product_code': billTypeCode,
                                #     'product_name': billerServiceName,
                                #     'name': fawry.related_partner.id,
                                #     'biller_info': suds_to_json(billerInfoType),
                                #     'product_id': service.id
                                # })
                            else:
                                if custLangPref == 'en-gb':
                                    service_providerinfo.sudo().write({'product_name': billerServiceName, 'biller_info': suds_to_json(billerInfoType)})
                                elif custLangPref == 'ar-eg':
                                    serviceName_translate = self.env['ir.translation'].sudo().search([
                                        ('type', '=', 'model'),
                                        ('name', '=', 'product.template,name'),
                                        ('module', '=', 'product'),
                                        ('lang', '=', 'ar_AA'),
                                        ('res_id', '=', service_providerinfo.product_tmpl_id.id),
                                        ('state', '=', 'translated')
                                    ])

                                    if not serviceName_translate:
                                        serviceName_translate = self.env['ir.translation'].sudo().create({
                                            'type': 'model',
                                            'name': 'product.template,name',
                                            'module': 'product',
                                            'lang': 'ar_AA',
                                            'res_id': service_providerinfo.product_tmpl_id.id,
                                            'value': billerServiceName,
                                            'state': 'translated',
                                        })
                                    else:
                                        serviceName_translate.sudo().write({"value": billerServiceName})

                                    billerInfo_translate = self.env['ir.translation'].sudo().search([
                                        ('type', '=', 'model'),
                                        ('name', '=', 'product.supplierinfo,biller_info'),
                                        ('module', '=', 'product'),
                                        ('lang', '=', 'ar_AA'),
                                        ('res_id', '=', service_providerinfo.id),
                                        ('state', '=', 'translated')
                                    ])

                                    if not billerInfo_translate:
                                        billerInfo_translate = self.env['ir.translation'].sudo().create({
                                            'type': 'model',
                                            'name': 'product.supplierinfo,biller_info',
                                            'module': 'product',
                                            'lang': 'ar_AA',
                                            'res_id': service_providerinfo.id,
                                            'value': suds_to_json(billerInfoType),
                                            'state': 'translated',
                                        })
                                    else:
                                        billerInfo_translate.sudo().write({"value": suds_to_json(billerInfoType)})

                            '''
                            billTypeaccountLabel = billerInfoType.BillTypeAcctLabel
                            extraInfo = billerInfoType.ExtraInfo
                            billerPaymentType = billerInfoType.PmtType
                            type = billerInfoType.Type
                            receiptFooter = billerInfoType.ReceiptFooter
                            receiptFooterLanguage = billerInfoType.ReceiptFooterLang
                            receiptHeader = billerInfoType.ReceiptHeader
                            receiptHeaderLanguage = billerInfoType.ReceiptHeaderLang

                            expiryDate = billerInfoType.ExpiryDate
                            startDate = billerInfoType.StartDate

                            paymentRangeTypes = billerInfoType.PaymentRanges.PaymentRangeType
                            if paymentRangeTypes:
                                for paymentRangeType in paymentRangeTypes:
                                    paymentLowerAmount = paymentRangeType.Lower.Amt
                                    paymentLowerCurrencyCode = paymentRangeType.Lower.CurCode
                                    paymentUpperAmount = paymentRangeType.Upper.Amt
                                    paymentUpperCurrencyCode = paymentRangeType.Upper.CurCode

                            tierTypes = billerInfoType.Fees.Tier
                            if tierTypes:
                                for tierType in tierTypes:
                                    feesExpiryDate = tierType.ExpiryDate
                                    feesStartDate = tierType.StartDate
                                    feesFixedAmountCurrencyCode = tierType.FixedAmt.CurCode
                                    feesFixedAmount = tierType.FixedAmt.Amt
                                    feesLowerAmount = tierType.LowerAmt
                                    feesPercent = tierType.Percent
                                    feesUpperAmount = tierType.UpperAmt
                            '''

                    _logger.info(
                        " ====================================== Biller Fetch Data End " + billerRecType.BillerId + ": " + custLangPref + " =========================================")

        if not fetch_success:
            _logger.exception("Failed processing fawry biller inquiry")
            return False
        else:
            return True

    def get_fawry_bill_details(self, lang, billTypeCode, billingAcct, extraBillingAcctKeys, fawry_channel=None):
        superself = self.sudo()

        if not fawry_channel and superself.fawry_channel_ids:
            fawry_channel = superself.fawry_channel_ids[0]
        elif not fawry_channel and not superself.fawry_channel_ids:
            raise ValidationError(_('The fetch of fawry bill details cannot be processed because the fawry has not any chennel in confiquration!'))

        # Production and Testing url
        endurl = superself.fawry_prod_url
        suppressEcho = False
        if superself.environment == "test":
            endurl = superself.fawry_test_url
            suppressEcho = True

        '''
            sender, receiver, version, originatorCode, terminalId, deliveryMethod,  # msgCode: BillerInqRq, BillInqRq and PmtAddRq
            profileCode,                                                            # msgCode: BillerInqRq ==> Optional
            bankId,                                                                 # msgCode: BillInqRq and PmtAddRq
            acctId, acctType, acctKey, secureAcctKey, acctCur, posSerialNumber      # msgCode: PmtAddRq
        '''
        # _logger.info("endurl             >>>>>>>>>>>>>>>>>>>>> " + endurl)
        # _logger.info("sender             >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_sender)
        # _logger.info("receiver           >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_receiver)
        # _logger.info("version            >>>>>>>>>>>>>>>>>>>>> " + superself.fawry_version)
        # _logger.info("originatorCode     >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_originatorCode)
        # _logger.info("terminalId         >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_terminalId)
        # _logger.info("deliveryMethod     >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_deliveryMethod)
        # _logger.info("bankId             >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_bankId)
        srm = FAWRYRequest(debug_logger=self.log_xml, endurl=endurl, sender=fawry_channel.fawry_sender, receiver=fawry_channel.fawry_receiver, version=superself.fawry_version,
                           originatorCode=fawry_channel.fawry_originatorCode, terminalId=fawry_channel.fawry_terminalId, deliveryMethod=fawry_channel.fawry_deliveryMethod,
                           bankId = fawry_channel.fawry_bankId)

        result = {}
        custLangPref = 'en-gb'
        if lang == 'ar_AA' or (lang != 'en_US' and self.env.user.lang == 'ar_AA'):
            custLangPref = 'ar-eg'
        result_bill = srm.get_bill_details(custLangPref, suppressEcho, billTypeCode, billingAcct, extraBillingAcctKeys)
        if result_bill.get('billRecType'):
            result['Success'] = result_bill['billRecType']
        else:
            result = result_bill

        return result

    def pay_fawry_bill(self, lang, billTypeCode,
                       billingAcct, extraBillingAcctKeys,
                       amt, curCode, pmtMethod,
                       notifyMobile, billRefNumber,
                       billerId, pmtType, fawry_channel):
        superself = self.sudo()

        if not fawry_channel and superself.fawry_channel_ids:
            fawry_channel = superself.fawry_channel_ids[0]
        elif not fawry_channel and not superself.fawry_channel_ids:
            raise ValidationError(_('The pay of fawry bill cannot be processed because the fawry has not any chennel in confiquration!'))

        # Production and Testing url
        endurl = superself.fawry_prod_url
        suppressEcho = False
        if superself.environment == "test":
            endurl = superself.fawry_test_url
            suppressEcho = True

        '''
            sender, receiver, version, originatorCode, terminalId, deliveryMethod,  # msgCode: BillerInqRq, BillInqRq and PmtAddRq
            profileCode,                                                            # msgCode: BillerInqRq ==> Optional
            bankId,                                                                 # msgCode: BillInqRq and PmtAddRq
            acctId, acctType, acctKey, secureAcctKey, acctCur, posSerialNumber      # msgCode: PmtAddRq
        '''
        # _logger.info("endurl             >>>>>>>>>>>>>>>>>>>>> " + endurl)
        # _logger.info("sender             >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_sender)
        # _logger.info("receiver           >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_receiver)
        # _logger.info("version            >>>>>>>>>>>>>>>>>>>>> " + superself.fawry_version)
        # _logger.info("originatorCode     >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_originatorCode)
        # _logger.info("terminalId         >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_terminalId)
        # _logger.info("deliveryMethod     >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_deliveryMethod)
        # _logger.info("deliveryMethod     >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_posSerialNumber)
        # _logger.info("bankId             >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_bankId)
        # _logger.info("acctId             >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_acctId)
        # _logger.info("acctType           >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_acctType)
        # _logger.info("acctKey            >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_acctKey)
        # _logger.info("secureAcctKey      >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_secureAcctKey)
        # _logger.info("acctCur            >>>>>>>>>>>>>>>>>>>>> " + fawry_channel.fawry_acctCur)
        srm = FAWRYRequest(debug_logger=self.log_xml, endurl=endurl, sender=fawry_channel.fawry_sender, receiver=fawry_channel.fawry_receiver, version=superself.fawry_version,
                           originatorCode=fawry_channel.fawry_originatorCode, terminalId=fawry_channel.fawry_terminalId, deliveryMethod=fawry_channel.fawry_deliveryMethod,
                           posSerialNumber=fawry_channel.fawry_posSerialNumber, bankId=fawry_channel.fawry_bankId, acctId=fawry_channel.fawry_acctId, acctType=fawry_channel.fawry_acctType,
                           acctKey=fawry_channel.fawry_acctKey, secureAcctKey=fawry_channel.fawry_secureAcctKey, acctCur=fawry_channel.fawry_acctCur)

        result = {}
        custLangPref = 'en-gb'
        if lang == 'ar_AA' or (lang != 'en_US' and self.env.user.lang == 'ar_AA'):
            custLangPref = 'ar-eg'
        result_bill = srm.pay_bill(custLangPref, suppressEcho, billTypeCode,
                                   billingAcct, extraBillingAcctKeys,
                                   amt, curCode, pmtMethod,
                                   notifyMobile, billRefNumber,
                                   billerId, pmtType)
        if result_bill.get('pmtInfoValType'):
            result['Success'] = result_bill['pmtInfoValType']
        else:
            result = result_bill

        return result
