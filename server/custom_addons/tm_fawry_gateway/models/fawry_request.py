# -*- coding: utf-8 -*-
# This module and its content is copyright of Tamayozsoft.
# - © Tamayozsoft 2020. All rights reserved.

import logging
import os
from datetime import datetime
import uuid

import suds
from suds.client import Client
from suds.plugin import MessagePlugin

SUDS_VERSION = suds.__version__


_logger = logging.getLogger(__name__)
# uncomment to enable logging of SOAP requests and responses
# logging.getLogger('suds.transport').setLevel(logging.DEBUG)


FAWRY_ERROR_MAP = {
    '1': "Failed to log received Data.",
    '2': "No Log Storage Configured.",
    '3': "Configured Log Storage is not Accessible.",
    '4': "Unknown Message Type.",
    '5': "Failed to Transform Message.",
    '6': "Sender is not authorized.",
    '7': "Message Not Valid.",
    '8': "Function Not Available.",
    '9': "Unsupported Service.",
    '10': "Unsupported Message.",
    '11': "Unsupported Function.",
    '12': "Required Element Not Included.",
    '13': "Duplicate <RqUID>.",
    '14': "Field not found.",
    '15': "Message type not exists.",
    '16': "Missing elements.",
    '17': "Wrong element data type.",
    '18': "Element Amount Value Out of Range.",
    '19': "Element location is not valid.",
    '20': "Sign in to destination failed.",
    '21': "Biller Timeout",
    '23': "Asynchronous Request Does Not Match Original Request",
    '24': "DateTime Too Far In Future",
    '25': "General Data Error",
    '26': "General Error",
    '27': "Invalid  Biller Id",
    '28': "Invalid DateTime - Single date or Low of Range",
    '29': "Invalid DateTime Range",
    '30': "Invalid Enum Value",
    '31': "Message Authentication Error",
    '32': "None of Selection Criteria Supported",
    '33': "Request Denied",
    '34': "Service not Enabled",
    '35': "The <Cursor> returned within <RecCtrlIn> is invalid or has expired",
    '36': "Usage Limit Exceeded",
    '37': "Message version is not valid or not supported.",
    '39': "Invalid Bill Type Code",
    '40': "Invalid Transaction State",
    '41': "Biller is unauthorized or In-Active",
    '42': "Bank is unauthorized or In-Active",
    '51': "EBPP Switch Timeout ",
    '61': "EBPP Gateway Timeout",
    '11001': "Failed to Retrieve Billers\ Operators List",
    '12002': "In-Active Customer Account",
    '12006': "Bill account is not available at biller repository.",
    '12007': "Biller request customer to contact the biller offices.",
    '12008': "Failed to retrieve bill information due to system error.",
    '12009': "Billing account does not allow the payment through this channel.",
    '12010': "Failed to fetch payment rules due to some system error.",
    '12011': "Invalid Billing Account Number.",
    '12012': "Failed to get payment business rules for this bill type.",
    '12013': "Invalid Bill Number.",
    '21001': "Bill Account Number Strucure Error",
    '21002': "Biller Is Not authorized or In-Active.",
    '21003': "Bank Is Not authorized or In-Active.",
    '21004': "Payment Amount validation Error",
    '21005': "Connection Time Out or Biller unreachable",
    '21006': "Bill Validation Failed",
    '21007': "You are not authorized to access this service",
    '21008': "Gateway Connection time out",
    '21009': "Bill not allowed for payment. Previous bills should be paid.",
    '21010': "Payment Amount Exceeds Due Payment amount.",
    '21011': "Payment Amount is less than Due Payment amount.",
    '21012': "Bill not available for payment.",
    '21013': "Invalid Billing Account.",
    '21014': "Invalid Bill Number.",
    '21015': "Bill not allowed for payment. Previous bills should be paid.",
    '21016': "Payment Amount Exceeds Due Payment amount.",
    '21017': "Payment Amount is less than Due Payment amount.",
    '21018': "Bill not available for payment.",
    '21019': "Fawry Payment Amount Exceeds Due Payment amount.",
    '21020': "Fawry Payment Amount is less than Due Payment amount.",
    '21021': "duplicate payment transaction.",
    '21090': "Vehicle License Renewal Fees should be paid first",
    '22001': "Payment Not Valid.",
    '22002': "Biller is unauthorized or in-active.",
    '22003': "Bank is unauthorized or in-active.",
    '22004': "Payment Amount validation Error",
    '22005': "Invalid Channel Type Code.",
    '22006': "Payment is already advised.",
    '22007': "Mismatch in payment & Advice Amounts.",
    '22008': "Gateway Connection time out",
    '22009': "Payment Advice Request Failed",
    '22010': "Invalid Billing Account.",
    '22011': "Invalid Bill Number.",
    '24002': "Transaction will be delayed.",
    '24003': "Payment Rejected From Biller",
    '24004': "Payment Reversal Rejected by Biller",
    '24005': "No Response From Biller",
    '31001': "Source Account Invalid",
    '31002': "Source Account Not Eligible For Transaction",
    '31004': "Insufficient Funds.",
    '31005': "Collection Account Invalid.",
    '31006': "Daily Limit Exceeded",
    '32201': "Message Accepted for Asynchronous Processing.",
    '22012': "Failed to Process Payment. General Error.",
    '23001': "Invalid transaction.",
    '23002': "Tranaction already Confirmed.",
    '23101': "Payment Advice In Progress .",
    '32001': "Reverse Request Does Not Match Original Debit Request.",
    '32002': "Reverse Request is for invalid Debit transaction.",
    '32003': "Failed to reverse payment.",
    '32004': "Invalid Source Account (From account).",
    '32005': "Invalid Collection Account (To account).",
    '32006': "Reverse Payment request declined.",
    '33101': "No Transactions Exists for Requested Date.",
    '33001': "FAWRY EBPP Cut off request received for Reconciliation Date with Payment Totals Log already sent.",
    '34001': "Wrong Reconciliation Date.",
    '34002': "Totals Already Received.",
    '35101': "No Transactions exists",
    '35001': "Wrong Reconciliation date requested",
    '35002': "Waiting to Send Payment Totals Log",
    '35003': "Received Bill Type Totals not belongs to the current reconciliation date.",
    '36001': "Wrong Reconciliation Date",
    '36002': "Details are not for the targeted Bill Type",
    '36003': "Details Already Received",
    '37001': "Failed to Transfer Reconciled Bill amounts",
    '37002': "Wrong reconciliation date requested",
    '37003': "Waiting to Send Payment Totals Log",
    '37004': "Received Bill Type Totals not belongs to the current reconciliation date.",
    '41001': "Wrong Reconciliation Date",
    '38001': "Wrong Settlement Date",
    '38101': "Settlement Report Already Received",
}

class LogPlugin(MessagePlugin):
    """ Small plugin for suds that catches out/ingoing XML requests and logs them"""
    def __init__(self, debug_logger):
        self.debug_logger = debug_logger

    def sending(self, context):
        self.debug_logger(context.envelope, 'fawry_request')

    def received(self, context):
        self.debug_logger(context.reply, 'fawry_response')

