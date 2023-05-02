from odoo import models, fields


class SgyCom(models.Model):
    _name = "sgycom"
    _description = "sgycom"

    name = fields.Char(string="اسم الشركة ")