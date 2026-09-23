// Copyright (c) 2026, Sufiyan Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Damage Assessment", {
	setup(frm) {
		frm.set_query("item_code", "parts", () => ({ filters: { is_stock_item: 1, disabled: 0 } }));
	},
	refresh(frm) {
		if (frm.doc.job_card) {
			frm.add_custom_button(__("Job Card"), () => frappe.set_route("Form", "Workshop Job Card", frm.doc.job_card), __("View"));
		}
	},
	calculate(frm) {
		let parts = 0, labour = 0, hours = 0;
		(frm.doc.parts || []).forEach((r) => {
			r.amount = flt(r.qty) * flt(r.rate);
			parts += r.amount;
		});
		(frm.doc.labour || []).forEach((r) => {
			r.amount = flt(r.hours) * flt(r.rate);
			labour += r.amount;
			hours += flt(r.hours);
		});
		frm.set_value({ parts_total: parts, labour_total: labour, estimated_labour_hours: hours, estimated_total: parts + labour });
		frm.refresh_field("parts");
		frm.refresh_field("labour");
	},
});

frappe.ui.form.on("Damage Assessment Part", {
	qty: (frm) => frm.trigger("calculate"),
	rate: (frm) => frm.trigger("calculate"),
	parts_remove: (frm) => frm.trigger("calculate"),
});

frappe.ui.form.on("Damage Assessment Labour", {
	hours: (frm) => frm.trigger("calculate"),
	rate: (frm) => frm.trigger("calculate"),
	labour_remove: (frm) => frm.trigger("calculate"),
});
