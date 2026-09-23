# User guide

Everything happens on the **Workshop Job Card**. Open one and you see, at the
top: where the vehicle is, what it is waiting for, who is responsible, and the
next thing to do. The two menus at the top right — **Create** and **Actions** —
only ever offer what is valid right now.

---

## Reception: booking a vehicle in

1. **Workshop → Workshop Job Card → Add Workshop Job Card**.
2. Pick the **Vehicle**. Search by plate. If the vehicle is new, create it from
   the same field (and its owner from the Customer field inside it) — nothing is
   typed twice afterwards: customer, registration and VIN all follow the vehicle.
3. Record **mileage**, the **customer complaint**, the **service type** and,
   if known, the **expected delivery** date. Photos can be attached.
4. Save. The Job Card gets its number (`JC-2026-00001`) and the workflow starts
   at Reception.

The vehicle is marked *In Workshop*, and it cannot be booked in twice at once.

## Workshop Manager: getting the job moving

- **Actions → Start Inspection** — choose the trade and the technician. The
  inspection opens prefilled with that trade's checklist.
- Once the inspections are submitted, the job moves to *Inspection Completed*
  on its own.
- **Actions → Create Damage Assessment** — damage items and labour hours are
  carried over from the inspections. Add the required parts (real stock items)
  and check the labour lines, then submit.
- **Actions → Prepare Quotation** — parts and labour become quotation lines, VAT
  is applied from the template. Submit it, and the job moves to
  *Awaiting Approval*.

## Technicians (Denter, Mechanic, Electrician)

You see the vehicles currently in the workshop, and your own inspections and
repair tasks.

- **Inspection:** fill the checklist — mark each point OK, Attention or Faulty,
  add remarks and photos, record your estimated labour hours, then submit. Your
  faulty rows become the damage items on the assessment.
- **Repair:** your tasks are assigned to you and appear in your to-dos. Work is
  recorded from the Job Card: **Actions → Update Repair Progress** — set status,
  progress and the hours you worked. A task cannot be completed without hours.
- You cannot start work before the manager has started the repair (which needs
  the customer's approval and the parts).

## Reception / Manager: the customer's decision

- **Actions → Send Quotation** — email it to the customer (the quotation print is
  attached), or record that it was handed over in person. Only then does the
  workflow ask for a decision.
- **Actions → Record Customer Approval** — Approved, Rejected or Revision
  Requested, with the customer's remarks.
  - *Approved* moves the job to *Parts Pending* and allows repair to start.
  - *Rejected* / *Revision Requested* keeps the job where it is and offers
    **Actions → Revise Quotation**, which cancels the old quotation so a revised
    one can be prepared.

## Store Keeper: parts

The **Parts** tab shows every required part and where it stands — required,
issued, in stock, requested, ordered, received.

- **Actions → Issue Parts to Job** — a Material Issue, prefilled with what is in
  stock, from the workshop warehouse. You cannot issue more than the assessment
  requires.
- **Actions → Request Parts** — a Material Request for exactly what is short. It
  carries the Job Card reference, and so do the Purchase Order and Purchase
  Receipt that follow, so every part stays traceable to its job.

## Purchase: buying parts in

Work from the Material Request as usual: Supplier Quotation or RFQ if needed,
then Purchase Order, then Purchase Receipt. The Job Card reference travels with
each line, and the Job Card's Parts tab updates as the parts are ordered and
received. **Job Card Parts** report lists everything outstanding across the shop.

## Manager: repair

- **Actions → Assign Repair Task** — trade, technician, the work and the
  estimated hours. A technician can only be given work of their own trade.
- **Actions → Start Repair** — only offered once the quotation is approved, all
  parts are issued and at least one task is assigned. If something is missing,
  the panel at the top says exactly what.
- When every task is complete, **Actions → Request Quality Check** moves the job
  to QC and notifies the quality inspectors.

## Quality Inspector

- **Actions → Pass Quality Check** or **Reject Quality Check** opens a final
  inspection, prefilled with one line per repair task plus the standard QC
  checklist.
- A pass moves the job to *Completed*. A fail sends it back to repair, reopens
  the repair tasks with your remarks attached, and counts the rework.
- QC cannot be passed while any checklist item is still marked Faulty.

## Accounts: invoice and payment

- **Actions → Generate Sales Invoice** — built from the approved quotation, with
  VAT. An invoice cannot be submitted for a job that has not passed QC.
- **Actions → Record Payment** — ERPNext's payment entry against that invoice.
  The Job Card shows the outstanding balance until it is settled.

## Reception: delivering the vehicle

**Actions → Release Vehicle** — available once QC has passed, the invoice is
submitted and the balance is paid. Record the delivery notes and release. The
Job Card closes, the vehicle returns to *Active*, and the visit becomes part of
its service history.

If the workshop allows credit, a Workshop Manager can release an unpaid vehicle
with a recorded reason — turn off *Require Full Payment Before Release* in
Workshop Settings first.

## Service history

Open any **Vehicle Master** to see every visit: date, service type, complaint,
status and what was invoiced, with a link to each Job Card. The same history
appears on the Job Card's History tab, so a returning customer's record is
visible while the current job is being worked on.

## Dashboard and reports

**Automotive Workshop** workspace: vehicles received, active jobs, work in progress,
approvals pending, parts pending, awaiting QC, ready for delivery, revenue this
month and outstanding payments, plus charts for jobs by status, QC results,
monthly revenue, revenue by service type and labour hours by technician.

Reports: Workshop Job Card Register, Job Card Parts, Workshop Revenue,
Technician Performance, Customer Vehicle Report, and ERPNext's own Accounts
Receivable, Stock Balance, Profit and Loss Statement and Balance Sheet.

## Arabic

The workshop's own labels and messages are translated. Switch language per user
in **My Settings → Language**, or for the site in **System Settings**.

## What the system does not do

Quotations and invoices print in ERPNext's standard format; there is no
workshop-branded print format, and no ZATCA e-invoicing. The system records no
customer satisfaction rating. Historical data must be imported with ERPNext's
standard Data Import tool — no migration tooling ships with the app. And if a
customer rejects a quotation outright, the job can be revised or left open, but
there is not yet a way to close it and hand the car back unrepaired: that needs
a decision on whether an inspection fee is charged.
