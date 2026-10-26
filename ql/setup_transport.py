# Copyright (c) 2026, QL and contributors
# For license information, please see license.txt

import frappe

TRANSPORT_MODES = [
	{"mode": "FCL Container", "colli_capacity": 1315, "description": "Full Container Load (1315 colli capacity)"},
	{"mode": "FTL BUP", "colli_capacity": 1500, "description": "Full Truckload BUP (1500 colli capacity)"},
	{"mode": "CDD", "colli_capacity": 550, "description": "Colt Diesel Double (550 colli capacity)"},
]

VENDORS = [
	"Lestari Jalan Raya (LJR)",
	"Winarta Putra Sejati (WPS)",
	"Samudra Perdana Selasara (SPS)",
	"Puninar Logistic",
	"Livi Logistics"
]

DESTINATIONS = [
	{"name": "APL Medan", "city": "Medan", "island": "Sumatera", "base_cdd": 7500000, "base_fcl": 16500000, "base_ftl": 18000000},
	{"name": "APL Pekanbaru", "city": "Pekanbaru", "island": "Sumatera", "base_cdd": 6500000, "base_fcl": 14500000, "base_ftl": 16000000},
	{"name": "APL Padang", "city": "Padang", "island": "Sumatera", "base_cdd": 6000000, "base_fcl": 13500000, "base_ftl": 15000000},
	{"name": "APL Jambi", "city": "Jambi", "island": "Sumatera", "base_cdd": 5500000, "base_fcl": 12500000, "base_ftl": 14000000},
	{"name": "APL Palembang", "city": "Palembang", "island": "Sumatera", "base_cdd": 4500000, "base_fcl": 10500000, "base_ftl": 11500000},
	{"name": "APL Lampung", "city": "Bandar Lampung", "island": "Sumatera", "base_cdd": 3500000, "base_fcl": 8500000, "base_ftl": 9500000},
	{"name": "APL Jakarta1", "city": "Jakarta", "island": "Jawa", "base_cdd": 1500000, "base_fcl": 3500000, "base_ftl": 4000000},
	{"name": "APL Tangerang", "city": "Tangerang", "island": "Jawa", "base_cdd": 1400000, "base_fcl": 3300000, "base_ftl": 3800000},
	{"name": "APL Bandung", "city": "Bandung", "island": "Jawa", "base_cdd": 2200000, "base_fcl": 5000000, "base_ftl": 5500000},
	{"name": "APL Semarang", "city": "Semarang", "island": "Jawa", "base_cdd": 3200000, "base_fcl": 7500000, "base_ftl": 8000000},
	{"name": "APL Yogyakarta", "city": "Yogyakarta", "island": "Jawa", "base_cdd": 3500000, "base_fcl": 8000000, "base_ftl": 8500000},
	{"name": "APL Surabaya", "city": "Surabaya", "island": "Jawa", "base_cdd": 4500000, "base_fcl": 10000000, "base_ftl": 11000000},
	{"name": "APL Denpasar", "city": "Denpasar", "island": "Bali", "base_cdd": 5500000, "base_fcl": 12500000, "base_ftl": 13500000},
	{"name": "APL Kupang", "city": "Kupang", "island": "NTT", "base_cdd": 11000000, "base_fcl": 24000000, "base_ftl": 26500000},
	{"name": "APL Banjarmasin", "city": "Banjarmasin", "island": "Kalimantan", "base_cdd": 8000000, "base_fcl": 18000000, "base_ftl": 20000000},
	{"name": "APL Pontianak", "city": "Pontianak", "island": "Kalimantan", "base_cdd": 8500000, "base_fcl": 19000000, "base_ftl": 21000000},
	{"name": "APL Samarinda", "city": "Samarinda", "island": "Kalimantan", "base_cdd": 9500000, "base_fcl": 21000000, "base_ftl": 23000000},
	{"name": "APL Makassar", "city": "Makassar", "island": "Sulawesi", "base_cdd": 8500000, "base_fcl": 19500000, "base_ftl": 21500000},
	{"name": "APL Palu", "city": "Palu", "island": "Sulawesi", "base_cdd": 10500000, "base_fcl": 23000000, "base_ftl": 25000000},
	{"name": "APL Manado", "city": "Manado", "island": "Sulawesi", "base_cdd": 12000000, "base_fcl": 26000000, "base_ftl": 28500000},
]

# Relative cost multiplier per vendor to produce realistic competitive variations
VENDOR_MULTIPLIERS = {
	"Lestari Jalan Raya (LJR)": {"CDD": 1.00, "FCL Container": 0.98, "FTL BUP": 1.02},
	"Winarta Putra Sejati (WPS)": {"CDD": 0.95, "FCL Container": 1.02, "FTL BUP": 0.96},
	"Samudra Perdana Selasara (SPS)": {"CDD": 1.03, "FCL Container": 0.94, "FTL BUP": 1.01},
	"Puninar Logistic": {"CDD": 0.98, "FCL Container": 1.01, "FTL BUP": 0.95},
	"Livi Logistics": {"CDD": 1.02, "FCL Container": 0.97, "FTL BUP": 0.99},
}

CITY_FLEET_MODES = [
	{"mode": "Blind Van", "capacity": 120, "base_cost": 200000, "per_km_rate": 6000, "description": "Blind Van / Gran Max (120 colli capacity)"},
	{"mode": "Pick Up Box", "capacity": 250, "base_cost": 350000, "per_km_rate": 8000, "description": "Small Box / Pick Up Box (250 colli capacity)"},
	{"mode": "CDE Box", "capacity": 400, "base_cost": 500000, "per_km_rate": 10000, "description": "Colt Diesel Engkel - 4 Wheeler (400 colli capacity)"},
	{"mode": "CDD Box", "capacity": 550, "base_cost": 750000, "per_km_rate": 12000, "description": "Colt Diesel Double - 6 Wheeler (550 colli capacity)"},
]

