"""Workflow actions run from the Job Card Actions menu.

Each endpoint checks the caller's role (menus.ACTION_ROLES) and the business
rules (lifecycle guards) itself; the menu hiding an action is a convenience,
not the control.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L
from automotive_workshop.workshop.menus import assert_can_run
from automotive_workshop.workshop.settings import get_settings


def _job(job_card, action):
	assert_can_run(action)
	job = frappe.get_doc("Workshop Job Card", job_card, for_update=True)
	job.check_permission("read")
	L.assert_not_released(job)
	return job


# ------------------------------------------------------------------ quotation
@frappe.whitelist(methods=["POST"])
def mark_quotation_sent(job_card, channel="In person"):
	job = _job(job_card, "send_quotation")
	L.assert_status(job, C.AWAITING_APPROVAL, action=_("Sending the quotation"))
	record_quotation_sent(job, channel)
	return job.name


def record_quotation_sent(job, channel):
	now = L.now()
	frappe.db.set_value("Quotation", job.quotation, "aw_sent_on", now)
	L.update_fields(job, quotation_sent_on=now)
	job.add_comment("Info", _("Quotation {0} sent to the customer ({1}).").format(job.quotation, _(channel)))


@frappe.whitelist(methods=["POST"])
def record_customer_approval(job_card, decision, remarks=None):
	job = _job(job_card, "record_approval")
	L.assert_status(job, C.AWAITING_APPROVAL, action=_("Recording the customer's decision"))
	if decision not in C.APPROVAL_DECISIONS:
		frappe.throw(_("Customer decision must be one of: {0}.").format(", ".join(_(d) for d in C.APPROVAL_DECISIONS)))
	if job.customer_approval != C.APPROVAL_PENDING:
		frappe.throw(_("The customer's decision ({0}) has already been recorded for Quotation {1}.").format(
			_(job.customer_approval), job.quotation))
	if not job.quotation_sent_on:
		frappe.throw(_("Send the quotation to the customer before recording their decision."), L.WorkflowError)
	quotation = frappe.get_doc("Quotation", job.quotation)
	if quotation.docstatus != 1:
		frappe.throw(_("Quotation {0} is not submitted.").format(quotation.name))
	if quotation.valid_till and decision == C.APPROVAL_APPROVED and quotation.valid_till < frappe.utils.getdate():
		frappe.throw(_("Quotation {0} expired on {1}. Revise the quotation before approval.").format(
			quotation.name, frappe.format(quotation.valid_till, "Date")))
	if decision != C.APPROVAL_APPROVED and not (remarks or "").strip():
		frappe.throw(_("Record the customer's reason when the quotation is {0}.").format(_(decision)))

	now = L.now()
	quotation.db_set({"aw_customer_approval": decision, "aw_approval_remarks": remarks, "aw_approved_on": now})
	values = {"customer_approval": decision, "approval_on": now, "approval_remarks": remarks}
	if decision == C.APPROVAL_APPROVED:
		L.transition(job, C.PARTS_PENDING, _("Customer approved Quotation {0}.").format(quotation.name), **values)
	else:
		L.update_fields(job, **values)
		job.add_comment("Info", _("Customer decision on Quotation {0}: {1}. {2}").format(quotation.name, _(decision), remarks))
	return job.name


@frappe.whitelist(methods=["POST"])
def revise_quotation(job_card):
	"""Cancel the rejected quotation so a revised one can be prepared."""
	job = _job(job_card, "revise_quotation")
	L.assert_status(job, C.AWAITING_APPROVAL, action=_("Revising the quotation"))
	if job.customer_approval not in (C.APPROVAL_REJECTED, C.APPROVAL_REVISION):
		frappe.throw(_("A quotation can only be revised after the customer rejected it or asked for a revision."))
	quotation = frappe.get_doc("Quotation", job.quotation)
	quotation.flags.ignore_permissions = True
	quotation.cancel()  # events.quotation.on_cancel returns the job to Inspection Completed
	return quotation.name


# ------------------------------------------------------------------ repair
@frappe.whitelist(methods=["POST"])
def create_repair_task(job_card, trade, technician, subject, expected_time=0):
	assert_can_run("assign_task")
	frappe.flags.args = frappe._dict(trade=trade, technician=technician, subject=subject, expected_time=expected_time)
	from automotive_workshop.workshop.mappers import make_repair_task

	task = make_repair_task(job_card)
	task.insert()
	return task.name


@frappe.whitelist(methods=["POST"])
def start_repair(job_card):
	job = _job(job_card, "start_repair")
	L.assert_can_start_repair(job, L.get_facts(job))
	L.transition(job, C.WORK_IN_PROGRESS, _("Repair started."), repair_started_on=L.now())
	return job.name


@frappe.whitelist(methods=["POST"])
def update_repair_progress(job_card, updates):
	job = _job(job_card, "update_repair_progress")
	L.assert_status(job, C.WORK_IN_PROGRESS, action=_("Updating repair progress"))
	updates = json.loads(updates) if isinstance(updates, str) else updates
	changed = []
	for row in updates:
		task = frappe.get_doc("Task", row.get("task"))
		if task.aw_job_card != job.name:
			frappe.throw(_("Task {0} does not belong to Job Card {1}.").format(task.name, job.name))
		task.check_permission("write")
		task.status = row.get("status") or task.status
		task.progress = cint(row.get("progress")) if row.get("progress") is not None else task.progress
		if row.get("labour_hours") is not None:
			task.aw_labour_hours = flt(row.get("labour_hours"))
		if row.get("notes"):
			task.aw_work_notes = row.get("notes")
		task.save()
		changed.append(task.name)
	return changed


@frappe.whitelist(methods=["POST"])
def request_quality_check(job_card):
	job = _job(job_card, "request_qc")
	L.assert_can_request_qc(job, L.get_facts(job))
	L.transition(job, C.QUALITY_CHECK, _("Repair finished; Quality Check requested."), repair_completed_on=L.now())
	notify_quality_inspectors(job)
	return job.name


def notify_quality_inspectors(job):
	from frappe.desk.form.assign_to import _add as assign

	inspectors = frappe.get_all(
		"Has Role", filters={"role": C.QUALITY_INSPECTOR, "parenttype": "User"}, pluck="parent", distinct=True
	)
	inspectors = [u for u in inspectors if frappe.db.get_value("User", u, "enabled") and u != "Administrator"]
	if inspectors:
		assign({
			"doctype": "Workshop Job Card", "name": job.name, "assign_to": inspectors,
			"description": _("Final Quality Check for {0} ({1})").format(job.vehicle_title, job.registration_number),
			"priority": "High" if job.priority in ("High", "Urgent") else "Medium",
		}, ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def return_to_repair(job_card, reason):
	job = _job(job_card, "return_to_repair")
	L.assert_status(job, C.QUALITY_CHECK, action=_("Returning the vehicle to repair"))
	if not (reason or "").strip():
		frappe.throw(_("Give the reason for returning the vehicle to repair."))
	L.transition(job, C.WORK_IN_PROGRESS, _("Returned to repair: {0}").format(reason),
		rework_count=cint(job.rework_count) + 1, repair_completed_on=None)
	return job.name


# ------------------------------------------------------------------ delivery
@frappe.whitelist(methods=["POST"])
def release_vehicle(job_card, notes=None, release_on_credit=0):
	job = _job(job_card, "release_vehicle")
	settings = get_settings()
	facts = L.get_facts(job)
	on_credit = cint(release_on_credit)
	if on_credit:
		if settings.require_full_payment:
			frappe.throw(_("Workshop Settings require full payment before release."), L.WorkflowError)
		if not set(frappe.get_roles()) & {C.MANAGER, C.SYSTEM_MANAGER}:
			frappe.throw(_("Only a Workshop Manager can release a vehicle with an outstanding balance."), frappe.PermissionError)
		if not (notes or "").strip():
			frappe.throw(_("Record why the vehicle is released with a balance outstanding."))
	L.throw_blockers(L.release_blockers(job, facts, settings, allow_credit=on_credit), _("Vehicle Cannot Be Released"))

	outstanding = L.outstanding_of(job, facts)
	payment_status = "Paid" if outstanding <= 0 else _("Released on credit, {0} outstanding").format(
		frappe.format(outstanding, {"fieldtype": "Currency", "options": "currency"}, doc=job))
	L.update_fields(
		job, released=1, released_on=L.now(), released_by=frappe.session.user,
		release_payment_status=payment_status, delivery_notes=notes,
		outstanding_amount=outstanding, payment_status=payment_state(facts.invoice),
	)
	frappe.db.set_value("Vehicle Master", job.vehicle, "status", "Active")
	job.add_comment("Info", _("Vehicle released to the customer. {0}").format(notes or ""))
	return job.name


def payment_state(invoice):
	"""Unpaid / Partly Paid / Paid, compared against the total actually billed."""
	if not invoice or invoice.docstatus != 1:
		return None
	billed = flt(invoice.get("rounded_total")) or flt(invoice.get("grand_total"))
	if flt(invoice.outstanding_amount) <= 0:
		return "Paid"
	if flt(invoice.outstanding_amount) < billed:
		return "Partly Paid"
	return "Unpaid"
