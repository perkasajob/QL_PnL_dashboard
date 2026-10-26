# Copyright (c) 2026, QL and contributors
# License: MIT. See LICENSE

import json
import frappe
from frappe import _


def setup_all():
	"""
	Master programmatic setup script for Regional P&L & Contribution Margin packed in QL app.
	Creates/updates Number Cards, Dashboard Charts, and Workspace.
	Run via: bench --site <sitename> execute ql.regional_pnl.setup.setup_dashboard.setup_all
	"""
	print("--- Setting up Regional P&L & Contribution Margin in QL App ---")
	setup_reports_in_db()
	cards = setup_number_cards()
	charts = setup_dashboard_charts()
	setup_workspace(cards, charts)
	frappe.db.commit()
	print("=== Setup Completed Successfully ===")


def setup_reports_in_db():
	"""Ensures Report records exist in tabReport so Desk renders them immediately."""
	reports = [
		{
			"report_name": "Regional Contribution Margin P&L",
			"ref_doctype": "Sales Person",
			"report_type": "Script Report",
			"is_standard": "Yes",
			"module": "QL"
		},
		{
			"report_name": "Sales Person Pivot Tree Report",
			"ref_doctype": "Sales Person",
			"report_type": "Script Report",
			"is_standard": "Yes",
			"module": "QL"
		}
	]

	for r in reports:
		name = r["report_name"]
		if not frappe.db.exists("Report", name):
			doc = frappe.get_doc({
				"doctype": "Report",
				"name": name,
				"report_name": name,
				"ref_doctype": r["ref_doctype"],
				"report_type": r["report_type"],
				"is_standard": "Yes",
				"module": "QL"
			})
			doc.flags.ignore_links = True
			doc.flags.ignore_permissions = True
			doc.insert(ignore_permissions=True)
			print(f"Created Report: {name}")
		else:
			frappe.db.set_value("Report", name, {
				"module": "QL",
				"ref_doctype": r["ref_doctype"],
				"is_standard": "Yes",
				"disabled": 0
			})
			print(f"Updated Report: {name}")


def setup_number_cards():
	"""
	Creates the 6 core executive financial metric Number Cards:
	1. Total Net Sales (NSV)
	2. Total Contribution Margin
	3. Contribution Margin %
	4. Total Manufacturing Overhead
	5. Total Regional Sales Cost
	6. Regional Net Profit
	"""
	number_cards = [
		{
			"name": "Total Net Sales (NSV)",
			"label": "Total Net Sales (NSV)",
			"type": "Custom",
			"method": "ql.regional_pnl.api.get_total_nsv",
			"color": "#2563eb",
			"is_public": 1,
			"show_percentage_stats": 1,
			"stats_time_interval": "Monthly"
		},
		{
			"name": "Total Contribution Margin",
			"label": "Total Contribution Margin",
			"type": "Custom",
			"method": "ql.regional_pnl.api.get_total_contribution_margin",
			"color": "#10b981",
			"is_public": 1,
			"show_percentage_stats": 1,
			"stats_time_interval": "Monthly"
		},
		{
			"name": "Contribution Margin %",
			"label": "Contribution Margin %",
			"type": "Custom",
			"method": "ql.regional_pnl.api.get_contribution_margin_pct",
			"color": "#f59e0b",
			"is_public": 1,
			"show_percentage_stats": 1,
			"stats_time_interval": "Monthly"
		},
		{
			"name": "Total Manufacturing Overhead",
			"label": "Total Manufacturing Overhead",
			"type": "Custom",
			"method": "ql.regional_pnl.api.get_total_manufacturing_overhead",
			"color": "#8b5cf6",
			"is_public": 1,
			"show_percentage_stats": 1,
			"stats_time_interval": "Monthly"
		},
		{
			"name": "Total Regional Sales Cost",
			"label": "Total Regional Sales Cost",
			"type": "Custom",
			"method": "ql.regional_pnl.api.get_total_sales_operational_cost",
			"color": "#ec4899",
			"is_public": 1,
			"show_percentage_stats": 1,
			"stats_time_interval": "Monthly"
		},
		{
			"name": "Regional Net Profit",
			"label": "Regional Net Profit",
			"type": "Custom",
			"method": "ql.regional_pnl.api.get_total_net_profit",
			"color": "#06b6d4",
			"is_public": 1,
			"show_percentage_stats": 1,
			"stats_time_interval": "Monthly"
		}
	]

	created_names = []
	for card in number_cards:
		card_name = card["name"]
		if not frappe.db.exists("Number Card", card_name):
			doc = frappe.get_doc({
				"doctype": "Number Card",
				"name": card_name,
				"label": card["label"],
				"type": card["type"],
				"method": card["method"],
				"color": card["color"],
				"is_public": card["is_public"],
				"show_percentage_stats": card.get("show_percentage_stats", 1),
				"stats_time_interval": card.get("stats_time_interval", "Monthly"),
				"module": "QL"
			})
			doc.insert(ignore_permissions=True)
			print(f"Created Number Card: {card_name}")
		else:
			frappe.db.set_value("Number Card", card_name, {
				"label": card["label"],
				"type": card["type"],
				"method": card["method"],
				"color": card["color"],
				"is_public": card["is_public"],
				"module": "QL"
			})
			print(f"Updated Number Card: {card_name}")
		created_names.append(card_name)

	return created_names


