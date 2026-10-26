# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TransportMode(Document):
	def validate(self):
		if not self.colli_capacity or self.colli_capacity <= 0:
			frappe.throw("Colli Capacity must be greater than 0.")
