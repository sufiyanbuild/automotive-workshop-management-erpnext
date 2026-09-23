"""The Workshop Job Card lifecycle.

One state machine owns the Job Card status. Every status change goes through
`transition()`, which checks the move is allowed and flags the save so that
WorkshopJobCard.validate accepts it; any other change to `status` is refused.

The guards (`assert_*`) state the business rules. They are called both from
user actions (actions.py) and from standard-document hooks (events/), so the
rules hold whichever screen the user works from.

`get_facts()` reads the Job Card's related documents once; `compute_stages()`
turns the status plus those facts into the ten visual stages.
"""

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form, now_datetime

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop.parts import describe as describe_parts
from automotive_workshop.workshop.parts import get_parts_summary

ALLOWED = {
	C.OPEN: {C.INSPECTION_COMPLETED},
	C.INSPECTION_COMPLETED: {C.OPEN, C.AWAITING_APPROVAL},
	C.AWAITING_APPROVAL: {C.INSPECTION_COMPLETED, C.PARTS_PENDING},
	C.PARTS_PENDING: {C.WORK_IN_PROGRESS},
	C.WORK_IN_PROGRESS: {C.QUALITY_CHECK},
	C.QUALITY_CHECK: {C.COMPLETED, C.WORK_IN_PROGRESS},
	C.COMPLETED: {C.INVOICED, C.QUALITY_CHECK},
	C.INVOICED: {C.COMPLETED},
}


class WorkflowError(frappe.ValidationError):
	pass


def rank(status):
	return C.STATUSES.index(status)


def at_least(job, status):
	return rank(job.status) >= rank(status)


def get_job(job_card, for_update=False):
	if isinstance(job_card, str):
		return frappe.get_doc("Workshop Job Card", job_card, for_update=for_update)
	return job_card


def job_link(job):
	return get_link_to_form("Workshop Job Card", job.name)


# ------------------------------------------------------------------ transition
def transition(job, to_status, reason=None, **values):
	"""Move a Job Card to `to_status`, writing `values` in the same save."""
	job = get_job(job)
	from_status = job.status
	if to_status not in ALLOWED.get(from_status, ()):
		frappe.throw(
			_("Job Card {0} cannot move from {1} to {2}.").format(job_link(job), _(from_status), _(to_status)),
			WorkflowError,
			title=_("Invalid Workflow Step"),
		)
	job.update(values)
	job.status = to_status
	job.flags.lifecycle_transition = True
	job.flags.ignore_permissions = True
	job.save()
	message = _("Status changed from {0} to {1}.").format(_(from_status), _(to_status))
	if reason:
		message += " " + reason
	job.add_comment("Info", message)
	return job


def update_fields(job, **values):
	"""Write non-status Job Card fields maintained by the system."""
	job = get_job(job)
	job.update(values)
	job.flags.lifecycle_transition = True
	job.flags.ignore_permissions = True
	job.save()
	return job


def assert_status(job, *statuses, action):
	if job.status not in statuses:
		frappe.throw(
			_("{0} is not possible while Job Card {1} is {2}. It is allowed only when the Job Card is {3}.").format(
				_(action), job_link(job), frappe.bold(_(job.status)),
				_(" or ").join(frappe.bold(_(s)) for s in statuses),
			),
			WorkflowError,
			title=_("Not Allowed at This Stage"),
		)


def assert_not_released(job):
	if job.released:
		frappe.throw(
			_("Job Card {0} is closed: the vehicle was released on {1}.").format(job_link(job), job.released_on),
			WorkflowError,
		)


