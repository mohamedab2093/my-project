from odoo import models, fields


class LabDoct(models.Model):
    _name = "labdoct"
    _description = "LabDoct"

    name = fields.Char(string="اسم الطبيب ")
