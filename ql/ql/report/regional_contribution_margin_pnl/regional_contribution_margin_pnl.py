# Copyright (c) 2026, QL and contributors
# License: MIT. See LICENSE

import re
import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months
from ql.tools.ql_tools import extract_sales_team_data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	
	columns = get_columns(filters)
	data = get_data(filters)
	chart = get_chart(data, filters)
	report_summary = get_report_summary(data, filters)
	message = get_financial_insights_html(data, filters)

	return columns, data, message, chart, report_summary


def validate_filters(filters):
	if not filters.get("from_date"):
		filters.from_date = add_months(nowdate(), -1)
	if not filters.get("to_date"):
		filters.to_date = nowdate()

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be greater than To Date"))

	if not filters.get("cost_basis"):
		filters.cost_basis = "Variable Costing (Contribution)"

	if not filters.get("hierarchy_level"):
		filters.hierarchy_level = "All"


def get_column_mapping():
	"""Dynamically inspects tabSales Item columns."""
	existing_cols = {c[0] for c in frappe.db.sql("DESC `tabSales Item`")}
	
	item_col = "item_code" if "item_code" in existing_cols else "custom_item"
	name_col = "item_name" if "item_name" in existing_cols else "custom_item_name"
	qty_col = "qty" if "qty" in existing_cols else "custom_quantity"
	amount_col = "amount" if "amount" in existing_cols else "custom_amount"
	hna_col = "custom_hna" if "custom_hna" in existing_cols else None
	
	if "GSV" in existing_cols:
		gsv_col = "GSV"
	elif "custom_gsv" in existing_cols:
		gsv_col = "custom_gsv"
	else:
		gsv_col = amount_col

	return item_col, name_col, qty_col, amount_col, gsv_col, hna_col


def parse_sales_field(raw_text, default_tier):
	"""Extracts territory, person name, and tier using extract_sales_team_data."""
	extracted = extract_sales_team_data(raw_text)
	if extracted:
		item = extracted[0]
		terr = item.get("territory") or item.get("sales_person_name") or f"{default_tier}_OTHER"
		name = item.get("sales_person_name") or terr
		tier = item.get("tier") or default_tier
		return terr.strip(), name.strip(), tier.strip()
	return f"{default_tier}_OTHER", f"Other {default_tier}", default_tier


def get_sales_person_tree():
	"""Legacy stub for backwards compatibility."""
	return frappe.db.sql("""
		SELECT name, sales_person_name, parent_sales_person, custom_jabatan, custom_area, is_group, lft, rgt
		FROM `tabSales Person`
		WHERE enabled = 1
		ORDER BY lft ASC
	""", as_dict=True)


def calculate_depth_map(sales_person_nodes):
	"""Legacy stub for depth map calculation."""
	depth_map = {}
	for node in sales_person_nodes:
		ancestors = [p for p in sales_person_nodes if p.lft < node.lft and p.rgt > node.rgt]
		depth_map[node.name] = len(ancestors)
	return depth_map


def get_tier_label(name_or_depth, is_group=0, parent=None):
	"""Returns tier label for node."""
	clean = str(name_or_depth or "").strip().upper()
	if clean in ("GSM", "SM", "DM", "MR", "SPV"):
		return clean
	return "MR" if not is_group else "DM"


def get_direct_sales_data(filters):
	"""Legacy stub returning empty dict."""
	return {}


