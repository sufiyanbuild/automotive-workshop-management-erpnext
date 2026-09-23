# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle
from automotive_workshop.workshop.permissions import is_supervisor


class VehicleInspection(Document):
	@property
	def is_qc(self):
		return self.inspection_type == C.QC_TYPE

	def validate(self):
		job = lifecycle.get_job(self.job_card)
		lifecycle.assert_not_released(job)
		self.vehicle, self.customer = job.vehicle, job.customer
		if self.is_qc:
			lifecycle.assert_status(job, C.QUALITY_CHECK, action=_("A Quality Check inspection"))
			self.validate_inspector_role(C.QUALITY_INSPECTOR)
			self.overall_condition = None
			self.estimated_labour_hours = 0
		else:
			lifecycle.assert_status(job, C.OPEN, C.INSPECTION_COMPLETED, action=_("A {0} inspection").format(_(self.inspection_type)))
			self.validate_inspector_role(self.inspection_type)
			self.qc_result = None

	def validate_inspector_role(self, role):
		if role not in frappe.get_roles(self.technician):
			frappe.throw(
				_("{0} cannot carry out this inspection because they do not have the {1} role.").format(
					frappe.bold(frappe.utils.get_fullname(self.technician)), frappe.bold(_(role))),
				title=_("Wrong Inspector"),
			)

	def before_submit(self):
		if self.technician != frappe.session.user and not is_supervisor():
			frappe.throw(_("Only {0} or a Workshop Manager can submit this inspection.").format(
				frappe.utils.get_fullname(self.technician)))
		unchecked = [str(row.idx) for row in self.checklist if not row.condition]
		if unchecked:
			frappe.throw(_("Set a condition on every checklist row before submitting. Missing on rows: {0}.").format(", ".join(unchecked)),
				title=_("Checklist Incomplete"))
		if self.is_qc:
			faulty = [row.check_point for row in self.checklist if row.condition == "Faulty"]
			if self.qc_result == C.QC_PASSED and faulty:
				frappe.throw(_("Quality Check cannot pass while checklist items are Faulty: {0}.").format(", ".join(faulty)),
					title=_("QC Cannot Pass"))
			if self.qc_result == C.QC_FAILED and not (self.remarks or "").strip():
				frappe.throw(_("Record in Remarks why the Quality Check failed, so the technicians know what to rework."))

	def on_submit(self):
		job = lifecycle.get_job(self.job_card)
		if self.is_qc:
			self.apply_qc_result(job)
		else:
			sync_inspection_status(job)

	def apply_qc_result(self, job):
		values = {"qc_inspection": self.name, "qc_result": self.qc_result, "qc_on": lifecycle.now()}
		if self.qc_result == C.QC_PASSED:
			lifecycle.transition(job, C.COMPLETED, _("Quality Check {0} passed.").format(self.name), **values)
		else:
			values["rework_count"] = cint(job.rework_count) + 1
			values["repair_completed_on"] = None
			lifecycle.transition(
				job, C.WORK_IN_PROGRESS,
				_("Quality Check {0} failed: {1}").format(self.name, self.remarks), **values,
			)
			reopen_tasks_for_rework(job, self)

	def before_cancel(self):
		job = lifecycle.get_job(self.job_card)
		lifecycle.assert_not_released(job)
		if self.is_qc:
			if job.qc_inspection == self.name and job.status not in (C.COMPLETED, C.WORK_IN_PROGRESS):
				frappe.throw(_("This Quality Check cannot be cancelled because Job Card {0} is already {1}.").format(job.name, _(job.status)))
			if job.qc_inspection == self.name and self.qc_result == C.QC_FAILED and job.status == C.WORK_IN_PROGRESS:
				frappe.throw(_("A failed Quality Check that sent the job back to repair cannot be cancelled. Record a new Quality Check instead."))
		elif lifecycle.at_least(job, C.AWAITING_APPROVAL):
			frappe.throw(
				_("This inspection cannot be cancelled: Job Card {0} has already moved on to {1}.").format(job.name, _(job.status)),
				title=_("Inspection Locked"),
			)

	def on_cancel(self):
		job = lifecycle.get_job(self.job_card)
		if self.is_qc:
			if job.qc_inspection == self.name and job.status == C.COMPLETED:
				lifecycle.transition(job, C.QUALITY_CHECK, _("Quality Check {0} was cancelled.").format(self.name),
					qc_inspection=None, qc_result=None, qc_on=None)
		else:
			sync_inspection_status(job)

	def after_delete(self):
		if not self.is_qc and frappe.db.exists("Workshop Job Card", self.job_card):
			sync_inspection_status(lifecycle.get_job(self.job_card))


def sync_inspection_status(job):
	"""Open <-> Inspection Completed follows the submitted and draft trade inspections."""
	facts = lifecycle.get_facts(job)
	submitted = [i for i in facts.trade_inspections if i.docstatus == 1]
	drafts = [i for i in facts.trade_inspections if i.docstatus == 0]
	if job.status == C.OPEN and submitted and not drafts:
		lifecycle.transition(job, C.INSPECTION_COMPLETED, _("All inspections submitted."),
			inspection_completed_on=lifecycle.now())
	elif job.status == C.INSPECTION_COMPLETED and not submitted:
		if job.damage_assessment:
			frappe.throw(_("Cancel Damage Assessment {0} before cancelling the last inspection.").format(job.damage_assessment))
		lifecycle.transition(job, C.OPEN, _("No submitted inspection remains."), inspection_completed_on=None)


def reopen_tasks_for_rework(job, qc):
	"""Send the job's completed repair tasks back to Working after a failed QC."""
	for name in frappe.get_all("Task", filters={"aw_job_card": job.name, "status": "Completed"}, pluck="name"):
		task = frappe.get_doc("Task", name)
		task.status = "Working"
		task.progress = 50
		task.completed_on = None
		task.aw_work_notes = ((task.aw_work_notes or "") + "\n" + _("Rework requested by {0}: {1}").format(qc.name, qc.remarks)).strip()
		task.flags.ignore_permissions = True
		task.flags.from_rework = True
		task.save()