# ------------------------------------------------------------------ facts
def get_facts(job):
	job = get_job(job)
	facts = frappe._dict()
	facts.inspections = frappe.get_all(
		"Vehicle Inspection",
		filters={"job_card": job.name, "docstatus": ["<", 2]},
		fields=["name", "inspection_type", "technician", "docstatus", "qc_result", "overall_condition",
				"inspection_datetime", "estimated_labour_hours"],
		order_by="creation asc",
	)
	facts.trade_inspections = [i for i in facts.inspections if i.inspection_type != C.QC_TYPE]
	facts.qc_inspections = [i for i in facts.inspections if i.inspection_type == C.QC_TYPE]
	facts.assessments = frappe.get_all(
		"Damage Assessment",
		filters={"job_card": job.name, "docstatus": ["<", 2]},
		fields=["name", "docstatus", "estimated_total"],
		order_by="creation asc",
	)
	facts.quotations = frappe.get_all(
		"Quotation",
		filters={"aw_job_card": job.name, "docstatus": ["<", 2]},
		fields=["name", "docstatus", "status", "grand_total", "aw_customer_approval", "aw_sent_on"],
		order_by="creation asc",
	)
	facts.parts = get_parts_summary(job.name)
	facts.tasks = frappe.get_all(
		"Task",
		filters={"aw_job_card": job.name, "status": ["!=", "Cancelled"]},
		fields=["name", "subject", "status", "progress", "aw_trade", "aw_technician", "expected_time",
				"aw_labour_hours", "completed_on"],
		order_by="creation asc",
	)
	facts.tasks_done = bool(facts.tasks) and all(t.status == "Completed" for t in facts.tasks)
	facts.invoice = None
	if job.sales_invoice:
		facts.invoice = frappe.db.get_value(
			"Sales Invoice", job.sales_invoice,
			["name", "docstatus", "grand_total", "outstanding_amount", "status", "currency"], as_dict=True,
		)
	facts.material_requests = frappe.get_all(
		"Material Request", filters={"aw_job_card": job.name, "docstatus": ["<", 2]},
		fields=["name", "docstatus", "status"], order_by="creation asc",
	)
	facts.parts_issues = frappe.get_all(
		"Stock Entry", filters={"aw_job_card": job.name, "docstatus": ["<", 2]},
		fields=["name", "docstatus"], order_by="creation asc",
	)
	facts.payments = frappe.get_all(
		"Payment Entry", filters={"aw_job_card": job.name, "docstatus": 1},
		fields=["name", "paid_amount", "posting_date"], order_by="posting_date asc",
	)
	return facts


def outstanding_of(job, facts):
	if facts.invoice and facts.invoice.docstatus == 1:
		return flt(facts.invoice.outstanding_amount)
	return 0.0


# ------------------------------------------------------------------ stages
def _stage(meta, done, detail="", doc=None, attention=False, owner=None):
	return frappe._dict(
		key=meta.key, label=_(meta.label), done=bool(done), detail=detail, doc=doc,
		attention=attention, owner=owner, tab=C.STAGE_TABS[meta.key],
	)


