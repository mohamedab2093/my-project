from odoo import api, fields, models
from datetime import date, datetime, timedelta
from dateutil import relativedelta
from odoo.exceptions import ValidationError


class LabResult(models.Model):
    _name = "labresult"
    _description = "LabResult"

    name = fields.Char(string="الاسم", required=True)
    resultdate = fields.Date(string="تاريخ الكشف", default=date.today(), required=True)
    doct_id = fields.Many2one("labdoct", string="اسم الطبيب ", required=True)
    reson_id = fields.Many2one("labreson", string="سبب الرفض ", required=True)
    cust_lab = fields.Many2many('labemp', string="اسم العميل")
    is_accept = fields.Boolean(string="لائق")
    is_not_accept = fields.Boolean(string="غير لائق")
    is_not_reson = fields.Text(string="راى الطبيب", required=True)
    is_positive = fields.Boolean(string="تحليل ايجابى")
    is_negative = fields.Boolean(string="تحليل سلبى ")
