// Copyright (c) 2026, Sufiyan Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vehicle Master", {
	refresh(frm) {
		const $history = frm.get_field("service_history_html").$wrapper;
		if (frm.is_new()) {
			$history.html("");
			return;
		}
		if (frm.doc.status !== "In Workshop" && frm.doc.status !== "Inactive") {
			frm.add_custom_button(__("Book In (New Job Card)"), () => {
				frappe.new_doc("Workshop Job Card", { vehicle: frm.doc.name, current_mileage: frm.doc.current_mileage });
			}).addClass("btn-primary");
		}
		frm.add_custom_button(__("Customer"), () => frappe.set_route("Form", "Customer", frm.doc.customer), __("View"));

		frappe
			.call("automotive_workshop.workshop.history.get_service_history", { vehicle: frm.doc.name })
			.then(({ message: rows }) => {
				const e = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
				if (!rows || !rows.length) {
					$history.html(`<div class="text-muted">${__("No workshop visits recorded yet.")}</div>`);
					return;
				}
				$history.html(`
					<p><b>${e(frm.doc.vehicle_title)}</b> · ${__("Registration")}: ${e(frm.doc.registration_number)}</p>
					<div class="aw-table-wrap"><table class="aw-table">
						<thead><tr><th>${__("Job Card")}</th><th>${__("Date")}</th><th>${__("Service")}</th>
						<th>${__("Complaint")}</th><th>${__("Status")}</th><th>${__("Invoiced")}</th></tr></thead>
						<tbody>${rows
							.map(
								(r) => `<tr>
								<td>${frappe.utils.get_form_link("Workshop Job Card", r.name, true)}</td>
								<td>${e(frappe.datetime.str_to_user(r.intake_datetime))}</td>
								<td>${e(__(r.service_type))}</td><td>${e(r.complaint)}</td>
								<td>${e(r.released ? __("Delivered") : __(r.status))}</td>
								<td>${r.invoice_total ? format_currency(r.invoice_total, r.currency) : ""}</td></tr>`
							)
							.join("")}</tbody></table></div>`);
			});
	},
});
