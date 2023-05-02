from odoo import models, fields


class EgyCom(models.Model):
    _name = "egycom"
    _description = "egycom"

    name = fields.Char(string="اسم الشركة ")