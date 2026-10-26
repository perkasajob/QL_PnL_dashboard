# Copyright (c) 2026, QL and contributors
# License: MIT. See LICENSE

import re
from datetime import datetime
import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, nowdate
from ql.tools.ql_tools import extract_sales_team_data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	dynamic_columns, pivot_keys = build_pivot_columns(filters)
	columns = get_base_columns(filters) + dynamic_columns + [get_accumulated_column(filters)]
	data = get_data(filters, dynamic_columns, pivot_keys)
	chart = get_chart(data, dynamic_columns, filters)
	report_summary = get_report_summary(data, columns, filters)
	message = get_pivot_insights_html(data, dynamic_columns, filters)

	return columns, data, message, chart, report_summary


def validate_filters(filters):
	if not filters.get("from_date"):
		filters.from_date = add_months(nowdate(), -3)
	if not filters.get("to_date"):
		filters.to_date = nowdate()

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be greater than To Date"))

	if not filters.get("pivot_by"):
		filters.pivot_by = "Monthly (Jan-Dec)"

	if not filters.get("value_field"):
		filters.value_field = "NSV"

	if not filters.get("hierarchy_level"):
		filters.hierarchy_level = "All"


def get_sales_person_tree():
	"""Legacy stub for backwards compatibility."""
	return []


def calculate_depth_map(tree_nodes):
	"""Legacy stub for backwards compatibility."""
	return {}


def get_tier_label(name_or_depth, is_group=0, parent=None):
	"""Returns tier label."""
	clean = str(name_or_depth or "").strip().upper()
	if clean in ("GSM", "SM", "DM", "MR"):
		return clean
	return "MR" if not is_group else "DM"


def get_column_mapping():
	"""Schema detection for tabSales Item."""
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


def build_pivot_columns(filters):
	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	pivot_by = filters.get("pivot_by")

	dynamic_cols = []
	pivot_keys = []

	if pivot_by == "Monthly (Jan-Dec)":
		curr_year = from_date.year
		curr_month = from_date.month
		end_year = to_date.year
		end_month = to_date.month

		while (curr_year < end_year) or (curr_year == end_year and curr_month <= end_month):
			ym_str = f"{curr_year}-{curr_month:02d}"
			fieldname = f"m_{curr_year}_{curr_month:02d}"
			label = datetime(curr_year, curr_month, 1).strftime("%b %Y")

			dynamic_cols.append({
				"label": _(label),
				"fieldname": fieldname,
				"fieldtype": "Currency",
				"options": "Company:company:default_currency",
				"width": 130
			})
			pivot_keys.append((ym_str, fieldname))

			curr_month += 1
			if curr_month > 12:
				curr_month = 1
				curr_year += 1

	elif pivot_by == "Quarter":
		curr_year = from_date.year
		curr_q = (from_date.month - 1) // 3 + 1
		end_year = to_date.year
		end_q = (to_date.month - 1) // 3 + 1

		while (curr_year < end_year) or (curr_year == end_year and curr_q <= end_q):
			q_str = f"{curr_year}-Q{curr_q}"
			fieldname = f"q_{curr_year}_q{curr_q}"
			label = f"{curr_year} Q{curr_q}"

			dynamic_cols.append({
				"label": _(label),
				"fieldname": fieldname,
				"fieldtype": "Currency",
				"options": "Company:company:default_currency",
				"width": 140
			})
			pivot_keys.append((q_str, fieldname))

			curr_q += 1
			if curr_q > 4:
				curr_q = 1
				curr_year += 1

	else:
		# Item Group / Product
		item_col, name_col, qty_col, amount_col, gsv_col, _hna_col = get_column_mapping()
		
		sold_items = frappe.db.sql(f"""
			SELECT 
				si.{item_col} as item_code,
				COALESCE(si.{name_col}, si.{item_col}) as item_name,
				SUM(COALESCE(si.{amount_col}, 0)) as total_val
			FROM `tabSales` s
			JOIN `tabSales Item` si ON si.parent COLLATE utf8mb4_unicode_ci = s.name COLLATE utf8mb4_unicode_ci
			WHERE s.custom_customers_purchase_order_date BETWEEN %(from_date)s AND %(to_date)s
				AND s.docstatus IN (0, 1)
			GROUP BY si.{item_col}, si.{name_col}
			ORDER BY total_val DESC
			LIMIT 15
		""", {
			"from_date": filters.get("from_date"),
			"to_date": filters.get("to_date")
		}, as_dict=True)

		if not sold_items:
			dynamic_cols.append({
				"label": _("All Products"),
				"fieldname": "item_all_products",
				"fieldtype": "Currency",
				"options": "Company:company:default_currency",
				"width": 150
			})
			pivot_keys.append(("__ALL__", "item_all_products"))
		else:
			for item in sold_items:
				code_clean = re.sub(r'[^a-zA-Z0-9_]', '_', item.item_code or "item").lower()
				fieldname = f"item_{code_clean[:20]}"
				label = item.item_name or item.item_code

				dynamic_cols.append({
					"label": _(label),
					"fieldname": fieldname,
					"fieldtype": "Currency",
					"options": "Company:company:default_currency",
					"width": 150
				})
				pivot_keys.append((item.item_code, fieldname))

			dynamic_cols.append({
				"label": _("Other Products"),
				"fieldname": "item_other",
				"fieldtype": "Currency",
				"options": "Company:company:default_currency",
				"width": 140
			})
			pivot_keys.append(("__OTHER__", "item_other"))

	return dynamic_cols, pivot_keys


