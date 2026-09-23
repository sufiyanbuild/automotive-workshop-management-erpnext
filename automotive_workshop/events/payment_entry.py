import frappe
from frappe import _

from automotive_workshop.events.sales_invoice import refresh_payment


def _jobs(doc):
	invoices = [r.reference_name for r in doc.references if r.reference_doctype == "Sales Invoice"]
	if not invoices:
		return []
	return list(set(frappe.get_all("Sales Invoice", filters={"name": ["in", invoices], "aw_job_card": ["is", "set"]},
		pluck="aw_job_card")))


def validate(doc, method=None):
	jobs = _jobs(doc)
	if len(jobs) == 1:
		doc.aw_job_card = jobs[0]
	elif doc.aw_job_card and doc.aw_job_card not in jobs:
		doc.aw_job_card = None


def on_change(doc, method=None):
	# Runs after submit and cancel, once ERPNext has updated invoice outstanding.
	for job in _jobs(doc):
		refresh_payment(job)
