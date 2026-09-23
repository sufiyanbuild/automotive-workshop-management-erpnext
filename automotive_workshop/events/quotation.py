import frappe
from frappe import _
from frappe.utils import flt

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L
from automotive_workshop.workshop.settings import get_settings

APPROVAL_FIELDS = ("aw_customer_approval", "aw_approval_remarks", "aw_approved_on", "aw_sent_on")


def validate(doc, method=None):
	if not doc.aw_job_card:
		return
	job = L.get_job(doc.aw_job_card)
	if doc.is_new() or doc.docstatus == 0:
		L.assert_not_released(job)
		L.assert_status(job, C.INSPECTION_COMPLETED, C.AWAITING_APPROVAL, action=_("Preparing a workshop quotation"))
	if doc.quotation_to != "Customer" or doc.party_name != job.customer:
		frappe.throw(_("Quotation for Job Card {0} must be addressed to its customer {1}.").format(job.name, job.customer_name),
			title=_("Wrong Customer"))
	if not job.damage_assessment:
		frappe.throw(_("Submit the Damage Assessment for Job Card {0} before quoting.").format(job.name))
	doc.aw_vehicle = job.vehicle
	doc.aw_registration = job.registration_number
	if doc.docstatus == 0:
		for field in APPROVAL_FIELDS:
			doc.set(field, None)


def before_submit(doc, method=None):
	if not doc.aw_job_card:
		return
	job = L.get_job(doc.aw_job_card)
	if job.status != C.INSPECTION_COMPLETED:
		frappe.throw(
			_("Job Card {0} already has Quotation {1} awaiting the customer. Revise that quotation instead of submitting a second one.").format(
				job.name, job.quotation) if job.quotation else
			_("Quotation cannot be submitted while Job Card {0} is {1}.").format(job.name, _(job.status)),
			L.WorkflowError, title=_("Quotation Not Allowed"),
		)
	template = get_settings().sales_taxes_template
	if template and not doc.taxes:
		frappe.throw(_("Apply the VAT template {0} before submitting the quotation.").format(template), title=_("VAT Missing"))


def on_submit(doc, method=None):
	if not doc.aw_job_card:
		return
	doc.db_set("aw_customer_approval", C.APPROVAL_PENDING)
	L.transition(
		doc.aw_job_card, C.AWAITING_APPROVAL, _("Quotation {0} submitted.").format(doc.name),
		quotation=doc.name, quotation_total=flt(doc.rounded_total) or flt(doc.grand_total), customer_approval=C.APPROVAL_PENDING,
		quotation_sent_on=None, approval_on=None, approval_remarks=None,
	)


def before_update_after_submit(doc, method=None):
	if not doc.aw_job_card or doc.flags.ignore_validate_update_after_submit:
		return
	before = doc.get_doc_before_save()
	if before and any((doc.get(f) or None) != (before.get(f) or None) for f in APPROVAL_FIELDS):
		frappe.throw(_("Customer approval is recorded from the Job Card's Actions menu, not by editing the quotation."))


def before_cancel(doc, method=None):
	if not doc.aw_job_card:
		return
	job = L.get_job(doc.aw_job_card)
	if job.quotation == doc.name and job.status != C.AWAITING_APPROVAL:
		frappe.throw(
			_("Quotation {0} was approved and Job Card {1} is now {2}. It can no longer be cancelled.").format(
				doc.name, job.name, _(job.status)),
			L.WorkflowError, title=_("Quotation Locked"),
		)


def on_cancel(doc, method=None):
	if not doc.aw_job_card:
		return
	job = L.get_job(doc.aw_job_card)
	if job.quotation == doc.name and job.status == C.AWAITING_APPROVAL:
		L.transition(
			job, C.INSPECTION_COMPLETED, _("Quotation {0} cancelled for revision.").format(doc.name),
			quotation=None, quotation_total=0, quotation_sent_on=None,
			customer_approval=None, approval_on=None, approval_remarks=None,
		)
