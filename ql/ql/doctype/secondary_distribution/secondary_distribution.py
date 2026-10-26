# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint
from ql.tools.fleet_optimizer import calculate_within_city_optimization

class SecondaryDistribution(Document):
	def autoname(self):
		from frappe.model.naming import append_number_if_name_exists

		if not self.destination and self.primary_distribution:
			self.destination = frappe.db.get_value("Primary Distribution", self.primary_distribution, "destination")
		if not self.destination:
			frappe.throw("Please select a Primary Distribution record with a valid Destination.")
		if not self.outlet:
			frappe.throw("Please enter an Outlet name.")
		base_name = f"{self.destination.strip()}-{self.outlet.strip()}"
		self.name = append_number_if_name_exists(self.doctype, base_name)


	def validate(self):
		self.fetch_primary_details()
		if not self.within_city_transport_cost and cint(self.package_count) > 0:
			self.run_optimization()
		self.calculate_total_cost()

	def fetch_primary_details(self):
		if self.primary_distribution:
			primary = frappe.get_doc("Primary Distribution", self.primary_distribution)
			if not self.destination:
				self.destination = primary.destination
			if not self.intercity_cost:
				self.intercity_cost = flt(primary.best_total_cost)
			if not self.intercity_vendor:
				self.intercity_vendor = primary.best_vendor
			if not self.intercity_fleet_mix:
				self.intercity_fleet_mix = primary.best_fleet_mix
			if not self.package_count:
				self.package_count = primary.package_count
			if not self.unit_count_in_package:
				self.unit_count_in_package = primary.unit_count_in_package or 1

		if self.destination and not self.distributor_warehouse:
			# Look up Transport Destination description or format standard warehouse name
			warehouse_name = frappe.db.get_value("Transport Destination", {"destination_name": self.destination}, "description")
			self.distributor_warehouse = warehouse_name or f"{self.destination} Distribution Center"

	@frappe.whitelist()
	def run_optimization(self):
		if not self.primary_distribution:
			frappe.throw("Please select a Primary Distribution.")
		if not self.outlet:
			frappe.throw("Please specify an Outlet.")
		if not self.package_count or cint(self.package_count) <= 0:
			frappe.throw("Package Count must be greater than 0.")

		distance = flt(self.distance_km) or 15.0
		unit_count = cint(self.unit_count_in_package) or 1

		results = calculate_within_city_optimization(
			package_count=self.package_count,
			distance_km=distance,
			unit_count_in_package=unit_count
		)

		self.set("within_city_optimization_results", [])
		for r in results:
			self.append("within_city_optimization_results", {
				"vehicle_mode": r["vehicle_mode"],
				"fleet_mix": r["fleet_mix"],
				"cost": r["cost"],
				"cost_per_unit": r["cost_per_unit"],
				"capacity": r["capacity"],
				"remaining_capacity": r["remaining_capacity"],
				"is_recommended": r["is_recommended"]
			})

		if results:
			best = results[0]
			self.within_city_transport_cost = best["cost"]
			self.within_city_fleet_mix = best["fleet_mix"]
			self.status = "Calculated"

		self.calculate_total_cost()

		return {
			"within_city_optimization_results": results,
			"within_city_transport_cost": self.within_city_transport_cost,
			"within_city_fleet_mix": self.within_city_fleet_mix,
			"total_cost": self.total_cost,
			"total_cost_per_unit": self.total_cost_per_unit
		}

	def calculate_total_cost(self):
		# Total Cost = Intercity (Primary Distribution) + Handling & Labor Cost + Within the City Transport Cost
		intercity = flt(self.intercity_cost)
		handling = flt(self.handling_and_labor_cost)
		within_city = flt(self.within_city_transport_cost)

		self.total_cost = round(intercity + handling + within_city, 2)

		total_units = cint(self.package_count) * (cint(self.unit_count_in_package) or 1)
		if total_units > 0:
			self.total_cost_per_unit = round(self.total_cost / total_units, 2)
		else:
			self.total_cost_per_unit = 0.0
