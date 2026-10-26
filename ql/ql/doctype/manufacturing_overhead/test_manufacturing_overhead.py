# Copyright (c) 2026, QL and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate, get_first_day


class TestManufacturingOverhead(FrappeTestCase):
	def test_moh_calculation_and_uniqueness(self):
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
		if not company:
			company = frappe.db.get_value("Company", {}, "name")
		if not company:
			return

		period = get_first_day(nowdate())
		# Clean up any existing test record
		frappe.db.delete("Manufacturing Overhead", {"company": company, "period_date": period})

		doc = frappe.get_doc({
			"doctype": "Manufacturing Overhead",
			"company": company,
			"period_date": period,
			"biaya_kerusakan_bahan": 1000,
			"biaya_analisa": 2000,
			"biaya_pegawai_tak_langsung": 5000,
			"biaya_listrik_dan_air": 3000
		})
		doc.insert()

		self.assertEqual(doc.total_variable_moh, 3000)
		self.assertEqual(doc.total_fixed_moh, 8000)
		self.assertEqual(doc.total, 11000)

		# Duplicate check
		dup = frappe.get_doc({
			"doctype": "Manufacturing Overhead",
			"company": company,
			"period_date": period,
		})
		self.assertRaises(frappe.DuplicateEntryError, dup.insert)

		doc.delete()
