# DATA MODEL — Breathe ESG Ingestion Platform

## Design Goals

The model must satisfy five requirements simultaneously:
1. **Multi-tenancy** — rows from different clients never touch
2. **Scope 1/2/3 categorisation** — explicit on every record, not inferred at query time
3. **Source-of-truth tracking** — every row knows its origin: which file, which batch, which row
4. **Unit normalisation** — raw values preserved, normalised values computed once at ingest
5. **Audit trail** — immutable append-only log; approved rows cannot be silently mutated

---

## Entity Overview

```
Organization
  └── User (ForeignKey)
  └── IngestionBatch (ForeignKey)
      └── IngestionError (ForeignKey)
      └── EmissionsRecord (ForeignKey)
          └── AuditLog (ForeignKey)
          └── EmissionFactor (ForeignKey, nullable)
          └── FacilityLookup (ForeignKey, nullable)
```

---

## Core Tables

### `Organization`
The tenancy root. Every data-bearing table has a FK to Organization. Row-level security is enforced in every queryset via `filter(organization=request.user.organization)`.

```python
id: UUID (PK)
name: str
slug: str (unique)
created_at: datetime
```

### `User` (extends AbstractUser)
```python
organization: FK → Organization
role: enum('analyst', 'admin')
```

Analysts review records; admins can upload and manage reference data. Both are scoped to one org. No cross-org access.

### `IngestionBatch`
One batch = one upload event. Immutable after creation. If the same file is uploaded twice, two batches are created — we do not deduplicate silently.

```python
id: UUID (PK)
organization: FK
source_type: enum('sap', 'utility', 'travel')
status: enum('processing', 'complete', 'failed')
original_filename: str
uploaded_by: FK → User (nullable, SET_NULL)
uploaded_at: datetime (auto)
row_count: int
error_count: int
notes: text  # error details if status=failed
```

**Why UUID PK:** batches are referenced from records; UUIDs are safe to expose in audit exports and API responses without revealing sequence information.

### `IngestionError`
Per-row parse failures. Stored separately so a batch with 2 parse errors and 48 good rows still produces 48 records, not 0.

```python
batch: FK
row_number: int (nullable — some errors are file-level)
field_name: str
raw_value: text
error_message: text
```

### `EmissionsRecord`
The canonical normalised row. This is the most important table.

#### Identity and versioning
```python
id: UUID (PK)
organization: FK
version: int (default 1)
superseded_by: UUID (nullable) # → newer version's id
is_deleted: bool (default False)
```

**Immutability contract:** Records are never updated in place once approved. If an analyst edits a row, a new record is created with `version = old.version + 1`, and the old row gets `superseded_by = new.id`. Queries for "current" records filter `superseded_by IS NULL AND is_deleted = FALSE`. This gives us a full edit history without a separate history table.

This is a deliberate tradeoff against a separate `EmissionsRecordHistory` table — simpler schema, adequate for current scale.

#### Source tracking
```python
batch: FK → IngestionBatch
source_type: str  # denormalised from batch for query speed
source_row_id: str  # SAP doc number, travel booking ref, meter+period
```

`source_row_id` is a string because each source has a different natural key. For SAP it's the Belegnummer (document number). For utility it's `{meter_serial}_{billing_period_start}`. For travel it's the Trip ID from Concur.

#### Scope and category
```python
scope: int  # 1, 2, or 3 — assigned at parse time, explicit
category: enum('fuel', 'procurement', 'electricity', 'flight', 'hotel', 'ground_transport')
```

Scope is assigned at parse time, not computed at query time. SAP fuel rows → Scope 1. Electricity → Scope 2. Travel → Scope 3. This is opinionated but right for the current client; a future version would support per-org scope mapping rules.

#### Temporal
```python
activity_date: date  # normalised to the day the activity occurred
billing_period_start: date (nullable)  # for utility bills
billing_period_end: date (nullable)
```

Utility bills present a date alignment problem: a billing period of 22 Jan – 20 Feb doesn't align to calendar months. We store both `activity_date` (the read/invoice date, used for reporting period assignment) and the billing period for accurate pro-rating if needed.

#### Raw values (preserved verbatim)
```python
raw_quantity: str
raw_unit: str
raw_description: text
```

These columns are immutable after creation. They preserve exactly what came in from the source, before any normalisation. If our unit conversion is wrong, we can re-derive from raw.

#### Normalised quantities
```python
quantity_kwh: decimal (nullable)   # electricity
quantity_litres: decimal (nullable) # fuel
quantity_km: decimal (nullable)    # travel distance
quantity_nights: int (nullable)    # hotel
```

