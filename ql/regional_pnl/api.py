# Copyright (c) 2026, QL and contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils import flt, nowdate, add_months
from ql.ql.report.regional_contribution_margin_pnl.regional_contribution_margin_pnl import (
	execute as run_regional_pnl
)


@frappe.whitelist()
def get_total_nsv(from_date=None, to_date=None, company=None):
	"""Returns the Total Net Sales Value (NSV) for the selected period."""
	res = get_summary_metrics(from_date, to_date, company)
	return {
		"value": res.get("total_nsv", 0.0),
		"fieldtype": "Currency"
	}


@frappe.whitelist()
def get_total_contribution_margin(from_date=None, to_date=None, company=None):
	"""Returns the Total Contribution Margin and CM %."""
	res = get_summary_metrics(from_date, to_date, company)
	return {
		"value": res.get("total_cm", 0.0),
		"fieldtype": "Currency"
	}


@frappe.whitelist()
def get_contribution_margin_pct(from_date=None, to_date=None, company=None):
	"""Returns the Contribution Margin %."""
	res = get_summary_metrics(from_date, to_date, company)
	return {
		"value": res.get("cm_pct", 0.0),
		"fieldtype": "Percent"
	}


@frappe.whitelist()
def get_total_direct_cogs(from_date=None, to_date=None, company=None):
	"""Returns the Total Direct COGS."""
	res = get_summary_metrics(from_date, to_date, company)
	return {
		"value": res.get("total_cogs", 0.0),
		"fieldtype": "Currency"
	}


@frappe.whitelist()
def get_total_net_profit(from_date=None, to_date=None, company=None):
	"""Returns the Regional Net Profit."""
	res = get_summary_metrics(from_date, to_date, company)
	return {
		"value": res.get("total_net_profit", 0.0),
		"fieldtype": "Currency"
	}


def get_summary_metrics(from_date=None, to_date=None, company=None):
	filters = {
		"from_date": from_date or add_months(nowdate(), -1),
		"to_date": to_date or nowdate(),
		"company": company or frappe.defaults.get_user_default("Company"),
		"hierarchy_level": "All",
		"cost_basis": "Variable Costing (Contribution)"
	}
	_, data, _, _, _ = run_regional_pnl(filters)
	
	root_rows = [r for r in data if r.get("indent") == 0]
	if not root_rows:
		root_rows = data

	tot_nsv = sum(r.get("gross_revenue", 0.0) for r in root_rows)
	tot_cogs = sum(r.get("direct_cogs", 0.0) for r in root_rows)
	tot_cm = sum(r.get("contribution_margin", 0.0) for r in root_rows)
	tot_profit = sum(r.get("net_profit", 0.0) for r in root_rows)
	cm_pct = flt((tot_cm / tot_nsv * 100) if tot_nsv > 0 else 0.0, 2)

	return {
		"total_nsv": flt(tot_nsv, 2),
		"total_cogs": flt(tot_cogs, 2),
		"total_cm": flt(tot_cm, 2),
		"cm_pct": cm_pct,
		"total_net_profit": flt(tot_profit, 2)
	}


@frappe.whitelist()
def get_sm_performance_chart(from_date=None, to_date=None, company=None):
	"""Bar Chart: Sales Performance by Geography / SM Node."""
	filters = {
		"from_date": from_date or add_months(nowdate(), -1),
		"to_date": to_date or nowdate(),
		"company": company or frappe.defaults.get_user_default("Company"),
		"hierarchy_level": "SM",
		"cost_basis": "Variable Costing (Contribution)"
	}
	_, data, _, _, _ = run_regional_pnl(filters)
	sm_rows = data[:10]

	return {
		"labels": [r.get("sales_person_name") for r in sm_rows],
		"datasets": [
			{"name": "Gross Revenue (NSV)", "values": [r.get("gross_revenue", 0.0) for r in sm_rows]},
			{"name": "Contribution Margin", "values": [r.get("contribution_margin", 0.0) for r in sm_rows]}
		]
	}


