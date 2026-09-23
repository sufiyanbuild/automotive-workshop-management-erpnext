import frappe

from automotive_workshop.workshop import constants as C


def after_insert(doc, method=None):
	"""A quotation emailed to the customer counts as sent."""
	if doc.reference_doctype != "Quotation" or doc.sent_or_received != "Sent" or doc.communication_medium != "Email":
		return
	job_card = frappe.db.get_value("Quotation", doc.reference_name, "aw_job_card")
	if not job_card:
		return
	job = frappe.get_doc("Workshop Job Card", job_card)
	if job.quotation == doc.reference_name and job.status == C.AWAITING_APPROVAL and not job.released:
		from automotive_workshop.workshop.actions import record_quotation_sent

		record_quotation_sent(job, "Email")
