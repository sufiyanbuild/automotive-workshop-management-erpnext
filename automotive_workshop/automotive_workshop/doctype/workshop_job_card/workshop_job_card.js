// Copyright (c) 2026, Sufiyan Shaikh and contributors
// For license information, please see license.txt

const AW_STATUS_COLORS = {
	Open: "red",
	"Inspection Completed": "orange",
	"Awaiting Approval": "yellow",
	"Parts Pending": "orange",
	"Work In Progress": "blue",
	"Quality Check": "purple",
	Completed: "green",
	Invoiced: "green",
};

frappe.ui.form.on("Workshop Job Card", {
	setup(frm) {
		frm.set_query("vehicle", () => ({ filters: { status: ["!=", "Inactive"] } }));
		frm.set_query("workshop_manager", () => ({
			query: "frappe.core.doctype.user.user.user_query",
			filters: { ignore_user_type: 1 },
		}));
	},

	refresh(frm) {
		if (frm.is_new()) {
			frm.set_intro(__("Select the vehicle (or create it with its owner), record the complaint and mileage, then save to open the Job Card."), "blue");
			return;
		}
		frm.set_intro("");
		const color = frm.doc.released ? "gray" : AW_STATUS_COLORS[frm.doc.status] || "gray";
		frm.page.set_indicator(frm.doc.released ? __("Delivered") : __(frm.doc.status), color);

		// The context is fetched asynchronously. If the user has moved to another Job
		// Card (or another page) in the meantime, this form is gone and drawing into it
		// would leave detached nodes behind, so the late answer is dropped.
		const requested_for = frm.doc.name;
		frappe
			.call("automotive_workshop.workshop.context.get_job_card_context", { job_card: requested_for })
			.then(({ message: ctx }) => {
				if (!ctx || cur_frm !== frm || frm.doc.name !== requested_for) return;
				frm.__aw_ctx = ctx;
				automotive.workshop.render_header(frm, ctx);
				automotive.workshop.render_panels(frm, ctx);
				automotive.workshop.add_menus(frm, ctx);
			});
	},

	vehicle(frm) {
		if (!frm.doc.vehicle) return;
		frappe.db.get_value("Vehicle Master", frm.doc.vehicle, "current_mileage").then(({ message }) => {
			if (message && !frm.doc.current_mileage) {
				frm.set_value("current_mileage", message.current_mileage);
			}
		});
	},
});
