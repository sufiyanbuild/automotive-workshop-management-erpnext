"""Workshop dashboard: number cards and charts.

Number Card and Dashboard Chart are not synced from app files by Frappe, so they
are created here instead, once, and never overwritten afterwards: a workshop that
retunes a chart keeps its version through every migrate.

Every card and chart reads live documents. Nothing is hard-coded.
"""

import json

import frappe

from automotive_workshop.workshop import constants as C

JOB = "Workshop Job Card"
ALL_ROLES = [C.SYSTEM_MANAGER, C.MANAGER, C.RECEPTION, C.ACCOUNTS, C.STORE_KEEPER, C.PURCHASE, C.QUALITY_INSPECTOR]


def _filters(doctype=JOB, **conditions):
	"""Number Card and chart filters are a JSON list of [doctype, field, operator, value]."""
	return json.dumps([[doctype, field, op, value] for field, (op, value) in conditions.items()])


NUMBER_CARDS = [
	# Operations
	("Workshop Vehicles Received (Month)", JOB, "Count", "name",
	 _filters(intake_datetime=("Timespan", "this month")), "Blue"),
	("Workshop Active Job Cards", JOB, "Count", "name", _filters(released=("=", 0)), "Blue"),
	("Workshop Jobs In Progress", JOB, "Count", "name", _filters(status=("=", C.WORK_IN_PROGRESS)), "Orange"),
	("Workshop Pending Approvals", JOB, "Count", "name", _filters(status=("=", C.AWAITING_APPROVAL)), "Yellow"),
	("Workshop Parts Pending", JOB, "Count", "name", _filters(status=("=", C.PARTS_PENDING)), "Orange"),
	("Workshop Awaiting Quality Check", JOB, "Count", "name", _filters(status=("=", C.QUALITY_CHECK)), "Purple"),
	("Workshop Ready for Delivery", JOB, "Count", "name",
	 _filters(status=("=", C.INVOICED), released=("=", 0)), "Green"),
	# Financial
	("Workshop Revenue (Month)", "Sales Invoice", "Sum", "grand_total",
	 _filters(doctype="Sales Invoice", docstatus=("=", 1), aw_job_card=("is", "set"),
			  posting_date=("Timespan", "this month")), "Green"),
	("Workshop Outstanding Payments", "Sales Invoice", "Sum", "outstanding_amount",
	 _filters(doctype="Sales Invoice", docstatus=("=", 1), aw_job_card=("is", "set")), "Red"),
]

CHARTS = [
	# (name, chart type, doctype, config)
	("Workshop Job Cards by Status", "Group By", JOB, {
		"group_by_type": "Count", "group_by_based_on": "status", "type": "Donut", "number_of_groups": 8,
		"filters_json": _filters(released=("=", 0)),
	}),
	("Workshop Monthly Revenue", "Count", "Sales Invoice", {
		"chart_type": "Sum", "value_based_on": "grand_total", "based_on": "posting_date", "timespan": "Last Year",
		"time_interval": "Monthly", "type": "Bar", "document_type": "Sales Invoice",
		"filters_json": _filters(doctype="Sales Invoice", docstatus=("=", 1), aw_job_card=("is", "set")),
	}),
	# Joins Sales Invoice to Job Card, which a Group By chart cannot do, so it uses
	# the app's own Dashboard Chart Source.
	("Workshop Revenue by Service Type", "Custom", None, {
		"source": "Workshop Revenue by Service Type", "type": "Bar", "filters_json": "{}",
	}),
	("Workshop Labour Hours by Technician", "Group By", "Task", {
		"group_by_type": "Sum", "group_by_based_on": "aw_technician", "aggregate_function_based_on": "aw_labour_hours",
		"type": "Bar", "number_of_groups": 10, "filters_json": _filters(doctype="Task", aw_job_card=("is", "set")),
	}),
	("Workshop Quality Check Results", "Group By", "Vehicle Inspection", {
		"group_by_type": "Count", "group_by_based_on": "qc_result", "type": "Donut", "number_of_groups": 3,
		"filters_json": _filters(doctype="Vehicle Inspection", inspection_type=("=", C.QC_TYPE), docstatus=("=", 1)),
	}),
]


def create_number_cards():
	for label, doctype, function, field, filters, colour in NUMBER_CARDS:
		if frappe.db.exists("Number Card", label):
			continue
		# A card compares itself with the previous period only when its filters carry a
		# timespan; without one the comparison has nothing to divide by.
		periodic = "Timespan" in filters
		# Money is shown in full: Frappe's shortened-number path renders a zero-valued
		# currency card as NaN, and finance figures read better unabbreviated anyway.
		money = function != "Count"
		frappe.get_doc({
			"doctype": "Number Card", "name": label, "label": label, "document_type": doctype,
			"function": function, "aggregate_function_based_on": field if function != "Count" else None,
			"filters_json": filters, "color": colour, "is_public": 1,
			"show_full_number": 1 if money else 0,
			"show_percentage_stats": 1 if periodic else 0,
			"stats_time_interval": "Monthly" if periodic else None, "type": "Document Type",
			"roles": [{"role": r} for r in ALL_ROLES],
		}).insert(ignore_permissions=True)


def create_charts():
	for label, chart_type, doctype, config in CHARTS:
		if frappe.db.exists("Dashboard Chart", label):
			continue
		doc = {
			"doctype": "Dashboard Chart", "name": label, "chart_name": label, "chart_type": chart_type,
			"document_type": doctype, "is_public": 1, "timeseries": 0, "type": "Bar",
			"roles": [{"role": r} for r in ALL_ROLES],
		}
		doc.update(config)
		if chart_type in ("Report", "Custom"):
			doc["document_type"] = None
		frappe.get_doc(doc).insert(ignore_permissions=True)


def setup_dashboard():
	create_number_cards()
	create_charts()
