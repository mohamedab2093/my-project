from odoo import models, fields


class LabReson(models.Model):
    _name = "labreson"
    _description = "LabReson"

    name = fields.Char(string="سبب الرفض ")
