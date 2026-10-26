# Copyright (c) 2026, QL and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate, get_first_day


class TestSalesOperationalCost(FrappeTestCase):
	def test_soc_calculation_and_uniqueness(self):
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
		if not company:
			company = frappe.db.get_value("Company", {}, "name")
		territory = frappe.db.get_value("Territory", {}, "name")
		sales_person = frappe.db.get_value("Sales Person", {}, "name")

		if not (company and territory and sales_person):
			return

		period = get_first_day(nowdate())
		# Clean up any existing test record
		frappe.db.delete("Sales Operational Cost", {
			"territory": territory,
			"sales_person": sales_person,
			"period_date": period
		})

		doc = frappe.get_doc({
			"doctype": "Sales Operational Cost",
			"company": company,
			"period_date": period,
			"territory": territory,
			"sales_person": sales_person,
			"biaya_komisi_penjualan": 1000,
			"biaya_pendistribusian_produk": 2000,
			"biaya_gaji": 5000,
			"biaya_perjalanan_dinas": 1500
		})
		doc.insert()

		self.assertEqual(doc.total_variable_sales_cost, 3000)
		self.assertEqual(doc.total_employee_cost, 6000) # Gaji (5000) + Komisi (1000)
		self.assertEqual(doc.total_fixed_operating_cost, 1500)
		self.assertEqual(doc.total, 9500) # 3000 + 5000 + 1500

		# Duplicate check
		dup = frappe.get_doc({
			"doctype": "Sales Operational Cost",
			"company": company,
			"period_date": period,
			"territory": territory,
			"sales_person": sales_person,
		})
		self.assertRaises(frappe.DuplicateEntryError, dup.insert)

		doc.delete()