'''
class FixRequestNamespacePlug(MessagePlugin):
    def __init__(self, root):
        self.root = root

    def marshalled(self, context):
        context.envelope = context.envelope.prune()
'''

class FAWRYRequest():
    def __init__(self, debug_logger, endurl,
                 sender, receiver, version, originatorCode, terminalId, deliveryMethod,                             # msgCode: BillerInqRq, BillInqRq and PmtAddRq
                 profileCode=None,                                                                                  # msgCode: BillerInqRq
                 bankId=None,                                                                                       # msgCode: BillInqRq and PmtAddRq
                 acctId=None, acctType=None, acctKey=None, secureAcctKey=None, acctCur=None, posSerialNumber=None   # msgCode: PmtAddRq
                 ):
        self.debug_logger = debug_logger
        # Production and Testing url
        self.endurl = endurl

        # Basic detail require to authenticate
        self.sender = sender                         # sender: SmartPay2_MOB                      ==> Per Channel
        self.receiver = receiver                     # receiver: SmartPay2
        self.version = version                       # version: V1.0
        self.originatorCode = originatorCode         # originatorCode: SmartPay2
        self.terminalId = terminalId                 # terminalId: 104667                         ==> Per Channel
        self.deliveryMethod = deliveryMethod         # DeliveryMethod: MOB                        ==> Per Channel
        if profileCode:
            self.profileCode = profileCode           # ProfileCode: 22013                         ==> Per Channel
        if acctId:
            self.acctId = acctId                     # acctId: 104667                             ==> Per Channel
        if bankId:
            self.bankId = bankId                     # bankId: SmartPay2
        if acctType:
            self.acctType = acctType                 # acctType: SDA                             ==> Per Channel
        if acctKey:
            self.acctKey = acctKey                   # acctKey: 1234                             ==> Per Channel
        if secureAcctKey:
            self.secureAcctKey = secureAcctKey       # secureAcctKey: gdyb21LQTcIANtvYMT7QVQ==   ==> Per Channel
        if acctCur:
            self.acctCur = acctCur.name              # acctCur: EGP                              ==> Per Channel
        self.posSerialNumber = posSerialNumber       # posSerialNumber: 332-491-1222             ==> Per Channel

        self.wsdl = '../api/ApplicationBusinessFacadeService.wsdl'

    '''
        def _add_security_header(self, client, namspace):
            # # set the detail which require to authenticate

            # security_ns = ('tns', 'http://www.fawry-eg.com/ebpp/IFXMessages/')
            # security = Element('UPSSecurity', ns=security_ns)

            # username_token = Element('UsernameToken', ns=security_ns)
            # username = Element('Username', ns=security_ns).setText(self.username)
            # password = Element('Password', ns=security_ns).setText(self.password)
            # username_token.append(username)
            # username_token.append(password)

            # service_token = Element('ServiceAccessToken', ns=security_ns)
            # license = Element('AccessLicenseNumber', ns=security_ns).setText(self.access_number)
            # service_token.append(license)

            # security.append(username_token)
            # security.append(service_token)

            # client.set_options(soapheaders=security)

            self.SignonProfileType = self.client.factory.create('{}:SignonProfileType'.format(namespace))
            self.SignonProfileType.Sender = self.sender
            self.SignonProfileType.Receiver = self.receiver
            self.SignonProfileType.MsgCode = self.msgCode
            self.SignonProfileType.Version = self.version
        '''

    def _set_client(self, wsdl
                    # , api, root
                    ):
        wsdl_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), wsdl)
        # _logger.info("wsdl             >>>>>>>>>>>>>>>>>>>>> " + wsdl)
        # _logger.info("wsdl_path        >>>>>>>>>>>>>>>>>>>>> " + wsdl_path)
        # _logger.info("wsdl_path.lstrip >>>>>>>>>>>>>>>>>>>>> " + 'file:///%s' % wsdl_path.lstrip('/'))
        # _logger.info("endurl           >>>>>>>>>>>>>>>>>>>>> " + self.endurl)
        client = Client('file:///%s' % wsdl_path.lstrip('/'),
                        # plugins=[FixRequestNamespacePlug(root), LogPlugin(self.debug_logger)]
                        plugins=[LogPlugin(self.debug_logger)]
                        )
        # self._add_security_header(client)
        client.set_options(location='%s'
                                    # '%s'
                                    % (self.endurl
                                       # , api
                                       ))
        # _logger.info("client           >>>>>>>>>>>>>>>>>>>>> " + str(client))
        return client

    def get_error_message(self, error_code, description):
        result = {}
        result['error_message'] = FAWRY_ERROR_MAP.get(error_code)
        if not result['error_message']:
            result['error_message'] = description
        return result

    def _buildRequest(self, client, msgCode, custLangPref, suppressEcho, namespace,
                      pmtType=None, billTypeCode=None, billingAcct=None, extraBillingAcctKeys=None,   # msgCode: BillInqRq, PmtAddRq
                      amt=None, curCode=None, pmtMethod=None, notifyMobile=None,                      # msgCode: PmtAddRq
                      billRefNumber=None,                                                             # msgCode: PmtAddRq & pmtType: POST
                      billerId=None,                                                                  # msgCode: PmtAddRq & pmtType: PREP
                      ): # BillInqRq: IsRetry, IncOpenAmt => False, BillerId, PmtType => PREP
                         # PmtAddRq: IsRetry, billerId, pmtType
        '''
        # FAWRY JAVA Example Code
        FAWRYType fawryType = new FAWRYType();

		SignonRqType signonRqType = new SignonRqType();
        GregorianCalendar gcal = new GregorianCalendar();
        XMLGregorianCalendar xgcal = DatatypeFactory.newInstance().newXMLGregorianCalendar(gcal);
		signonRqType.setClientDt(xgcal);
		signonRqType.setCustLangPref("en-gb");
		signonRqType.setSuppressEcho(true);
		'''
        signonRqType = client.factory.create('{}:SignonRqType'.format(namespace))
        signonRqType.ClientDt = datetime.now()
        signonRqType.CustLangPref = custLangPref  # 'ar-eg' or 'en-gb'
        signonRqType.SuppressEcho = suppressEcho  # False

        '''
        # FAWRY JAVA Example Code
		SignonProfileType signonProfileType = new SignonProfileType();

		signonProfileType.setMsgCode("PmtAddRq"); /* SignonRq*/ // BillerInqRq, BillInqRq or PmtAddRq
		signonProfileType.setReceiver("%Configuration Value will be provided by Fawry%");
		signonProfileType.setVersion("V1.0");
		signonProfileType.setSender("%Configuration Value will be provided by Fawry%");
		signonRqType.setSignonProfile(signonProfileType); /* SignonRq*/
		'''
        signonProfileType = client.factory.create('{}:SignonProfileType'.format(namespace))
        signonProfileType.Sender = self.sender     # ("%Configuration Value will be provided by Fawry%")
        signonProfileType.Receiver = self.receiver # ("%Configuration Value will be provided by Fawry%")
        signonProfileType.MsgCode = msgCode        # BillerInqRq, BillInqRq or PmtAddRq
        signonProfileType.Version = self.version
        signonRqType.SignonProfile = signonProfileType

        msgRqHdrType = client.factory.create('{}:MsgRqHdrType'.format(namespace))
        networkTrnInfoType = client.factory.create('{}:NetworkTrnInfoType'.format(namespace))
        networkTrnInfoType.OriginatorCode = self.originatorCode  # ("%Configuration Value will be provided by Fawry%")
        networkTrnInfoType.TerminalId = self.terminalId          # ("%Configuration Value will be provided by Fawry%")
        msgRqHdrType.NetworkTrnInfo = networkTrnInfoType

        '''
        # FAWRY JAVA Example Code
		// BillerInqRq, BillInqRq
			PresSvcRqType presSvcRqType = new PresSvcRqType();
			presSvcRqType.setRqUID(java.util.UUID.randomUUID().toString());

			// BillerInqRq
				//presSvcRqType.setAsyncRqUID(java.util.UUID.randomUUID().toString());
				BillerInqRqType billerInqRqType = new BillerInqRqType();
				billerInqRqType.setDeliveryMethod("INT");
				billerInqRqType.setReturnLogos(true);
				billerInqRqType.setReturnBillingFreqCycles(true);
				billerInqRqType.setReturnPaymentRanges(true);
				presSvcRqType.setBillerInqRq(billerInqRqType);

			// BillInqRq
				BillInqRqType billInqRqType = new BillInqRqType();
				billInqRqType.setPmtType("POST");
				billInqRqType.setDeliveryMethod("INT");
				billInqRqType.setBillTypeCode(155L);
				presSvcRqType.setBillInqRq(billInqRqType);
		'''
        if msgCode == "BillerInqRq" or msgCode == "BillInqRq":
            presSvcRqType = client.factory.create('{}:PresSvcRqType'.format(namespace))
            presSvcRqType.RqUID = str(uuid.uuid1())
            presSvcRqType.MsgRqHdr = msgRqHdrType

            if msgCode == "BillerInqRq":
                billerInqRqType = client.factory.create('{}:BillerInqRqType'.format(namespace))
                billerInqRqType.DeliveryMethod = self.deliveryMethod
                billerInqRqType.ReturnLogos = True
                billerInqRqType.ReturnBillingFreqCycles = True
                billerInqRqType.ReturnPaymentRanges = True
                presSvcRqType.BillerInqRq = billerInqRqType

            if msgCode == "BillInqRq":
                billInqRqType = client.factory.create('{}:BillInqRqType'.format(namespace))
                if pmtType:
                    billInqRqType.PmtType = pmtType # POST, PREP or VOCH
                billInqRqType.DeliveryMethod = self.deliveryMethod
                billInqRqType.BillTypeCode = billTypeCode
                if extraBillingAcctKeys:
                    extraBillingAcctKeysType = client.factory.create('{}:ExtraBillingAcctKeysType'.format(namespace))
                    extraBillingAcctKeysList = []
                    for extraBillingAcctKey in extraBillingAcctKeys:
                        extraBillingAcctKeyType = client.factory.create('{}:ExtraBillingAcctKeyType'.format(namespace))
                        extraBillingAcctKeyType.Key = extraBillingAcctKey.get("Key")
                        extraBillingAcctKeyType.Value = extraBillingAcctKey.get("Value")
                        extraBillingAcctKeysList.append(extraBillingAcctKeyType)
                    extraBillingAcctKeysType.ExtraBillingAcctKey = extraBillingAcctKeysList
                    billInqRqType.ExtraBillingAcctKeys = extraBillingAcctKeysType
                billInqRqType.BankId = self.bankId
                billInqRqType.BillingAcct = billingAcct  # 01200000200
                billInqRqType.IncOpenAmt = True
                presSvcRqType.BillInqRq = billInqRqType


        '''
        # FAWRY JAVA Example Code
		// PmtAddRq
			PaySvcRqType paySvcRqType = new PaySvcRqType();
			paySvcRqType.setRqUID(java.util.UUID.randomUUID().toString());  /* PaySvcRq */
			paySvcRqType.setAsyncRqUID("a74419c9-02cf-4104-b2ea-5f3b757036e1");  /* Received in BillInqRs */

			MsgRqHdrType msgRqHdrType = new MsgRqHdrType();
			NetworkTrnInfoType networkTrnInfoType = new NetworkTrnInfoType();

			networkTrnInfoType.setOriginatorCode("%Configuration Value will be provided by Fawry%");
			msgRqHdrType.setNetworkTrnInfo(networkTrnInfoType);

			PmtAddRqType pmtAddRqType = new PmtAddRqType();
			PmtInfoType pmtInfoType = new PmtInfoType(); /* PmtAddRq */

			// PmtAddRq -- Post Paid
				pmtInfoType.setBillingAcct("01200000200");
				pmtInfoType.setBillRefNumber("f16e2fa1-2611-42fc-80aa-4b12e84c6b96");  /* Received in BillInqRs */

			// PmtAddRq -- Pre Paid
				pmtInfoType.setBillerId("1");
				pmtInfoType.setBillingAcct("01000000200");//01012341254
				pmtInfoType.setPmtType(PmtTypeEnum.PREP);

			pmtInfoType.setBillTypeCode(111L);
			pmtInfoType.setDeliveryMethod("INT");

			CurAmtType curAmtType = new CurAmtType();
			curAmtType.setAmt(new BigDecimal(100));
			curAmtType.setCurCode("EGP");

			pmtInfoType.setCurAmt(curAmtType);

			pmtInfoType.setProfileCode("165");
			pmtInfoType.setBankId("%Configuration Value will be provided by Fawry%");

			DepAcctIdFromType depAcctIdFromType = new DepAcctIdFromType();
			depAcctIdFromType.setAcctId("101755");
			depAcctIdFromType.setAcctCur("EGP");

			pmtInfoType.setDepAccIdFrom(depAcctIdFromType);
			pmtInfoType.setPmtMethod(("CASH"));

			pmtAddRqType.getPmtInfo().add(pmtInfoType);

			paySvcRqType.setPmtAddRq(pmtAddRqType);
			paySvcRqType.setMsgRqHdr(msgRqHdrType);

			XMLGregorianCalendar xgcal2 = DatatypeFactory.newInstance().newXMLGregorianCalendar(gcal);
			pmtInfoType.setPrcDt(xgcal2);
		'''
        if msgCode == "PmtAddRq":
            paySvcRqType = client.factory.create('{}:PaySvcRqType'.format(namespace))
            paySvcRqType.RqUID = str(uuid.uuid1())
            paySvcRqType.AsyncRqUID = str(uuid.uuid1()) # FYI: Received in BillInqRs

            if self.posSerialNumber:
                customPropertiesType = client.factory.create('{}:CustomPropertiesType'.format(namespace))
                customPropertiesList = []
                customPropertyType = client.factory.create('{}:CustomPropertyType'.format(namespace))
                customPropertyType.Key = 'PosSerialNumber'
                customPropertyType.Value = self.posSerialNumber
                customPropertiesList.append(customPropertyType)
                customPropertiesType.CustomProperty = customPropertiesList
                msgRqHdrType.CustomProperties = customPropertiesType

            paySvcRqType.MsgRqHdr = msgRqHdrType

            pmtAddRqType = client.factory.create('{}:PmtAddRqType'.format(namespace))
            pmtInfoType = client.factory.create('{}:PmtInfoType'.format(namespace))

            pmtInfoType.BillingAcct = billingAcct  # 01200000200
            if extraBillingAcctKeys:
                extraBillingAcctKeysType = client.factory.create('{}:ExtraBillingAcctKeysType'.format(namespace))
                extraBillingAcctKeysList = []
                for extraBillingAcctKey in extraBillingAcctKeys:
                    extraBillingAcctKeyType = client.factory.create('{}:ExtraBillingAcctKeyType'.format(namespace))
                    extraBillingAcctKeyType.Key = extraBillingAcctKey.get("Key")
                    extraBillingAcctKeyType.Value = extraBillingAcctKey.get("Value")
                    extraBillingAcctKeysList.append(extraBillingAcctKeyType)
                extraBillingAcctKeysType.ExtraBillingAcctKey = extraBillingAcctKeysList
                pmtInfoType.ExtraBillingAcctKeys = extraBillingAcctKeysType

            if notifyMobile:
                pmtInfoType.NotifyMobile = notifyMobile

            if pmtType == "POST" or billRefNumber:
                pmtInfoType.BillRefNumber = billRefNumber # Received in BillInqRs
            elif pmtType == "PREP":
                pmtInfoType.BillerId = billerId
                pmtInfoType.PmtType = pmtType;

            pmtInfoType.BillTypeCode =  billTypeCode # 111L
            pmtInfoType.DeliveryMethod = self.deliveryMethod

            curAmtType = client.factory.create('{}:CurAmtType'.format(namespace))
            curAmtType.Amt = amt         # new BigDecimal(100)
            curAmtType.CurCode = curCode # "EGP"

            pmtInfoType.CurAmt = curAmtType
            pmtInfoType.BankId = self.bankId           # ("%Configuration Value will be provided by Fawry%")

            depAcctIdFromType = client.factory.create('{}:DepAcctIdFromType'.format(namespace))
            depAcctIdFromType.AcctId = self.acctId     # "101755"
            depAcctIdFromType.AcctType = self.acctType # "SDA"
            depAcctIdFromType.AcctKey = self.acctKey   # "1234"
            depAcctIdFromType.AcctCur = self.acctCur   # "EGP"

            pmtInfoType.DepAccIdFrom = depAcctIdFromType
            pmtInfoType.PmtMethod = pmtMethod # "CASH"
            pmtInfoType.PrcDt = datetime.now()

            pmtAddRqType.PmtInfo = pmtInfoType

            paySvcRqType.PmtAddRq = pmtAddRqType

        '''
        # FAWRY JAVA Example Code
		RequestType requestType = new RequestType();
		requestType.setSignonRq(signonRqType);

		// BillerInqRq, BillInqRq
			requestType.setPresSvcRq(presSvcRqType);
		// PmtAddRq
			requestType.setPaySvcRq(paySvcRqType);

		fawryType.setRequest(requestType);

		return fawryType;
        '''
        requestType = client.factory.create('{}:RequestType'.format(namespace))
        requestType.SignonRq = signonRqType

        if msgCode == "BillerInqRq" or msgCode == "BillInqRq":
            requestType.PresSvcRq = presSvcRqType
        elif msgCode == "PmtAddRq":
            requestType.PaySvcRq = paySvcRqType

        fawryType = client.factory.create('{}:FAWRYType'.format(namespace))
        fawryType.Request = requestType

        return fawryType

    def _buildResponse(fawryType):
        '''
        # FAWRY JAVA Example Code
        SignonRsType  signonRsType= fawryType.getResponse().getSignonRs();
		System.out.println("Client Date: "+ signonRsType.getClientDt());
		System.out.println("Customer Language: "+ signonRsType.getCustLangPref());
		System.out.println("Server Language: "+ signonRsType.getLanguage());
		System.out.println("Server Date: "+ signonRsType.getServerDt());

		SignonProfileType signonProfileType=signonRsType.getSignonProfile();
		System.out.println("Message Code: "+ signonProfileType.getMsgCode());
		System.out.println("Reciever: "+ signonProfileType.getReceiver());
		System.out.println("Sender: "+ signonProfileType.getSender());
		System.out.println("Version: "+ signonProfileType.getVersion());

		ResponseType responseType = fawryType.getResponse();
		// BillerInqRq, BillInqRq
			PresSvcRsType presSvcRsType= responseType.getPresSvcRs();
			StatusType statusType = presSvcRsType.getStatus();
			MsgRqHdrType msgRqHdrType = presSvcRsType.getMsgRqHdr();
		// PmtAddRq
			PaySvcRsType paySvcRsType= responseType.getPaySvcRs();
			StatusType statusType = paySvcRsType.getStatus();
			MsgRqHdrType msgRqHdrType = paySvcRsType.getMsgRqHdr();
		System.out.println("Status Code: "+ statusType.getStatusCode());
		System.out.println("Status Desc: "+ statusType.getStatusDesc());
		System.out.println("Status Severity: "+ statusType.getSeverity());

		if(msgRqHdrType!=null)
		{
			List<CustomPropertyType> customPropertyTypes= msgRqHdrType.getCustomProperties().getCustomProperty();
			if(customPropertyTypes!=null)
			{
				for(CustomPropertyType customPropertyType: customPropertyTypes)
				{
					System.out.println("Customer Property Key: "+ customPropertyType.getKey());
					System.out.println("Customer Property Value: "+ customPropertyType.getValue());
				}
			}
		}

		// BillerInqRq
		BillerInqRsType billerInqRsType = presSvcRsType.getBillerInqRs();
		System.out.println("Biller Payment Type: "+ billerInqRsType.getPmtType());
		System.out.println("Biller Delivery Method: "+ billerInqRsType.getDeliveryMethod());
		System.out.println("Biller Service Type: "+ billerInqRsType.getServiceType());

		List<BillerRecType> billerRecTypes =billerInqRsType.getBillerRec();
		if(billerRecTypes!=null)
		{
			for(BillerRecType billerRecType:billerRecTypes)
			{
				System.out.println(" ====================================== Biller Data Begin "+ billerRecType.getBillerId() +" =========================================");
				System.out.println("Biller ID: "+ billerRecType.getBillerId());
				System.out.println("Biller Name: "+ billerRecType.getBillerName());
				System.out.println("Biller Name Language: "+ billerRecType.getBillerNameLang());
				System.out.println("Biller Status: "+ billerRecType.getBillerStatus());

				List<BillerInfoType> billerInfoTypes = billerRecType.getBillerInfo();
				if(billerInfoTypes!=null)
				{
					for(BillerInfoType billerInfoType :billerInfoTypes)
					{
						System.out.println("Bill Type Account Label: "+ billerInfoType.getBillTypeAcctLabel());
						System.out.println("Bill Type Code: "+ billerInfoType.getBillTypeCode());
						System.out.println("Bill Type Status: "+ billerInfoType.getBillTypeStatus());
						System.out.println("Extra Info: "+ billerInfoType.getExtraInfo());
						System.out.println("Biller Service Name: "+ billerInfoType.getName());
						System.out.println("Biller Service Name Language: "+ billerInfoType.getNameLang());
						System.out.println("Biller Payment Type: "+ billerInfoType.getPmtType());
						System.out.println("Bill Type Code: "+ billerInfoType.getBillTypeCode());
						System.out.println("Service Type: "+ billerInfoType.getServiceType());
						System.out.println("Type: "+ billerInfoType.getType());
						System.out.println("Receipt Footer: "+ billerInfoType.getReceiptFooter());
						System.out.println("Receipt Footer Language: "+ billerInfoType.getReceiptFooterLang());
						System.out.println("Receipt Header: "+ billerInfoType.getReceiptHeader());
						System.out.println("Receipt Header Language: "+ billerInfoType.getReceiptHeaderLang());

						System.out.println("Service Name: "+ billerInfoType.getServiceName());
						System.out.println("Expiry Date: "+ billerInfoType.getExpiryDate());
						System.out.println("Start Date: "+ billerInfoType.getStartDate());

						List<PaymentRangeType> paymentRangeTypes =  billerInfoType.getPaymentRanges().getPaymentRangeType();
						if(paymentRangeTypes!=null)
						{
							for(PaymentRangeType paymentRangeType :paymentRangeTypes)
							{
								System.out.println("Payment Lower Amount: "+ paymentRangeType.getLower().getAmt());
								System.out.println("Payment Lower Currency Code: "+ paymentRangeType.getLower().getCurCode());
								System.out.println("Payment Upper Amount: "+ paymentRangeType.getUpper().getAmt());
								System.out.println("Payment Upper Currency Code: "+ paymentRangeType.getUpper().getCurCode());
							}
						}

						List<TierType> tierTypes = billerInfoType.getFees().getTier();

						if(tierTypes!=null)
						for(TierType tierType : tierTypes)
						{
							System.out.println("Fees Expiry Date: "+tierType.getExpiryDate());
							System.out.println("Fees Start Date: "+tierType.getStartDate());
							System.out.println("Fees Fixed Amount Currency Code: "+tierType.getFixedAmt().getCurCode());
							System.out.println("Fees Fixed Amount: "+tierType.getFixedAmt().getAmt());
							System.out.println("Fees Lower Amount: "+tierType.getLowerAmt());
							System.out.println("Fees Percent: "+tierType.getPercent());
							System.out.println("Fees Upper Amount: "+tierType.getUpperAmt());
						}
					}
				}
				System.out.println(" ====================================== Biller Data End "+ billerRecType.getBillerId() +" =========================================");
			}
		}

		// BillInqRq
		BillInqRsType billInqRsType = presSvcRsType.getBillInqRs();
		if(billInqRsType!=null)
		{
			System.out.println("Payment Type: "+ billInqRsType.getPmtType());
			System.out.println("Delivery Method: "+ billInqRsType.getDeliveryMethod());
			System.out.println("Service Type: "+ billInqRsType.getServiceType());


			List<BillRecType> billRecTypes = billInqRsType.getBillRec();
			if(billRecTypes!=null)
			{
				for(BillRecType billRecType: billRecTypes)
				{
					System.out.println("Biller Id: "+ billRecType.getBillerId());
					System.out.println("Billing Account: "+ billRecType.getBillingAcct());
					System.out.println("Bill Number: "+ billRecType.getBillNumber());
					System.out.println("Bill Ref Number: "+ billRecType.getBillRefNumber());
					System.out.println("Bill Status: "+ billRecType.getBillStatus());
					System.out.println("Bill Type Code: "+ billRecType.getBillTypeCode());

					BillInfoType billInfoTypes=billRecType.getBillInfo();
					System.out.println("Bill Category: "+ billInfoTypes.getBillCategory());
					System.out.println("Bill Due Date: "+ billInfoTypes.getDueDt());
					System.out.println("Bill Issue Date: "+ billInfoTypes.getIssueDt());
					System.out.println("Bill Expiry Date: "+ billInfoTypes.getExpDt());
					System.out.println("Extra Bill Info: "+ billInfoTypes.getExtraBillInfo());

					List<BillSummAmtType> billSummAmtTypes = billInfoTypes.getBillSummAmt();
					if(billSummAmtTypes!=null)
					for(BillSummAmtType billSummAmtType:billSummAmtTypes)
					{
						System.out.println("Bill Sum Amount Code: "+ billSummAmtType.getBillSummAmtCode());
						System.out.println("Bill Amount Curency Code: "+ billSummAmtType.getCurAmt().getCurCode());
						System.out.println("Bill Amount: "+ billSummAmtType.getCurAmt().getAmt());
					}

					List<PaymentRangeType> paymentRangeTypes= billInfoTypes.getPaymentRange();
					if(paymentRangeTypes!=null)
					for(PaymentRangeType paymentRangeType:paymentRangeTypes)
					{
						System.out.println("Range Lower Amount: "+ paymentRangeType.getLower().getAmt());
						System.out.println("Range Lower Amount Currency: "+ paymentRangeType.getLower().getCurCode());
						System.out.println("Range Upper Amount: "+ paymentRangeType.getUpper().getAmt());
						System.out.println("Range Upper Amount Currency: "+ paymentRangeType.getUpper().getCurCode());
					}
				}
			}
		}

		// PmtAddRq
			PmtAddRsType pmtAddRsType= fawryType.getResponse().getPaySvcRs().getPmtAddRs();

			List<CustIdType> custIdTypes = pmtAddRsType.getCustId();
			if(custIdTypes!=null)
				for(CustIdType custIdType:custIdTypes)
				{
					System.out.println("Official ID: "+ custIdType.getOfficialId());
					System.out.println("Official ID Type: "+ custIdType.getOfficialIdType());
				}

			List<PmtInfoValType> pmtInfoValTypes = pmtAddRsType.getPmtInfoVal();
			if(pmtInfoValTypes!=null)
			{
				for(PmtInfoValType pmtInfoValType: pmtInfoValTypes)
				{
					PmtInfoType pmtInfoType = pmtInfoValType.getPmtInfo();
					System.out.println("Biller ID: "+ pmtInfoType.getBillerId());
					System.out.println("Billing Account: "+ pmtInfoType.getBillingAcct());
					System.out.println("Bill Number: "+ pmtInfoType.getBillNumber());
					System.out.println("Bill Ref Number: "+ pmtInfoType.getBillRefNumber());
					System.out.println("Bill Type Code: "+ pmtInfoType.getBillTypeCode());
					System.out.println("Delivery Method: "+ pmtInfoType.getDeliveryMethod());
					System.out.println("Extra Bill Info: "+ pmtInfoType.getExtraBillInfo());
					System.out.println("Issue Date: "+ pmtInfoType.getIssueDt());
					System.out.println("Is Notify Mobile: "+ pmtInfoType.getNotifyMobile());
					System.out.println("Payment Description: "+ pmtInfoType.getPmtDesc());
					System.out.println("Payment Method: "+ pmtInfoType.getPmtMethod());
					System.out.println("Payment Processing Date: "+ pmtInfoType.getPrcDt());
					System.out.println("Amount Currency Code: "+ pmtInfoType.getCurAmt().getCurCode());
					System.out.println("Amount: "+ pmtInfoType.getCurAmt().getAmt());

					 List<ExtraBillingAcctKeyType> acctKeyTypes = pmtInfoType.getExtraBillingAcctKeys().getExtraBillingAcctKey();
					 if(acctKeyTypes!=null)
					  for(ExtraBillingAcctKeyType acctKeyType: acctKeyTypes){
						 System.out.println("Extra Billing Account Key: "+ acctKeyType.getKey());
						 System.out.println("Extra Billing Account Value: "+ acctKeyType.getValue());
					 }

					 FeesAmtType feesAmtType = pmtInfoType.getFeesAmt();
					 System.out.println("Fees Currency Code: "+ feesAmtType.getCurCode());
					 System.out.println("Fees Amount: "+ feesAmtType.getAmt());

					List<PmtTransIdType> pmtTransIdTypes= pmtInfoType.getPmtTransId();
					if(pmtTransIdTypes!=null)
						  for(PmtTransIdType pmtTransIdType: pmtTransIdTypes){
							 System.out.println("Payment Transaction Creation Date: "+ pmtTransIdType.getCreatedDt());
							 System.out.println("Payment ID: "+ pmtTransIdType.getPmtId());
							 System.out.println("Payment ID Type: "+ pmtTransIdType.getPmtIdType());
						 }
				}
			}
        '''
        responseType = fawryType.Response

        signonRsType = responseType.SignonRs
        _logger.info("Client Date: "+ signonRsType.ClientDt)
        _logger.info("Customer Language: "+ signonRsType.CustLangPref)
        _logger.info("Server Language: "+ signonRsType.Language)
        _logger.info("Server Date: "+ signonRsType.ServerDt)

        signonProfileType = signonRsType.SignonProfile
        _logger.info("Message Code: "+ signonProfileType.MsgCode)
        _logger.info("Reciever: "+ signonProfileType.Receiver)
        _logger.info("Sender: "+ signonProfileType.Sender)
        _logger.info("Version: "+ signonProfileType.Version)
        if signonProfileType.MsgCode == "BillerInqRq" or signonProfileType.MsgCode == "BillInqRq":
            presSvcRsType= responseType.PresSvcRs
            statusType = presSvcRsType.Status
            msgRqHdrType = presSvcRsType.MsgRqHdr
        elif signonProfileType.MsgCode == "PmtAddRq":
            paySvcRsType= responseType.PaySvcRs
            statusType = paySvcRsType.Status
            msgRqHdrType = paySvcRsType.MsgRqHdr

        _logger.info("Status Code: "+ statusType.StatusCode)
        _logger.info("Status Desc: "+ statusType.StatusDesc)
        _logger.info("Status Severity: "+ statusType.Severity)

        if msgRqHdrType:
            customPropertyTypes= msgRqHdrType.CustomProperties.CustomProperty
            if customPropertyTypes:
                for customPropertyType in customPropertyTypes:
                    _logger.info("Customer Property Key: "+ customPropertyType.Key)
                    _logger.info("Customer Property Value: "+ customPropertyType.Value)

        if signonProfileType.MsgCode == "BillerInqRq":
            billerInqRsType = presSvcRsType.BillerInqRs
            _logger.info("Biller Payment Type: "+ billerInqRsType.PmtType)
            _logger.info("Biller Delivery Method: "+ billerInqRsType.DeliveryMethod)
            _logger.info("Biller Service Type: "+ billerInqRsType.ServiceType)

            billerRecTypes = billerInqRsType.BillerRec
            if billerRecTypes:
                for billerRecType in billerRecTypes:
                    _logger.info(" ====================================== Biller Data Begin "+ billerRecType.BillerId +" =========================================")
                    _logger.info("Biller ID: "+ billerRecType.BillerId)
                    _logger.info("Biller Name: "+ billerRecType.BillerName)
                    _logger.info("Biller Name Language: "+ billerRecType.BillerNameLang)
                    _logger.info("Biller Status: "+ billerRecType.BillerStatus)

                    billerInfoTypes = billerRecType.BillerInfo
                    if billerInfoTypes:
                        for billerInfoType in billerInfoTypes:
                            _logger.info("Biller Info Type: " + billerInfoType)
                            _logger.info("Bill Type Account Label: "+ billerInfoType.BillTypeAcctLabel)
                            _logger.info("Bill Type Code: "+ billerInfoType.BillTypeCode)
                            _logger.info("Bill Type Status: "+ billerInfoType.BillTypeStatus)
                            _logger.info("Extra Info: "+ billerInfoType.ExtraInfo)
                            _logger.info("Biller Service Name: "+ billerInfoType.Name)
                            _logger.info("Biller Service Name Language: "+ billerInfoType.NameLang)
                            _logger.info("Biller Payment Type: "+ billerInfoType.PmtType)
                            _logger.info("Bill Type Code: "+ billerInfoType.BillTypeCode)
                            _logger.info("Service Type: "+ billerInfoType.ServiceType)
                            _logger.info("Type: "+ billerInfoType.Type)
                            _logger.info("Receipt Footer: "+ billerInfoType.ReceiptFooter)
                            _logger.info("Receipt Footer Language: "+ billerInfoType.ReceiptFooterLang)
                            _logger.info("Receipt Header: "+ billerInfoType.ReceiptHeader)
                            _logger.info("Receipt Header Language: "+ billerInfoType.ReceiptHeaderLang)

                            _logger.info("Service Name: "+ billerInfoType.ServiceName)
                            _logger.info("Expiry Date: "+ billerInfoType.ExpiryDate)
                            _logger.info("Start Date: "+ billerInfoType.StartDate)

                            paymentRangeTypes =  billerInfoType.PaymentRanges.PaymentRangeType
                            if paymentRangeTypes:
                                for paymentRangeType in paymentRangeTypes:
                                    _logger.info("Payment Lower Amount: "+ paymentRangeType.Lower.Amt)
                                    _logger.info("Payment Lower Currency Code: "+ paymentRangeType.Lower.CurCode)
                                    _logger.info("Payment Upper Amount: "+ paymentRangeType.Upper.Amt)
                                    _logger.info("Payment Upper Currency Code: "+ paymentRangeType.Upper.CurCode)

                            tierTypes = billerInfoType.Fees.Tier
                            if tierTypes:
                                for tierType in tierTypes:
                                    _logger.info("Fees Expiry Date: "+tierType.ExpiryDate)
                                    _logger.info("Fees Start Date: "+tierType.StartDate)
                                    _logger.info("Fees Fixed Amount Currency Code: "+tierType.FixedAmt.CurCode)
                                    _logger.info("Fees Fixed Amount: "+tierType.FixedAmt.Amt)
                                    _logger.info("Fees Lower Amount: "+tierType.LowerAmt)
                                    _logger.info("Fees Percent: "+tierType.Percent)
                                    _logger.info("Fees Upper Amount: "+tierType.UpperAmt)

                    _logger.info(" ====================================== Biller Data End "+ billerRecType.BillerId +" =========================================")

        if signonProfileType.MsgCode == "BillInqRq":
            billInqRsType = presSvcRsType.BillInqRs
            if billInqRsType:
                _logger.info("Payment Type: "+ billInqRsType.PmtType)
                _logger.info("Delivery Method: "+ billInqRsType.DeliveryMethod)
                _logger.info("Service Type: "+ billInqRsType.ServiceType)

                billRecTypes = billInqRsType.BillRec
                if billRecTypes:
                    for billRecType in billRecTypes:
                        _logger.info(" ====================================== Bill Data Begin " + billRecType.BillerId + " =========================================")
                        _logger.info("Biller Id: "+ billRecType.BillerId)
                        _logger.info("Billing Account: "+ billRecType.BillingAcct)
                        _logger.info("Bill Number: "+ billRecType.BillNumber)
                        _logger.info("Bill Ref Number: "+ billRecType.BillRefNumber)
                        _logger.info("Bill Status: "+ billRecType.BillStatus)
                        _logger.info("Bill Type Code: "+ billRecType.BillTypeCode)

                        billInfoTypes=billRecType.BillInfo
                        _logger.info("Bill Category: "+ billInfoTypes.BillCategory)
                        _logger.info("Bill Due Date: "+ billInfoTypes.DueDt)
                        _logger.info("Bill Issue Date: "+ billInfoTypes.IssueDt)
                        _logger.info("Bill Expiry Date: "+ billInfoTypes.ExpDt)
                        _logger.info("Extra Bill Info: "+ billInfoTypes.ExtraBillInfo)

                        billSummAmtTypes = billInfoTypes.BillSummAmt
                        if billSummAmtTypes:
                            for billSummAmtType in billSummAmtTypes:
                                _logger.info("Bill Sum Amount Code: "+ billSummAmtType.BillSummAmtCode)
                                _logger.info("Bill Amount Curency Code: "+ billSummAmtType.CurAmt.CurCode)
                                _logger.info("Bill Amount: "+ billSummAmtType.CurAmt.Amt)

                        paymentRangeTypes= billInfoTypes.PaymentRange
                        if paymentRangeTypes:
                            for paymentRangeType in paymentRangeTypes:
                                _logger.info("Range Lower Amount: "+ paymentRangeType.Lower.Amt)
                                _logger.info("Range Lower Amount Currency: "+ paymentRangeType.Lower.CurCode)
                                _logger.info("Range Upper Amount: "+ paymentRangeType.Upper.Amt)
                                _logger.info("Range Upper Amount Currency: "+ paymentRangeType.Upper.CurCode)

                        _logger.info(" ====================================== Bill Data End " + billRecType.BillerId + " =========================================")

        if signonProfileType.MsgCode == "PmtAddRq":
            pmtAddRsType= responseType.PaySvcRs.PmtAddRs

            custIdTypes = pmtAddRsType.CustId

            if custIdTypes:
                for custIdType in custIdTypes:
                    _logger.info("Official ID: "+ custIdType.OfficialId)
                    _logger.info("Official ID Type: "+ custIdType.OfficialIdType)

            pmtInfoValTypes = pmtAddRsType.PmtInfoVal
            if pmtInfoValTypes:
                for pmtInfoValType in pmtInfoValTypes:
                    pmtInfoType = pmtInfoValType.PmtInfo
                    _logger.info("Biller ID: "+ pmtInfoType.BillerId)
                    _logger.info("Billing Account: "+ pmtInfoType.BillingAcct)
                    _logger.info("Bill Number: "+ pmtInfoType.BillNumber)
                    _logger.info("Bill Ref Number: "+ pmtInfoType.BillRefNumber)
                    _logger.info("Bill Type Code: "+ pmtInfoType.BillTypeCode)
                    _logger.info("Delivery Method: "+ pmtInfoType.DeliveryMethod)
                    _logger.info("Extra Bill Info: "+ pmtInfoType.ExtraBillInfo)
                    _logger.info("Issue Date: "+ pmtInfoType.IssueDt)
                    _logger.info("Is Notify Mobile: "+ pmtInfoType.NotifyMobile)
                    _logger.info("Payment Description: "+ pmtInfoType.PmtDesc)
                    _logger.info("Payment Method: "+ pmtInfoType.PmtMethod)
                    _logger.info("Payment Processing Date: "+ pmtInfoType.PrcDt)
                    _logger.info("Amount Currency Code: "+ pmtInfoType.CurAmt.CurCode)
                    _logger.info("Amount: "+ pmtInfoType.CurAmt.Amt)

                    acctKeyTypes = pmtInfoType.ExtraBillingAcctKeys.ExtraBillingAcctKey
                    if acctKeyTypes:
                        for acctKeyType in acctKeyTypes:
                            _logger.info("Extra Billing Account Key: "+ acctKeyType.Key)
                            _logger.info("Extra Billing Account Value: "+ acctKeyType.Value)

                    feesAmtType = pmtInfoType.FeesAmt
                    _logger.info("Fees Currency Code: "+ feesAmtType.CurCode)
                    _logger.info("Fees Amount: "+ feesAmtType.Amt)

                    pmtTransIdTypes= pmtInfoType.PmtTransId
                    if pmtTransIdTypes:
                        for pmtTransIdType in pmtTransIdTypes:
                            _logger.info("Payment Transaction Creation Date: "+ pmtTransIdType.CreatedDt)
                            _logger.info("Payment ID: "+ pmtTransIdType.PmtId)
                            _logger.info("Payment ID Type: "+ pmtTransIdType.PmtIdType)

    def get_biller_details(self, custLangPref, suppressEcho):
        client = self._set_client(self.wsdl)

        '''
            client, msgCode, custLangPref, suppressEcho, namespace,
            pmtType, billTypeCode, billingAcct, extraBillingAcctKeys,     # msgCode: BillInqRq, PmtAddRq
            amt, curCode, pmtMethod, notifyMobile,                        # msgCode: PmtAddRq
            billRefNumber,                                                # msgCode: PmtAddRq & pmtType: POST
            billerId,                                                     # msgCode: PmtAddRq & pmtType: PREP
        '''
        namespace = 'ns1'
        fawryType = self._buildRequest(client=client, msgCode="BillerInqRq", custLangPref=custLangPref,
                                       suppressEcho=suppressEcho, namespace=namespace) # PmtType (POST/PREP), ServiceType, ProfileCode
        # _logger.info("FawryType Request: " + str(fawryType))

        try:
            # Get All of billers data and associated bill types for a specific channel
            # _logger.info("Before Calling BillerInqRq Fawry Service")
            fawryResponse = client.service.process(fawryType)
            # _logger.info("After Calling BillerInqRq Fawry Service")
            # _logger.info("BillerInqRq FawryType Response: " + str(fawryResponse))

            # Check if process is not success then return reason for that
            if fawryResponse.Response.PresSvcRs.Status.StatusCode != 200:
                _logger.error("Fawry Response ERROR: [" +
                              str(fawryResponse.Response.PresSvcRs.Status.StatusCode) + "]: " +
                              fawryResponse.Response.PresSvcRs.Status.StatusDesc)
                return self.get_error_message(fawryResponse.Response.PresSvcRs.Status.StatusCode,
                                              fawryResponse.Response.PresSvcRs.Status.StatusDesc)

            # _logger.info("Before Calling BillerInqRq _buildResponse")
            # self._buildResponse(fawryResponse)
            # _logger.info("After Calling BillerInqRq _buildResponse")

            result = {}
            result['billerRecTypes'] = fawryResponse.Response.PresSvcRs.BillerInqRs.BillerRec
            # _logger.info("Fawry Biller Details Result: " + str(result))

            return result

        except suds.WebFault as e:
            # childAtPath behaviour is changing at version 0.6
            prefix = ''
            if SUDS_VERSION >= "0.6":
                prefix = '/Envelope/Body/Fault'
            _logger.error("ERROR: " + str(e))
            return self.get_error_message(
                e.document.childAtPath(prefix + '/faultcode').getText(),
                e.document.childAtPath(prefix + '/faultstring').getText())
        except IOError as e:
            _logger.error("ERROR: " + str(e))
            return self.get_error_message('0', 'FAWRY Server Not Found:\n%s' % e)

    def get_bill_details(self, custLangPref, suppressEcho,
                         # pmtType,
                         billTypeCode, billingAcct, extraBillingAcctKeys=None):
        client = self._set_client(self.wsdl)

        '''
            client, msgCode, custLangPref, suppressEcho, namespace,
            pmtType, billTypeCode, billingAcct, extraBillingAcctKeys,     # msgCode: BillInqRq, PmtAddRq
            amt, curCode, pmtMethod, notifyMobile,                        # msgCode: PmtAddRq
            billRefNumber,                                                # msgCode: PmtAddRq & pmtType: POST
            billerId,                                                     # msgCode: PmtAddRq & pmtType: PREP
        '''
        namespace = 'ns1'
        fawryType = self._buildRequest(client=client, msgCode="BillInqRq", custLangPref=custLangPref, suppressEcho=suppressEcho, namespace=namespace,
                                       # pmtType=pmtType,
                                       billTypeCode=billTypeCode, billingAcct=billingAcct, extraBillingAcctKeys=extraBillingAcctKeys) # IsRetry, IncOpenAmt => False, BillerId, PmtType => PREP
        # _logger.info("FawryType Request: " + str(fawryType))

        try:
            # Get All of bill data
            # _logger.info("Before Calling BillInqRq Fawry Service")
            fawryResponse = client.service.process(fawryType)
            # _logger.info("After Calling BillInqRq Fawry Service")
            # _logger.info("BillInqRq FawryType Response: " + str(fawryResponse))

            # Check if process is not success then return reason for that
            if fawryResponse.Response.PresSvcRs.Status.StatusCode != 200:
                _logger.error("Fawry Response ERROR: [" +
                              str(fawryResponse.Response.PresSvcRs.Status.StatusCode) + "]: " +
                              fawryResponse.Response.PresSvcRs.Status.StatusDesc)
                return self.get_error_message(fawryResponse.Response.PresSvcRs.Status.StatusCode,
                                              fawryResponse.Response.PresSvcRs.Status.StatusDesc)

            # _logger.info("Before Calling BillInqRq _buildResponse")
            # self._buildResponse(fawryResponse)
            # _logger.info("After Calling BillerInqRq _buildResponse")

            result = {}
            result['billRecType'] = fawryResponse.Response.PresSvcRs.BillInqRs.BillRec[0]
            # _logger.info("Fawry Bill Details Result: " + str(result))

            return result

        except suds.WebFault as e:
            # childAtPath behaviour is changing at version 0.6
            prefix = ''
            if SUDS_VERSION >= "0.6":
                prefix = '/Envelope/Body/Fault'
            _logger.error("ERROR: " + str(e))
            return self.get_error_message(
                e.document.childAtPath(prefix + '/faultcode').getText(),
                e.document.childAtPath(prefix + '/faultstring').getText())
        except IOError as e:
            _logger.error("ERROR: " + str(e))
            return self.get_error_message('0', 'FAWRY Server Not Found:\n%s' % e)

    def pay_bill(self, custLangPref,
                 suppressEcho, billTypeCode,
                 billingAcct, extraBillingAcctKeys,
                 amt, curCode, pmtMethod,
                 notifyMobile, billRefNumber,
                 billerId, pmtType):
        client = self._set_client(self.wsdl)

        '''
            client, msgCode, custLangPref, suppressEcho, namespace,
            pmtType, billTypeCode, billingAcct, extraBillingAcctKeys,     # msgCode: BillInqRq, PmtAddRq
            amt, curCode, pmtMethod, notifyMobile,                        # msgCode: PmtAddRq
            billRefNumber,                                                # msgCode: PmtAddRq & pmtType: POST
            billerId,                                                     # msgCode: PmtAddRq & pmtType: PREP
        '''
        namespace = 'ns1'
        fawryType = self._buildRequest(client=client, msgCode="PmtAddRq", custLangPref=custLangPref, suppressEcho=suppressEcho, namespace=namespace,
                                       # pmtType=pmtType,
                                       billTypeCode=billTypeCode, billingAcct=billingAcct, extraBillingAcctKeys=extraBillingAcctKeys,
                                       amt=amt, curCode=curCode, pmtMethod=pmtMethod, notifyMobile=notifyMobile,
                                       billRefNumber=billRefNumber,
                                       # billerId=billerId
                                       ) # IsRetry, BillerId, PmtType
        # _logger.info("FawryType Request: " + str(fawryType))

        try:
            # Pay Bill
            # _logger.info("Before Calling Fawry Pay Bill")
            fawryResponse = client.service.process(fawryType)
            # _logger.info("After Calling Fawry Pay Bill")
            # _logger.info("PmtAddRq FawryType Response: " + str(fawryResponse))

            # Check if process is not success then return reason for that
            if fawryResponse.Response.PaySvcRs.Status.StatusCode != 200:
                _logger.error("Fawry Response ERROR: [" +
                              str(fawryResponse.Response.PaySvcRs.Status.StatusCode) + "]: " +
                              fawryResponse.Response.PaySvcRs.Status.StatusDesc)
                return self.get_error_message(fawryResponse.Response.PaySvcRs.Status.StatusCode,
                                              fawryResponse.Response.PaySvcRs.Status.StatusDesc)

            # _logger.info("Before Calling PmtAddRq _buildResponse")
            # self._buildResponse(fawryResponse)
            # _logger.info("After Calling PmtAddRq _buildResponse")

            result = {}
            result['pmtInfoValType'] = fawryResponse.Response.PaySvcRs.PmtAddRs.PmtInfoVal[0]
            # _logger.info("Fawry Pay Bill Result: " + str(result))

            return result

        except suds.WebFault as e:
            # childAtPath behaviour is changing at version 0.6
            prefix = ''
            if SUDS_VERSION >= "0.6":
                prefix = '/Envelope/Body/Fault'
            _logger.error("ERROR: " + str(e))
            return self.get_error_message(
                e.document.childAtPath(prefix + '/faultcode').getText(),
                e.document.childAtPath(prefix + '/faultstring').getText())
        except IOError as e:
            _logger.error("ERROR: " + str(e))
            return self.get_error_message('0', 'FAWRY Server Not Found:\n%s' % e)
