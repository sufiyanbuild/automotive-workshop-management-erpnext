# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt
"""Technician workload from repair tasks and inspections.

Customer satisfaction is deliberately absent: the system captures no rating, and
a performance figure that is not measured would be misleading.
"""

import frappe
from frappe import _
from frappe.utils import flt

from automotive_workshop.workshop import constants as C


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "technician", "label": _("Technician"), "fieldtype": "Link", "options": "User", "width": 200},
		{"fieldname": "trade", "label": _("Trade"), "fieldtype": "Data", "width": 110},
		{"fieldname": "jobs", "label": _("Job Cards"), "fieldtype": "Int", "width": 100},
		{"fieldname": "tasks", "label": _("Tasks"), "fieldtype": "Int", "width": 80},
		{"fieldname": "completed", "label": _("Completed"), "fieldtype": "Int", "width": 100},
		{"fieldname": "open_tasks", "label": _("Open"), "fieldtype": "Int", "width": 80},
		{"fieldname": "estimated_hours", "label": _("Estimated Hours"), "fieldtype": "Float", "precision": 1, "width": 130},
		{"fieldname": "actual_hours", "label": _("Actual Hours"), "fieldtype": "Float", "precision": 1, "width": 120},
		{"fieldname": "variance", "label": _("Variance"), "fieldtype": "Float", "precision": 1, "width": 100},
		{"fieldname": "inspections", "label": _("Inspections"), "fieldtype": "Int", "width": 110},
		{"fieldname": "rework_jobs", "label": _("Jobs with Rework"), "fieldtype": "Int", "width": 140},
	]


def get_data(filters):
	conditions = ["t.aw_job_card is not null", "t.status != 'Cancelled'"]
	values = {}
	if filters.get("from_date"):
		conditions.append("jc.intake_datetime >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("jc.intake_datetime <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("trade"):
		conditions.append("t.aw_trade = %(trade)s")
		values["trade"] = filters.trade

	rows = frappe.db.sql(
		f"""select t.aw_technician as technician, t.aw_trade as trade,
				count(distinct t.aw_job_card) as jobs, count(t.name) as tasks,
				sum(case when t.status = 'Completed' then 1 else 0 end) as completed,
				sum(case when t.status != 'Completed' then 1 else 0 end) as open_tasks,
				sum(t.expected_time) as estimated_hours, sum(t.aw_labour_hours) as actual_hours,
				count(distinct case when jc.rework_count > 0 then jc.name end) as rework_jobs
			from `tabTask` t join `tabWorkshop Job Card` jc on jc.name = t.aw_job_card
			where {' and '.join(conditions)}
			group by t.aw_technician, t.aw_trade
			order by actual_hours desc""",
		values, as_dict=True,
	)
	inspections = dict(frappe.db.sql(
		"""select technician, count(name) from `tabVehicle Inspection`
		where docstatus = 1 and inspection_type != %(qc)s group by technician""", {"qc": C.QC_TYPE}))
	for row in rows:
		row.inspections = inspections.get(row.technician, 0)
		row.variance = flt(row.actual_hours) - flt(row.estimated_hours)
	return rows
