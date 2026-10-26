# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

class IntegrationTestSecondaryDistribution(IntegrationTestCase):
	def test_secondary_distribution_calculation_and_naming(self):
		# Create Primary Distribution first
		pd = frappe.get_doc({
			"doctype": "Primary Distribution",
			"destination": "APL Bandung",
			"package_count": 500,
			"unit_count_in_package": 10
		})
		pd.insert(ignore_permissions=True)

		# Create Secondary Distribution linking to Primary Distribution
		sd = frappe.get_doc({
			"doctype": "Secondary Distribution",
			"primary_distribution": pd.name,
			"outlet": "Apotek Kimia Farma Dago",
			"distance_km": 12.0,
			"handling_and_labor_cost": 150000.0
		})
		sd.insert(ignore_permissions=True)

		# Check name format: {Destination}-{Outlet}
		expected_name = f"{pd.destination}-Apotek Kimia Farma Dago"
		self.assertEqual(sd.name, expected_name)

		# Check destination derived from primary distribution
		self.assertEqual(sd.destination, pd.destination)

		# Check intercity cost fetched from primary distribution
		self.assertEqual(sd.intercity_cost, pd.best_total_cost)

		# Check within-city transport cost calculated
		self.assertTrue(sd.within_city_transport_cost > 0)
		self.assertTrue(len(sd.within_city_optimization_results) > 0)

		# Check total cost formula: intercity + handling + within-city
		expected_total = flt(sd.intercity_cost) + flt(sd.handling_and_labor_cost) + flt(sd.within_city_transport_cost)
		self.assertEqual(round(sd.total_cost, 2), round(expected_total, 2))
