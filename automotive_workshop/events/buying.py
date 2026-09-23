"""Carry the Job Card through Material Request -> RFQ / Supplier Quotation -> Purchase Order -> Purchase Receipt."""

import frappe
from frappe import _

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L


def validate_material_request(doc, method=None):
	if not doc.aw_job_card:
		return
	job = L.get_job(doc.aw_job_card)
	if doc.is_new():
		L.assert_not_released(job)
		L.assert_status(job, C.PARTS_PENDING, C.WORK_IN_PROGRESS,
			action=_("Requesting parts (the customer must approve the quotation first)"))
	doc.aw_vehicle = job.vehicle


def trace_items(doc, method=None):
	"""Set aw_job_card on each buying item from the Material Request or Purchase Order it came from."""
	mr_cache, po_cache = {}, {}
	for item in doc.items:
		if item.get("aw_job_card"):
			continue
		job = None
		if item.get("purchase_order_item"):
			if item.purchase_order_item not in po_cache:
				po_cache[item.purchase_order_item] = frappe.db.get_value(
					"Purchase Order Item", item.purchase_order_item, "aw_job_card")
			job = po_cache[item.purchase_order_item]
		if not job and item.get("material_request"):
			if item.material_request not in mr_cache:
				mr_cache[item.material_request] = frappe.db.get_value("Material Request", item.material_request, "aw_job_card")
			job = mr_cache[item.material_request]
		item.aw_job_card = job
