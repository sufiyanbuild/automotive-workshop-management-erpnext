# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt
"""Workshop revenue from submitted Sales Invoices linked to Job Cards.

Parts and labour are separated by comparing each invoice line against the labour
service item configured in Workshop Settings, so no revenue figure is invented.
"""

import frappe
from frappe import _
from frappe.utils import flt, formatdate, getdate

from automotive_workshop.workshop.settings import get_settings


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_by = filters.get("group_by") or "Service Type"
	data = get_data(filters, group_by)
	return get_columns(group_by), data, None, get_chart(data, group_by)


def get_columns(group_by):
	return [
		{"fieldname": "group", "label": _(group_by), "fieldtype": "Data", "width": 180},
		{"fieldname": "jobs", "label": _("Jobs"), "fieldtype": "Int", "width": 80},
		{"fieldname": "parts", "label": _("Parts"), "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "labour", "label": _("Labour"), "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "net_total", "label": _("Net Total"), "fieldtype": "Currency", "options": "currency", "width": 140},
		{"fieldname": "vat", "label": _("VAT"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "grand_total", "label": _("Total"), "fieldtype": "Currency", "options": "currency", "width": 140},
		{"fieldname": "outstanding", "label": _("Outstanding"), "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters, group_by):
	labour_item = get_settings().labour_item
	conditions = ["si.docstatus = 1", "si.aw_job_card is not null", "si.is_return = 0"]
	values = {"labour_item": labour_item}
	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")
		values["customer"] = filters.customer

	rows = frappe.db.sql(
		f"""select si.name, si.posting_date, si.currency, si.net_total, si.total_taxes_and_charges,
				si.grand_total, si.outstanding_amount, jc.service_type,
				sum(case when sii.item_code = %(labour_item)s then sii.net_amount else 0 end) as labour,
				sum(case when sii.item_code = %(labour_item)s then 0 else sii.net_amount end) as parts
			from `tabSales Invoice` si
			join `tabSales Invoice Item` sii on sii.parent = si.name
			join `tabWorkshop Job Card` jc on jc.name = si.aw_job_card
			where {' and '.join(conditions)}
			group by si.name""",
		values, as_dict=True,
	)

	buckets = {}
	for row in rows:
		key = row.service_type if group_by == "Service Type" else formatdate(getdate(row.posting_date), "MMM yyyy")
		bucket = buckets.setdefault(key, frappe._dict(
			group=key, jobs=0, parts=0, labour=0, net_total=0, vat=0, grand_total=0, outstanding=0,
			currency=row.currency, sort_key=getdate(row.posting_date).replace(day=1),
		))
		bucket.jobs += 1
		bucket.parts += flt(row.parts)
		bucket.labour += flt(row.labour)
		bucket.net_total += flt(row.net_total)
		bucket.vat += flt(row.total_taxes_and_charges)
		bucket.grand_total += flt(row.grand_total)
		bucket.outstanding += flt(row.outstanding_amount)

	data = list(buckets.values())
	data.sort(key=lambda r: r.sort_key if group_by != "Service Type" else -r.grand_total)
	for row in data:
		row.pop("sort_key", None)
	return data


def get_chart(data, group_by):
	if not data:
		return None
	return {
		"data": {
			"labels": [r.group for r in data],
			"datasets": [
				{"name": _("Parts"), "values": [flt(r.parts, 2) for r in data]},
				{"name": _("Labour"), "values": [flt(r.labour, 2) for r in data]},
			],
		},
		"type": "bar",
		"barOptions": {"stacked": True},
	}
