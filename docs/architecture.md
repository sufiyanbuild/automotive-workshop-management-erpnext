# Architecture

## 1. Principles

1. **Configuration first.** If ERPNext already does it, ERPNext does it. The app
   adds four business DocTypes and one settings DocType, nothing more.
2. **One anchor.** The Workshop Job Card is the only hub. Related documents point
   back at it through `aw_job_card`; the Job Card stores only the links it needs
   to show its own state (assessment, quotation, QC, invoice).
3. **One rule engine.** The lifecycle lives in `workshop/lifecycle.py`. The
   browser draws what the server computes and never decides anything.
4. **Upgrade-safe.** No Frappe or ERPNext file is modified. Extension happens
   through `doc_events`, custom fields, permission hooks and client scripts.

## 2. Data model

```
Customer  (standard)
   │
   └── Vehicle Master ──────────── Workshop Job Card ─────────────┐
         VEH-00001                  JC-2026-00001                 │
                                        │                         │
       ┌────────────────────────────────┼──────────────────┐      │
       │                 │              │                  │      │
   Vehicle           Damage         Quotation           Task   Sales Invoice
   Inspection       Assessment     (standard)        (standard)  (standard)
   INSP-2026-…      DA-2026-…           │                          │
   (trade + QC)          │              │                     Payment Entry
                         │        Material Request                 │
                         │        → Purchase Order          Service history
                         │        → Purchase Receipt        (derived, not stored)
                         └──────► Stock Entry (parts issued to the job)
```

Custom fields are prefixed `aw_` so ownership is unambiguous on a bench that
hosts more than one app.

| DocType | Fields added |
| --- | --- |
| Quotation | `aw_job_card`, `aw_vehicle`, `aw_registration`, `aw_customer_approval`, `aw_sent_on`, `aw_approved_on`, `aw_approval_remarks` |
| Sales Invoice | `aw_job_card`, `aw_vehicle`, `aw_quotation` |
| Payment Entry | `aw_job_card` |
| Material Request | `aw_job_card`, `aw_vehicle` |
| Stock Entry | `aw_job_card` |
| Purchase Order Item, Purchase Receipt Item, Supplier Quotation Item, RFQ Item | `aw_job_card` (traced from the Material Request, per line) |
| Task | `aw_job_card`, `aw_vehicle`, `aw_customer`, `aw_trade`, `aw_technician`, `aw_labour_hours`, `aw_work_notes` |

## 3. Lifecycle

The eight business statuses from the proposal are preserved exactly:

```
Open → Inspection Completed → Awaiting Approval → Parts Pending
     → Work In Progress → Quality Check → Completed → Invoiced
```

Delivery is not a ninth status: it is recorded on the Job Card
(`released`, `released_on`, `released_by`), because a delivered vehicle is a
closed job rather than a different stage of work.

### How a status changes

Every change goes through `lifecycle.transition()`, which checks the move is in
the allowed table and flags the save. `WorkshopJobCard.validate` rejects any
change to `status` — or to any other system-maintained field — that did not come
through that function. Users cannot move a job by editing a field.

| From | To | Triggered by |
| --- | --- | --- |
| Open | Inspection Completed | all trade inspections submitted, no drafts left |
| Inspection Completed | Awaiting Approval | quotation submitted |
| Awaiting Approval | Inspection Completed | quotation cancelled for revision |
| Awaiting Approval | Parts Pending | customer approval recorded as Approved |
| Parts Pending | Work In Progress | *Start Repair* (approval + all parts issued + tasks assigned) |
| Work In Progress | Quality Check | *Request Quality Check* (every repair task completed) |
| Quality Check | Completed | Quality Check inspection submitted as Passed |
| Quality Check | Work In Progress | Quality Check failed, or *Return to Repair* |
| Completed | Invoiced | Sales Invoice submitted |
| Invoiced | Completed | Sales Invoice cancelled |

A **Frappe Workflow was deliberately not used**. It would be a second engine
with a second native "Actions" menu, and its conditions cannot express rules
like "every required part has been issued". One state machine, in Python, keeps
the technical workflow and the visual workflow in step by construction.

## 4. Visual workflow

Ten stages are shown; each is derived from the status plus the related
documents, in `lifecycle.compute_stages()`:

| Stage | Complete when |
| --- | --- |
| Reception | an inspection has been started, or the job has moved past Open |
| Inspection | status is at least Inspection Completed |
| Assessment | a Damage Assessment is submitted |
| Quotation | the quotation is submitted **and** sent to the customer |
| Approval | the customer approved (status at least Parts Pending) |
| Parts | every required part has been issued to the job |
| Repair | status is at least Quality Check |
| QC | status is at least Completed |
| Invoice | status is Invoiced |
| Delivery | the vehicle has been released |

The first incomplete stage is the current one; the rest are pending. A stage is
marked *attention* (amber) when it needs intervention: a rejected quotation, a
parts shortage, or rework after a failed QC.

