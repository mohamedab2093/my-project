from odoo import models, fields


class SgyCom(models.Model):
    _name = "empjob"
    _description = "sgycom"

    name = fields.Char(string="المهنة ", required=True)