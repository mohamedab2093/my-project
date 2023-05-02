from odoo import api, fields, models, _, tools
from datetime import date, datetime, timedelta
from dateutil import relativedelta
from odoo.exceptions import ValidationError

STATUS = [
    ("draft", "عميل جديد"),
    ("chek", "عميل مستخدم"),

]


class LabEmp(models.Model):
    _name = "labemp"
    _description = "Lab_Emp"
    name = fields.Char(string="مسلسل")
    nnid = fields.Char(string="رقم البطاقة", required=True)
    egy_id = fields.Many2one("egycom", string="الشركة المصرية ", required=True)
    sa_id = fields.Many2one("sgycom", string="الشركة السعودية ", required=True)
    job_id = fields.Many2one("empjob", string="المهنة  ", required=True)
    date = fields.Date(string="تاريخ الميلاد", default=date.today(), required=True)
    age = fields.Integer(string="العمر", compute="_compute_age", required=True)
    pic = fields.Binary(string="صورة شخصية ")
    reference = fields.Char(string='اسم العميل ')
    is_accept = fields.Boolean(string="لائق")
    is_not_accept = fields.Boolean(string="غير لائق")
    is_not_reson = fields.Text(string="راى الطبيب", required=False)
    is_positive = fields.Boolean(string="تحليل ايجابى")
    is_negative = fields.Boolean(string="تحليل سلبى ")
    resultdate = fields.Date(string="تاريخ الكشف", default=date.today(), required=False)
    doct_id = fields.Many2one("labdoct", string="اسم الطبيب ", required=False)
    reson_id = fields.Many2one("labreson", string="سبب الرفض ", required=False)
    state = fields.Selection(STATUS, string="الحالة", default="draft")

    _sql_constraints = [
        ('unique_nnid', 'unique (nnid)', 'رقم بطاقة العميل موجود مسبقا '),
    ]

    @api.constrains('date')
    def _check_dob(self):
        if self.date >= date.today():
            raise ValidationError('تاريخ الميلاد لابد ان يكون اقل من تاريخ اليوم ')



    @api.model
    def create(self, vals):
        # assigning the sequence for the record

        vals['name'] = self.env['ir.sequence'].next_by_code('labemp')
        return super(LabEmp, self).create(vals)

    def write(self, vals):
        # assigning the sequence for the record

        vals['state'] = "chek"
        return super(LabEmp, self).write(vals)

    @api.constrains('nnid')
    def check_NID(self):
        for rec in self:
            if len(rec.nnid) != 14:
                raise ValidationError(_('رقم البطاقة لابد ان يكون  14 رقم '))

    @api.depends("date")
    def _compute_age(self):
        for rec in self:
            cy = date.today()
            if rec.date:
                rec.age = cy.year - rec.date.year
            else:
                rec.age = 0

    @api.onchange("lab_acc")
    def onchange_lab_acc(self):
        for rec in self:
            if rec.lab_acc:
                self.lab1 = True
                self.lab2 = True
                self.lab3 = True
                self.lab4 = True
                self.lab5 = True
                self.lab6 = True

            else:
                self.lab1 = False
                self.lab2 = False
                self.lab3 = False
                self.lab4 = False
                self.lab5 = False
                self.lab6 = False
