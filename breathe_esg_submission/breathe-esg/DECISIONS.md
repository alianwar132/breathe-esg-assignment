# DECISIONS.md — Every Ambiguity Resolved

## SAP: Format Choice

**Chose:** SAP ALV Grid Export (tab-separated .txt/.csv flat file)

**Rejected alternatives:**
- **IDoc (flat file):** The segment-based format (EDI_DC40, E2...) requires SAP BASIS configuration. Most sustainability teams don't have an EDI port set up and asking them to create one adds weeks. IDocs are right for system-to-system integration; wrong for "our SAP admin just needs to give us a file."
- **OData service:** Requires SAP Gateway to be configured and the right ODATA service activated. Common on S/4HANA, rare on ECC 6.x which many industrial clients still run. Also requires us to implement OAuth or SAML.
- **BAPI:** Requires ABAP development on the client side. Out of scope.

**What ALV export gives us:** It's the "Export to Spreadsheet" button in any SAP transaction (MB51, ME2M, etc.). Every SAP user knows it. No BASIS involvement. The output is a tab-separated file with headers that vary by language and configuration — hence our `HEADER_ALIASES` mapping table.

**What we handle:** EKPO/MSEG-style fuel and goods receipt rows. Material group `FUEL` and variants (`PETRL`, `DIESEL`, `LNG`, etc.) are Scope 1. Other material groups are flagged as procurement but not assigned CO2e (no spend-based factor implemented — see TRADEOFFS.md).

**What we explicitly ignore:** FI posting documents (BKPF/BSEG), production orders, asset accounting, HR data.

**Why this scope:** The PM said "fuel and procurement data." Fuel is straightforward. Full Scope 3 Category 1 procurement emissions require a spend-based calculation with supplier-specific emission intensities — that's a separate product feature, not a one-sprint ingestion task.

---

## Utility: Format Choice

**Chose:** Portal CSV export

**Rejected alternatives:**
- **PDF bill:** Requires OCR or a paid PDF extraction API. Layout varies per utility. Brittle. The facilities team already exports CSVs from portal — why add a step?
- **Green Button / Utility API:** Green Button (XML-based ESPI standard) is US-specific and mainly residential. Most UK/EU commercial utility portals don't support it. The Utility API (Bayou Energy, Urjanet) would require us to integrate a third-party data aggregator — appropriate for production but out of scope for a prototype.

**What we handle:** Portal CSV with fields: Account Reference, Meter Serial Number, Read Date, Period Start, Period End, Read Type (Actual/Estimated), Consumption (kWh), Cost, Tariff, Site.

**Real-world complexity acknowledged:**
- `Read Type = Estimated` is flagged as suspicious — estimated reads should be validated against subsequent actual reads
- Billing periods don't align to calendar months. We store `billing_period_start` and `billing_period_end` separately from `activity_date`. Pro-rating across reporting periods is not yet implemented (see TRADEOFFS.md).
- Unit conversion: kWh is canonical. We handle MWh → kWh and GWh → kWh conversion.
- Multi-meter facilities: each meter row is a separate EmissionsRecord. Aggregation by site happens at query time.

**What we ignore:** Demand (kW peak), time-of-use tariff breakdown, power factor, gas co-consumption on the same bill.

---

## Travel: Format Choice

**Chose:** Concur Travel CSV export (flat, not API)

**Rejected alternatives:**
- **Navan API:** Well-documented, modern. But Navan is newer and this client is described as "enterprise" — more likely Concur. Even if Navan, their API requires OAuth setup that IT teams often haven't done for sustainability reporting.
- **SAP Concur REST API:** The `/api/v4/` endpoints exist and are well-documented at developer.concur.com. Requires an OAuth 2.0 client credential registered by the client's Concur admin. The "Download" button exists everywhere and requires no IT setup.

