# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ExpeditionTariff(Document):
	def validate(self):
		if not self.shipping_cost or self.shipping_cost <= 0:
			frappe.throw("Shipping Cost must be greater than 0.")
		
		# Ensure unique combination of shipping_vendor, destination, and transport_mode
		existing = frappe.db.get_value(
			"Expedition Tariff",
			{
				"shipping_vendor": self.shipping_vendor,
				"destination": self.destination,
				"transport_mode": self.transport_mode,
				"name": ["!=", self.name or ""]
			},
			"name"
		)
		if existing:
			frappe.throw(
				f"Tariff already exists for Vendor '{self.shipping_vendor}', Destination '{self.destination}', and Mode '{self.transport_mode}' (Doc: {existing})."
			)
