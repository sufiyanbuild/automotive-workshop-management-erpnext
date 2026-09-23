frappe.query_reports["Workshop Job Card Register"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
		  default: frappe.datetime.add_months(frappe.datetime.get_today(), -3) },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select",
		  options: ["", "Open", "Inspection Completed", "Awaiting Approval", "Parts Pending", "Work In Progress",
					"Quality Check", "Completed", "Invoiced"] },
		{ fieldname: "service_type", label: __("Service Type"), fieldtype: "Select",
		  options: ["", "General Service", "Mechanical Repair", "Electrical Repair", "Body and Paint",
					"Accident Repair", "AC Repair", "Diagnostics", "Other"] },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "workshop_manager", label: __("Workshop Manager"), fieldtype: "Link", options: "User" },
		{ fieldname: "only_open", label: __("Only vehicles still in the workshop"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "outstanding_amount" && data && data.outstanding_amount > 0) {
			value = `<span style="color: var(--red-600)">${value}</span>`;
		}
		return value;
	},
};
