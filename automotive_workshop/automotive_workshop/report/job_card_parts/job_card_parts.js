frappe.query_reports["Job Card Parts"] = {
	filters: [
		{ fieldname: "job_card", label: __("Job Card"), fieldtype: "Link", options: "Workshop Job Card" },
		{ fieldname: "status", label: __("Job Status"), fieldtype: "Select",
		  options: ["", "Parts Pending", "Work In Progress", "Quality Check", "Completed", "Invoiced"] },
		{ fieldname: "only_pending", label: __("Only parts not yet issued"), fieldtype: "Check", default: 1 },
		{ fieldname: "include_delivered", label: __("Include delivered vehicles"), fieldtype: "Check" },
	],
};
