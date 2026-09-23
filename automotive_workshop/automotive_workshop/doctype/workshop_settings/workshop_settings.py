# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WorkshopSettings(Document):
	def validate(self):
		if self.labour_item and frappe.db.get_value("Item", self.labour_item, "is_stock_item"):
			frappe.throw(_("Labour Service Item {0} must be a non-stock (service) item.").format(self.labour_item))
		if self.workshop_warehouse and self.company:
			wh_company = frappe.db.get_value("Warehouse", self.workshop_warehouse, "company")
			if wh_company != self.company:
				frappe.throw(_("Parts Warehouse {0} belongs to {1}, not {2}.").format(self.workshop_warehouse, wh_company, self.company))
		if self.sales_taxes_template and self.company:
			tpl_company = frappe.db.get_value("Sales Taxes and Charges Template", self.sales_taxes_template, "company")
			if tpl_company != self.company:
				frappe.throw(_("VAT Template {0} belongs to {1}, not {2}.").format(self.sales_taxes_template, tpl_company, self.company))

	def on_update(self):
		frappe.clear_document_cache("Workshop Settings", "Workshop Settings")
