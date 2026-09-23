// Visual workflow tracker and current-stage panel for the Workshop Job Card.
// Draws only what the server computed (workshop/context.py); holds no rules.

frappe.provide("automotive.workshop");

const esc = (value) => frappe.utils.escape_html(value == null ? "" : String(value));

automotive.workshop.format_figure = function (figure, doc) {
	if (figure.type === "Currency") {
		return format_currency(figure.value, doc.currency);
	}
	if (figure.type === "Date") {
		return frappe.datetime.str_to_user(figure.value);
	}
	return esc(figure.value);
};

automotive.workshop.render_header = function (frm, ctx) {
	// The form dashboard sits above the tabs and stays visible on every tab.
	// Frappe's dashboard.reset() removes nodes marked "custom", so the header is
	// cleaned up by the framework instead of being torn out of the form layout.
	let $header = frm.dashboard.parent.find(".aw-header");
	if (!$header.length) {
		// Prepended so the workflow is the first thing on the screen, above the
		// connections Frappe renders in the same area.
		$header = $('<div class="aw-header custom"></div>').prependTo(frm.dashboard.parent);
	}
	frm.dashboard.show();

	const steps = ctx.stages
		.map((stage, i) => {
			const icon = stage.state === "done" ? "✓" : "";
			const classes = ["aw-step", stage.state, stage.attention ? "attention" : ""].join(" ");
			const arrow = i < ctx.stages.length - 1 ? '<span class="aw-arrow">→</span>' : "";
			return `<button type="button" class="${classes}" data-stage="${esc(stage.key)}"
					title="${esc(stage.detail)}" aria-label="${esc(stage.label)}: ${esc(__(stage.state))}">
					<span class="aw-dot">${icon}</span><span>${esc(stage.label)}</span>
				</button>${arrow}`;
		})
		.join("");

	const next = ctx.next_step || {};
	const blockers = (next.blockers || []).length
		? `<ul class="aw-blockers">${next.blockers.map((b) => `<li>${esc(b)}</li>`).join("")}</ul>`
		: "";
	const next_html = next.key
		? `<button type="button" class="btn btn-xs btn-primary aw-next" data-action="${esc(next.key)}">${esc(next.label)}</button>`
		: `<div class="aw-value">${esc(next.label || "")}</div>`;
	const current = ctx.stages.find((s) => s.state === "current");
	const figures = (ctx.figures || [])
		.map(
			(f) => `<div class="aw-figure"><div class="aw-label">${esc(f.label)}</div>
				<div class="aw-value">${automotive.workshop.format_figure(f, frm.doc)}</div></div>`
		)
		.join("");

	$header.html(`
		<div class="aw-tracker" role="list">${steps}</div>
		<div class="aw-panel">
			<div>
				<div class="aw-label">${__("Current Stage")}</div>
				<div class="aw-value">${esc(ctx.current_stage)}</div>
				<div class="aw-sub">${esc(__(frm.doc.status))}${current ? " · " + esc(current.detail) : ""}</div>
			</div>
			<div class="aw-figures">${figures || `<div class="aw-sub">${__("No figures yet")}</div>`}</div>
			<div>
				<div class="aw-label">${__("Next Action")}</div>
				${next_html}
				${next.owner ? `<div class="aw-sub">${__("Responsible")}: ${esc(__(next.owner))}</div>` : ""}
				${blockers}
			</div>
		</div>`);

	$header.find(".aw-step").on("click", (e) => {
		const key = $(e.currentTarget).attr("data-stage");
		automotive.workshop.on_stage_click(frm, ctx, ctx.stages.find((s) => s.key === key));
	});
	$header.find(".aw-next").on("click", (e) => {
		automotive.workshop.run(frm, $(e.currentTarget).attr("data-action"));
	});
};

automotive.workshop.on_stage_click = function (frm, ctx, stage) {
	if (stage.state === "done" && stage.doc && stage.doc.doctype !== frm.doctype) {
		frappe.set_route("Form", stage.doc.doctype, stage.doc.name);
		return;
	}
	if (stage.state === "current" || stage.state === "done") {
		automotive.workshop.focus_tab(frm, stage.tab);
		return;
	}
	frappe.msgprint({
		title: __("{0}: pending", [stage.label]),
		message: `<p>${esc(stage.detail)}</p>
			${stage.owner ? `<p class="text-muted">${__("Responsible")}: ${esc(__(stage.owner))}</p>` : ""}
			<p class="text-muted">${__("This stage starts once {0} is complete.", [esc(ctx.current_stage)])}</p>`,
		indicator: "gray",
	});
};

automotive.workshop.focus_tab = function (frm, fieldname) {
	const tab = (frm.layout.tabs || []).find((t) => t.df.fieldname === fieldname);
	if (tab) {
		tab.set_active();
		frm.layout.wrapper[0].scrollIntoView({ behavior: "smooth", block: "start" });
	}
};