def compute_stages(job, facts):
	"""Return the ten visual stages, each marked done / current / pending."""
	s = {m.key: m for m in C.STAGES}
	status = job.status
	submitted_trade = [i for i in facts.trade_inspections if i.docstatus == 1]
	draft_trade = [i for i in facts.trade_inspections if i.docstatus == 0]
	approval = job.customer_approval
	rows = []

	rows.append(_stage(
		s["reception"], bool(facts.trade_inspections) or status != C.OPEN,
		_("Vehicle received {0}").format(frappe.format(job.intake_datetime, "Datetime")) if job.intake_datetime else "",
		doc={"doctype": "Workshop Job Card", "name": job.name}, owner=C.RECEPTION,
	))

	if submitted_trade:
		insp_detail = _("{0} inspection(s) submitted").format(len(submitted_trade))
	elif draft_trade:
		insp_detail = _("{0} inspection(s) in progress, not yet submitted").format(len(draft_trade))
	else:
		insp_detail = _("No inspection started yet")
	rows.append(_stage(
		s["inspection"], at_least(job, C.INSPECTION_COMPLETED), insp_detail,
		doc=_doc("Vehicle Inspection", (submitted_trade or draft_trade or [None])[-1]), owner=_("Technicians"),
	))

	rows.append(_stage(
		s["assessment"], bool(job.damage_assessment) and at_least(job, C.INSPECTION_COMPLETED),
		_("Estimate {0}").format(_money(job.assessment_total, job)) if job.damage_assessment
		else (_("Waiting for inspections to be completed") if status == C.OPEN else _("Damage Assessment not submitted")),
		doc=_doc("Damage Assessment", job.damage_assessment), owner=C.MANAGER,
	))

	quotation_done = at_least(job, C.AWAITING_APPROVAL) and bool(job.quotation_sent_on)
	if job.quotation:
		q_detail = _("{0} · {1}").format(_money(job.quotation_total, job),
			_("sent {0}").format(frappe.format(job.quotation_sent_on, "Datetime")) if job.quotation_sent_on else _("not yet sent to the customer"))
	else:
		q_detail = _("No submitted quotation yet")
	rows.append(_stage(
		s["quotation"], quotation_done, q_detail, doc=_doc("Quotation", job.quotation), owner=C.MANAGER,
	))

	rejected = approval in (C.APPROVAL_REJECTED, C.APPROVAL_REVISION)
	rows.append(_stage(
		s["approval"], at_least(job, C.PARTS_PENDING),
		_("Customer decision: {0}").format(_(approval)) if approval and approval != C.APPROVAL_PENDING
		else _("Waiting for the customer's decision"),
		doc=_doc("Quotation", job.quotation), attention=rejected and status == C.AWAITING_APPROVAL,
		owner=C.RECEPTION,
	))

	parts_done = at_least(job, C.WORK_IN_PROGRESS) or (status == C.PARTS_PENDING and facts.parts.complete)
	rows.append(_stage(
		s["parts"], parts_done, describe_parts(facts.parts),
		doc=_doc("Material Request", (facts.material_requests or [None])[-1]),
		attention=status == C.PARTS_PENDING and bool(facts.parts.shortages), owner=C.STORE_KEEPER,
	))

	done_tasks = len([t for t in facts.tasks if t.status == "Completed"])
	repair_detail = (
		_("{0} of {1} repair tasks completed").format(done_tasks, len(facts.tasks)) if facts.tasks
		else _("No repair tasks assigned")
	)
	if job.qc_result == C.QC_FAILED and status == C.WORK_IN_PROGRESS:
		repair_detail = _("Rework after failed QC ({0}). ").format(job.rework_count) + repair_detail
	rows.append(_stage(
		s["repair"], at_least(job, C.QUALITY_CHECK), repair_detail,
		doc=_doc("Task", (facts.tasks or [None])[-1]),
		attention=job.qc_result == C.QC_FAILED and status == C.WORK_IN_PROGRESS, owner=_("Technicians"),
	))

	rows.append(_stage(
		s["qc"], at_least(job, C.COMPLETED),
		_("QC {0}").format(_(job.qc_result)) if job.qc_result else _("Final inspection not yet done"),
		doc=_doc("Vehicle Inspection", job.qc_inspection), owner=C.QUALITY_INSPECTOR,
	))

	outstanding = outstanding_of(job, facts)
	if facts.invoice:
		inv_detail = _("{0} · outstanding {1}").format(_money(facts.invoice.grand_total, job), _money(outstanding, job))
	else:
		inv_detail = _("Not invoiced")
	rows.append(_stage(
		s["invoice"], status == C.INVOICED, inv_detail, doc=_doc("Sales Invoice", job.sales_invoice),
		attention=status == C.INVOICED and outstanding > 0 and not job.released, owner=C.ACCOUNTS,
	))

	rows.append(_stage(
		s["delivery"], job.released,
		_("Released {0} by {1}").format(frappe.format(job.released_on, "Datetime"), job.released_by)
		if job.released else _("Vehicle is in the workshop"),
		doc={"doctype": "Workshop Job Card", "name": job.name} if job.released else None, owner=C.RECEPTION,
	))

	current_found = False
	for row in rows:
		if row.done:
			row.state = "done"
		elif not current_found:
			row.state = "current"
			current_found = True
		else:
			row.state = "pending"
	return rows


