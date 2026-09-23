frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (!frm.doc.aw_job_card) return;
		frm.add_custom_button(__("Workshop Job Card"), () =>
			frappe.set_route("Form", "Workshop Job Card", frm.doc.aw_job_card), __("View"));
		if (frm.doc.docstatus === 1) {
			const colors = { Pending: "orange", Approved: "green", Rejected: "red", "Revision Requested": "yellow" };
			const state = frm.doc.aw_customer_approval || "Pending";
			frm.dashboard.add_indicator(__("Customer: {0}", [__(state)]), colors[state] || "gray");
			frm.set_intro(__("Send this quotation and record the customer's decision from the Workshop Job Card."), "blue");
		}
		// Sales Orders are not part of the workshop flow; invoicing runs from the Job Card after QC.
		if (frm.doc.docstatus === 1) {
			setTimeout(() => {
				frm.remove_custom_button(__("Sales Order"), __("Create"));
				frm.remove_custom_button(__("Sales Invoice"), __("Create"));
			}, 0);
		}
	},
});
