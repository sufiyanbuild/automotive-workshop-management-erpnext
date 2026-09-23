# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from automotive_workshop.workshop.parts import get_parts_summary


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "job_card", "label": _("Job Card"), "fieldtype": "Link", "options": "Workshop Job Card", "width": 140},
		{"fieldname": "registration_number", "label": _("Registration"), "fieldtype": "Data", "width": 110},
		{"fieldname": "status", "label": _("Job Status"), "fieldtype": "Data", "width": 130},
		{"fieldname": "item_code", "label": _("Part"), "fieldtype": "Link", "options": "Item", "width": 160},
		{"fieldname": "item_name", "label": _("Part Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "required", "label": _("Required"), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "issued", "label": _("Issued"), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "in_stock", "label": _("In Stock"), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "requested", "label": _("Requested"), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "ordered", "label": _("Ordered"), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "received", "label": _("Received"), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "state", "label": _("State"), "fieldtype": "Data", "width": 110},
	]


def get_data(filters):
	conditions = {"released": 0} if not filters.get("include_delivered") else {}
	if filters.get("job_card"):
		conditions["name"] = filters.job_card
	if filters.get("status"):
		conditions["status"] = filters.status

	rows = []
	for job in frappe.get_list("Workshop Job Card", filters=conditions, limit_page_length=0,
			fields=["name", "registration_number", "status"], order_by="intake_datetime desc"):
		summary = get_parts_summary(job.name)
		for line in summary.lines:
			if filters.get("only_pending") and line.state == "Issued":
				continue
			rows.append({
				"job_card": job.name, "registration_number": job.registration_number, "status": job.status,
				**{k: line[k] for k in ("item_code", "item_name", "required", "issued", "in_stock",
										"requested", "ordered", "received", "state")},
			})
	return rows
