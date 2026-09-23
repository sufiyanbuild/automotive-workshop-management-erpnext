# Automotive Workshop Management

A complete workshop-management system for vehicle repair businesses, built as a
Frappe app (`automotive_workshop`) on top of ERPNext v16.

The Workshop Job Card is the centre of the system: one screen follows a vehicle
from reception to delivery, shows where it is, what is blocking it and who is
responsible, and creates every related document already filled in.

```
Customer → Vehicle Master → Workshop Job Card → Inspection → Damage Assessment
        → Quotation → Customer approval → Parts → Repair → Quality Check
        → Sales Invoice → Payment → Vehicle delivery → Service history
```

Everything that ERPNext already does well is used as it is: customers, items,
stock, buying, quotations, invoices, payments, taxes and projects. The app adds
only what an automotive workshop needs on top.

## What the app adds

| Custom DocType | Why it exists |
| --- | --- |
| **Vehicle Master** | ERPNext's `Vehicle` is a company fleet record tied to employees. A workshop needs the *customer's* vehicle, with plate and VIN validation, ownership and service history. |
| **Workshop Job Card** | The operational hub for one visit. Nothing else in ERPNext tracks a vehicle through inspection, approval, parts, repair, QC and delivery. |
| **Vehicle Inspection** | Role-specific inspections (Denter, Mechanic, Electrician) and the final Quality Check, with digital checklists. |
| **Damage Assessment** | Consolidates damage, required parts and labour into the estimate the quotation is built from. |
| **Workshop Settings** | Warehouse, labour item, VAT template and the vehicle-release rule, so none of these are hard-coded. |

Standard ERPNext carries the rest, each linked back to the Job Card through an
`aw_job_card` field: Quotation, Material Request, Purchase Order, Purchase
Receipt, Stock Entry, Task, Sales Invoice and Payment Entry.

Quality Check deliberately does **not** use ERPNext's `Quality Inspection`: that
DocType requires an `item_code` and only accepts stock documents as a reference,
so it cannot inspect a repaired vehicle.

## Main features

- **One screen per visit.** The Job Card shows the stage, the figures that
  matter, the next action, who owns it and what is blocking it.
- **Visual workflow tracker** across ten stages — Reception, Inspection,
  Assessment, Quotation, Approval, Parts, Repair, QC, Invoice, Delivery —
  computed from the real documents, never decorative.
- **Context-aware Create and Actions menus.** Only what is valid at this stage,
  for this user, is offered; every endpoint re-checks it server-side.
- **Prefilled documents.** Inspections, assessments, quotations, material
  requests, parts issues, repair tasks, invoices and payments all open with the
  customer, vehicle and job already filled in.
- **Role-specific inspections** for Denter, Mechanic and Electrician, with
  digital checklists configured in Workshop Settings.
- **Customer approval gate.** Repair cannot begin until the customer has
  approved the quotation; rejection and revision are first-class paths.
- **Parts traceability** from the assessment through Material Request, Purchase
  Order and Purchase Receipt to the Stock Entry that issues the part to the job.
- **Mandatory Quality Check** before invoicing; a failed QC returns the job to
  repair, reopens its tasks and counts the rework.
- **Controlled delivery.** A vehicle is released only after QC, invoicing and
  payment (or on credit, if configured, by a Workshop Manager with a reason).
- **Service history** per vehicle, derived from the Job Cards themselves.
- **Workshop dashboard and five reports**, all on live data.
- **Arabic translations** and 15% VAT through standard ERPNext tax templates.

## Workflow

Eight business statuses own the lifecycle:

```
Open → Inspection Completed → Awaiting Approval → Parts Pending
     → Work In Progress → Quality Check → Completed → Invoiced
```

Delivery is recorded on the Job Card (`released`, `released_on`, `released_by`)
rather than as a ninth status. The ten visual stages are a projection of these
eight statuses plus the state of the related documents, so the tracker and the
workflow cannot disagree.

