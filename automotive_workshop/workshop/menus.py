"""Context-aware Create and Actions menus for the Workshop Job Card.

The menus are computed here, on the server, from the Job Card status, the
related documents and the user's roles. The form only draws what this returns,
and every entry is re-checked by the endpoint it calls (mappers.py/actions.py).
"""

import frappe
from frappe import _

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L
from automotive_workshop.workshop.parts import SHORTAGE

# Who may run each action. System Manager may run everything.
ACTION_ROLES = {
	"start_inspection": (C.MANAGER, C.RECEPTION, *C.TECHNICIAN_ROLES),
	"prepare_quotation": (C.MANAGER, C.ACCOUNTS),
	"create_damage_assessment": (C.MANAGER, *C.TECHNICIAN_ROLES),
	"send_quotation": (C.MANAGER, C.RECEPTION, C.ACCOUNTS),
	"record_approval": (C.MANAGER, C.RECEPTION),
	"revise_quotation": (C.MANAGER, C.ACCOUNTS),
	"check_parts": None,
	"issue_parts": (C.MANAGER, C.STORE_KEEPER),
	"request_parts": (C.MANAGER, C.STORE_KEEPER, C.PURCHASE),
	"assign_task": (C.MANAGER,),
	"start_repair": (C.MANAGER,),
	"update_repair_progress": (C.MANAGER, *C.TECHNICIAN_ROLES),
	"request_qc": (C.MANAGER, *C.TECHNICIAN_ROLES),
	"pass_qc": (C.QUALITY_INSPECTOR,),
	"reject_qc": (C.QUALITY_INSPECTOR,),
	"return_to_repair": (C.MANAGER, C.QUALITY_INSPECTOR),
	"generate_invoice": (C.MANAGER, C.ACCOUNTS),
	"record_payment": (C.ACCOUNTS,),
	"release_vehicle": (C.MANAGER, C.RECEPTION, C.QUALITY_INSPECTOR),
}

# Actions that end up creating a document. They are offered only to users who
# may create that document, so the Actions menu cannot lead into a permission error.
ACTION_DOCTYPES = {
	"start_inspection": "Vehicle Inspection",
	"pass_qc": "Vehicle Inspection",
	"reject_qc": "Vehicle Inspection",
	"create_damage_assessment": "Damage Assessment",
	"prepare_quotation": "Quotation",
	"revise_quotation": "Quotation",
	"request_parts": "Material Request",
	"issue_parts": "Stock Entry",
	"assign_task": "Task",
	"generate_invoice": "Sales Invoice",
	"record_payment": "Payment Entry",
}

# Create options that need a role beyond the target DocType's create permission.
# A mechanic may create inspections, but only a Quality Inspector records the final QC.
CREATE_ROLES = {
	"quality_check": (C.QUALITY_INSPECTOR,),
}

CREATE_DOCTYPES = {
	"inspection": "Vehicle Inspection",
	"damage_assessment": "Damage Assessment",
	"quotation": "Quotation",
	"material_request": "Material Request",
	"parts_issue": "Stock Entry",
	"repair_task": "Task",
	"quality_check": "Vehicle Inspection",
	"sales_invoice": "Sales Invoice",
	"payment_entry": "Payment Entry",
}


def can_run(action, user=None):
	roles = ACTION_ROLES.get(action)
	if roles is None:
		return True
	user_roles = set(frappe.get_roles(user))
	return bool(user_roles & {C.SYSTEM_MANAGER, *roles}) or (user or frappe.session.user) == "Administrator"


def assert_can_run(action):
	if not can_run(action):
		roles = ", ".join(_(r) for r in ACTION_ROLES[action])
		frappe.throw(
			_("You are not allowed to perform this action. It requires one of these roles: {0}.").format(roles),
			frappe.PermissionError, title=_("Not Permitted"),
		)


def can_create(key, user=None):
	roles = CREATE_ROLES.get(key)
	if roles and not (set(frappe.get_roles(user)) & {C.SYSTEM_MANAGER, *roles}):
		return False
	return frappe.has_permission(CREATE_DOCTYPES[key], "create")


def assert_can_create(key):
	if not can_create(key):
		allowed = ", ".join(_(r) for r in CREATE_ROLES.get(key, ())) or _(CREATE_DOCTYPES[key])
		frappe.throw(
			_("You are not allowed to create this document. It requires: {0}.").format(allowed),
			frappe.PermissionError, title=_("Not Permitted"),
		)


def _entry(key, label, **kw):
	return frappe._dict(key=key, label=label, **kw)


