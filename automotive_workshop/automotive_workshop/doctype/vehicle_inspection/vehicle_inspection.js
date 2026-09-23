// Copyright (c) 2026, Sufiyan Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vehicle Inspection", {
	setup(frm) {
		frm.set_query("technician", () => ({
			query: "frappe.core.doctype.user.user.user_query",
			filters: { ignore_user_type: 1 },
		}));
	},
	refresh(frm) {
		if (frm.doc.job_card) {
			frm.add_custom_button(__("Job Card"), () => frappe.set_route("Form", "Workshop Job Card", frm.doc.job_card), __("View"));
		}
		if (frm.doc.docstatus === 0 && frm.doc.inspection_type === "Quality Check") {
			frm.set_intro(__("Final Quality Check: verify each repaired item. A failed result sends the vehicle back to repair."), "blue");
		}
	},
});

frappe.ui.form.on("Vehicle Inspection Item", {
	condition(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.condition === "Faulty" && frm.doc.inspection_type !== "Quality Check") {
			frappe.model.set_value(cdt, cdn, "damage_found", 1);
		}
	},
});