One Python state machine (`workshop/lifecycle.py`) owns every transition. The
status field is read-only, and the controller rejects any change to it — or to
any other system-maintained field — that did not come through that state
machine. Critical rules are enforced on the server: no repair before approval,
issued parts and an assigned technician; no invoice before QC passes; no release
before QC, invoice and payment.

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/sufiyanbuild/automotive-workshop-management-erpnext.git --branch version-16
bench --site <site> install-app automotive_workshop
```

The install creates roles, role profiles, custom fields, permissions, the KSA
VAT 15% templates, a labour service item and the default inspection checklists.
It never overwrites configuration that already exists, so `bench migrate` is
safe to run repeatedly.

Afterwards, open **Workshop Settings** and confirm the parts warehouse, labour
rate and VAT template.

## Demo data

```bash
bench --site <site> execute automotive_workshop.demo.create_demo
bench --site <site> execute automotive_workshop.demo.drop_demo
```

Creates a Saudi workshop scenario: three customers, five vehicles, parts with
stock, a supplier, nine staff users (one per role) and six Job Cards, one at
each stage of the lifecycle plus one delivered vehicle with full history. Demo
records are tagged `[DEMO]` and can be removed again.

The demo users' password is **not stored in this repository**. A random one is
generated per run and printed once when the users are created; set
`AW_DEMO_PASSWORD` in the environment to choose your own. Demo users belong on
a local demo site only — never create them on a client site.

## Tests

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app automotive_workshop
```

55 integration tests covering the lifecycle, the tracker, both menus, document
prefilling, parts and purchasing, validation and role permissions — positive
and negative cases in each area.

## Development conventions

- **Never modify Frappe or ERPNext.** Extension happens only through
  `doc_events`, custom fields, permission hooks, client scripts and fixtures.
- **`aw_` prefixes every custom field**, so ownership is unambiguous on a bench
  that hosts several apps.
- **Configuration is created in code** (`setup/`), idempotently, and re-applied
  on every migrate; it never overwrites a value a site already has. Permissions
  on standard DocTypes use `frappe.permissions.add_permission`, never Custom
  DocPerm fixtures, which would strip ERPNext's own roles.
- **Business rules live on the server.** Client scripts draw what the server
  computed (`workshop/context.py`) and decide nothing on their own.
- **No secrets in the repository** — no passwords, keys or tokens, including in
  demo code.
- **Branch:** `version-16`, matching the Frappe/ERPNext major version the app
  targets.
- Python follows the ruff configuration in `pyproject.toml` (tabs, 110 columns).

## Scope and known gaps

These are **not implemented**, and are listed so nobody mistakes them for
delivered features:

| Not implemented | Detail |
| --- | --- |
| **Data migration** | No import templates, transformation scripts or post-import reconciliation. The DocTypes work with ERPNext's standard Data Import tool, but no migration tooling has been built or tested. |
| **Custom print formats** | Quotations, invoices and Job Cards print with ERPNext's standard formats. No workshop-branded print format exists. |
| **ZATCA e-invoicing** | Not integrated in any form. VAT at 15% is configured through standard tax templates and tested; nothing about Saudi e-invoicing compliance is built or claimed. The architecture keeps the route open, since invoices are standard ERPNext Sales Invoices. |
| **Technician customer-satisfaction rating** | The system captures no customer rating, so the Technician Performance report deliberately omits it rather than showing a number nothing measures. |
| **Quotation rejection / inspection-fee closure** | If a customer rejects the quotation outright, the job can be revised or left open, but there is no path to close it and hand the vehicle back unrepaired. This needs a business decision from the client: whether an inspection fee is charged, and how such a visit is closed and invoiced. |

Phase-2 items from the proposal — WhatsApp integration, mobile app, customer
portal, VIN decoder, advanced analytics — are out of scope and not built.

## Deployment

The app is deployed like any other Frappe app — there is nothing bespoke about
it, and no vendor-specific code.

| | |
| --- | --- |
| Repository | `automotive-workshop-management-erpnext` |
| Branch | `version-16` |
| Requires | Frappe v16 and ERPNext v16 (`required_apps`), Python 3.14 or newer |

On Frappe Cloud, add the repository to a bench running **Frappe v16 with Python
3.14**, then install the app on the site. The Python floor is declared in
`pyproject.toml` and is deliberate: the bench should match it rather than the
app being loosened to fit an older bench.

After installing on a new site:

1. Open **Workshop Settings** and confirm the parts warehouse, labour item,
   labour rate and VAT template (the install seeds them from the company, but a
   real workshop should confirm them).
2. Create the staff users and give each one the matching role profile.
3. Do **not** run the demo module on a production site — it exists for local
   demonstration only.

## Documentation

- [docs/architecture.md](docs/architecture.md) — data model, workflow, menu logic, validation, permissions
- [docs/user-guide.md](docs/user-guide.md) — how each role works the system, day to day

## Licence

MIT
