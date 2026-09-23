// Tab contents (inspections, parts, repair, history) and the Create / Actions
// handlers for the Workshop Job Card. Menu entries come from the server; this
// file only knows how to carry each one out.

frappe.provide("automotive.workshop");

const e = (value) => frappe.utils.escape_html(value == null ? "" : String(value));
const API = "automotive_workshop.workshop";
// frappe.utils.get_form_link builds the desk route, so these links stay correct
// wherever the desk is mounted.
const link = (doctype, name) => (name ? frappe.utils.get_form_link(doctype, name, true) : "");
const pill = (label, color) => `<span class="indicator-pill ${color}">${e(__(label))}</span>`;
const table = (headers, rows) =>
	`<div class="aw-table-wrap"><table class="aw-table"><thead><tr>${headers
		.map((h) => `<th>${e(h)}</th>`)
		.join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;

const DOC_STATE = { 0: ["Draft", "red"], 1: ["Submitted", "blue"], 2: ["Cancelled", "gray"] };
const PART_COLORS = { Issued: "green", Available: "blue", "On Order": "orange", Requested: "orange", Shortage: "red" };
const TASK_COLORS = { Completed: "green", Working: "orange", Open: "gray", "Pending Review": "blue", Overdue: "red" };

automotive.workshop.render_panels = function (frm, ctx) {
	const set = (field, html) => frm.get_field(field) && frm.get_field(field).$wrapper.html(html);

	// Inspection
	set(
		"inspection_html",
		ctx.inspections.length
			? table(
					[__("Inspection"), __("Type"), __("Inspected By"), __("When"), __("Result"), __("Status")],
					ctx.inspections.map(
						(i) => `<tr><td>${link("Vehicle Inspection", i.name)}</td><td>${e(__(i.inspection_type))}</td>
						<td>${e(frappe.user.full_name(i.technician))}</td>
						<td>${e(frappe.datetime.str_to_user(i.inspection_datetime))}</td>
						<td>${e(__(i.qc_result || i.overall_condition || ""))}</td>
						<td>${pill(...DOC_STATE[i.docstatus])}</td></tr>`
					)
			  )
			: `<div class="aw-empty">${__("No inspections yet. Use Actions → Start Inspection.")}</div>`
	);

	// Parts
	const parts = ctx.parts;
	const docs = [
		...ctx.material_requests.map((m) => `${__("Material Request")} ${link("Material Request", m.name)} (${e(__(m.status))})`),
		...ctx.parts_issues.map((s) => `${__("Parts Issue")} ${link("Stock Entry", s.name)} (${e(__(DOC_STATE[s.docstatus][0]))})`),
	];
	set(
		"parts_html",
		parts.total
			? `<p class="text-muted">${__("Warehouse")}: ${e(parts.warehouse)}</p>` +
					table(
						[__("Part"), __("Required"), __("Issued"), __("In Stock"), __("Requested"), __("Ordered"), __("Received"), __("State")],
						parts.lines.map(
							(p) => `<tr><td>${link("Item", p.item_code)}<div class="text-muted">${e(p.item_name)}</div></td>
							<td>${p.required} ${e(p.uom || "")}</td><td>${p.issued}</td><td>${p.in_stock}</td>
							<td>${p.requested}</td><td>${p.ordered}</td><td>${p.received}</td>
							<td>${pill(p.state, PART_COLORS[p.state] || "gray")}</td></tr>`
						)
					) +
					(docs.length ? `<p class="mt-3">${docs.join("<br>")}</p>` : "")
			: `<div class="aw-empty">${__("No parts required on the submitted Damage Assessment.")}</div>`
	);

	// Repair
	set(
		"repair_html",
		ctx.tasks.length
			? table(
					[__("Task"), __("Trade"), __("Technician"), __("Progress"), __("Hours (est. / actual)"), __("Status")],
					ctx.tasks.map(
						(t) => `<tr><td>${link("Task", t.name)}<div class="text-muted">${e(t.subject)}</div></td>
						<td>${e(__(t.aw_trade || ""))}</td><td>${e(frappe.user.full_name(t.aw_technician))}</td>
						<td>${t.progress || 0}%</td><td>${t.expected_time || 0} / ${t.aw_labour_hours || 0}</td>
						<td>${pill(t.status, TASK_COLORS[t.status] || "gray")}</td></tr>`
					)
			  )
			: `<div class="aw-empty">${__("No repair tasks assigned yet.")}</div>`
	);

	// History
	set(
		"history_html",
		ctx.history.length
			? `<p><b>${e(frm.doc.vehicle_title)}</b> · ${__("Registration")}: ${e(frm.doc.registration_number)}</p>` +
					table(
						[__("Job Card"), __("Date"), __("Service"), __("Status"), __("Mileage"), __("Invoiced")],
						ctx.history.map(
							(h) => `<tr><td>${link("Workshop Job Card", h.name)}</td>
							<td>${e(frappe.datetime.str_to_user(h.intake_datetime))}</td><td>${e(__(h.service_type))}</td>
							<td>${e(h.released ? __("Delivered") : __(h.status))}</td><td>${e(h.current_mileage)}</td>
							<td>${h.invoice_total ? format_currency(h.invoice_total, h.currency) : ""}</td></tr>`
						)
					)
			: `<div class="aw-empty">${__("This is the first recorded visit for this vehicle.")}</div>`
	);
};

// ------------------------------------------------------------------ menus
automotive.workshop.add_menus = function (frm, ctx) {
	const CREATE = __("Create");
	const ACTIONS = __("Actions");
	// Frappe disables the button while a returned thenable settles, and calls
	// .finally() on it. frappe.call returns a jQuery promise, which has .then but
	// not .finally, so the result is adopted into a native promise here.
	const handler = (item) => () => Promise.resolve(automotive.workshop.run(frm, item.key, item));
	ctx.create.forEach((item) => frm.add_custom_button(item.label, handler(item), CREATE));
	ctx.actions.forEach((item) => frm.add_custom_button(item.label, handler(item), ACTIONS));
};

// ------------------------------------------------------------------ handlers
const mapped = (frm, method, args) =>
	frappe.model.open_mapped_doc({ method: `${API}.mappers.${method}`, frm, args: args || {} });

const call = (frm, method, args, message) =>
	frappe
		.call({ method: `${API}.actions.${method}`, args: { job_card: frm.doc.name, ...(args || {}) }, freeze: true })
		.then(() => {
			if (message) frappe.show_alert({ message, indicator: "green" });
			frm.reload_doc();
		});

function technician_options(frm, role) {
	return (frm.__aw_ctx.technicians[role] || []).map((t) => ({ label: t.label, value: t.value }));
}

function inspection_dialog(frm) {
	const trades = frm.__aw_ctx.trades;
	const own = trades.find((t) => frappe.user.has_role(t));
	const d = new frappe.ui.Dialog({
		title: __("Start Inspection"),
		fields: [
			{ fieldname: "inspection_type", fieldtype: "Select", label: __("Inspection Type"), reqd: 1,
			  options: trades.map((t) => ({ label: __(t), value: t })), default: own || trades[0],
			  onchange: () => {
				  const f = d.get_field("technician");
				  f.df.options = technician_options(frm, d.get_value("inspection_type"));
				  f.refresh();
				  d.set_value("technician", own ? frappe.session.user : "");
			  } },
			{ fieldname: "technician", fieldtype: "Select", label: __("Technician"), reqd: 1,
			  options: technician_options(frm, own || trades[0]), default: own ? frappe.session.user : "" },
		],
		primary_action_label: __("Start"),
		primary_action: (values) => {
			d.hide();
			mapped(frm, "make_vehicle_inspection", values);
		},
	});
	d.show();
}

function send_quotation_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Send Quotation {0}", [frm.doc.quotation]),
		fields: [
			{ fieldname: "channel", fieldtype: "Select", label: __("How is the quotation shared?"), reqd: 1,
			  options: [
				  { label: __("Email to the customer"), value: "Email" },
				  { label: __("Printed / handed over in person"), value: "In person" },
				  { label: __("Shared by phone or message"), value: "Phone or message" },
			  ], default: "Email" },
		],
		primary_action_label: __("Continue"),
		primary_action: ({ channel }) => {
			d.hide();
			if (channel !== "Email") {
				call(frm, "mark_quotation_sent", { channel }, __("Quotation marked as sent"));
				return;
			}
			frappe.model.with_doc("Quotation", frm.doc.quotation).then((doc) => {
				new frappe.views.CommunicationComposer({
					doc,
					frm: { doctype: "Quotation", docname: doc.name, doc, reload_doc: () => frm.reload_doc() },
					subject: __("Quotation {0} for {1} ({2})", [doc.name, frm.doc.vehicle_title, frm.doc.registration_number]),
					recipients: doc.contact_email || "",
					attach_document_print: true,
					title: __("Email Quotation"),
				});
			});
		},
	});
	d.show();
}

function approval_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Record Customer Approval"),
		fields: [
			{ fieldtype: "HTML", options: `<p>${__("Quotation")} ${link("Quotation", frm.doc.quotation)} · ${format_currency(frm.doc.quotation_total, frm.doc.currency)}</p>` },
			{ fieldname: "decision", fieldtype: "Select", label: __("Customer Decision"), reqd: 1,
			  options: [
				  { label: __("Approved"), value: "Approved" },
				  { label: __("Revision Requested"), value: "Revision Requested" },
				  { label: __("Rejected"), value: "Rejected" },
			  ] },
			{ fieldname: "remarks", fieldtype: "Small Text", label: __("Customer Remarks"),
			  mandatory_depends_on: "eval:doc.decision && doc.decision !== 'Approved'" },
		],
		primary_action_label: __("Record"),
		primary_action: (values) => {
			d.hide();
			call(frm, "record_customer_approval", values, __("Customer decision recorded"));
		},
	});
	d.show();
}

function parts_dialog(frm) {
	frappe.msgprint({
		title: __("Parts Availability"),
		message: frm.get_field("parts_html").$wrapper.html(),
		wide: true,
	});
}

function task_dialog(frm) {
	const trades = frm.__aw_ctx.trades;
	const d = new frappe.ui.Dialog({
		title: __("Assign Repair Task"),
		fields: [
			{ fieldname: "trade", fieldtype: "Select", label: __("Trade"), reqd: 1,
			  options: trades.map((t) => ({ label: __(t), value: t })), default: trades[0],
			  onchange: () => {
				  const f = d.get_field("technician");
				  f.df.options = technician_options(frm, d.get_value("trade"));
				  f.refresh();
			  } },
			{ fieldname: "technician", fieldtype: "Select", label: __("Technician"), reqd: 1,
			  options: technician_options(frm, trades[0]) },
			{ fieldname: "subject", fieldtype: "Data", label: __("Work to Do"), reqd: 1 },
			{ fieldname: "expected_time", fieldtype: "Float", label: __("Estimated Hours") },
		],
		primary_action_label: __("Assign"),
		primary_action: (values) => {
			d.hide();
			call(frm, "create_repair_task", values, __("Repair task assigned"));
		},
	});
	d.show();
}

function progress_dialog(frm) {
	const tasks = frm.__aw_ctx.tasks;
	const d = new frappe.ui.Dialog({
		title: __("Update Repair Progress"),
		size: "large",
		fields: [
			{ fieldname: "updates", fieldtype: "Table", label: __("Repair Tasks"), cannot_add_rows: 1,
			  in_place_edit: true, data: tasks.map((t) => ({
				  task: t.name, subject: t.subject, status: t.status, progress: t.progress || 0,
				  labour_hours: t.aw_labour_hours || 0,
			  })),
			  fields: [
				  { fieldname: "task", fieldtype: "Data", label: __("Task"), read_only: 1, hidden: 1 },
				  { fieldname: "subject", fieldtype: "Data", label: __("Task"), read_only: 1, in_list_view: 1, columns: 4 },
				  { fieldname: "status", fieldtype: "Select", label: __("Status"), in_list_view: 1, columns: 2,
					options: ["Open", "Working", "Pending Review", "Completed"] },
				  { fieldname: "progress", fieldtype: "Int", label: __("Progress %"), in_list_view: 1, columns: 2 },
				  { fieldname: "labour_hours", fieldtype: "Float", label: __("Hours Worked"), in_list_view: 1, columns: 2 },
			  ] },
		],
		primary_action_label: __("Save Progress"),
		primary_action: ({ updates }) => {
			d.hide();
			call(frm, "update_repair_progress", { updates: updates.map(({ task, status, progress, labour_hours }) => ({ task, status, progress, labour_hours })) },
				__("Repair progress saved"));
		},
	});
	d.show();
}

function reason_dialog(frm, title, method, label, message) {
	frappe.prompt({ fieldname: "reason", fieldtype: "Small Text", label, reqd: 1 },
		({ reason }) => call(frm, method, { reason }, message), title, __("Confirm"));
}

function release_dialog(frm) {
	const ctx = frm.__aw_ctx;
	const outstanding = ctx.outstanding || 0;
	const d = new frappe.ui.Dialog({
		title: __("Release Vehicle"),
		fields: [
			{ fieldtype: "HTML", options: `<p>${e(frm.doc.vehicle_title)} · ${e(frm.doc.registration_number)}<br>
				${__("Outstanding")}: <b>${format_currency(outstanding, frm.doc.currency)}</b></p>` },
			{ fieldname: "release_on_credit", fieldtype: "Check", label: __("Release with balance outstanding"),
			  hidden: outstanding <= 0 || ctx.release.require_full_payment ? 1 : 0 },
			{ fieldname: "notes", fieldtype: "Small Text", label: __("Delivery Notes"),
			  mandatory_depends_on: "eval:doc.release_on_credit" },
		],
		primary_action_label: __("Release Vehicle"),
		primary_action: (values) => {
			d.hide();
			call(frm, "release_vehicle", values, __("Vehicle released"));
		},
	});
	d.show();
}

function confirm_call(frm, text, method, message) {
	frappe.confirm(text, () => call(frm, method, {}, message));
}

automotive.workshop.run = function (frm, key, item) {
	const qc = (result) =>
		mapped(frm, "make_vehicle_inspection", { inspection_type: "Quality Check", qc_result: result, technician: frappe.session.user });
	const handlers = {
		inspection: () => inspection_dialog(frm),
		start_inspection: () => inspection_dialog(frm),
		damage_assessment: () => mapped(frm, "make_damage_assessment"),
		create_damage_assessment: () => mapped(frm, "make_damage_assessment"),
		quotation: () => mapped(frm, "make_quotation"),
		prepare_quotation: () => mapped(frm, "make_quotation"),
		revise_quotation: () =>
			frappe.confirm(__("Cancel Quotation {0} and prepare a revised one?", [frm.doc.quotation]), () =>
				frappe
					.call({ method: `${API}.actions.revise_quotation`, args: { job_card: frm.doc.name }, freeze: true })
					.then(() => frm.reload_doc())
					.then(() => mapped(frm, "make_quotation"))
			),
		send_quotation: () => send_quotation_dialog(frm),
		record_approval: () => approval_dialog(frm),
		check_parts: () => parts_dialog(frm),
		material_request: () => mapped(frm, "make_material_request"),
		request_parts: () => mapped(frm, "make_material_request"),
		parts_issue: () => mapped(frm, "make_parts_issue"),
		issue_parts: () => mapped(frm, "make_parts_issue"),
		repair_task: () => task_dialog(frm),
		assign_task: () => task_dialog(frm),
		start_repair: () => confirm_call(frm, __("Start the repair now?"), "start_repair", __("Repair started")),
		update_repair_progress: () => progress_dialog(frm),
		request_qc: () => confirm_call(frm, __("All repair tasks are complete. Request the final Quality Check?"), "request_quality_check", __("Quality Check requested")),
		quality_check: () =>
			frm.doc.status === "Quality Check"
				? qc("")
				: frappe
						.call({ method: `${API}.actions.request_quality_check`, args: { job_card: frm.doc.name }, freeze: true })
						.then(() => frm.reload_doc())
						.then(() => qc("")),
		pass_qc: () => qc("Passed"),
		reject_qc: () => qc("Failed"),
		return_to_repair: () =>
			reason_dialog(frm, __("Return to Repair"), "return_to_repair", __("What must be reworked?"), __("Returned to repair")),
		sales_invoice: () => mapped(frm, "make_sales_invoice"),
		generate_invoice: () => mapped(frm, "make_sales_invoice"),
		payment_entry: () => mapped(frm, "make_payment_entry"),
		record_payment: () => mapped(frm, "make_payment_entry"),
		release_vehicle: () => release_dialog(frm),
		view_history: () => automotive.workshop.focus_tab(frm, "history_tab"),
		view_customer: () => frappe.set_route("Form", "Customer", frm.doc.customer),
		view_tasks: () => frappe.set_route("List", "Task", { aw_job_card: frm.doc.name }),
	};
	if (handlers[key]) return handlers[key]();
	if (item && item.doc) return frappe.set_route("Form", item.doc.doctype, item.doc.name);
	if (key && key.startsWith("view_")) {
		const docs = { view_quotation: ["Quotation", frm.doc.quotation], view_invoice: ["Sales Invoice", frm.doc.sales_invoice],
			view_damage_assessment: ["Damage Assessment", frm.doc.damage_assessment] };
		if (docs[key] && docs[key][1]) return frappe.set_route("Form", ...docs[key]);
	}
	frappe.msgprint(__("This action is not available here."));
};
