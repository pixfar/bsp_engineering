# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Requisition(Document):
	def before_insert(self):
		self.requested_by = frappe.session.user
