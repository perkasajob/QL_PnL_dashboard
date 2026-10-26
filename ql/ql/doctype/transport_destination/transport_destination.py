# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TransportDestination(Document):
	def validate(self):
		if not self.destination_name:
			frappe.throw("Destination Name is required.")
