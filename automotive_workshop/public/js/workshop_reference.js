// Shows which Workshop Job Card a standard document belongs to, with a way back.
// Shared by Sales Invoice, Material Request, Stock Entry and Payment Entry.

// doctype_js loads this file once per DocType; register the handlers only once.
if (!frappe.flags.aw_reference_loaded) {
frappe.flags.aw_reference_loaded = true;
["Sales Invoice", "Material Request", "Stock Entry", "Payment Entry"].forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (!frm.doc.aw_job_card) return;
			frm.add_custom_button(__("Workshop Job Card"), () =>
				frappe.set_route("Form", "Workshop Job Card", frm.doc.aw_job_card), __("View"));
			if (frm.is_new()) {
				frm.set_intro(__("Linked to Workshop Job Card {0}.", [frm.doc.aw_job_card.bold()]), "blue");
			}
		},
	});
});
}