@frappe.whitelist()
def get_product_margin_breakdown_chart(from_date=None, to_date=None):
	"""Donut / Bar Chart: Product Revenue & Margin Breakdown grouping Sales Item & Manufacturing Cost."""
	from_date = from_date or add_months(nowdate(), -1)
	to_date = to_date or nowdate()

	existing_cols = {c[0] for c in frappe.db.sql("DESC `tabSales Item`")}
	item_col = "item_code" if "item_code" in existing_cols else "custom_item"
	name_col = "item_name" if "item_name" in existing_cols else "custom_item_name"
	qty_col = "qty" if "qty" in existing_cols else "custom_quantity"
	amount_col = "amount" if "amount" in existing_cols else "custom_amount"
	hna_col = "custom_hna" if "custom_hna" in existing_cols else None
	hna_select = f", COALESCE({hna_col}, 0.0) as unit_hna" if hna_col else ", 0.0 as unit_hna"

	# 1. Fetch Sales Headers
	sales_headers = frappe.db.sql("""
		SELECT 
			name,
			custom_customers_purchase_order_date as po_date,
			COALESCE(custom_gsv, 0.0) as gsv,
			COALESCE(custom_nsv1, 0.0) as nsv
		FROM `tabSales`
		WHERE custom_customers_purchase_order_date BETWEEN %(from_date)s AND %(to_date)s
			AND docstatus IN (0, 1)
	""", {"from_date": from_date, "to_date": to_date}, as_dict=True)

	if not sales_headers:
		return {"labels": [], "datasets": []}

	# 2. Fetch Sales Items in batches
	all_names = [h.name for h in sales_headers]
	items_by_parent = {}
	chunk_size = 1000
	for i in range(0, len(all_names), chunk_size):
		batch = all_names[i:i+chunk_size]
		batch_items = frappe.db.sql(f"""
			SELECT 
				parent,
				{item_col} as item_code,
				COALESCE({name_col}, {item_col}) as item_name,
				COALESCE({qty_col}, 1.0) as qty,
				COALESCE({amount_col}, 0.0) as item_raw_amount
				{hna_select}
			FROM `tabSales Item`
			WHERE parent IN %(names)s
		""", {"names": tuple(batch)}, as_dict=True)
		for it in batch_items:
			if it.parent not in items_by_parent:
				items_by_parent[it.parent] = []
			items_by_parent[it.parent].append(it)

	# 3. Load Manufacturing Costs
	cost_rows = frappe.db.sql("""
		SELECT 
			product_id,
			item_code,
			period_start_date,
			period_end_date,
			COALESCE(variable_cogs_per_piece, 0.0) as unit_cost
		FROM `tabManufacturing Cost`
	""", as_dict=True)

	cost_list = []
	for c in cost_rows:
		keys = {str(c.product_id).strip(), str(c.item_code).strip()} - {"None", ""}
		cost_list.append({
			"keys": keys,
			"start": c.period_start_date,
			"end": c.period_end_date,
			"cost": flt(c.unit_cost)
		})

	def get_unit_cost(item_code, po_date):
		if not item_code or not po_date:
			return 0.0
		item_str = str(item_code).strip()
		for c in cost_list:
			if item_str in c["keys"]:
				if (not c["start"] or c["start"] <= po_date) and (not c["end"] or po_date <= c["end"]):
					return c["cost"]
		return 0.0

	# 4. Group by Product
	item_agg = {}
	for h in sales_headers:
		h_items = items_by_parent.get(h.name, [])
		header_gsv = flt(h.gsv)
		header_nsv = flt(h.nsv)
		po_date = h.po_date

		for it in h_items:
			code = it.item_code or "Unknown"
			name = it.item_name or code
			if code not in item_agg:
				item_agg[code] = {"name": name, "nsv": 0.0, "cogs": 0.0}

			qty = flt(it.qty) or 1.0
			unit_hna = flt(it.unit_hna)
			amt = flt(it.item_raw_amount)

			if unit_hna > 0:
				item_gsv = qty * unit_hna
			elif amt > 0:
				item_gsv = amt
			else:
				item_gsv = header_gsv / len(h_items) if len(h_items) > 0 else 0.0

			if header_nsv > 0:
				if header_gsv > 0:
					item_nsv = (item_gsv / header_gsv) * header_nsv
				else:
					item_nsv = header_nsv / len(h_items)
			else:
				item_nsv = item_gsv

			u_cost = get_unit_cost(code, po_date)
			direct_cogs = qty * u_cost

			item_agg[code]["nsv"] += item_nsv
			item_agg[code]["cogs"] += direct_cogs

	sorted_items = sorted(item_agg.values(), key=lambda x: x["nsv"], reverse=True)[:8]

	labels = [r["name"] for r in sorted_items]
	revenue_vals = [flt(r["nsv"], 2) for r in sorted_items]
	margin_vals = [flt(r["nsv"] - r["cogs"], 2) for r in sorted_items]

	return {
		"labels": labels,
		"datasets": [
			{"name": "Revenue (NSV)", "values": revenue_vals},
			{"name": "Contribution Margin", "values": margin_vals}
		]
	}


@frappe.whitelist()
def get_cost_stack_chart(from_date=None, to_date=None, company=None):
	"""
	Stacked Bar / Waterfall:
	X-Axis = SM Node;
	Stacked Y-Series = Direct COGS, Variable OPEX, Fixed Operating + Employee Costs, Overhead Costs, Net Profit.
	"""
	filters = {
		"from_date": from_date or add_months(nowdate(), -1),
		"to_date": to_date or nowdate(),
		"company": company or frappe.defaults.get_user_default("Company"),
		"hierarchy_level": "SM",
		"cost_basis": "Variable Costing (Contribution)"
	}
	_, data, _, _, _ = run_regional_pnl(filters)
	sm_rows = data[:8]

	labels = [r.get("sales_person_name") for r in sm_rows]
	cogs_vals = [r.get("direct_cogs", 0.0) for r in sm_rows]
	var_opex_vals = [r.get("variable_opex", 0.0) for r in sm_rows]
	fixed_vals = [flt(r.get("fixed_operating_costs", 0.0) + r.get("employee_costs", 0.0), 2) for r in sm_rows]
	overhead_vals = [r.get("overhead_costs", 0.0) for r in sm_rows]
	profit_vals = [r.get("net_profit", 0.0) for r in sm_rows]

	return {
		"labels": labels,
		"datasets": [
			{"name": "Direct COGS", "values": cogs_vals},
			{"name": "Variable OPEX", "values": var_opex_vals},
			{"name": "Fixed Operating & Employee", "values": fixed_vals},
			{"name": "Overhead Costs", "values": overhead_vals},
			{"name": "Net Profit", "values": profit_vals}
		]
	}


@frappe.whitelist()
def get_hierarchical_sales_trajectory_chart(from_date=None, to_date=None):
	"""Line Chart: Sales trajectory across months for top hierarchy nodes."""
	from ql.ql.report.sales_person_pivot_tree_report.sales_person_pivot_tree_report import execute as run_pivot
	filters = {
		"from_date": from_date or add_months(nowdate(), -3),
		"to_date": to_date or nowdate(),
		"pivot_by": "Monthly (Jan-Dec)",
		"value_field": "NSV"
	}
	_, _, _, chart, _ = run_pivot(filters)
	if chart and chart.get("data"):
		return chart["data"]
	return {"labels": [], "datasets": []}

