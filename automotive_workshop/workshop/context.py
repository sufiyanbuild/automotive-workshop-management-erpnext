"""Everything the Job Card form draws, computed in one server call."""

import frappe
from frappe import _
from frappe.utils import flt

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L
from automotive_workshop.workshop import menus
from automotive_workshop.workshop.history import get_service_history
from automotive_workshop.workshop.settings import get_settings


@frappe.whitelist()
def get_job_card_context(job_card):
	job = frappe.get_doc("Workshop Job Card", job_card)
	job.check_permission("read")
	settings = get_settings()
	facts = L.get_facts(job)
	stages = L.compute_stages(job, facts)
	outstanding = L.outstanding_of(job, facts)
	available = menus.build(job, facts, settings)

	return {
		"stages": stages,
		"current_stage": L.current_stage_label(stages),
		"next_step": menus.next_step(job, facts, settings),
		"create": available.create,
		"actions": available.actions,
		"figures": _figures(job, facts, outstanding),
		"inspections": facts.inspections,
		"assessments": facts.assessments,
		"quotations": facts.quotations,
		"parts": facts.parts,
		"material_requests": facts.material_requests,
		"parts_issues": facts.parts_issues,
		"tasks": facts.tasks,
		"invoice": facts.invoice,
		"payments": facts.payments,
		"outstanding": outstanding,
		"history": get_service_history(job.vehicle, exclude=job.name) if frappe.has_permission("Vehicle Master", "read", job.vehicle) else [],
		"release": {
			"require_full_payment": settings.require_full_payment,
			"blockers": L.release_blockers(job, facts, settings, allow_credit=not settings.require_full_payment),
		},
		"technicians": _technicians(),
		"trades": list(C.TRADES),
	}


def _figures(job, facts, outstanding):
	figures = []
	if job.quotation_total:
		figures.append({"label": _("Quotation"), "value": flt(job.quotation_total), "type": "Currency"})
	elif job.assessment_total:
		figures.append({"label": _("Estimate (excl. VAT)"), "value": flt(job.assessment_total), "type": "Currency"})
	if job.customer_approval:
		figures.append({"label": _("Customer Approval"), "value": _(job.customer_approval), "type": "Data"})
	if facts.parts.total:
		figures.append({"label": _("Parts Issued"), "value": f"{facts.parts.issued} / {facts.parts.total}", "type": "Data"})
	if facts.tasks:
		done = len([t for t in facts.tasks if t.status == "Completed"])
		figures.append({"label": _("Repair Tasks"), "value": f"{done} / {len(facts.tasks)}", "type": "Data"})
	if facts.invoice:
		figures.append({"label": _("Outstanding"), "value": outstanding, "type": "Currency"})
	if job.expected_delivery_date:
		figures.append({"label": _("Expected Delivery"), "value": job.expected_delivery_date, "type": "Date"})
	return figures


def _technicians():
	"""Enabled users per trade, for the Assign Repair Task and Start Inspection dialogs."""
	rows = frappe.db.sql(
		"""select hr.role, u.name, u.full_name from `tabHas Role` hr join `tabUser` u on u.name = hr.parent
		where hr.parenttype = 'User' and hr.role in %(roles)s and u.enabled = 1 and u.name != 'Administrator'
		order by u.full_name""",
		{"roles": (*C.TRADES, C.QUALITY_INSPECTOR)}, as_dict=True,
	)
	out = {}
	for r in rows:
		out.setdefault(r.role, []).append({"value": r.name, "label": r.full_name or r.name})
	return out