def setup_all():
	"""Seeds master data and tariffs for Transport Calculator module."""
	setup_transport_modes()
	setup_city_fleet_modes()
	setup_suppliers()
	setup_territories_and_destinations()
	setup_expedition_tariffs()
	frappe.db.commit()
	print("All transport data successfully seeded.")


def setup_city_fleet_modes():
	print("Setting up City Fleet Modes...")
	if not frappe.db.table_exists("City Fleet Mode"):
		return
	for item in CITY_FLEET_MODES:
		if not frappe.db.exists("City Fleet Mode", item["mode"]):
			doc = frappe.get_doc({
				"doctype": "City Fleet Mode",
				"mode": item["mode"],
				"capacity": item["capacity"],
				"base_cost": item["base_cost"],
				"per_km_rate": item["per_km_rate"],
				"description": item["description"],
				"enabled": 1
			})
			doc.insert(ignore_permissions=True)
		else:
			frappe.db.set_value("City Fleet Mode", item["mode"], {
				"capacity": item["capacity"],
				"base_cost": item["base_cost"],
				"per_km_rate": item["per_km_rate"],
				"enabled": 1
			})



def setup_transport_modes():
	print("Setting up Transport Modes...")
	for item in TRANSPORT_MODES:
		if not frappe.db.exists("Transport Mode", item["mode"]):
			doc = frappe.get_doc({
				"doctype": "Transport Mode",
				"mode": item["mode"],
				"colli_capacity": item["colli_capacity"],
				"description": item["description"]
			})
			doc.insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Transport Mode", item["mode"], "colli_capacity", item["colli_capacity"])


def setup_suppliers():
	print("Setting up Suppliers (Logistics Vendors)...")
	# Ensure Services supplier group exists
	if not frappe.db.exists("Supplier Group", "Services"):
		frappe.get_doc({"doctype": "Supplier Group", "supplier_group_name": "Services"}).insert(ignore_permissions=True)

	for vendor_name in VENDORS:
		if not frappe.db.exists("Supplier", vendor_name):
			doc = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": vendor_name,
				"supplier_group": "Services",
				"supplier_type": "Company"
			})
			doc.insert(ignore_permissions=True)


def setup_territories_and_destinations():
	print("Setting up Territories and Transport Destinations...")
	# Make sure Indonesia is a group territory so it can have children
	if frappe.db.exists("Territory", "Indonesia"):
		frappe.db.set_value("Territory", "Indonesia", "is_group", 1)

	parent_territory = "Indonesia" if frappe.db.exists("Territory", "Indonesia") else "All Territories"

	for d in DESTINATIONS:
		# Seed Territory
		if not frappe.db.exists("Territory", d["name"]):
			try:
				t_doc = frappe.get_doc({
					"doctype": "Territory",
					"territory_name": d["name"],
					"parent_territory": parent_territory,
					"is_group": 0
				})
				t_doc.insert(ignore_permissions=True)
			except Exception as e:
				print(f"Notice inserting Territory {d['name']}: {e}")

		# Seed Transport Destination
		if frappe.db.table_exists("Transport Destination") and not frappe.db.exists("Transport Destination", d["name"]):
			try:
				td_doc = frappe.get_doc({
					"doctype": "Transport Destination",
					"destination_name": d["name"],
					"distributor": "APL",
					"city": d["city"],
					"territory": d["name"],
					"description": f"APL Distribution Center - {d['city']} ({d['island']})"
				})
				td_doc.insert(ignore_permissions=True)
			except Exception as e:
				print(f"Notice inserting Transport Destination {d['name']}: {e}")


def setup_expedition_tariffs():
	print("Setting up Expedition Tariffs...")
	if not frappe.db.table_exists("Expedition Tariff"):
		print("Expedition Tariff does not exist yet. Please run bench migrate first.")
		return

	mode_base_keys = {
		"CDD": "base_cdd",
		"FCL Container": "base_fcl",
		"FTL BUP": "base_ftl"
	}

	for dest in DESTINATIONS:
		dest_name = dest["name"]
		for vendor_name in VENDORS:
			mults = VENDOR_MULTIPLIERS.get(vendor_name, {"CDD": 1.0, "FCL Container": 1.0, "FTL BUP": 1.0})
			for mode_name, base_key in mode_base_keys.items():
				base_cost = dest[base_key]
				factor = mults.get(mode_name, 1.0)
				shipping_cost = round(base_cost * factor, -3)  # round to thousands

				existing = frappe.db.get_value(
					"Expedition Tariff",
					{
						"shipping_vendor": vendor_name,
						"destination": dest_name,
						"transport_mode": mode_name
					},
					"name"
				)

				if not existing:
					doc = frappe.get_doc({
						"doctype": "Expedition Tariff",
						"shipping_vendor": vendor_name,
						"destination": dest_name,
						"transport_mode": mode_name,
						"shipping_cost": shipping_cost,
						"currency": "IDR",
						"description": f"Standard tariff from plant to {dest_name} via {mode_name}"
					})
					doc.insert(ignore_permissions=True)
				else:
					frappe.db.set_value("Expedition Tariff", existing, "shipping_cost", shipping_cost)
