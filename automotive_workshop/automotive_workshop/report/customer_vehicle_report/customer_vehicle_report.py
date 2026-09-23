# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 220},
		{"fieldname": "mobile_no", "label": _("Mobile"), "fieldtype": "Data", "width": 120},
		{"fieldname": "vehicles", "label": _("Vehicles"), "fieldtype": "Int", "width": 90},
		{"fieldname": "registrations", "label": _("Registrations"), "fieldtype": "Data", "width": 220},
		{"fieldname": "visits", "label": _("Visits"), "fieldtype": "Int", "width": 80},
		{"fieldname": "open_jobs", "label": _("In Workshop"), "fieldtype": "Int", "width": 110},
		{"fieldname": "last_visit", "label": _("Last Visit"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "billed", "label": _("Billed"), "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "outstanding", "label": _("Outstanding"), "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters):
	conditions, values = [], {}
	if filters.get("customer"):
		conditions.append("v.customer = %(customer)s")
		values["customer"] = filters.customer

	where = ("where " + " and ".join(conditions)) if conditions else ""
	rows = frappe.db.sql(
		f"""select v.customer, c.mobile_no, count(distinct v.name) as vehicles,
				group_concat(distinct v.registration_number order by v.registration_number separator ', ') as registrations
			from `tabVehicle Master` v join `tabCustomer` c on c.name = v.customer
			{where}
			group by v.customer, c.mobile_no
			order by vehicles desc""",
		values, as_dict=True,
	)
	jobs = frappe.db.sql(
		"""select customer, count(name) as visits, sum(case when released = 0 then 1 else 0 end) as open_jobs,
			max(intake_datetime) as last_visit, sum(invoice_total) as billed,
			sum(outstanding_amount) as outstanding, max(currency) as currency
		from `tabWorkshop Job Card` group by customer""", as_dict=True)
	by_customer = {j.customer: j for j in jobs}
	for row in rows:
		stats = by_customer.get(row.customer)
		row.update({
			"visits": stats.visits if stats else 0,
			"open_jobs": stats.open_jobs if stats else 0,
			"last_visit": stats.last_visit if stats else None,
			"billed": flt(stats.billed) if stats else 0,
			"outstanding": flt(stats.outstanding) if stats else 0,
			"currency": stats.currency if stats else None,
		})
		if filters.get("only_outstanding") and not row.outstanding:
			row["_skip"] = True
	return [r for r in rows if not r.get("_skip")]
