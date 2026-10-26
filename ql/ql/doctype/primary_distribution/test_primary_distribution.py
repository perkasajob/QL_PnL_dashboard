# Copyright (c) 2026, QL and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

class IntegrationTestPrimaryDistribution(IntegrationTestCase):
	def test_naming_and_calculation(self):
		doc = frappe.get_doc({
			"doctype": "Primary Distribution",
			"destination": "APL Surabaya",
			"package_count": 2000,
			"unit_count_in_package": 10
		})
		doc.insert(ignore_permissions=True)
		self.assertTrue(doc.name.startswith("APL Surabaya-"))
		self.assertEqual(doc.status, "Calculated")
		self.assertTrue(len(doc.optimization_results) > 0)
		self.assertTrue(doc.best_total_cost > 0)