Clicking a completed stage opens its document, the current stage focuses its
tab, and a pending stage explains what it is waiting for and who owns it.

## 5. Create and Actions menus

Both are built by `workshop/menus.py` from the Job Card state, and filtered by
what the signed-in user may actually do. Nothing is hard-coded per status in the
browser; `public/js/job_card/panels.js` only knows how to carry out a key.

| Status | Create | Actions |
| --- | --- | --- |
| Open | Vehicle Inspection, Damage Assessment | Start Inspection, View Customer |
| Inspection Completed | Vehicle Inspection, Damage Assessment, Quotation | Create/View Damage Assessment, Prepare Quotation |
| Awaiting Approval | Revised Quotation (only after rejection) | Send Quotation, Record Customer Approval, Revise Quotation, View Quotation |
| Parts Pending | Material Request, Parts Issue, Repair Task | Check Parts Availability, Issue Parts, Request Parts, Assign Repair Task, Start Repair |
| Work In Progress | Repair Task, Quality Check | Update Repair Progress, Request Quality Check, View Repair Tasks |
| Quality Check | Quality Check | Pass QC, Reject QC, Return to Repair |
| Completed | Sales Invoice | Generate Sales Invoice, View Service History |
| Invoiced | Payment Entry | Record Payment, Release Vehicle, View Invoice, View Service History |
| Delivered | — | View Invoice, View Service History |

An option appears only when it is both valid at that stage and permitted for the
user: *Start Repair* is hidden until approval, parts and tasks are all in place;
*Release Vehicle* is hidden while the invoice is unpaid; *Generate Sales Invoice*
is offered to Accounts, not to the Workshop Manager; only a Quality Inspector is
offered the Quality Check. Every endpoint re-checks both conditions server-side
(`menus.assert_can_run`, `menus.assert_can_create`, and the lifecycle guards), so
hiding a menu entry is a convenience, never the control.

## 6. Prefilled documents

`workshop/mappers.py` builds each document from the Job Card, so nothing is
typed twice:

| Created | Prefilled with |
| --- | --- |
| Vehicle Inspection | job card, vehicle, customer, inspection type, technician, checklist from Workshop Settings (a QC also lists one row per repair task) |
| Damage Assessment | job card, vehicle, customer, damage items from faulty checklist rows, labour lines from the inspectors' estimated hours |
| Quotation | customer, job card, vehicle, parts and labour from the assessment, VAT template, validity |
| Material Request | job card, vehicle, exactly the quantities still short, workshop warehouse |
| Stock Entry | job card, the parts available to issue, from the workshop warehouse |
| Task | job card, vehicle, customer, trade, technician, estimated hours; assigned to the technician |
| Sales Invoice | built from the approved quotation, plus job card, vehicle and quotation references |
| Payment Entry | ERPNext's own payment entry against the invoice, tagged with the job card |

`get_mapped_doc` copies same-named fields, which would carry the Job Card's
naming series onto the new document, so `naming_series`, `status`, `company`,
`currency`, `priority` and `amended_from` are excluded from the mapping.

## 7. Parts

Nothing about parts is stored on the Job Card; `workshop/parts.py` computes the
position from the ledgers each time:

- **Required** — the submitted Damage Assessment's parts table
- **Issued** — submitted Material Issue Stock Entries tagged with the job
- **In stock** — `Bin.actual_qty` in the workshop warehouse
- **Requested / Ordered / Received** — submitted Material Requests, Purchase
  Order items and Purchase Receipt items traced back to the job

Each line is then *Issued*, *Available*, *On Order*, *Requested* or *Shortage*,
which drives the Parts stage, the next action and the Job Card Parts report.

## 8. Server-side validation

The rules below are enforced in Python, not only in the browser:

- VIN is exactly 17 characters without I, O or Q, and unique
- Saudi plates are normalised (Arabic or Latin letters, Arabic-Indic digits) and unique
- a vehicle cannot have two open Job Cards
- the owner cannot change while a job is open
- an inspection can only be carried out by a technician holding that trade's role
- a Quality Check can only be recorded by a Quality Inspector, only at the QC stage, and cannot pass with faulty checklist items
- the Damage Assessment can only be submitted once the inspections are complete
- a quotation must carry VAT, must belong to the job's customer, and needs a submitted assessment
- customer approval can only be recorded after the quotation has been sent, and only once
- an approved quotation cannot be cancelled once work has started
- repair cannot start without approval, parts and an assigned technician — and a repair task cannot be moved to Working before that either
- labour hours must be recorded before a repair task is completed
- Quality Check cannot be requested while any repair task is open
- a Sales Invoice cannot be submitted unless the job passed QC, and only one invoice per job
- a vehicle cannot be released without QC, an invoice and settled payment (unless Workshop Settings allow credit release, which only a Workshop Manager may use, with a recorded reason)
- a closed (released) Job Card can no longer be edited