def setup_dashboard_charts():
	"""
	Creates the 4 analytical charts:
	1. Sales Performance by Geography / SM Node (Bar Chart)
	2. Product / Item Revenue & Margin Breakdown (Donut / Bar Chart)
	3. Regional P&L Cost Stack (Waterfall / Stacked Bar)
	4. Hierarchical Sales Trajectory (Line Chart)
	"""
	charts = [
		{
			"chart_name": "Sales Performance by Geography (SM Node)",
			"chart_type": "Custom",
			"source": "ql.regional_pnl.api.get_sm_performance_chart",
			"type": "Bar",
			"color": "#2563eb",
			"is_public": 1,
			"timeseries": 0,
			"custom_options": json.dumps({
				"colors": ["#2563eb", "#10b981"],
				"axisOptions": {"xIsSeries": True}
			})
		},
		{
			"chart_name": "Product Revenue & Margin Breakdown",
			"chart_type": "Custom",
			"source": "ql.regional_pnl.api.get_product_margin_breakdown_chart",
			"type": "Bar",
			"color": "#8b5cf6",
			"is_public": 1,
			"timeseries": 0,
			"custom_options": json.dumps({
				"colors": ["#3b82f6", "#10b981"],
				"axisOptions": {"xIsSeries": True}
			})
		},
		{
			"chart_name": "Regional P&L Cost Stack",
			"chart_type": "Custom",
			"source": "ql.regional_pnl.api.get_cost_stack_chart",
			"type": "Bar",
			"color": "#ec4899",
			"is_public": 1,
			"timeseries": 0,
			"custom_options": json.dumps({
				"barOptions": {"stacked": True},
				"colors": ["#ef4444", "#8b5cf6", "#f97316", "#eab308", "#10b981"]
			})
		},
		{
			"chart_name": "Hierarchical Sales Trajectory",
			"chart_type": "Report",
			"report_name": "Sales Person Pivot Tree Report",
			"use_report_chart": 1,
			"type": "Line",
			"color": "#06b6d4",
			"is_public": 1,
			"timeseries": 1,
			"custom_options": json.dumps({
				"lineOptions": {"regionFill": 1}
			})
		}
	]

	created_charts = []
	for chart in charts:
		name = chart["chart_name"]
		src = chart.get("source")
		if src and not frappe.db.exists("Dashboard Chart Source", src):
			try:
				s_doc = frappe.get_doc({
					"doctype": "Dashboard Chart Source",
					"name": src,
					"source_name": src,
					"module": "QL"
				})
				s_doc.insert(ignore_permissions=True)
			except Exception:
				pass

		if not frappe.db.exists("Dashboard Chart", name):
			doc = frappe.get_doc({
				"doctype": "Dashboard Chart",
				"chart_name": name,
				"chart_type": chart["chart_type"],
				"source": chart.get("source"),
				"report_name": chart.get("report_name"),
				"use_report_chart": chart.get("use_report_chart", 0),
				"type": chart["type"],
				"color": chart["color"],
				"is_public": chart["is_public"],
				"timeseries": chart.get("timeseries", 0),
				"filters_json": "{}",
				"custom_options": chart.get("custom_options"),
				"module": "QL"
			})
			doc.flags.ignore_links = True
			doc.flags.ignore_permissions = True
			doc.flags.ignore_mandatory = True
			doc.insert(ignore_permissions=True)
			print(f"Created Dashboard Chart: {name}")
		else:
			frappe.db.set_value("Dashboard Chart", name, {
				"chart_type": chart["chart_type"],
				"source": chart.get("source"),
				"report_name": chart.get("report_name"),
				"use_report_chart": chart.get("use_report_chart", 0),
				"type": chart["type"],
				"color": chart["color"],
				"filters_json": "{}",
				"custom_options": chart.get("custom_options"),
				"module": "QL"
			})
			print(f"Updated Dashboard Chart: {name}")
		created_charts.append(name)

	return created_charts


