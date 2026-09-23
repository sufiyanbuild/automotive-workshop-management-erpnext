"""Parts position of a Job Card, read from standard ERPNext stock and buying records.

Required  - the submitted Damage Assessment's parts table
Issued    - submitted Material Issue Stock Entries tagged with the Job Card
Available - Bin.actual_qty in the workshop warehouse
Requested - submitted Material Requests tagged with the Job Card
Ordered   - submitted Purchase Order items traced back to the Job Card
Received  - submitted Purchase Receipt items traced back to the Job Card

Nothing is stored: every figure is computed from the ledgers each time.
"""

import frappe
from frappe import _
from frappe.utils import flt

from automotive_workshop.workshop.settings import get_settings

ISSUED = "Issued"
AVAILABLE = "Available"
ON_ORDER = "On Order"
REQUESTED = "Requested"
SHORTAGE = "Shortage"


def _sum_by_item(sql, job_card):
	return {row.item_code: flt(row.qty) for row in frappe.db.sql(sql, {"job": job_card}, as_dict=True)}


def get_required_parts(job_card):
	assessment = frappe.db.get_value("Workshop Job Card", job_card, "damage_assessment")
	if not assessment:
		return {}
	rows = frappe.get_all(
		"Damage Assessment Part",
		filters={"parent": assessment, "parenttype": "Damage Assessment"},
		fields=["item_code", "item_name", "qty", "uom"],
		order_by="idx",
	)
	required = {}
	for row in rows:
		entry = required.setdefault(row.item_code, frappe._dict(item_name=row.item_name, uom=row.uom, qty=0))
		entry.qty += flt(row.qty)
	return required


def get_parts_summary(job_card):
	required = get_required_parts(job_card)
	# NOTE: 'items' would shadow dict.items on frappe._dict, so the rows are 'lines'.
	summary = frappe._dict(
		lines=[], total=len(required), issued=0, available=0, pending_purchase=0,
		complete=True, warehouse=get_settings().workshop_warehouse,
	)
	if not required:
		return summary

	issued = _sum_by_item(
		"""select sed.item_code, sum(sed.transfer_qty) qty
		from `tabStock Entry Detail` sed join `tabStock Entry` se on se.name = sed.parent
		where se.aw_job_card = %(job)s and se.docstatus = 1 and se.purpose = 'Material Issue'
		group by sed.item_code""",
		job_card,
	)
	requested = _sum_by_item(
		"""select mri.item_code, sum(mri.stock_qty) qty
		from `tabMaterial Request Item` mri join `tabMaterial Request` mr on mr.name = mri.parent
		where mr.aw_job_card = %(job)s and mr.docstatus = 1 and mr.status != 'Stopped'
		group by mri.item_code""",
		job_card,
	)
	ordered = _sum_by_item(
		"""select poi.item_code, sum(poi.stock_qty) qty
		from `tabPurchase Order Item` poi
		where poi.aw_job_card = %(job)s and poi.docstatus = 1
		group by poi.item_code""",
		job_card,
	)
	received = _sum_by_item(
		"""select pri.item_code, sum(pri.stock_qty) qty
		from `tabPurchase Receipt Item` pri
		where pri.aw_job_card = %(job)s and pri.docstatus = 1
		group by pri.item_code""",
		job_card,
	)
	in_stock = {}
	if summary.warehouse:
		in_stock = {
			b.item_code: flt(b.actual_qty)
			for b in frappe.get_all(
				"Bin",
				filters={"warehouse": summary.warehouse, "item_code": ["in", list(required)]},
				fields=["item_code", "actual_qty"],
			)
		}

	for item_code, req in required.items():
		row = frappe._dict(
			item_code=item_code,
			item_name=req.item_name,
			uom=req.uom,
			required=req.qty,
			issued=issued.get(item_code, 0),
			in_stock=in_stock.get(item_code, 0),
			requested=requested.get(item_code, 0),
			ordered=ordered.get(item_code, 0),
			received=received.get(item_code, 0),
		)
		row.to_issue = max(row.required - row.issued, 0)
		row.shortage = max(row.to_issue - row.in_stock, 0)
		# Quantity still coming from open purchasing, net of what already arrived.
		row.incoming = max(max(row.requested, row.ordered) - row.received, 0)
		row.to_request = max(row.shortage - row.incoming, 0)

		if row.to_issue <= 0:
			row.state = ISSUED
			summary.issued += 1
		elif row.shortage <= 0:
			row.state = AVAILABLE
			summary.available += 1
		elif row.ordered > row.received:
			row.state = ON_ORDER
			summary.pending_purchase += 1
		elif row.requested > row.received:
			row.state = REQUESTED
			summary.pending_purchase += 1
		else:
			row.state = SHORTAGE
		summary.lines.append(row)

	summary.complete = summary.issued == summary.total
	summary.shortages = [r for r in summary.lines if r.shortage > 0]
	summary.to_request = [r for r in summary.lines if r.to_request > 0]
	summary.issuable = [r for r in summary.lines if r.to_issue > 0 and r.in_stock > 0]
	return summary


def describe(summary):
	"""One-line explanation of the parts position, for the tracker and errors."""
	if not summary.total:
		return _("No parts required")
	parts = [_("{0} items").format(summary.total), _("{0} issued").format(summary.issued)]
	if summary.available:
		parts.append(_("{0} in stock, ready to issue").format(summary.available))
	if summary.pending_purchase:
		parts.append(_("{0} awaiting purchase").format(summary.pending_purchase))
	unrequested = len([r for r in summary.lines if r.state == SHORTAGE])
	if unrequested:
		parts.append(_("{0} not yet requested").format(unrequested))
	return " · ".join(parts)
