# TRADEOFFS.md — Three Things We Deliberately Did Not Build

---

## 1. Asynchronous Processing

**What we built instead:** Synchronous file processing in the HTTP request cycle.

**The tradeoff:** The `/api/upload/` view calls `process_upload()` inline and returns after all rows are created. For the sample files (10-50 rows), this takes milliseconds. For a real enterprise client — a quarterly SAP extract with 50,000 purchase orders, or a year's worth of Concur records — this will hit HTTP timeout (30-60s on most proxies) and fail silently.

**The right solution:** Celery + Redis task queue. The upload endpoint creates the batch, queues a task, and returns immediately with `{"batch_id": "...", "status": "processing"}`. The frontend polls `/api/batches/{id}/` until `status = complete`. We'd also add progress reporting (rows processed / rows total) to the batch model.

**Why we didn't build it:** Adds a Redis dependency and a Celery worker process, which complicates deployment for a 4-day prototype. The tradeoff is explicit: this app is not production-ready for large files. A note in the Upload UI acknowledges the file size limitation.

---

## 2. Spend-Based Scope 3 Procurement Emissions

**What we built instead:** Procurement rows from SAP are ingested and stored but `co2e_kg` is left null.

**The tradeoff:** The assignment says "fuel and procurement data from SAP." We handle fuel correctly (Scope 1, litre-based emission factor). For procurement — office supplies, raw materials, chemicals — the correct approach is spend-based calculation using Environmentally Extended Input-Output (EEIO) tables, mapped from UN ISIC or NAICS industry codes to kgCO2e per £ spent. This is Scope 3 Category 1 (Purchased Goods and Services) per the GHG Protocol.

**Why we didn't build it:**
- EEIO tables require a substantial reference dataset (the EPA USEEIO or EXIOBASE models are gigabytes of input-output matrices)
- Mapping SAP material groups to ISIC codes requires either a lookup table maintained by the client or a machine learning classifier — neither is a one-sprint task
- Without it, the ingested procurement rows still have value: they document what was purchased, from whom, at what cost — the data needed for a future spend-based calculation

**What the app does instead:** Procurement rows are flagged with `flag_reasons: ['no_co2e_factor_for_procurement']` and show `—` in the CO2e column. Analysts can see them, review them, and approve them for completeness of the source data record even without a CO2e figure.

---

## 3. Record-Level Locking and Concurrent Review Protection

**What we built instead:** Last-write-wins with no optimistic concurrency control.

**The tradeoff:** If two analysts open the same record simultaneously, the second `POST /api/records/{id}/review/` overwrites the first. For a team of 2-5 analysts on a single client's quarter of data, this is unlikely but not impossible. It also means that once a record is approved, any analyst can still flag or reject it — there is no "locked for audit" state that requires admin override.

**The right solution:** Optimistic locking with a `version` or `etag` field on EmissionsRecord. The review endpoint would accept the current version, reject the request if it doesn't match (HTTP 409 Conflict), and force the analyst to reload. Separately, `approved` records should transition to a `locked` state that requires admin permission to re-open.

**Why we didn't build it:**
- The assignment specifies a 4-day timeline and a prototype, not a production system
- Implementing optimistic locking adds client-side version tracking in the frontend and error handling for the 409 case
- The immutable audit log (AuditLog table) mitigates the risk: even if a record is accidentally overwritten, the full history of who did what is preserved and visible to auditors

The TRADEOFF is documented, the mitigation (audit log) is in place, and the fix path is clear.

---

## Honourable mentions (didn't fit the "three" constraint)

- **Bulk review actions** (approve all pending from batch X) — useful UX feature, not implemented
- **CSV/Excel export of approved records** — auditors will want this; not implemented
- **Email notifications on flagged records** — not implemented; no email service configured
- **Multi-factor authentication** — JWT without 2FA; fine for a prototype, not for prod
