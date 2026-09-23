frappe.query_reports["Customer Vehicle Report"] = {
	filters: [
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "only_outstanding", label: __("Only customers with an outstanding balance"), fieldtype: "Check" },
	],
};