def setup_workspace(card_names, chart_names):
	"""
	Constructs the rich Workspace 'Regional P&L & Contribution Margin'.
	Embeds Number Cards, Analytical Charts, and Quick Launchers.
	"""
	ws_name = "Regional P&L"
	ws_label = "Regional P&L & Contribution Margin"

	content = [
		{"type": "header", "data": {"text": "Executive Financial Highlights", "level": 4}},
		{"type": "number_card", "data": {"number_card_name": "Total Net Sales (NSV)"}},
		{"type": "number_card", "data": {"number_card_name": "Total Contribution Margin"}},
		{"type": "number_card", "data": {"number_card_name": "Contribution Margin %"}},
		{"type": "number_card", "data": {"number_card_name": "Total Manufacturing Overhead"}},
		{"type": "number_card", "data": {"number_card_name": "Total Regional Sales Cost"}},
		{"type": "number_card", "data": {"number_card_name": "Regional Net Profit"}},
		{"type": "header", "data": {"text": "Regional Analytics & Cost Breakdowns", "level": 4}},
		{"type": "chart", "data": {"chart_name": "Sales Performance by Geography (SM Node)", "col": 6}},
		{"type": "chart", "data": {"chart_name": "Regional P&L Cost Stack", "col": 6}},
		{"type": "chart", "data": {"chart_name": "Product Revenue & Margin Breakdown", "col": 6}},
		{"type": "chart", "data": {"chart_name": "Hierarchical Sales Trajectory", "col": 6}},
		{"type": "header", "data": {"text": "Reports & Masters", "level": 4}}
	]

	shortcuts = [
		{
			"type": "Report",
			"link_to": "Regional Contribution Margin P&L",
			"label": "Regional Contribution Margin P&L",
			"color": "#10b981",
			"icon": "table"
		},
		{
			"type": "Report",
			"link_to": "Sales Person Pivot Tree Report",
			"label": "Sales Person Pivot Tree Report",
			"color": "#2563eb",
			"icon": "git-commit"
		},
		{
			"type": "DocType",
			"link_to": "Manufacturing Overhead",
			"label": "Manufacturing Overhead (BOP)",
			"color": "#8b5cf6",
			"icon": "settings"
		},
		{
			"type": "DocType",
			"link_to": "Sales Operational Cost",
			"label": "Sales Operational Cost (SOC)",
			"color": "#ec4899",
			"icon": "dollar-sign"
		},
		{
			"type": "DocType",
			"link_to": "Manufacturing Cost",
			"label": "Manufacturing Cost Rates",
			"color": "#f59e0b",
			"icon": "activity"
		},
		{
			"type": "DocType",
			"link_to": "Sales Person",
			"label": "Sales Person Tree",
			"color": "#06b6d4",
			"icon": "users"
		}
	]

	links = [
		{
			"label": "Financial Reports & Business Intelligence",
			"type": "Card Break",
			"icon": "file-text"
		},
		{
			"type": "Link",
			"link_type": "Report",
			"link_to": "Regional Contribution Margin P&L",
			"label": "Regional Contribution Margin P&L",
			"onboard": 1
		},
		{
			"type": "Link",
			"link_type": "Report",
			"link_to": "Sales Person Pivot Tree Report",
			"label": "Sales Person Pivot Tree Report",
			"onboard": 1
		},
		{
			"label": "Dedicated Monthly Cost Inputs",
			"type": "Card Break",
			"icon": "database"
		},
		{
			"type": "Link",
			"link_type": "DocType",
			"link_to": "Manufacturing Overhead",
			"label": "Manufacturing Overhead (Factory BOP)",
			"onboard": 1
		},
		{
			"type": "Link",
			"link_type": "DocType",
			"link_to": "Sales Operational Cost",
			"label": "Sales Operational Cost (Marketing OPEX)",
			"onboard": 1
		},
		{
			"type": "Link",
			"link_type": "DocType",
			"link_to": "Manufacturing Cost",
			"label": "Manufacturing Cost (Period COGS)",
			"onboard": 1
		},
		{
			"type": "Link",
			"link_type": "DocType",
			"link_to": "Sales Person",
			"label": "Sales Person Hierarchy (GSM -> SM -> DM -> MR)",
			"onboard": 1
		}
	]

	target_ws = "Regional P&L" if frappe.db.exists("Workspace", "Regional P&L") else ws_name

	if not frappe.db.exists("Workspace", target_ws):
		doc = frappe.get_doc({
			"doctype": "Workspace",
			"name": target_ws,
			"label": ws_label,
			"title": ws_label,
			"type": "Workspace",
			"icon": "chart-line",
			"module": "QL",
			"public": 1,
			"is_hidden": 0,
			"content": json.dumps(content)
		})
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
	else:
		doc = frappe.get_doc("Workspace", target_ws)
		doc.label = ws_label
		doc.title = ws_label
		doc.type = "Workspace"
		doc.icon = "chart-line"
		doc.public = 1
		doc.module = "QL"
		doc.content = json.dumps(content)

	doc.set("shortcuts", [])
	for s in shortcuts:
		doc.append("shortcuts", {
			"type": s["type"],
			"link_to": s["link_to"],
			"label": s["label"],
			"color": s.get("color"),
			"icon": s.get("icon")
		})

	doc.set("links", [])
	for l in links:
		doc.append("links", {
			"label": l["label"],
			"type": l["type"],
			"link_type": l.get("link_type"),
			"link_to": l.get("link_to"),
			"icon": l.get("icon"),
			"onboard": l.get("onboard", 0)
		})

	doc.set("charts", [])
	for c in chart_names:
		doc.append("charts", {
			"chart_name": c,
			"label": c
		})

	doc.set("custom_blocks", [])
	for nb in card_names:
		doc.append("custom_blocks", {
			"number_card_name": nb,
			"label": nb
		})

	doc.flags.ignore_links = True
	doc.flags.ignore_mandatory = True
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	print(f"Created/Updated Workspace: {target_ws}")


if __name__ == "__main__":
	setup_all()
