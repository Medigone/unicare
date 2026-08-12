// Copyright (c) 2026, IntraPro and contributors
// For license information, please see license.txt

frappe.query_reports["Tracabilite Lot"] = {
	filters: [
		{
			fieldname: "batch_no",
			label: __("Lot"),
			fieldtype: "Link",
			options: "Batch",
			reqd: 1,
		},
	],
};
