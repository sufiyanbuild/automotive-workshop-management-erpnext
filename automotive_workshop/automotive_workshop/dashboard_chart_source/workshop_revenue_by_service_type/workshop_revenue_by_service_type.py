# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt
"""Invoiced workshop revenue grouped by the Job Card's service type.

A Group By chart cannot do this: the amount is on the Sales Invoice while the
service type is on the Job Card, so the two are joined here.
"""

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.dashboard import cache_source


@frappe.whitelist()
@cache_source
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	filters = frappe.parse_json(filters) or {}
	conditions = ["si.docstatus = 1", "si.aw_job_card is not null", "si.is_return = 0"]
	values = {}
	if from_date:
		conditions.append("si.posting_date >= %(from_date)s")
		values["from_date"] = from_date
	if to_date:
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = to_date
	if filters.get("company"):
		conditions.append("si.company = %(company)s")
		values["company"] = filters["company"]

	rows = frappe.db.sql(
		f"""select jc.service_type, sum(si.base_grand_total) as revenue
			from `tabSales Invoice` si join `tabWorkshop Job Card` jc on jc.name = si.aw_job_card
			where {' and '.join(conditions)}
			group by jc.service_type order by revenue desc""",
		values, as_dict=True,
	)
	return {
		"labels": [_(r.service_type) for r in rows],
		"datasets": [{"name": _("Revenue"), "values": [flt(r.revenue, 2) for r in rows]}],
	}
