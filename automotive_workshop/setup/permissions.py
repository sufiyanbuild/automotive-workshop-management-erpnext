"""Workshop role access to standard ERPNext DocTypes.

If any Custom DocPerm row exists for a DocType, Frappe ignores its standard
DocPerm rows. frappe.permissions.add_permission() copies the standard rows into
Custom DocPerm first, so existing ERPNext roles keep their access. Never insert
Custom DocPerm rows directly.
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

from automotive_workshop.workshop import constants as C

R = {"read": 1}
SELECT = {"select": 1}
CRW = {"read": 1, "write": 1, "create": 1}
RW = {"read": 1, "write": 1}
CRWS = {"read": 1, "write": 1, "create": 1, "submit": 1}
CRWSX = {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "amend": 1}
TECH = {r: R for r in C.TECHNICIAN_ROLES}

PERMISSIONS = {
	"Customer": {C.RECEPTION: CRW, C.MANAGER: CRW, C.ACCOUNTS: RW, C.QUALITY_INSPECTOR: R},
	"Contact": {C.RECEPTION: CRW, C.MANAGER: CRW, C.ACCOUNTS: R},
	"Address": {C.RECEPTION: CRW, C.MANAGER: CRW, C.ACCOUNTS: R},
	"Item": {C.MANAGER: R, C.STORE_KEEPER: CRW, C.PURCHASE: R, C.ACCOUNTS: R, **TECH},
	"Quotation": {C.RECEPTION: R, C.MANAGER: CRWSX, C.ACCOUNTS: CRWSX},
	"Material Request": {C.MANAGER: CRWS, C.STORE_KEEPER: CRWSX, C.PURCHASE: CRWSX},
	"Request for Quotation": {C.PURCHASE: CRWSX},
	"Supplier Quotation": {C.PURCHASE: CRWSX},
	"Supplier": {C.PURCHASE: CRW, C.STORE_KEEPER: R, C.ACCOUNTS: R},
	"Purchase Order": {C.PURCHASE: CRWSX, C.STORE_KEEPER: R, C.MANAGER: R, C.ACCOUNTS: R},
	"Purchase Receipt": {C.STORE_KEEPER: CRWSX, C.PURCHASE: CRWS, C.ACCOUNTS: R},
	"Stock Entry": {C.STORE_KEEPER: CRWSX, C.MANAGER: R},
	"Warehouse": {C.STORE_KEEPER: R, C.PURCHASE: R, C.MANAGER: R},
	"Bin": {C.STORE_KEEPER: R, C.PURCHASE: R, C.MANAGER: R},
	"Task": {C.MANAGER: CRW, **{r: RW for r in C.TECHNICIAN_ROLES}, C.QUALITY_INSPECTOR: R},
	"Sales Invoice": {C.ACCOUNTS: CRWSX, C.MANAGER: R, C.RECEPTION: R},
	# ERPNext resolves the party account when a buying or selling document is made
	# (erpnext/accounts/party.py::get_party_account), which needs at least select here.
	"Account": {C.PURCHASE: SELECT, C.STORE_KEEPER: SELECT, C.MANAGER: SELECT},
	"Cost Center": {C.PURCHASE: SELECT, C.STORE_KEEPER: SELECT, C.MANAGER: SELECT},
	"Payment Entry": {C.ACCOUNTS: CRWSX, C.MANAGER: R},
}


def setup_permissions():
	applied = 0
	for doctype, roles in PERMISSIONS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for role, ptypes in roles.items():
			if not frappe.db.exists("Role", role):
				continue
			add_permission(doctype, role, 0)
			for ptype, value in ptypes.items():
				update_permission_property(doctype, role, 0, ptype, value, validate=False)
			for ptype in ("report", "print", "email", "export"):
				update_permission_property(doctype, role, 0, ptype, 1, validate=False)
			applied += 1
	frappe.clear_cache()
	return applied