def build(job, facts, settings):
	create, actions = [], []
	status = job.status
	draft_da = next((a for a in facts.assessments if a.docstatus == 0), None)
	active_quotation = next((q for q in reversed(facts.quotations)), None)
	draft_quotation = next((q for q in facts.quotations if q.docstatus == 0), None)
	outstanding = L.outstanding_of(job, facts)

	if job.released:
		actions += [_entry("view_invoice", _("View Invoice"), doc=_d("Sales Invoice", job.sales_invoice)),
					_entry("view_history", _("View Service History"))]
		return _finalise(create, actions)

	if status in (C.OPEN, C.INSPECTION_COMPLETED):
		create.append(_entry("inspection", _("Vehicle Inspection")))
		if not job.damage_assessment and not draft_da:
			create.append(_entry("damage_assessment", _("Damage Assessment")))

	if status == C.OPEN:
		actions.append(_entry("start_inspection", _("Start Inspection")))
		actions.append(_entry("view_customer", _("View Customer"), doc=_d("Customer", job.customer)))

	if status == C.INSPECTION_COMPLETED:
		if job.damage_assessment:
			actions.append(_entry("view_damage_assessment", _("View Damage Assessment"), doc=_d("Damage Assessment", job.damage_assessment)))
		elif draft_da:
			actions.append(_entry("view_damage_assessment", _("Continue Damage Assessment"), doc=_d("Damage Assessment", draft_da.name)))
		else:
			actions.append(_entry("create_damage_assessment", _("Create Damage Assessment")))
		if job.damage_assessment and not draft_quotation:
			create.append(_entry("quotation", _("Quotation")))
			actions.append(_entry("prepare_quotation", _("Prepare Quotation")))
		if draft_quotation:
			actions.append(_entry("view_quotation", _("Continue Quotation"), doc=_d("Quotation", draft_quotation.name)))

	if status == C.AWAITING_APPROVAL:
		approval = job.customer_approval
		if approval in (C.APPROVAL_REJECTED, C.APPROVAL_REVISION):
			create.append(_entry("quotation", _("Revised Quotation")))
			actions.append(_entry("revise_quotation", _("Revise Quotation")))
		else:
			actions.append(_entry("send_quotation", _("Resend Quotation") if job.quotation_sent_on else _("Send Quotation")))
			if job.quotation_sent_on:
				actions.append(_entry("record_approval", _("Record Customer Approval")))
		actions.append(_entry("view_quotation", _("View Quotation"), doc=_d("Quotation", job.quotation)))

	if status in (C.PARTS_PENDING, C.WORK_IN_PROGRESS):
		if facts.parts.to_request:
			create.append(_entry("material_request", _("Material Request")))
		if facts.parts.issuable:
			create.append(_entry("parts_issue", _("Parts Issue")))
		create.append(_entry("repair_task", _("Repair Task")))

	if status == C.PARTS_PENDING:
		actions.append(_entry("check_parts", _("Check Parts Availability")))
		if facts.parts.issuable:
			actions.append(_entry("issue_parts", _("Issue Parts to Job")))
		if facts.parts.to_request:
			actions.append(_entry("request_parts", _("Request Parts")))
		actions.append(_entry("assign_task", _("Assign Repair Task")))
		if not L.start_repair_blockers(job, facts):
			actions.append(_entry("start_repair", _("Start Repair"), primary=True))

	if status == C.WORK_IN_PROGRESS:
		if facts.tasks:
			actions.append(_entry("update_repair_progress", _("Update Repair Progress")))
		if facts.tasks_done:
			create.append(_entry("quality_check", _("Quality Check")))
			actions.append(_entry("request_qc", _("Request Quality Check"), primary=True))
		actions.append(_entry("view_tasks", _("View Repair Tasks"), route=["List", "Task", {"aw_job_card": job.name}]))

	if status == C.QUALITY_CHECK:
		create.append(_entry("quality_check", _("Quality Check")))
		actions += [
			_entry("pass_qc", _("Pass Quality Check")),
			_entry("reject_qc", _("Reject Quality Check")),
			_entry("return_to_repair", _("Return to Repair")),
		]

	if status == C.COMPLETED and not job.sales_invoice:
		create.append(_entry("sales_invoice", _("Sales Invoice")))
		actions.append(_entry("generate_invoice", _("Generate Sales Invoice"), primary=True))

	if status == C.INVOICED:
		if outstanding > 0:
			create.append(_entry("payment_entry", _("Payment Entry")))
			actions.append(_entry("record_payment", _("Record Payment"), primary=True))
		if can_release(job, facts, settings):
			actions.append(_entry("release_vehicle", _("Release Vehicle"), primary=outstanding <= 0))
		actions.append(_entry("view_invoice", _("View Invoice"), doc=_d("Sales Invoice", job.sales_invoice)))

	if status in (C.COMPLETED, C.INVOICED):
		actions.append(_entry("view_history", _("View Service History")))

	return _finalise(create, actions)


