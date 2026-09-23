import frappe
from frappe import _
from frappe.utils import flt

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L
from automotive_workshop.workshop.actions import payment_state


def validate(doc, method=None):
	if not doc.aw_job_card:
		return
	job = L.get_job(doc.aw_job_card)
	if doc.customer != job.customer:
		frappe.throw(_("Sales Invoice for Job Card {0} must be billed to {1}.").format(job.name, job.customer_name),
			title=_("Wrong Customer"))
	doc.aw_vehicle = job.vehicle
	doc.aw_quotation = job.quotation


def before_submit(doc, method=None):
	if not doc.aw_job_card or doc.is_return:
		return
	job = L.get_job(doc.aw_job_card)
	if job.qc_result != C.QC_PASSED or job.status != C.COMPLETED:
		frappe.throw(
			_("Invoice cannot be submitted because Job Card {0} has not passed Quality Check (status: {1}).").format(
				job.name, _(job.status)),
			L.WorkflowError, title=_("Quality Check Required"),
		)
	if job.sales_invoice and job.sales_invoice != doc.name:
		frappe.throw(_("Job Card {0} is already invoiced on {1}.").format(job.name, job.sales_invoice))


def billed_total(invoice):
	"""What the customer is asked to pay: the rounded total when ERPNext rounds."""
	return flt(invoice.rounded_total) or flt(invoice.grand_total)


def on_submit(doc, method=None):
	if not doc.aw_job_card or doc.is_return:
		return
	L.transition(
		doc.aw_job_card, C.INVOICED, _("Sales Invoice {0} submitted.").format(doc.name),
		sales_invoice=doc.name, invoice_total=billed_total(doc),
		outstanding_amount=doc.outstanding_amount, payment_status=payment_state(doc),
	)


def before_cancel(doc, method=None):
	if not doc.aw_job_card or doc.is_return:
		return
	job = L.get_job(doc.aw_job_card)
	if job.sales_invoice == doc.name and job.released:
		frappe.throw(_("Sales Invoice {0} cannot be cancelled: the vehicle on Job Card {1} has already been released.").format(
			doc.name, job.name), L.WorkflowError)


def on_cancel(doc, method=None):
	if not doc.aw_job_card or doc.is_return:
		refresh_payment(doc.aw_job_card or frappe.db.get_value("Sales Invoice", doc.return_against, "aw_job_card"))
		return
	job = L.get_job(doc.aw_job_card)
	if job.sales_invoice == doc.name and job.status == C.INVOICED:
		L.transition(job, C.COMPLETED, _("Sales Invoice {0} cancelled.").format(doc.name),
			sales_invoice=None, invoice_total=0, outstanding_amount=0, payment_status=None)


def on_update_after_submit(doc, method=None):
	refresh_payment(doc.aw_job_card)


def refresh_payment(job_card):
	"""Mirror the invoice's outstanding amount onto the Job Card for lists and reports."""
	if not job_card or not frappe.db.exists("Workshop Job Card", job_card):
		return
	job = L.get_job(job_card)
	if not job.sales_invoice:
		return
	invoice = frappe.db.get_value("Sales Invoice", job.sales_invoice,
		["name", "docstatus", "grand_total", "rounded_total", "outstanding_amount"], as_dict=True)
	values = {
		"outstanding_amount": flt(invoice.outstanding_amount),
		"payment_status": payment_state(invoice),
		"invoice_total": billed_total(invoice),
	}
	if any(_changed(job, field, value) for field, value in values.items()):
		L.update_fields(job, **values)


def _changed(job, field, value):
	current = job.get(field)
	if isinstance(value, float):
		return flt(current) != flt(value)
	return current != value