Errors say what to do rather than just failing: *"Repair cannot start because the
customer quotation has not been approved."*

## 9. Permissions

Ten roles, granted through Role Profiles that bundle each workshop role with the
standard ERPNext roles that department needs:

| Role profile | Roles |
| --- | --- |
| Workshop Reception | Reception |
| Workshop Manager | Workshop Manager, Sales User, Projects User, Stock User |
| Workshop Denter / Mechanic / Electrician | the trade role |
| Workshop Quality Inspector | Quality Inspector |
| Workshop Purchase | Purchase Department, Purchase User |
| Workshop Store Keeper | Store Keeper, Stock User |
| Workshop Accounts | Accounts Department, Accounts User, Sales User |
| Workshop Administrator | System Manager, Workshop Manager |

"System Administrator" from the proposal maps to ERPNext's own System Manager
rather than a duplicate role.

Permissions on standard DocTypes are applied with `frappe.permissions.add_permission`
in `setup/permissions.py`, never as a Custom DocPerm fixture: Frappe ignores the
standard DocPerm rows for a DocType as soon as one Custom DocPerm row exists, so
importing a fixture would silently strip ERPNext's own roles.

Technicians additionally get row-level limits (`workshop/permissions.py`): they
see the Job Cards and assessments of vehicles currently in the workshop, but only
their own inspections and repair tasks, and once a vehicle is delivered its Job
Card stays visible only to the technicians who worked on it.

## 10. Dashboards and reports

The **Automotive Workshop** workspace shows nine number cards (vehicles received this month,
active jobs, in progress, pending approvals, parts pending, awaiting QC, ready for
delivery, revenue this month, outstanding) and five charts (jobs by status, QC
results, monthly revenue, revenue by service type, labour hours by technician).
Every figure is a live query; none is stored or hard-coded.

Five script reports ship with the app — Workshop Job Card Register, Job Card
Parts, Workshop Revenue, Technician Performance, Customer Vehicle Report — and
the workspace links to ERPNext's own Accounts Receivable, Stock Balance, Profit
and Loss Statement and Balance Sheet rather than reimplementing them.

Technician "customer satisfaction" is deliberately absent: the system captures no
rating, and a number that is not measured would be misleading.

## 11. VAT

15% VAT is created once, at install, as an ERPNext tax template
(`KSA VAT 15%`) with a `VAT 15%` tax account. After that the template is the only
source of the rate; no VAT percentage is computed in code. Quotations and invoices
carry the template, and a workshop quotation cannot be submitted without it.

This is tax configuration only. **No ZATCA e-invoicing integration is configured
or claimed.** The architecture keeps that route open — invoices are standard
ERPNext Sales Invoices — but nothing about phase-2 e-invoicing has been built or
tested.

## 12. Layout of the app

```
automotive_workshop/
├── workshop/            business logic
│   ├── constants.py     statuses, stages, roles
│   ├── lifecycle.py     state machine, guards, stage computation
│   ├── menus.py         Create and Actions menus, next action
│   ├── mappers.py       prefilled document creation
│   ├── actions.py       whitelisted workflow actions
│   ├── parts.py         parts position from the ledgers
│   ├── context.py       one call that feeds the Job Card screen
│   ├── permissions.py   row-level visibility
│   ├── pricing.py       price-list lookup
│   ├── settings.py      Workshop Settings access
│   └── history.py       service history
├── events/              hooks on standard DocTypes
├── setup/               install: roles, fields, permissions, VAT, dashboard
├── automotive_workshop/  DocTypes, reports, workspace, chart source
├── public/js/job_card/  tracker and panels (client)
├── public/scss/         tracker styling, theme-aware
├── locale/ar.po         Arabic translations
├── tests/               55 integration tests
└── demo.py              demo workshop, and its removal
```

## 13. What is not implemented

Stated plainly so that no reader mistakes an intention for a delivered feature.
The same list, with more detail, is in the README.

| Not implemented | Consequence for the client |
| --- | --- |
| Data migration | Customers, vehicles, suppliers, parts and historical jobs must still be imported with ERPNext's standard Data Import tool. No templates, transformation scripts or reconciliation step were built or tested. |
| Custom print formats | Quotations and invoices print with ERPNext's standard layouts, not a workshop-branded one. |
| ZATCA e-invoicing | Not integrated. 15% VAT is configured and tested through standard tax templates; no Saudi e-invoicing compliance is built or claimed. |
| Technician customer-satisfaction rating | No rating is captured anywhere, so no performance figure is derived from one. |
| Quotation rejection / inspection-fee closure | A rejected quotation can be revised, but a job cannot yet be closed with the vehicle handed back unrepaired. The client must decide whether an inspection fee applies and how such a visit is closed. |

Phase-2 items from the proposal — WhatsApp integration, mobile app, customer
portal, VIN decoder and advanced analytics — are out of scope for this build.
