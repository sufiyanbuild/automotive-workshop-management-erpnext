frappe.listview_settings["Vehicle Master"] = {
	get_indicator(doc) {
		const colors = { Active: "green", "In Workshop": "blue", Inactive: "gray" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