def get_gl_expenses_data(filters, node_codes):
	"""Fetches GL expenses matching active tree nodes or shared corporate overhead."""
	company_condition = ""
	params = {
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date")
	}
	if filters.get("company"):
		company_condition = "AND gle.company = %(company)s"
		params["company"] = filters.get("company")

	gl_entries = frappe.db.sql(f"""
		SELECT 
			gle.account,
			acc.account_name,
			gle.cost_center,
			gle.party,
			(gle.debit - gle.credit) as net_expense
		FROM `tabGL Entry` gle
		JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND gle.is_cancelled = 0
			AND gle.docstatus = 1
			AND acc.root_type = 'Expense'
			{company_condition}
	""", params, as_dict=True)

	node_variable_opex = {}
	node_fixed_operating = {}
	node_employee_costs = {}
	total_shared_overhead = 0.0

	for entry in gl_entries:
		net_amount = flt(entry.net_expense)
		if net_amount == 0.0:
			continue

		acc_text = f"{entry.account} {entry.account_name or ''}".lower()
		cost_center_text = (entry.cost_center or "").lower()

		target_node = None
		if entry.cost_center and entry.cost_center in node_codes:
			target_node = entry.cost_center
		elif entry.party and entry.party in node_codes:
			target_node = entry.party
		else:
			for code in node_codes:
				if code.lower() in cost_center_text:
					target_node = code
					break

		if any(k in acc_text for k in ["logistik", "bbm", "tol", "parkir", "ekspedisi", "freight", "delivery", "shipping", "transport", "komisi", "commission"]):
			if target_node:
				node_variable_opex[target_node] = node_variable_opex.get(target_node, 0.0) + net_amount
			else:
				total_shared_overhead += net_amount
		elif any(k in acc_text for k in ["sewa gudang", "rent", "listrik", "air", "telepon", "internet", "utilities", "pemeliharaan", "maintenance", "depresiasi"]):
			if target_node:
				node_fixed_operating[target_node] = node_fixed_operating.get(target_node, 0.0) + net_amount
			else:
				total_shared_overhead += net_amount
		elif any(k in acc_text for k in ["gaji", "salary", "salaries", "upah", "tunjangan", "benefit", "bpjs", "thr", "payroll"]):
			if target_node:
				node_employee_costs[target_node] = node_employee_costs.get(target_node, 0.0) + net_amount
			else:
				total_shared_overhead += net_amount
		else:
			total_shared_overhead += net_amount

	return {
		"node_variable_opex": node_variable_opex,
		"node_fixed_operating": node_fixed_operating,
		"node_employee_costs": node_employee_costs,
		"total_shared_overhead": total_shared_overhead
	}