def current_stage_label(stages):
	for row in stages:
		if row.state == "current":
			return row.label
	return _("Delivered")


def _doc(doctype, name):
	if isinstance(name, dict):
		name = name.get("name")
	return {"doctype": doctype, "name": name} if name else None


def _money(value, job):
	return frappe.format(flt(value), {"fieldtype": "Currency", "options": "currency"}, doc=job)


# ------------------------------------------------------------------ guards
def assert_can_complete_inspection(job, facts):
	submitted = [i for i in facts.trade_inspections if i.docstatus == 1]
	if not submitted:
		frappe.throw(_("Inspection cannot be completed: no inspection has been submitted for {0}.").format(job_link(job)))
	drafts = [i.name for i in facts.trade_inspections if i.docstatus == 0]
	if drafts:
		frappe.throw(_("Inspection cannot be completed while inspections {0} are still in draft.").format(", ".join(drafts)))


def start_repair_blockers(job, facts):
	if job.status != C.PARTS_PENDING:
		return [_("The Job Card must be at Parts Pending (it is {0}).").format(_(job.status))]
	reasons = []
	if job.customer_approval != C.APPROVAL_APPROVED:
		reasons.append(_("Repair cannot start because the customer quotation has not been approved."))
	if not facts.parts.complete:
		missing = ", ".join(f"{r.item_code} ({flt(r.to_issue):g} {r.uom or ''})".strip() for r in facts.parts.lines if r.to_issue > 0)
		reasons.append(_("Repair cannot start: required parts have not all been issued to this Job Card. Outstanding: {0}.").format(missing))
	if not facts.tasks:
		reasons.append(_("Repair cannot start: assign at least one repair task to a technician first."))
	unassigned = [t.name for t in facts.tasks if not t.aw_technician]
	if unassigned:
		reasons.append(_("Repair cannot start: tasks {0} have no technician assigned.").format(", ".join(unassigned)))
	return reasons


def request_qc_blockers(job, facts):
	if job.status != C.WORK_IN_PROGRESS:
		return [_("The Job Card must be Work In Progress (it is {0}).").format(_(job.status))]
	if not facts.tasks:
		return [_("Quality Check cannot be requested: this Job Card has no repair tasks.")]
	open_tasks = [f"{t.subject} ({_(t.status)})" for t in facts.tasks if t.status != "Completed"]
	if open_tasks:
		return [_("Quality Check cannot be requested until all repair tasks are completed. Still open: {0}.").format(", ".join(open_tasks))]
	return []


def throw_blockers(reasons, title):
	if reasons:
		frappe.throw("<br>".join(reasons), WorkflowError, title=title)


def assert_can_start_repair(job, facts):
	throw_blockers(start_repair_blockers(job, facts), _("Repair Cannot Start"))


def assert_can_request_qc(job, facts):
	throw_blockers(request_qc_blockers(job, facts), _("Repair Not Finished"))


def release_blockers(job, facts, settings, allow_credit=False):
	"""Return the reasons the vehicle cannot be released yet (empty when it can)."""
	reasons = []
	if job.released:
		return [_("The vehicle has already been released.")]
	if job.qc_result != C.QC_PASSED:
		reasons.append(_("Quality Check has not been passed."))
	if job.status != C.INVOICED or not facts.invoice or facts.invoice.docstatus != 1:
		reasons.append(_("No submitted Sales Invoice for this Job Card."))
	elif outstanding_of(job, facts) > 0 and (settings.require_full_payment or not allow_credit):
		reasons.append(_("Invoice {0} still has {1} outstanding.").format(
			job.sales_invoice, _money(outstanding_of(job, facts), job)))
	return reasons


def now():
	return now_datetime()