**What we handle:**
- **Flights:** Economy/Business/First/Premium class. Distance computed via Haversine on IATA airport coordinates when not provided by platform (which is common — Concur doesn't always include great circle distance). We apply 9% uplift over great circle distance per DEFRA guidance for actual flight paths.
- **Hotels:** Per-night factor (DEFRA 2023: 31 kgCO2e/night). Nights are provided in the source or defaulted to 1 if missing.
- **Ground transport:** Per-km factor using average car emission factor. Uber Business, taxi, rental car all treated the same (distinguishing would require vehicle type data not present in Concur exports).
- **Rail:** Per-km factor (UK national rail average: 0.037 kgCO2e/km).

**Distance resolution for flights:**
Priority order: (1) provided in file, (2) computed via IATA coordinate lookup + Haversine, (3) flagged as `distance_unknown_airport_not_in_lookup`. Our IATA table covers 35 major hubs; a production deployment would use the full OurAirports.com dataset (~9,000 airports).

---

## Ingestion Mechanism: File Upload

**Chose:** File upload (multipart POST)

**Rejected:** Direct API pull from SAP/utility portal/Concur

**Reasoning:** Direct API pull is correct for an automated pipeline in production. But it requires:
- SAP: OData service setup, credentials
- Utility portal: Account credentials or portal API (Green Button, where available)
- Concur: OAuth client registration

All three require IT involvement at the client. A file upload requires zero IT involvement — the sustainability lead exports from their existing tools and uploads. This matches the "new enterprise client onboarding" context where none of the above integrations exist yet.

The upload endpoint (`POST /api/upload/`) accepts the file and processes it synchronously. In production, processing would be async (Celery task) to handle large files without HTTP timeout. See TRADEOFFS.md.

---

## Emission Factors

**Chose:** DEFRA 2023 GHG Conversion Factors

**Why DEFRA:** The sample client is UK-based (plant codes P001 Birmingham, P002 Manchester, P003 Glasgow). DEFRA factors are the UK regulatory standard. For a non-UK client we'd substitute EPA (US), GHG Protocol factors, or an IEA grid factor by country.

**Grid electricity factor:** UK 2023 grid average = 0.2078 kgCO2e/kWh. We apply a single market-based factor. A location-based factor (by grid region) or a specific supplier factor (renewable certificate) would require additional configuration not yet supported.

**Procurement emissions:** We do not calculate CO2e for non-fuel procurement rows (e.g. office supplies). Spend-based Scope 3 Category 1 calculations require EEIO tables or supplier disclosure data — out of scope. These rows are ingested with `co2e_kg = null` and flagged.

---

## Review Workflow

**State machine:** `pending → approved | flagged | rejected`

**Chose:** Optimistic locking, no concurrent edit protection. If two analysts review the same record simultaneously, the last write wins. For a team of 2-5 analysts on a single client's data this is acceptable. See TRADEOFFS.md.

**Chose:** Approved records can be re-reviewed (an analyst can flag an approved record). An admin override to lock records for audit was not implemented — noted in TRADEOFFS.md.

---

## Questions I Would Ask the PM

1. **What's the target reporting period?** FY or CY? UK vs calendar year? This affects how we assign activity dates to reporting periods for bills that straddle period boundaries.
2. **Is there a FacilityLookup already or do we build it?** We need plant code → site name mapping before we can process SAP data for a new client. Is that an onboarding step we own or does the client provide it?
3. **What's the analyst team size?** If >10 analysts on one dataset, we need locking on records in review to prevent double-review.
4. **Do they have Scope 3 Category 1 ambitions?** If yes, we need a spend-based calculation pathway — the current model stores procurement rows but doesn't calculate emissions for them.
5. **Which auditing standard?** GHG Protocol Corporate Standard, ISO 14064, or a specific regulatory framework (TCFD, CSRD)? This affects which fields are mandatory on export.
6. **Electricity market-based vs location-based?** If they have renewable energy contracts (RECs/GOs), the market-based Scope 2 would be near zero. Do they want to track both methods?
