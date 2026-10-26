// Copyright (c) 2026, QL and contributors
// License: MIT. See LICENSE

frappe.query_reports["Regional Contribution Margin P&L"] = {
	tree: true,
	name_field: "sales_person",
	parent_field: "parent_sales_person",
	initial_depth: 2,

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
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
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
			fieldname: "hierarchy_level",
			label: __("Hierarchy Level"),
			fieldtype: "Select",
			options: ["All", "GSM", "SM", "DM", "MR"],
			default: "All"
		},
		{
			fieldname: "cost_basis",
			label: __("Costing Basis"),
			fieldtype: "Select",
			options: ["Variable Costing (Contribution)", "Statutory Valuation"],
			default: "Variable Costing (Contribution)",
			reqd: 1
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

		// 1. Bold all group nodes
		if (data.is_group === 1 || data.is_group === true || data.indent < 3) {
			value = `<span style="font-weight: 700;">${value}</span>`;
		}

		// 2. Highlight negative Contribution Margin in bold orange
		if (column.fieldname === "contribution_margin" || column.fieldname === "contribution_margin_pct") {
			var cm_val = flt(data.contribution_margin);
			if (cm_val < 0) {
				value = `<span style="color: #d97706; font-weight: 700;">${value}</span>`;
			}
		}

		// 3. Highlight Net Profit: bold red if < 0, green if > 0
		if (column.fieldname === "net_profit" || column.fieldname === "net_profit_pct") {
			var np_val = flt(data.net_profit);
			if (np_val < 0) {
				value = `<span style="color: #dc2626; font-weight: 700;">${value}</span>`;
			} else if (np_val > 0) {
				value = `<span style="color: #16a34a; font-weight: 700;">${value}</span>`;
			}
		}

		return value;
	}
};