def get_data(filters):
	"""
	Builds dynamic hierarchical P&L tree based strictly on tabSales:
	GSM (custom_gsm) -> SM (custom_sm) -> DM (custom_dm) -> MR (custom_mr).
	Uses extract_sales_team_data(raw_text) to parse codes, person names, and tiers.
	"""
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	cost_basis = filters.get("cost_basis", "Variable Costing (Contribution)")
	target_tier = filters.get("hierarchy_level", "All")
	docstatus_mode = filters.get("docstatus_filter", "All (0 & 1)")
	docstatus_sql = "AND docstatus = 1" if docstatus_mode == "Submitted Only (1)" else "AND docstatus IN (0, 1)"

	item_col, name_col, qty_col, amount_col, gsv_col, hna_col = get_column_mapping()
	hna_select = f", COALESCE(si.{hna_col}, 0.0) as unit_hna" if hna_col else ", 0.0 as unit_hna"

	# 1. Fetch Sales Headers from tabSales
	sales_headers = frappe.db.sql(f"""
		SELECT 
			name,
			custom_customers_purchase_order_date as po_date,
			COALESCE(custom_gsv, 0.0) as gsv,
			COALESCE(custom_nsv1, 0.0) as nsv,
			custom_gsm,
			custom_sm,
			custom_dm,
			custom_mr
		FROM `tabSales`
		WHERE custom_customers_purchase_order_date BETWEEN %(from_date)s AND %(to_date)s
		  {docstatus_sql}
	""", {"from_date": from_date, "to_date": to_date}, as_dict=True)

	if not sales_headers:
		return []

	# 2. Fetch Sales Items in batch
	sales_names = [s.name for s in sales_headers]
	item_map = {}
	batch_size = 1000
	for i in range(0, len(sales_names), batch_size):
		batch = sales_names[i:i + batch_size]
		items = frappe.db.sql(f"""
			SELECT 
				parent,
				si.{item_col} as item_code,
				COALESCE(si.{qty_col}, 1.0) as qty,
				COALESCE(si.{amount_col}, 0.0) as amount
				{hna_select}
			FROM `tabSales Item` si
			WHERE parent IN %(batch)s
		""", {"batch": batch}, as_dict=True)
		for it in items:
			if it.parent not in item_map:
				item_map[it.parent] = []
			item_map[it.parent].append(it)

	# 3. Load Manufacturing Costs for in-memory lookup
	mcf_records = frappe.db.sql("""
		SELECT 
			COALESCE(product_id, item_code) as item_code,
			period_start_date,
			period_end_date,
			COALESCE(variable_cogs_per_piece, 0.0) as var_cogs,
			COALESCE(statutory_valuation_rate, 0.0) as stat_cogs
		FROM `tabManufacturing Cost`
	""", as_dict=True)

	cost_lookup = {}
	use_statutory = "Statutory" in cost_basis
	for m in mcf_records:
		code = (m.item_code or "").strip()
		if code not in cost_lookup:
			cost_lookup[code] = []
		cost_lookup[code].append(m)

	def get_unit_cogs(item_code, po_date):
		if not po_date:
			return 0.0
		for c in cost_lookup.get(item_code, []):
			if c.period_start_date <= po_date <= c.period_end_date:
				return flt(c.stat_cogs if use_statutory else c.var_cogs)
		return 0.0

	# 4. Construct Dynamic Tree Nodes: GSM -> SM -> DM -> MR
	nodes = {}

	for s in sales_headers:
		po_date = getdate(s.po_date) if s.po_date else None
		header_gsv = flt(s.gsv)
		header_nsv = flt(s.nsv)

		gsm_t, gsm_n, gsm_tier = parse_sales_field(s.custom_gsm, "GSM")
		sm_t, sm_n, sm_tier = parse_sales_field(s.custom_sm, "SM")
		dm_t, dm_n, dm_tier = parse_sales_field(s.custom_dm, "DM")
		mr_t, mr_n, mr_tier = parse_sales_field(s.custom_mr, "MR")

		k_gsm = gsm_t
		k_sm = f"{gsm_t} / {sm_t}"
		k_dm = f"{gsm_t} / {sm_t} / {dm_t}"
		k_mr = f"{gsm_t} / {sm_t} / {dm_t} / {mr_t}"

		for k, p, t, ind, is_grp, c, nm in [
			(k_gsm, None, "GSM", 0, 1, gsm_t, f"{gsm_t} - {gsm_n}"),
			(k_sm, k_gsm, "SM", 1, 1, sm_t, f"{sm_t} - {sm_n}"),
			(k_dm, k_sm, "DM", 2, 1, dm_t, f"{dm_t} - {dm_n}"),
			(k_mr, k_dm, "MR", 3, 0, mr_t, f"{mr_t} - {mr_n}")
		]:
			if k not in nodes:
				nodes[k] = {
					"key": k, "parent": p, "tier": t, "indent": ind, "is_group": is_grp,
					"code": c, "name": nm, "gsv": 0.0, "nsv": 0.0, "cogs": 0.0,
					"var_opex": 0.0, "fixed_op": 0.0, "emp_costs": 0.0
				}

		# Compute Line Item Costs & GSV
		order_items = item_map.get(s.name, [])
		order_gsv = 0.0
		order_nsv = header_nsv
		order_cogs = 0.0

		if order_items:
			computed_items = []
			for it in order_items:
				qty = flt(it.qty) or 1.0
				hna = flt(it.unit_hna)
				item_gsv = qty * hna if hna > 0 else (flt(it.amount) or header_gsv)
				computed_items.append((it, qty, item_gsv))
				order_gsv += item_gsv

			for it, qty, item_gsv in computed_items:
				if order_gsv > 0 and header_nsv > 0:
					item_nsv = (item_gsv / order_gsv) * header_nsv
				else:
					item_nsv = item_gsv

				unit_cogs = get_unit_cogs(it.item_code, po_date)
				order_cogs += qty * unit_cogs
		else:
			order_gsv = header_gsv

		# Accumulate directly across all 4 levels in hierarchy
		for k in (k_gsm, k_sm, k_dm, k_mr):
			nodes[k]["gsv"] += order_gsv
			nodes[k]["nsv"] += order_nsv
			nodes[k]["cogs"] += order_cogs

	# 5. Fetch GL Expenses & Overhead
	all_node_codes = {n["code"] for n in nodes.values()}
	gl_data = get_gl_expenses_data(filters, all_node_codes)

	for k, n in nodes.items():
		code = n["code"]
		n["var_opex"] += gl_data["node_variable_opex"].get(code, 0.0)
		n["fixed_op"] += gl_data["node_fixed_operating"].get(code, 0.0)
		n["emp_costs"] += gl_data["node_employee_costs"].get(code, 0.0)

	total_overhead = gl_data["total_shared_overhead"]
	root_revenue = sum(v["nsv"] for v in nodes.values() if v["tier"] == "GSM")
	if root_revenue <= 0.0:
		root_revenue = max((v["nsv"] for v in nodes.values()), default=0.0)

	# 6. Hierarchical sort: GSM -> SM -> DM -> MR
	sorted_keys = []
	for gsm_k in sorted(k for k, v in nodes.items() if v["tier"] == "GSM"):
		sorted_keys.append(gsm_k)
		for sm_k in sorted(k for k, v in nodes.items() if v["tier"] == "SM" and v["parent"] == gsm_k):
			sorted_keys.append(sm_k)
			for dm_k in sorted(k for k, v in nodes.items() if v["tier"] == "DM" and v["parent"] == sm_k):
				sorted_keys.append(dm_k)
				for mr_k in sorted(k for k, v in nodes.items() if v["tier"] == "MR" and v["parent"] == dm_k):
					sorted_keys.append(mr_k)

	result_rows = []
	for k in sorted_keys:
		n = nodes[k]
		if target_tier != "All" and n["tier"] != target_tier:
			continue

		gross_rev = flt(n["nsv"])
		direct_cogs = flt(n["cogs"])
		mfg_margin = flt(gross_rev - direct_cogs)
		var_opex = flt(n["var_opex"])
		contrib_margin = flt(mfg_margin - var_opex)
		cm_pct = flt((contrib_margin / gross_rev * 100) if gross_rev > 0 else 0.0)

		fixed_op = flt(n["fixed_op"])
		emp_costs = flt(n["emp_costs"])
		overhead_allocated = flt((gross_rev / root_revenue * total_overhead) if root_revenue > 0 else 0.0)
		total_period_fixed = flt(fixed_op + emp_costs + overhead_allocated)

		net_profit = flt(contrib_margin - total_period_fixed)
		net_profit_pct = flt((net_profit / gross_rev * 100) if gross_rev > 0 else 0.0)

		result_rows.append({
			"sales_person": n["key"],
			"sales_person_name": n["name"],
			"parent_sales_person": n["parent"] if target_tier == "All" else None,
			"tier": n["tier"],
			"indent": n["indent"] if target_tier == "All" else 0,
			"is_group": n["is_group"],
			"has_value": True,
			"gsv": flt(n["gsv"], 2),
			"gross_revenue": flt(gross_rev, 2),
			"direct_cogs": flt(direct_cogs, 2),
			"manufacturing_margin": flt(mfg_margin, 2),
			"variable_opex": flt(var_opex, 2),
			"contribution_margin": flt(contrib_margin, 2),
			"contribution_margin_pct": flt(cm_pct, 2),
			"fixed_operating_costs": flt(fixed_op, 2),
			"employee_costs": flt(emp_costs, 2),
			"overhead_costs": flt(overhead_allocated, 2),
			"net_profit": flt(net_profit, 2),
			"net_profit_pct": flt(net_profit_pct, 2)
		})

	return result_rows


