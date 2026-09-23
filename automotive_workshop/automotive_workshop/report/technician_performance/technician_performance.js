frappe.query_reports["Technician Performance"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
		  default: frappe.datetime.add_months(frappe.datetime.get_today(), -3) },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "trade", label: __("Trade"), fieldtype: "Select", options: ["", "Denter", "Mechanic", "Electrician"] },
	],
};
