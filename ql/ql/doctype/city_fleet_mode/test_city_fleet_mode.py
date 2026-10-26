# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

class IntegrationTestCityFleetMode(IntegrationTestCase):
	def test_city_fleet_mode_creation(self):
		if not frappe.db.exists("City Fleet Mode", "Test Van"):
			doc = frappe.get_doc({
				"doctype": "City Fleet Mode",
				"mode": "Test Van",
				"capacity": 150,
				"base_cost": 220000,
				"per_km_rate": 6500,
				"enabled": 1
			})
			doc.insert(ignore_permissions=True)
			self.assertEqual(doc.name, "Test Van")
			frappe.delete_doc("City Fleet Mode", "Test Van", force=True)
