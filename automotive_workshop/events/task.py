import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L

EDITABLE_JOB_STATUSES = (C.PARTS_PENDING, C.WORK_IN_PROGRESS)
ACTIVE_TASK_STATUSES = ("Working", "Pending Review", "Completed")


def validate(doc, method=None):
	if not doc.aw_job_card:
		return
	job = L.get_job(doc.aw_job_card)
	L.assert_not_released(job)
	before = doc.get_doc_before_save()
	status_changed = not before or before.status != doc.status or flt(before.progress) != flt(doc.progress)
	if doc.is_new() or status_changed or (before and before.aw_technician != doc.aw_technician):
		if job.status not in EDITABLE_JOB_STATUSES:
			frappe.throw(
				_("Repair tasks for Job Card {0} cannot be changed while it is {1}.").format(job.name, _(job.status)),
				L.WorkflowError, title=_("Repair Locked"),
			)
	doc.aw_vehicle, doc.aw_customer = job.vehicle, job.customer
	if not doc.aw_trade:
		frappe.throw(_("Select the trade (Denter, Mechanic or Electrician) for this repair task."))
	if not doc.aw_technician:
		frappe.throw(_("Assign a technician to this repair task."))
	if doc.aw_trade not in frappe.get_roles(doc.aw_technician):
		frappe.throw(_("{0} does not have the {1} role and cannot be assigned {1} work.").format(
			frappe.utils.get_fullname(doc.aw_technician), _(doc.aw_trade)), title=_("Wrong Technician"))

	if doc.status in ACTIVE_TASK_STATUSES and job.status != C.WORK_IN_PROGRESS and not doc.flags.from_rework:
		frappe.throw(
			_("Repair cannot start because Job Card {0} is {1}. The Workshop Manager must start the repair first (customer approval and parts are required).").format(
				job.name, _(job.status)),
			L.WorkflowError, title=_("Repair Not Started"),
		)
	if doc.status == "Working" and not doc.act_start_date:
		doc.act_start_date = nowdate()
	if doc.status == "Completed":
		if flt(doc.aw_labour_hours) <= 0:
			frappe.throw(_("Record the labour hours worked before completing task {0}.").format(doc.subject),
				title=_("Labour Hours Required"))
		doc.progress = 100
		doc.completed_on = doc.completed_on or nowdate()
		doc.completed_by = doc.completed_by or frappe.session.user
		doc.act_end_date = doc.act_end_date or nowdate()


def on_update(doc, method=None):
	if not doc.aw_job_card or not doc.has_value_changed("aw_technician"):
		return
	from frappe.desk.form.assign_to import _add as assign

	if not frappe.db.exists("ToDo", {"reference_type": "Task", "reference_name": doc.name,
			"allocated_to": doc.aw_technician, "status": "Open"}):
		assign({"doctype": "Task", "name": doc.name, "assign_to": [doc.aw_technician],
			"description": doc.subject, "date": doc.exp_end_date}, ignore_permissions=True)
