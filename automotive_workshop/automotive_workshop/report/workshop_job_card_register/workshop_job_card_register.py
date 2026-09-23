# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, get_datetime

from automotive_workshop.workshop import constants as C


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "name", "label": _("Job Card"), "fieldtype": "Link", "options": "Workshop Job Card", "width": 140},
		{"fieldname": "intake_datetime", "label": _("Received"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "registration_number", "label": _("Registration"), "fieldtype": "Data", "width": 110},
		{"fieldname": "vehicle_title", "label": _("Vehicle"), "fieldtype": "Data", "width": 150},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 180},
		{"fieldname": "service_type", "label": _("Service Type"), "fieldtype": "Data", "width": 130},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 140},
		{"fieldname": "current_stage", "label": _("Stage"), "fieldtype": "Data", "width": 110},
		{"fieldname": "workshop_manager", "label": _("Manager"), "fieldtype": "Link", "options": "User", "width": 140},
		{"fieldname": "quotation_total", "label": _("Quotation"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "invoice_total", "label": _("Invoiced"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "outstanding_amount", "label": _("Outstanding"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "days_in_workshop", "label": _("Days in Workshop"), "fieldtype": "Float", "precision": 1, "width": 130},
		{"fieldname": "released_on", "label": _("Released"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters):
	conditions = {}
	for field in ("status", "service_type", "customer", "workshop_manager", "priority"):
		if filters.get(field):
			conditions[field] = filters[field]
	if filters.get("only_open"):
		conditions["released"] = 0
	if filters.get("from_date") and filters.get("to_date"):
		conditions["intake_datetime"] = ["between", [filters.from_date, filters.to_date]]

	rows = frappe.get_list(
		"Workshop Job Card", filters=conditions, order_by="intake_datetime desc", limit_page_length=0,
		fields=["name", "intake_datetime", "registration_number", "vehicle_title", "customer", "service_type",
				"status", "current_stage", "workshop_manager", "quotation_total", "invoice_total",
				"outstanding_amount", "released", "released_on", "currency"],
	)
	for row in rows:
		end = get_datetime(row.released_on) if row.released else now_datetime()
		row["days_in_workshop"] = flt((end - get_datetime(row.intake_datetime)).total_seconds() / 86400, 1)
	return rows