def get_columns(filters):
	return [
		{
			"label": _("Sales Person / Territory"),
			"fieldname": "sales_person_name",
			"fieldtype": "Data",
			"width": 260
		},
		{
			"label": _("Tier"),
			"fieldname": "tier",
			"fieldtype": "Data",
			"width": 80
		},
		{
			"label": _("Gross Sales Value (GSV)"),
			"fieldname": "gsv",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 140
		},
		{
			"label": _("Gross Revenue (NSV)"),
			"fieldname": "gross_revenue",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 150
		},
		{
			"label": _("Direct COGS"),
			"fieldname": "direct_cogs",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 130
		},
		{
			"label": _("Manufacturing Margin"),
			"fieldname": "manufacturing_margin",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 150
		},
		{
			"label": _("Variable OPEX"),
			"fieldname": "variable_opex",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 130
		},
		{
			"label": _("Contribution Margin"),
			"fieldname": "contribution_margin",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 160
		},
		{
			"label": _("CM %"),
			"fieldname": "contribution_margin_pct",
			"fieldtype": "Percent",
			"width": 90
		},
		{
			"label": _("Fixed Operating Costs"),
			"fieldname": "fixed_operating_costs",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 140
		},
		{
			"label": _("Employee Costs"),
			"fieldname": "employee_costs",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 130
		},
		{
			"label": _("Overhead Costs"),
			"fieldname": "overhead_costs",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 140
		},
		{
			"label": _("Net Profit"),
			"fieldname": "net_profit",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 150
		},
		{
			"label": _("Net Profit %"),
			"fieldname": "net_profit_pct",
			"fieldtype": "Percent",
			"width": 100
		}
	]


