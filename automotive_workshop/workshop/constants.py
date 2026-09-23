"""Names shared by the whole app: lifecycle statuses, visual stages and roles.

The eight statuses are the business lifecycle from the client proposal. The ten
stages are the visual tracker's breakdown of that lifecycle; lifecycle.py maps
one onto the other.
"""

from frappe import _dict

# -------------------------------------------------------------------- statuses
OPEN = "Open"
INSPECTION_COMPLETED = "Inspection Completed"
AWAITING_APPROVAL = "Awaiting Approval"
PARTS_PENDING = "Parts Pending"
WORK_IN_PROGRESS = "Work In Progress"
QUALITY_CHECK = "Quality Check"
COMPLETED = "Completed"
INVOICED = "Invoiced"

STATUSES = (
	OPEN,
	INSPECTION_COMPLETED,
	AWAITING_APPROVAL,
	PARTS_PENDING,
	WORK_IN_PROGRESS,
	QUALITY_CHECK,
	COMPLETED,
	INVOICED,
)

# -------------------------------------------------------------------- stages
STAGES = (
	_dict(key="reception", label="Reception"),
	_dict(key="inspection", label="Inspection"),
	_dict(key="assessment", label="Assessment"),
	_dict(key="quotation", label="Quotation"),
	_dict(key="approval", label="Approval"),
	_dict(key="parts", label="Parts"),
	_dict(key="repair", label="Repair"),
	_dict(key="qc", label="QC"),
	_dict(key="invoice", label="Invoice"),
	_dict(key="delivery", label="Delivery"),
)

# Job Card tab that each stage focuses when it is the current stage.
STAGE_TABS = {
	"reception": "overview_tab",
	"inspection": "inspection_tab",
	"assessment": "assessment_tab",
	"quotation": "quotation_tab",
	"approval": "quotation_tab",
	"parts": "procurement_tab",
	"repair": "repair_tab",
	"qc": "quality_tab",
	"invoice": "billing_tab",
	"delivery": "delivery_tab",
}

# -------------------------------------------------------------------- approvals
APPROVAL_PENDING = "Pending"
APPROVAL_APPROVED = "Approved"
APPROVAL_REJECTED = "Rejected"
APPROVAL_REVISION = "Revision Requested"
APPROVAL_DECISIONS = (APPROVAL_APPROVED, APPROVAL_REJECTED, APPROVAL_REVISION)

QC_PASSED = "Passed"
QC_FAILED = "Failed"
QC_TYPE = "Quality Check"
TRADES = ("Denter", "Mechanic", "Electrician")

# -------------------------------------------------------------------- roles
RECEPTION = "Reception"
MANAGER = "Workshop Manager"
DENTER = "Denter"
MECHANIC = "Mechanic"
ELECTRICIAN = "Electrician"
QUALITY_INSPECTOR = "Quality Inspector"
PURCHASE = "Purchase Department"
STORE_KEEPER = "Store Keeper"
ACCOUNTS = "Accounts Department"
SYSTEM_MANAGER = "System Manager"

TECHNICIAN_ROLES = (DENTER, MECHANIC, ELECTRICIAN)
WORKSHOP_ROLES = (
	RECEPTION,
	MANAGER,
	DENTER,
	MECHANIC,
	ELECTRICIAN,
	QUALITY_INSPECTOR,
	PURCHASE,
	STORE_KEEPER,
	ACCOUNTS,
)
# Roles that see every Job Card rather than only the ones they work on.
SUPERVISORY_ROLES = (SYSTEM_MANAGER, MANAGER, RECEPTION, QUALITY_INSPECTOR, PURCHASE, STORE_KEEPER, ACCOUNTS)