def can_release(job, facts, settings):
	if not L.release_blockers(job, facts, settings, allow_credit=True):
		# With credit allowed by settings, only a Workshop Manager may release unpaid.
		if L.outstanding_of(job, facts) > 0:
			return C.MANAGER in frappe.get_roles() or C.SYSTEM_MANAGER in frappe.get_roles()
		return True
	return False


def _d(doctype, name):
	return {"doctype": doctype, "name": name} if name else None


def _finalise(create, actions):
	create = [c for c in create if can_create(c.key)]
	for c in create:
		c.doctype = CREATE_DOCTYPES[c.key]
	actions = [
		a for a in actions
		if can_run(a.key) and (a.key not in ACTION_DOCTYPES or frappe.has_permission(ACTION_DOCTYPES[a.key], "create"))
	]
	return frappe._dict(create=create, actions=actions)


def next_step(job, facts, settings):
	"""The single most useful next step, who owns it, and what blocks it."""
	status = job.status
	if job.released:
		return _entry(None, _("Job complete. Vehicle delivered."), owner=None)
	if status == C.OPEN:
		drafts = [i.name for i in facts.trade_inspections if i.docstatus == 0]
		if drafts:
			return _entry(None, _("Submit inspection {0}").format(", ".join(drafts)), owner=_("Technicians"))
		return _entry("start_inspection", _("Start Inspection"), owner=C.MANAGER)
	if status == C.INSPECTION_COMPLETED:
		if not job.damage_assessment:
			draft = next((a.name for a in facts.assessments if a.docstatus == 0), None)
			if draft:
				return _entry(None, _("Submit Damage Assessment {0}").format(draft), owner=C.MANAGER)
			return _entry("create_damage_assessment", _("Create Damage Assessment"), owner=C.MANAGER)
		draft_q = next((q.name for q in facts.quotations if q.docstatus == 0), None)
		if draft_q:
			return _entry(None, _("Review and submit Quotation {0}").format(draft_q), owner=C.MANAGER)
		return _entry("prepare_quotation", _("Prepare Quotation"), owner=C.MANAGER)
	if status == C.AWAITING_APPROVAL:
		if job.customer_approval in (C.APPROVAL_REJECTED, C.APPROVAL_REVISION):
			return _entry("revise_quotation", _("Revise Quotation"), owner=C.MANAGER,
				blockers=[_("Customer decision: {0}. {1}").format(_(job.customer_approval), job.approval_remarks or "")])
		if not job.quotation_sent_on:
			return _entry("send_quotation", _("Send Quotation to Customer"), owner=C.RECEPTION)
		return _entry("record_approval", _("Record Customer Approval"), owner=C.RECEPTION)
	if status == C.PARTS_PENDING:
		blockers = L.start_repair_blockers(job, facts)
		if any(r.state == SHORTAGE for r in facts.parts.lines):
			return _entry("request_parts", _("Request Parts"), owner=C.STORE_KEEPER, blockers=blockers)
		if facts.parts.issuable:
			return _entry("issue_parts", _("Issue Parts to Job"), owner=C.STORE_KEEPER, blockers=blockers)
		if facts.parts.pending_purchase:
			on_order = any(r.ordered > r.received for r in facts.parts.lines)
			if on_order:
				return _entry(None, _("Receive the ordered parts (Purchase Receipt)"), owner=C.STORE_KEEPER, blockers=blockers)
			return _entry(None, _("Raise a Purchase Order for the requested parts"), owner=C.PURCHASE, blockers=blockers)
		if not facts.tasks:
			return _entry("assign_task", _("Assign Repair Tasks"), owner=C.MANAGER, blockers=blockers)
		return _entry("start_repair", _("Start Repair"), owner=C.MANAGER, blockers=blockers)
	if status == C.WORK_IN_PROGRESS:
		if facts.tasks_done:
			return _entry("request_qc", _("Request Quality Check"), owner=_("Technicians"))
		return _entry("update_repair_progress", _("Complete Repair Tasks"), owner=_("Technicians"),
			blockers=L.request_qc_blockers(job, facts))
	if status == C.QUALITY_CHECK:
		return _entry("pass_qc", _("Record Final Quality Check"), owner=C.QUALITY_INSPECTOR)
	if status == C.COMPLETED:
		return _entry("generate_invoice", _("Generate Sales Invoice"), owner=C.ACCOUNTS)
	# Invoiced
	blockers = L.release_blockers(job, facts, settings)
	if L.outstanding_of(job, facts) > 0:
		return _entry("record_payment", _("Record Payment"), owner=C.ACCOUNTS, blockers=blockers)
	return _entry("release_vehicle", _("Release Vehicle"), owner=C.RECEPTION, blockers=blockers)