def get_chart(data, filters):
	"""Generates regional performance bar chart grouped by SM nodes."""
	sm_rows = [r for r in data if r.get("tier") == "SM"]
	if not sm_rows:
		sm_rows = [r for r in data if r.get("tier") in ("DM", "GSM")]
	if not sm_rows:
		sm_rows = data[:8]

	labels = [r["sales_person_name"] for r in sm_rows[:8]]
	revenue_values = [r["gross_revenue"] for r in sm_rows[:8]]
	cm_values = [r["contribution_margin"] for r in sm_rows[:8]]
	profit_values = [r["net_profit"] for r in sm_rows[:8]]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Gross Revenue"), "values": revenue_values},
				{"name": _("Contribution Margin"), "values": cm_values},
				{"name": _("Net Profit"), "values": profit_values}
			]
		},
		"type": "bar",
		"colors": ["#2563eb", "#f59e0b", "#10b981"]
	}


def get_report_summary(data, filters):
	root_rows = [r for r in data if r.get("indent") == 0]
	if not root_rows:
		root_rows = data

	tot_rev = sum(r["gross_revenue"] for r in root_rows)
	tot_cm = sum(r["contribution_margin"] for r in root_rows)
	tot_cogs = sum(r["direct_cogs"] for r in root_rows)
	tot_net_profit = sum(r["net_profit"] for r in root_rows)
	tot_cm_pct = flt((tot_cm / tot_rev * 100) if tot_rev > 0 else 0.0, 2)

	currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency") or "IDR"

	return [
		{
			"value": tot_rev,
			"label": _("Total Net Sales (NSV)"),
			"datatype": "Currency",
			"currency": currency
		},
		{
			"value": tot_cogs,
			"label": _("Total Direct COGS"),
			"datatype": "Currency",
			"currency": currency
		},
		{
			"value": tot_cm,
			"label": _("Total Contribution Margin"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if tot_cm >= 0 else "Orange"
		},
		{
			"value": tot_cm_pct,
			"label": _("Contribution Margin %"),
			"datatype": "Percent"
		},
		{
			"value": tot_net_profit,
			"label": _("Regional Net Profit"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if tot_net_profit >= 0 else "Red"
		}
	]


def get_financial_insights_html(data, filters):
	"""Generates an executive QL Financial Insights commentary banner."""
	if not data:
		return ""

	root_rows = [r for r in data if r.get("indent") == 0]
	if not root_rows:
		root_rows = data

	tot_gsv = sum(r.get("gsv", 0.0) for r in root_rows)
	tot_nsv = sum(r.get("gross_revenue", 0.0) for r in root_rows)
	tot_cogs = sum(r.get("direct_cogs", 0.0) for r in root_rows)
	tot_mfg_margin = sum(r.get("manufacturing_margin", 0.0) for r in root_rows)
	tot_var_opex = sum(r.get("variable_opex", 0.0) for r in root_rows)
	tot_cm = sum(r.get("contribution_margin", 0.0) for r in root_rows)
	tot_fixed_op = sum(r.get("fixed_operating_costs", 0.0) for r in root_rows)
	tot_employee = sum(r.get("employee_costs", 0.0) for r in root_rows)
	tot_overhead = sum(r.get("overhead_costs", 0.0) for r in root_rows)
	tot_net_profit = sum(r.get("net_profit", 0.0) for r in root_rows)

	cm_pct = flt((tot_cm / tot_nsv * 100) if tot_nsv > 0 else 0.0, 1)
	cogs_pct = flt((tot_cogs / tot_nsv * 100) if tot_nsv > 0 else 0.0, 1)
	var_opex_pct = flt((tot_var_opex / tot_nsv * 100) if tot_nsv > 0 else 0.0, 1)
	net_profit_pct = flt((tot_net_profit / tot_nsv * 100) if tot_nsv > 0 else 0.0, 1)
	fixed_burden_pct = flt(((tot_fixed_op + tot_employee + tot_overhead) / tot_nsv * 100) if tot_nsv > 0 else 0.0, 1)

	# Identify top regional contributor (SM or DM with highest CM)
	sm_or_dm_rows = [r for r in data if r.get("tier") in ("SM", "DM") and r.get("contribution_margin", 0) > 0]
	if not sm_or_dm_rows:
		sm_or_dm_rows = [r for r in data if r.get("contribution_margin", 0) > 0]

	top_contributor = max(sm_or_dm_rows, key=lambda x: x.get("contribution_margin", 0.0)) if sm_or_dm_rows else None

	# Identify territory with lowest CM % or margin dilution
	potential_risks = [r for r in data if r.get("tier") in ("SM", "DM") and r.get("gross_revenue", 0) > 0]
	if not potential_risks:
		potential_risks = [r for r in data if r.get("gross_revenue", 0) > 0]
	lowest_contributor = min(potential_risks, key=lambda x: x.get("contribution_margin_pct", 100.0)) if potential_risks else None

	currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency") or "IDR"

	def fmt_money(val):
		v = flt(val)
		if abs(v) >= 1_000_000_000:
			return f"{v / 1_000_000_000:,.2f} B"
		elif abs(v) >= 1_000_000:
			return f"{v / 1_000_000:,.2f} M"
		return f"{v:,.0f}"

	# Dynamic narrative commentary
	observations = []
	if cm_pct >= 85:
		observations.append(f"<strong>Exceptional Commercial Margin:</strong> Contribution Margin stands at <strong>{cm_pct}%</strong> ({currency} {fmt_money(tot_cm)}), reflecting disciplined pricing and low variable cost leakage.")
	elif cm_pct >= 60:
		observations.append(f"<strong>Stable Contribution Margin:</strong> Margin performance is healthy at <strong>{cm_pct}%</strong> ({currency} {fmt_money(tot_cm)}). Direct COGS consumes {cogs_pct}% of net revenue.")
	else:
		observations.append(f"<strong>Margin Dilution Alert:</strong> Contribution Margin is at <strong>{cm_pct}%</strong>, below target thresholds. Recommend auditing regional trade discounts and transport rates.")

	if net_profit_pct > 0:
		observations.append(f"<strong>Positive Bottom Line:</strong> Regional operations generated net profit of <strong>{currency} {fmt_money(tot_net_profit)}</strong> ({net_profit_pct}% conversion), adequately covering all local fixed and shared overheads.")
	else:
		observations.append(f"<strong>Operational Deficit:</strong> Net Profit is currently in deficit (<strong>{currency} {fmt_money(tot_net_profit)}</strong>), driven by fixed cost and corporate overhead burden ({fixed_burden_pct}% of NSV).")

	top_card_html = ""
	if top_contributor:
		top_card_html = f"""
		<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px 16px; flex: 1; min-width: 240px;">
			<div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #166534; letter-spacing: 0.5px; margin-bottom: 4px;">
				🏆 Top Regional Contributor
			</div>
			<div style="font-size: 15px; font-weight: 700; color: #14532d; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{top_contributor.get('sales_person_name')}">
				{top_contributor.get('sales_person_name')} ({top_contributor.get('tier')})
			</div>
			<div style="font-size: 12px; color: #15803d; margin-top: 4px;">
				CM: <strong>{currency} {fmt_money(top_contributor.get('contribution_margin'))}</strong> &bull; Margin: <strong>{top_contributor.get('contribution_margin_pct')}%</strong>
			</div>
		</div>
		"""

	watch_card_html = ""
	if lowest_contributor and lowest_contributor != top_contributor:
		watch_card_html = f"""
		<div style="background: #fffbeb; border: 1px solid #fef3c7; border-radius: 8px; padding: 12px 16px; flex: 1; min-width: 240px;">
			<div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #92400e; letter-spacing: 0.5px; margin-bottom: 4px;">
				⚠️ Margin Attention Node
			</div>
			<div style="font-size: 15px; font-weight: 700; color: #78350f; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{lowest_contributor.get('sales_person_name')}">
				{lowest_contributor.get('sales_person_name')} ({lowest_contributor.get('tier')})
			</div>
			<div style="font-size: 12px; color: #b45309; margin-top: 4px;">
				CM: <strong>{currency} {fmt_money(lowest_contributor.get('contribution_margin'))}</strong> &bull; Margin: <strong>{lowest_contributor.get('contribution_margin_pct')}%</strong>
			</div>
		</div>
		"""

	efficiency_card_html = f"""
	<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; flex: 1; min-width: 240px;">
		<div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #475569; letter-spacing: 0.5px; margin-bottom: 4px;">
			📊 Cost Structure Ratios
		</div>
		<div style="font-size: 12px; color: #334155; display: flex; flex-direction: column; gap: 3px;">
			<div>Direct COGS: <strong>{cogs_pct}%</strong> of NSV</div>
			<div>Variable OPEX: <strong>{var_opex_pct}%</strong> of NSV</div>
			<div>Fixed Overhead: <strong>{fixed_burden_pct}%</strong> of NSV</div>
		</div>
	</div>
	"""

	obs_items_html = "".join(f"<li style='margin-bottom: 4px;'>{obs}</li>" for obs in observations)

	return f"""
	<div class="frappe-insight-pnl-card" style="margin-bottom: 18px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
		<div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 14px;">
			<div style="display: flex; align-items: center; gap: 8px;">
				<span style="background: #2563eb; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;">INSIGHTS</span>
				<h5 style="margin: 0; font-size: 14px; font-weight: 700; color: #1e293b;">QL Financial Insights & Executive Commentary</h5>
			</div>
			<div style="font-size: 12px; color: #64748b;">
				Period: <strong>{filters.get('from_date')}</strong> to <strong>{filters.get('to_date')}</strong>
			</div>
		</div>

		<div style="display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px;">
			{top_card_html}
			{watch_card_html}
			{efficiency_card_html}
		</div>

		<div style="background: #f8fafc; border-left: 3px solid #2563eb; padding: 10px 14px; border-radius: 0 6px 6px 0;">
			<ul style="margin: 0; padding-left: 18px; font-size: 12px; color: #334155; line-height: 1.6;">
				{obs_items_html}
			</ul>
		</div>
	</div>
	"""
