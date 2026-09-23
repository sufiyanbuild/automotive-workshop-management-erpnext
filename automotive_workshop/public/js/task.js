frappe.ui.form.on("Task", {
	setup(frm) {
		frm.set_query("aw_technician", () => ({
			query: "frappe.core.doctype.user.user.user_query",
			filters: { ignore_user_type: 1 },
		}));
	},
	refresh(frm) {
		if (!frm.doc.aw_job_card) return;
		frm.add_custom_button(__("Workshop Job Card"), () =>
			frappe.set_route("Form", "Workshop Job Card", frm.doc.aw_job_card), __("View"));
	},
	status(frm) {
		if (frm.doc.aw_job_card && frm.doc.status === "Completed" && !flt(frm.doc.aw_labour_hours)) {
			frappe.show_alert({ message: __("Enter the labour hours worked before saving."), indicator: "orange" });
			frm.scroll_to_field("aw_labour_hours");
		}
	},
});
