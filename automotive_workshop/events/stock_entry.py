import frappe
from frappe import _
from frappe.utils import flt

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L
from automotive_workshop.workshop.parts import get_parts_summary


def validate(doc, method=None):
	if not doc.aw_job_card:
		return
	job = L.get_job(doc.aw_job_card)
	if doc.purpose != "Material Issue":
		frappe.throw(_("Only a Material Issue can be linked to Job Card {0}.").format(job.name))
	if doc.docstatus == 0:
		L.assert_not_released(job)
		L.assert_status(job, C.PARTS_PENDING, C.WORK_IN_PROGRESS,
			action=_("Issuing parts (the customer must approve the quotation first)"))


def before_submit(doc, method=None):
	if not doc.aw_job_card:
		return
	job = L.get_job(doc.aw_job_card)
	summary = {r.item_code: r for r in get_parts_summary(job.name).lines}
	qty = {}
	for row in doc.items:
		qty[row.item_code] = qty.get(row.item_code, 0) + flt(row.transfer_qty or row.qty)
	for item_code, issued in qty.items():
		required = summary.get(item_code)
		if required is None:
			if job.status != C.WORK_IN_PROGRESS:
				frappe.throw(_("{0} is not a required part on the approved assessment for Job Card {1}.").format(item_code, job.name))
			continue
		if issued > flt(required.to_issue) + 1e-9 and job.status == C.PARTS_PENDING:
			frappe.throw(_("Issuing {0} of {1} exceeds the {2} still required for Job Card {3}.").format(
				issued, item_code, required.to_issue, job.name), title=_("Over-issue"))