def get_base_columns(filters):
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
		}
	]


def get_accumulated_column(filters):
	return {
		"label": _("Accumulated Sales (Total)"),
		"fieldname": "accumulated_sales",
		"fieldtype": "Currency",
		"options": "Company:company:default_currency",
		"width": 170
	}


def get_data(filters, dynamic_columns, pivot_keys):
	"""
	Generates multi-period/item pivot matrix grouped hierarchically:
	GSM -> SM -> DM -> MR strictly from tabSales records.
	"""
	item_col, name_col, qty_col, amount_col, gsv_col, hna_col = get_column_mapping()
	val_field_choice = filters.get("value_field", "NSV")
	pivot_by = filters.get("pivot_by")
	target_tier = filters.get("hierarchy_level", "All")

	docstatus_mode = filters.get("docstatus_filter", "All (0 & 1)")
	docstatus_sql = "AND docstatus = 1" if docstatus_mode == "Submitted Only (1)" else "AND docstatus IN (0, 1)"

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
	""", {
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date")
	}, as_dict=True)

	if not sales_headers:
		return []

	# Check if we need line items (for GSV, Item Amount, Contribution Margin, or Product pivot)
	need_items = (val_field_choice != "NSV") or (pivot_by == "Item Group / Product")
	item_map = {}
	cost_lookup = {}

	if need_items:
		sales_names = [s.name for s in sales_headers]
		batch_size = 1000
		hna_select = f", COALESCE(si.{hna_col}, 0.0) as unit_hna" if hna_col else ", 0.0 as unit_hna"

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

		if val_field_choice == "Contribution Margin":
			mcf_records = frappe.db.sql("""
				SELECT 
					COALESCE(product_id, item_code) as item_code,
					period_start_date,
					period_end_date,
					COALESCE(variable_cogs_per_piece, 0.0) as var_cogs
				FROM `tabManufacturing Cost`
			""", as_dict=True)
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
				return flt(c.var_cogs)
		return 0.0

	known_items_map = {}
	if pivot_by == "Item Group / Product":
		for code, fname in pivot_keys:
			if code not in ("__ALL__", "__OTHER__"):
				known_items_map[code] = fname

	nodes = {}
	dyn_col_names = [col["fieldname"] for col in dynamic_columns]

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
					"code": c, "name": nm, "accumulated_sales": 0.0
				}
				for c_k in dyn_col_names:
					nodes[k][c_k] = 0.0

		# Determine column allocations & metric values
		allocations = []  # list of (target_col_fieldname, metric_val)

		if not need_items:
			target_col = None
			if pivot_by == "Monthly (Jan-Dec)":
				if po_date:
					target_col = f"m_{po_date.year}_{po_date.month:02d}"
			elif pivot_by == "Quarter":
				if po_date:
					q = (po_date.month - 1) // 3 + 1
					target_col = f"q_{po_date.year}_q{q}"
			if target_col and target_col in dyn_col_names:
				allocations.append((target_col, header_nsv))
		else:
			order_items = item_map.get(s.name, [])
			if not order_items:
				target_col = None
				if pivot_by == "Monthly (Jan-Dec)" and po_date:
					target_col = f"m_{po_date.year}_{po_date.month:02d}"
				elif pivot_by == "Quarter" and po_date:
					q = (po_date.month - 1) // 3 + 1
					target_col = f"q_{po_date.year}_q{q}"
				elif pivot_by == "Item Group / Product":
					target_col = "item_other"
				if target_col and target_col in dyn_col_names:
					allocations.append((target_col, header_nsv))
			else:
				computed_items = []
				order_gsv = 0.0
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

					if val_field_choice == "GSV":
						metric_val = item_gsv
					elif val_field_choice == "Item Amount":
						metric_val = flt(it.amount) or item_gsv
					elif val_field_choice == "Contribution Margin":
						unit_cogs = get_unit_cogs(it.item_code, po_date)
						metric_val = item_nsv - (qty * unit_cogs)
					else:
						metric_val = item_nsv

					target_col = None
					if pivot_by == "Monthly (Jan-Dec)":
						if po_date:
							target_col = f"m_{po_date.year}_{po_date.month:02d}"
					elif pivot_by == "Quarter":
						if po_date:
							q = (po_date.month - 1) // 3 + 1
							target_col = f"q_{po_date.year}_q{q}"
					else:
						item_code = it.item_code
						if item_code in known_items_map:
							target_col = known_items_map[item_code]
						elif "__ALL__" in dict(pivot_keys):
							target_col = "item_all_products"
						else:
							target_col = "item_other"

					if target_col and target_col in dyn_col_names:
						allocations.append((target_col, metric_val))

		# Add allocations to all 4 hierarchy nodes
		for target_col, val in allocations:
			for k in (k_gsm, k_sm, k_dm, k_mr):
				nodes[k][target_col] = nodes[k].get(target_col, 0.0) + val
				nodes[k]["accumulated_sales"] += val

	# Sort hierarchically: GSM -> SM -> DM -> MR
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

		row = {
			"sales_person": n["key"],
			"sales_person_name": n["name"],
			"parent_sales_person": n["parent"] if target_tier == "All" else None,
			"tier": n["tier"],
			"indent": n["indent"] if target_tier == "All" else 0,
			"is_group": n["is_group"],
			"has_value": True,
			"accumulated_sales": flt(n["accumulated_sales"], 2)
		}
		for c_k in dyn_col_names:
			row[c_k] = flt(n.get(c_k, 0.0), 2)

		result_rows.append(row)

	return result_rows


def get_chart(data, dynamic_columns, filters):
	if not dynamic_columns:
		return None

	top_nodes = [r for r in data if r.get("tier") == "SM"][:5]
	if not top_nodes:
		top_nodes = [r for r in data if r.get("tier") in ("DM", "GSM")][:5]
	if not top_nodes:
		top_nodes = data[:3]

	labels = [col["label"] for col in dynamic_columns]
	datasets = []
	colors = ["#2563eb", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6"]

	for idx, node in enumerate(top_nodes):
		values = [node.get(col["fieldname"], 0.0) for col in dynamic_columns]
		datasets.append({
			"name": node.get("sales_person_name") or node.get("sales_person"),
			"values": values
		})

	return {
		"data": {
			"labels": labels,
			"datasets": datasets
		},
		"type": "line",
		"colors": colors[:len(datasets)]
	}


def get_report_summary(data, columns, filters):
	root_rows = [r for r in data if r.get("indent") == 0]
	if not root_rows:
		root_rows = data

	total_accumulated = sum(flt(r.get("accumulated_sales", 0.0)) for r in root_rows)
	currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency") or "IDR"
	metric_label = filters.get("value_field", "Sales")

	return [
		{
			"value": total_accumulated,
			"label": _(f"Total Accumulated {metric_label}"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Blue"
		}
	]


def get_pivot_insights_html(data, dynamic_columns, filters):
	"""Generates narrative insights banner for Sales Person Pivot Tree Report."""
	if not data:
		return ""

	root_rows = [r for r in data if r.get("indent") == 0]
	if not root_rows:
		root_rows = data

	total_sales = sum(flt(r.get("accumulated_sales", 0.0)) for r in root_rows)
	currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency") or "IDR"
	metric_name = filters.get("value_field", "NSV")

	def fmt_money(val):
		v = flt(val)
		if abs(v) >= 1_000_000_000:
			return f"{v / 1_000_000_000:,.2f} B"
		elif abs(v) >= 1_000_000:
			return f"{v / 1_000_000:,.2f} M"
		return f"{v:,.0f}"

	# Find top performing node (SM or DM)
	sm_nodes = [r for r in data if r.get("tier") in ("SM", "DM") and flt(r.get("accumulated_sales", 0)) > 0]
	if not sm_nodes:
		sm_nodes = [r for r in data if flt(r.get("accumulated_sales", 0)) > 0]
	top_seller = max(sm_nodes, key=lambda x: flt(x.get("accumulated_sales", 0.0))) if sm_nodes else None

	# Period breakdown & Peak period analysis
	peak_period = None
	peak_total = 0.0
	period_totals = {}
	if dynamic_columns:
		for col in dynamic_columns:
			col_key = col.get("fieldname")
			col_tot = sum(flt(r.get(col_key, 0.0)) for r in root_rows)
			period_totals[col["label"]] = col_tot
			if col_tot > peak_total:
				peak_total = col_tot
				peak_period = col["label"]

	# Trajectory direction: compare first and last period if available
	trend_text = "Stable"
	if len(dynamic_columns) >= 2:
		first_col = dynamic_columns[0].get("fieldname")
		last_col = dynamic_columns[-1].get("fieldname")
		first_val = sum(flt(r.get(first_col, 0.0)) for r in root_rows)
		last_val = sum(flt(r.get(last_col, 0.0)) for r in root_rows)
		if first_val > 0:
			growth = ((last_val - first_val) / first_val) * 100
			if growth > 5:
				trend_text = f"Expanding (+{growth:.1f}% vs first period)"
			elif growth < -5:
				trend_text = f"Contracting ({growth:.1f}% vs first period)"
			else:
				trend_text = f"Stable ({growth:+.1f}%)"

	top_card_html = ""
	if top_seller:
		top_card_html = f"""
		<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px 16px; flex: 1; min-width: 240px;">
			<div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #166534; letter-spacing: 0.5px; margin-bottom: 4px;">
				🏆 Leading Contributor
			</div>
			<div style="font-size: 15px; font-weight: 700; color: #14532d; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{top_seller.get('sales_person_name')}">
				{top_seller.get('sales_person_name')} ({top_seller.get('tier')})
			</div>
			<div style="font-size: 12px; color: #15803d; margin-top: 4px;">
				Accumulated: <strong>{currency} {fmt_money(top_seller.get('accumulated_sales'))}</strong>
			</div>
		</div>
		"""

	peak_card_html = ""
	if peak_period:
		peak_card_html = f"""
		<div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px 16px; flex: 1; min-width: 240px;">
			<div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #1e40af; letter-spacing: 0.5px; margin-bottom: 4px;">
				📈 Peak Sales Window
			</div>
			<div style="font-size: 15px; font-weight: 700; color: #1e3a8a;">
				{peak_period}
			</div>
			<div style="font-size: 12px; color: #2563eb; margin-top: 4px;">
				Volume: <strong>{currency} {fmt_money(peak_total)}</strong>
			</div>
		</div>
		"""

	trend_card_html = f"""
	<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; flex: 1; min-width: 240px;">
		<div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #475569; letter-spacing: 0.5px; margin-bottom: 4px;">
			📊 Sales Trajectory Trend
		</div>
		<div style="font-size: 15px; font-weight: 700; color: #0f172a;">
			{trend_text}
		</div>
		<div style="font-size: 12px; color: #64748b; margin-top: 4px;">
			Aggregated Periods: <strong>{len(dynamic_columns)} {filters.get('pivot_by', 'intervals')}</strong>
		</div>
	</div>
	"""

	return f"""
	<div class="frappe-insight-pivot-card" style="margin-bottom: 18px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
		<div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 14px;">
			<div style="display: flex; align-items: center; gap: 8px;">
				<span style="background: #0284c7; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;">INSIGHTS</span>
				<h5 style="margin: 0; font-size: 14px; font-weight: 700; color: #1e293b;">QL Sales Velocity & Periodic Trajectory Insights</h5>
			</div>
			<div style="font-size: 12px; color: #64748b;">
				Metric: <strong>{metric_name}</strong> &bull; Pivot: <strong>{filters.get('pivot_by')}</strong>
			</div>
		</div>

		<div style="display: flex; gap: 12px; flex-wrap: wrap;">
			{top_card_html}
			{peak_card_html}
			{trend_card_html}
		</div>
	</div>
	"""
