# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import math
import frappe
from frappe.utils import flt, cint

def solve_unbounded_knapsack_min_cost(target_colli, modes):
	"""
	Solves the minimum-cost covering problem using a modified Unbounded Knapsack algorithm.
	
	Parameters:
	- target_colli (int): Required number of packages (colli) to transport (> 0).
	- modes (list of dict): Each dict contains:
		- 'mode': str (e.g. 'FTL BUP', 'FCL Container', 'CDD')
		- 'capacity': int (e.g. 1500, 1315, 550)
		- 'cost': float (shipping cost for that mode)

	Returns:
	- dict:
		- 'total_cost': float (minimum total cost)
		- 'total_capacity': int (total capacity of chosen fleet)
		- 'remaining_capacity': int (excess capacity: total_capacity - target_colli)
		- 'fleet_mix': str (e.g. '1 x FTL BUP, 1 x CDD')
		- 'mode_counts': dict of {mode_name: count}
	"""
	if target_colli <= 0:
		return {
			"total_cost": 0.0,
			"total_capacity": 0,
			"remaining_capacity": 0,
			"fleet_mix": "No packages to transport",
			"mode_counts": {}
		}

	# Filter out any invalid modes
	valid_modes = [
		m for m in modes
		if cint(m.get("capacity")) > 0 and flt(m.get("cost")) > 0
	]

	if not valid_modes:
		return None

	max_single_capacity = max(cint(m["capacity"]) for m in valid_modes)
	# Upper bound for DP capacity: target_colli + max_single_capacity
	# Any configuration >= target_colli + max_single_capacity can have a vehicle removed
	# while still covering target_colli, thus would not be minimal in cost.
	limit_capacity = target_colli + max_single_capacity

	# DP table: min cost to achieve exact capacity c
	# dp[c] = float('inf')
	INF = float("inf")
	dp = [INF] * (limit_capacity + 1)
	parent = [None] * (limit_capacity + 1)
	dp[0] = 0.0

	for c in range(1, limit_capacity + 1):
		best_cost = INF
		best_choice = None
		for m in valid_modes:
			cap = cint(m["capacity"])
			cost = flt(m["cost"])
			if c >= cap:
				prev_cost = dp[c - cap]
				if prev_cost != INF:
					candidate_cost = prev_cost + cost
					if candidate_cost < best_cost:
						best_cost = candidate_cost
						best_choice = (c - cap, m)
		if best_choice is not None:
			dp[c] = best_cost
			parent[c] = best_choice

	# Find the best capacity >= target_colli that minimizes total cost,
	# and secondary criteria: minimizes excess capacity (c - target_colli)
	best_final_capacity = None
	min_total_cost = INF
	min_excess = INF

	for c in range(target_colli, limit_capacity + 1):
		cost = dp[c]
		if cost < INF:
			excess = c - target_colli
			if (cost < min_total_cost) or (math.isclose(cost, min_total_cost, abs_tol=1e-5) and excess < min_excess):
				min_total_cost = cost
				min_excess = excess
				best_final_capacity = c

	if best_final_capacity is None or min_total_cost == INF:
		return None

	# Backtrack to reconstruct the fleet mix
	mode_counts = {}
	curr = best_final_capacity
	while curr > 0 and parent[curr] is not None:
		prev_c, mode_used = parent[curr]
		mode_name = mode_used["mode"]
		mode_counts[mode_name] = mode_counts.get(mode_name, 0) + 1
		curr = prev_c

	# Map capacity for sorting fleet mix from largest mode to smallest
	cap_lookup = {m["mode"]: cint(m["capacity"]) for m in valid_modes}
	sorted_items = sorted(
		mode_counts.items(),
		key=lambda x: cap_lookup.get(x[0], 0),
		reverse=True
	)

	mix_parts = [f"{count} x {name}" for name, count in sorted_items]
	fleet_mix_str = ", ".join(mix_parts)

	return {
		"total_cost": round(min_total_cost, 2),
		"total_capacity": best_final_capacity,
		"remaining_capacity": best_final_capacity - target_colli,
		"fleet_mix": fleet_mix_str,
		"mode_counts": mode_counts
	}


@frappe.whitelist()
def calculate_logistics_optimization(destination, package_count, unit_count_in_package=1):
	"""
	Calculates the optimal fleet allocation for all available logistics vendors
	to the specified destination for the given package count.

	Returns a list of vendor result dicts sorted by lowest cost.
	"""
	package_count = cint(package_count)
	unit_count_in_package = cint(unit_count_in_package) or 1

	if not destination:
		frappe.throw("Please select a Destination.")
	if package_count <= 0:
		frappe.throw("Package Count (Colli) must be greater than 0.")
	if unit_count_in_package <= 0:
		unit_count_in_package = 1

	# Fetch all expedition tariffs for the destination
	tariffs = frappe.db.sql("""
		SELECT 
			et.shipping_vendor,
			et.transport_mode,
			et.shipping_cost,
			tm.colli_capacity
		FROM `tabExpedition Tariff` et
		JOIN `tabTransport Mode` tm ON tm.name = et.transport_mode
		WHERE et.destination = %(destination)s
		ORDER BY et.shipping_vendor, tm.colli_capacity DESC
	""", {"destination": destination}, as_dict=True)

	if not tariffs:
		frappe.throw(
			f"No Expedition Tariffs found for destination: {destination}. "
			"Please ensure Expedition Tariff records exist for this destination."
		)

	# Group tariffs by vendor
	vendor_modes = {}
	for t in tariffs:
		vendor = t.shipping_vendor
		if vendor not in vendor_modes:
			vendor_modes[vendor] = []
		vendor_modes[vendor].append({
			"mode": t.transport_mode,
			"capacity": cint(t.colli_capacity),
			"cost": flt(t.shipping_cost)
		})

	total_units = package_count * unit_count_in_package
	results = []

	for vendor, modes in vendor_modes.items():
		solution = solve_unbounded_knapsack_min_cost(package_count, modes)
		if not solution:
			continue

		total_cost = solution["total_cost"]
		cost_per_unit = round(total_cost / total_units, 2) if total_units > 0 else 0.0

		results.append({
			"vendor": vendor,
			"fleet_mix": solution["fleet_mix"],
			"intercity_total_cost": total_cost,
			"intercity_cost_per_unit": cost_per_unit,
			"remaining_package_capacity": solution["remaining_capacity"],
			"total_capacity": solution["total_capacity"],
			"is_recommended": 0
		})

	if not results:
		frappe.throw(f"Unable to calculate fleet optimization for destination: {destination}.")

	# Sort vendors by total cost ascending (cheapest first)
	results.sort(key=lambda x: (x["intercity_total_cost"], -x["remaining_package_capacity"]))

	# Mark the top vendor as recommended
	results[0]["is_recommended"] = 1

	return results


