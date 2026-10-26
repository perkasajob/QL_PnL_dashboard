// Copyright (c) 2026, QL and contributors
// License: MIT. See LICENSE

frappe.query_reports["Sales Person Pivot Tree"] = {
	tree: true,
	name_field: "sales_person",
	parent_field: "parent_sales_person",
	initial_depth: 3,

	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company")
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "pivot_by",
			label: __("Pivot By"),
			fieldtype: "Select",
			options: [
				"Monthly (Jan-Dec)",
				"Quarter",
				"Item Group / Product"
			],
			default: "Monthly (Jan-Dec)",
			reqd: 1
		},
		{
			fieldname: "value_field",
			label: __("Value Field"),
			fieldtype: "Select",
			options: [
				"NSV",
				"Item Amount",
				"GSV",
				"Contribution Margin"
			],
			default: "NSV",
			reqd: 1
		},
		{
			fieldname: "hierarchy_level",
			label: __("Hierarchy Level"),
			fieldtype: "Select",
			options: ["All", "GSM", "SM", "DM", "MR"],
			default: "All"
		},
		{
			fieldname: "docstatus_filter",
			label: __("Document Status"),
			fieldtype: "Select",
			options: ["All (0 & 1)", "Submitted Only (1)"],
			default: "All (0 & 1)"
		}
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) return value;

		// 1. Rightmost Anchored Columns Highlighting
		if (column.fieldname === "accumulated_sales") {
			value = `<span style="font-weight: 700; background-color: #f8fafc; color: #1e293b; display: inline-block; width: 100%; padding: 2px 6px; border-left: 2px solid #cbd5e1; border-radius: 2px;">${value}</span>`;
			return value;
		}

		if (column.fieldname === "accumulated_cm") {
			var cm_val = flt(data.accumulated_cm);
			var color = cm_val < 0 ? "#dc2626" : "#16a34a";
			var bg = cm_val < 0 ? "#fef2f2" : "#f0fdf4";
			var border = cm_val < 0 ? "#fca5a5" : "#86efac";
			value = `<span style="font-weight: 700; background-color: ${bg}; color: ${color}; display: inline-block; width: 100%; padding: 2px 6px; border-left: 2px solid ${border}; border-radius: 2px;">${value}</span>`;
			return value;
		}

		// 2. Bold group rows (GSM, SM, DM)
		if (data.is_group === 1 || data.is_group === true || data.indent < 3) {
			value = `<span style="font-weight: 700; color: #0f172a;">${value}</span>`;
		}

		return value;
	}
};
