frappe.listview_settings["Workshop Job Card"] = {
	add_fields: ["status", "released", "current_stage", "priority"],
	get_indicator(doc) {
		if (doc.released) return [__("Delivered"), "gray", "released,=,1"];
		const colors = {
			Open: "red", "Inspection Completed": "orange", "Awaiting Approval": "yellow", "Parts Pending": "orange",
			"Work In Progress": "blue", "Quality Check": "purple", Completed: "green", Invoiced: "green",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