# Alias for Primary Distribution
calculate_primary_distribution = calculate_logistics_optimization


@frappe.whitelist()
def get_city_fleet_modes():
	"""
	Retrieves available city fleet modes from the City Fleet Mode DocType.
	Falls back to default configurations if none found in database.
	"""
	if frappe.db and frappe.db.table_exists("City Fleet Mode"):
		modes = frappe.get_all(
			"City Fleet Mode",
			filters={"enabled": 1} if frappe.db.has_column("City Fleet Mode", "enabled") else {},
			fields=["mode", "capacity", "base_cost", "per_km_rate"],
			order_by="capacity asc"
		)
		if modes:
			return [
				{
					"mode": m["mode"],
					"capacity": cint(m["capacity"]),
					"base_cost": flt(m["base_cost"]),
					"per_km_rate": flt(m["per_km_rate"]),
				}
				for m in modes
			]

	# Default fallback if table has no records yet
	return [
		{"mode": "Blind Van", "capacity": 120, "base_cost": 200000, "per_km_rate": 6000},
		{"mode": "Pick Up Box", "capacity": 250, "base_cost": 350000, "per_km_rate": 8000},
		{"mode": "CDE Box", "capacity": 400, "base_cost": 500000, "per_km_rate": 10000},
		{"mode": "CDD Box", "capacity": 550, "base_cost": 750000, "per_km_rate": 12000},
	]


class _CityFleetModesProxy(list):
	def __iter__(self):
		return iter(get_city_fleet_modes())

	def __len__(self):
		return len(get_city_fleet_modes())

	def __getitem__(self, item):
		return get_city_fleet_modes()[item]


CITY_FLEET_MODES = _CityFleetModesProxy()


@frappe.whitelist()
def calculate_within_city_optimization(package_count, distance_km=15, unit_count_in_package=1):
	"""
	Calculates the optimal vehicle allocation and transport cost within the city,
	from distributor warehouse to a specific outlet based on package count and distance.
	"""
	package_count = cint(package_count)
	distance_km = flt(distance_km) or 15.0
	unit_count_in_package = cint(unit_count_in_package) or 1
	total_units = package_count * unit_count_in_package

	if package_count <= 0:
		frappe.throw("Package Count must be greater than 0.")

	fleet_modes = get_city_fleet_modes()

	# Compute distance-based cost for each city mode
	active_modes = []
	for m in fleet_modes:
		trip_cost = round(flt(m["base_cost"]) + flt(m["per_km_rate"]) * distance_km, -2)
		active_modes.append({
			"mode": m["mode"],
			"capacity": m["capacity"],
			"cost": trip_cost
		})


	# 1. Optimal Fleet Mix using Unbounded Knapsack
	optimal_solution = solve_unbounded_knapsack_min_cost(package_count, active_modes)

	options = []
	if optimal_solution:
		opt_cost = optimal_solution["total_cost"]
		opt_cpu = round(opt_cost / total_units, 2) if total_units > 0 else 0.0
		options.append({
			"vehicle_mode": "Optimal Fleet Mix",
			"fleet_mix": optimal_solution["fleet_mix"],
			"capacity": optimal_solution["total_capacity"],
			"cost": opt_cost,
			"cost_per_unit": opt_cpu,
			"remaining_capacity": optimal_solution["remaining_capacity"],
			"is_recommended": 1
		})

	# 2. Add single-mode alternatives for comparison
	for m in active_modes:
		cap = m["capacity"]
		trip_cost = m["cost"]
		needed_count = math.ceil(package_count / cap)
		total_cap = needed_count * cap
		total_cost = round(needed_count * trip_cost, 2)
		cpu = round(total_cost / total_units, 2) if total_units > 0 else 0.0
		fleet_mix = f"{needed_count} x {m['mode']}"

		# Check if this single mode option is identical to optimal solution
		if optimal_solution and fleet_mix == optimal_solution["fleet_mix"]:
			continue

		options.append({
			"vehicle_mode": f"{m['mode']} Dedicated",
			"fleet_mix": fleet_mix,
			"capacity": total_cap,
			"cost": total_cost,
			"cost_per_unit": cpu,
			"remaining_capacity": total_cap - package_count,
			"is_recommended": 0
		})

	# Sort options: lowest cost first
	options.sort(key=lambda x: (x["cost"], -x["remaining_capacity"]))
	if options:
		options[0]["is_recommended"] = 1

	return options

