# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import unittest
import frappe
from ql.tools.fleet_optimizer import (
	solve_unbounded_knapsack_min_cost,
	calculate_logistics_optimization
)

class TestTransportCalculator(unittest.TestCase):
	def setUp(self):
		self.modes = [
			{"mode": "CDD", "capacity": 550, "cost": 3000000},
			{"mode": "FCL Container", "capacity": 1315, "cost": 7000000},
			{"mode": "FTL BUP", "capacity": 1500, "cost": 7500000},
		]

	def test_knapsack_small_load(self):
		# 500 packages -> 1 CDD (capacity 550)
		res = solve_unbounded_knapsack_min_cost(500, self.modes)
		self.assertIsNotNone(res)
		self.assertEqual(res["total_cost"], 3000000)
		self.assertEqual(res["fleet_mix"], "1 x CDD")
		self.assertEqual(res["total_capacity"], 550)
		self.assertEqual(res["remaining_capacity"], 50)

	def test_knapsack_exact_single_mode(self):
		# 1500 packages -> 1 FTL BUP (1500 capacity, cost 7,500,000)
		# vs 3 CDD = 9,000,000 or 2 FCL = 14,000,000
		res = solve_unbounded_knapsack_min_cost(1500, self.modes)
		self.assertIsNotNone(res)
		self.assertEqual(res["total_cost"], 7500000)
		self.assertEqual(res["fleet_mix"], "1 x FTL BUP")
		self.assertEqual(res["remaining_capacity"], 0)

	def test_knapsack_combination_ftl_and_cdd(self):
		# 2050 packages -> 1 FTL BUP (1500) + 1 CDD (550) = 2050 capacity, exact fit!
		# Cost = 7,500,000 + 3,000,000 = 10,500,000
		# Alternatives: 2 FTL = 15,000,000; 2 FCL = 14,000,000 (cap 2630); 4 CDD = 12,000,000
		res = solve_unbounded_knapsack_min_cost(2050, self.modes)
		self.assertIsNotNone(res)
		self.assertEqual(res["total_cost"], 10500000)
		self.assertIn("1 x FTL BUP", res["fleet_mix"])
		self.assertIn("1 x CDD", res["fleet_mix"])
		self.assertEqual(res["total_capacity"], 2050)
		self.assertEqual(res["remaining_capacity"], 0)

	def test_knapsack_combination_fcl_and_cdd(self):
		# 1800 packages:
		# 1 FCL (1315) + 1 CDD (550) = 1865 cap >= 1800. Cost = 7,000,000 + 3,000,000 = 10,000,000
		# 1 FTL (1500) + 1 CDD (550) = 2050 cap. Cost = 10,500,000
		# 2 FCL = 14,000,000; 2 FTL = 15,000,000; 4 CDD = 12,000,000
		res = solve_unbounded_knapsack_min_cost(1800, self.modes)
		self.assertIsNotNone(res)
		self.assertEqual(res["total_cost"], 10000000)
		self.assertIn("1 x FCL Container", res["fleet_mix"])
		self.assertIn("1 x CDD", res["fleet_mix"])
		self.assertEqual(res["total_capacity"], 1865)
		self.assertEqual(res["remaining_capacity"], 65)

	def test_db_optimization_for_destination(self):
		# Run calculate_logistics_optimization for APL Surabaya with 2000 packages, 10 units/package
		results = calculate_logistics_optimization(
			destination="APL Surabaya",
			package_count=2000,
			unit_count_in_package=10
		)
		self.assertTrue(len(results) > 0)
		# Ensure sorted by cost
		for i in range(len(results) - 1):
			self.assertLessEqual(results[i]["intercity_total_cost"], results[i+1]["intercity_total_cost"])
		# Ensure first one is recommended
		self.assertEqual(results[0]["is_recommended"], 1)
		self.assertTrue(results[0]["intercity_cost_per_unit"] > 0)

	def test_transport_calculator_single_doctype(self):
		calc = frappe.get_single("Transport Calculator")
		calc.destination = "APL Jakarta1"
		calc.package_count = 1800
		calc.unit_count_in_package = 12
		calc.run_calculation()
		self.assertTrue(len(calc.results) >= 5)
		self.assertIsNotNone(calc.best_vendor)
		self.assertIsNotNone(calc.best_fleet_mix)
		self.assertTrue(calc.best_total_cost > 0)
		self.assertTrue(calc.best_cost_per_unit > 0)

	def test_primary_distribution_doctype(self):
		pd = frappe.get_doc({
			"doctype": "Primary Distribution",
			"destination": "APL Medan",
			"package_count": 3500,
			"unit_count_in_package": 8
		})
		pd.insert(ignore_permissions=True)
		self.assertTrue(pd.name.startswith("APL Medan-"))
		self.assertTrue(len(pd.optimization_results) >= 5)
		self.assertEqual(pd.status, "Calculated")
		self.assertTrue(pd.best_total_cost > 0)
		self.assertTrue(pd.best_cost_per_unit > 0)

	def test_secondary_distribution_doctype(self):
		test_outlet = "RSUD Dr Soetomo"
		expected_base = f"APL Surabaya-{test_outlet}"
		if frappe.db.exists("Secondary Distribution", expected_base):
			frappe.delete_doc("Secondary Distribution", expected_base, force=True)

		pd = frappe.get_doc({
			"doctype": "Primary Distribution",
			"destination": "APL Surabaya",
			"package_count": 800,
			"unit_count_in_package": 10
		})
		pd.insert(ignore_permissions=True)

		sd = frappe.get_doc({
			"doctype": "Secondary Distribution",
			"primary_distribution": pd.name,
			"outlet": test_outlet,
			"distance_km": 15.0,
			"handling_and_labor_cost": 200000.0
		})
		sd.insert(ignore_permissions=True)

		self.assertEqual(sd.name, expected_base)
		self.assertEqual(sd.destination, pd.destination)
		self.assertEqual(sd.intercity_cost, pd.best_total_cost)
		self.assertTrue(sd.within_city_transport_cost > 0)
		self.assertEqual(
			round(float(sd.total_cost), 2),
			round(float(sd.intercity_cost) + float(sd.handling_and_labor_cost) + float(sd.within_city_transport_cost), 2)
		)



def run_tests():
	suite = unittest.TestLoader().loadTestsFromTestCase(TestTransportCalculator)
	runner = unittest.TextTestRunner(verbosity=2)
	res = runner.run(suite)
	return res.wasSuccessful()

