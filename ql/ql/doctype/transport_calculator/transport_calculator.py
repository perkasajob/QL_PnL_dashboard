# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint
from ql.tools.fleet_optimizer import calculate_logistics_optimization

class TransportCalculator(Document):
	def validate(self):
		if self.destination and cint(self.package_count) > 0:
			self.run_calculation()

	@frappe.whitelist()
	def run_calculation(self):
		if not self.destination:
			frappe.throw("Please select a Destination.")
		if not self.package_count or cint(self.package_count) <= 0:
			frappe.throw("Package Count must be greater than 0.")

		results = calculate_logistics_optimization(
			destination=self.destination,
			package_count=self.package_count,
			unit_count_in_package=self.unit_count_in_package or 1
		)

		self.set("results", [])
		for r in results:
			self.append("results", {
				"vendor": r["vendor"],
				"fleet_mix": r["fleet_mix"],
				"intercity_total_cost": r["intercity_total_cost"],
				"intercity_cost_per_unit": r["intercity_cost_per_unit"],
				"remaining_package_capacity": r["remaining_package_capacity"],
				"total_capacity": r["total_capacity"],
				"is_recommended": r["is_recommended"]
			})

		if results:
			best = results[0]
			self.best_vendor = best["vendor"]
			self.best_fleet_mix = best["fleet_mix"]
			self.best_total_cost = best["intercity_total_cost"]
			self.best_cost_per_unit = best["intercity_cost_per_unit"]

		return {
			"results": results,
			"best_vendor": self.best_vendor,
			"best_fleet_mix": self.best_fleet_mix,
			"best_total_cost": self.best_total_cost,
			"best_cost_per_unit": self.best_cost_per_unit
		}


@frappe.whitelist()
def calculate_for_calculator(destination, package_count, unit_count_in_package=1):
	"""Whitelisted helper for client side calculation without saving document first."""
	return calculate_logistics_optimization(destination, package_count, unit_count_in_package)