We use separate columns per physical dimension rather than a single `(normalised_value, normalised_unit)` pair. This prevents a class of bugs where downstream queries need to know the unit before they can use the number. Query for all electricity consumption: `SUM(quantity_kwh)`. No secondary lookup required.

The tradeoff: four nullable columns instead of two. Worth it for query clarity.

#### Emissions
```python
co2e_kg: decimal (nullable)
emission_factor: FK → EmissionFactor (nullable)
calculation_method: str  # e.g. 'fuel_factor:diesel:2.6869kgCO2e/L'
```

`calculation_method` is a free-text audit string. It stores enough information to reconstruct the calculation without joining to EmissionFactor (which could be updated). The FK is still stored for reference.

#### Location
```python
facility: FK → FacilityLookup (nullable)
country_code: str (ISO 3166-1 alpha-3)
city: str
```

#### Flexible metadata
```python
extra: JSON (default {})
```

Source-specific fields that don't belong in normalised columns: SAP cost centre, Concur employee ID, airport codes, vendor name, tariff code. Using JSON here is a deliberate choice — these fields are needed for analyst review but not queried for aggregation. Putting them in `extra` keeps the main table clean without creating a wide table with 30 nullable columns.

#### Review workflow
```python
review_status: enum('pending', 'approved', 'flagged', 'rejected')
reviewed_by: FK → User (nullable)
reviewed_at: datetime (nullable)
review_notes: text
```

State machine: `pending → approved | flagged | rejected`. Flagged rows can be re-reviewed. Approved rows require an admin action to re-open (not yet implemented — noted in TRADEOFFS.md).

#### Quality flags
```python
is_flagged_suspicious: bool (default False)
flag_reasons: JSON list
```

Set automatically at ingest time. Examples: `distance_unknown_airport_not_in_lookup`, `estimated_read` (utility), `unusually_high_co2e`. The analyst sees these before making a review decision.

### `AuditLog`
Append-only. Never update or delete rows here.

```python
id: UUID (PK)
record: FK → EmissionsRecord
action: enum('approve', 'flag', 'reject', 'edit', 'note')
performed_by: FK → User (nullable)
performed_at: datetime (auto)
before_state: JSON  # snapshot of relevant fields
after_state: JSON
notes: text
```

Stores snapshots rather than diffs. Snapshot approach is more readable for auditors who need to verify "what did this record look like when it was approved" without replaying a diff chain.

### `EmissionFactor`
```python
activity_type: str  # 'diesel', 'electricity_uk', 'flight_economy'
scope: int
factor_kg_co2e_per_unit: decimal
unit: str  # 'litre', 'kWh', 'pax_km', 'night'
source: str  # 'DEFRA 2023'
valid_from: date
valid_to: date (nullable)
```

Factors are versioned by date range. When an IPCC or DEFRA update arrives, we add a new row with a new `valid_from` rather than updating the existing one. Existing records' `emission_factor` FK still points to the factor used at ingest time.

### `FacilityLookup`
```python
organization: FK
sap_plant_code: str  # e.g. 'P001'
site_name: str
country_code: str
region: str
```

Maps SAP plant codes (opaque to humans) to real-world sites. Per-org because plant codes are not globally unique across SAP instances. Uploaded by the client's SAP admin at onboarding.

---

## Indexes

```python
# On EmissionsRecord:
Index(fields=['organization', 'scope', 'activity_date'])  # scope reporting
Index(fields=['organization', 'review_status'])           # review queue
Index(fields=['batch'])                                   # batch drilldown
Index(fields=['superseded_by'])                           # version chain lookup
```

The `(organization, scope, activity_date)` composite index is the most important — it covers the primary reporting query: "give me all Scope 2 emissions for org X in Q1."

---

## Multi-tenancy enforcement

All querysets filter by `organization=request.user.organization`. This is applied in `get_queryset()` on every ViewSet and is not overridable by query params. There is no superuser endpoint that bypasses this — intentional: even Breathe ESG staff should not be able to read client data without explicit scoped access.

---

## What this model does not handle (yet)

- **Subsidiary / multi-org hierarchy** — `Organization` is flat; no parent-child
- **Reporting periods as a first-class object** — FY/CY boundary logic is in the frontend filter, not the model
- **Supply chain (Scope 3 Category 1)** — spend-based or supplier-reported emissions not yet modelled
- **Unit recalculation on factor update** — changing an EmissionFactor does not re-compute existing records; would require a batch job
