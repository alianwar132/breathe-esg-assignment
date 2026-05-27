# SOURCES.md — Research Notes on Each Data Source

---

## Source 1: SAP Fuel & Procurement

### What real-world format I researched

SAP exposes data through multiple paths: IDoc (EDI flat files for system-to-system), OData (REST API via SAP Gateway), BAPI (function modules called via RFC), and ALV Grid Export (the "Export to spreadsheet" button available in any SAP list transaction). I researched all four via the SAP Community forums, SAP Help documentation, and SAP developer blogs.

**IDoc format:** Segment-based fixed-width structure. Each segment starts with a record type code (e.g. `E2EDKT1001`). Fields are positional. Headers are in the control record (EDI_DC40). Used for EDI between companies or between SAP systems. Requires an EDI port configured in SAP (transaction WE20) — uncommon for sustainability reporting extraction.

**OData:** Available on SAP S/4HANA via SAP Gateway. Transaction `/IWFND/MAINT_SERVICE`. Standard services like `API_PURCHASEORDER_PROCESS_SRV` expose EKKO/EKPO (purchase header/item) in JSON or XML. Not available by default on SAP ECC 6.x, which many industrial enterprises still run.

**ALV Grid Export:** The most universal. Any SAP list (MB51, ME2M, ME80FN, etc.) can be exported via the "Local File" button → "Spreadsheet" or "Tab-separated". The output is a tab-delimited file with one header row. Column names depend on the user's SAP language setting and the specific transaction — hence German column names like "Belegdatum" (Document Date) and "Mengeneinheit" (Unit of Measure) appearing in files from German-configured systems.

### What I learned

The key tables for fuel and procurement data are:
- **EKKO/EKPO** — Purchase Order header and item (MENGE, MEINS, MATNR, MATKL, WERKS, NETPR)
- **MSEG/MKPF** — Material document / goods receipt (movement type BWART 101 = goods receipt)
- **MB51 transaction** — Material document list, commonly used by sustainability teams to extract material movements

SAP uses internal unit codes that are not ISO: `L` (litre), `LT` (alternate litre), `GL` / `GAL` (US gallon), `M3` (cubic metre), `KG`, `TO` (metric tonne), `PC` (piece/unit). These are distinct from the printed text on documents.

Plant codes (WERKS) are 4-character codes (`P001`, `DE01`, etc.) that are meaningful only with a lookup table. Without `FacilityLookup`, "P001" is opaque.

### What my sample data looks like and why

```
Belegdatum\tWerk\tMaterial\tMaterialgruppe\tMenge\tMengeneinheit\tBezeichnung\tBelegnummer\tBelegart\tKostenstelle\tLieferant
15.01.2024\tP001\tDIESEL001\tFUEL\t5000\tL\tDiesel EN590\t4500001234\tWE\tCC001\tBP Fuels Ltd
```

- **German column headers** — simulates a German-language SAP system (common for UK subsidiaries of German parent companies)
- **Date format DD.MM.YYYY** — SAP default for European locales
- **Document type WE (Wareneingang / Goods Receipt)** — this is how fuel is recorded: a goods receipt against a purchase order
- **Material group FUEL** — our classification trigger; real systems use numeric codes like `0001` which require a material group description lookup
- **Belegnummer 45000012xx** — purchase document numbers in SAP start with 45 for standard purchase orders
- **Mixed material types** — includes DIESEL001 (fuel) and OFFICE001 (office supplies, procurement category) to show both code paths
- **One intentionally bad row** — `invalid_date` and `XXX` quantity to test error handling and IngestionError creation

### What would break in a real deployment

1. **Material group codes** — real SAP exports use numeric material groups (`0001`, `0002`) not descriptive strings (`FUEL`). We'd need a client-provided material group → category mapping table.
2. **Plant codes without FacilityLookup** — if the client hasn't provided their plant code mapping, we can't assign facility to records. Currently we fail gracefully (facility FK stays null).
3. **Currency and price fields** — we store the Net Price (NETPR) in `extra` but don't use it. For spend-based Scope 3 calculations we'd need to normalise to a base currency with exchange rate lookup.
4. **Volume vs. weight** — diesel is typically measured in litres; LNG in cubic metres or kg; coal in tonnes. Our unit map covers these but a new fuel type in an unexpected unit would go through the catch-all path and be flagged.
5. **IDoc if client uses EDI** — if the client's SAP admin refuses to do an ALV export and insists on IDoc output, we'd need a separate IDoc parser. The segment structure is completely different from the flat file.

---

## Source 2: Utility / Electricity

### What real-world format I researched

Utility portals for UK commercial accounts (EDF, British Gas Business, Octopus Energy for Business, E.ON Next) all offer a "Download usage data" or "Export billing history" function. The output varies:

- **EDF Commercial:** Account number, meter serial, period start, period end, consumption (kWh), cost (£), read type (actual/estimated/change-of-tenancy)
- **British Gas Business portal:** Similar columns, adds tariff name and standing charge separately
- **EnergyCAP format** (widely used in US): `account_number, meter_code, commodity, unit, bill_start, bill_end, use, demand, cost` — a well-documented flat format

**Green Button Data (US ESPI standard):** XML-based, well-structured, but US-specific and mainly residential/small business. Not standard for UK commercial accounts.

**Interval data (smart meter 30-min reads):** Available via Green Button Download or utility APIs for meters with AMI (Advanced Metering Infrastructure). More granular than monthly bills but the same underlying data.

The key insight from research: UK commercial utility portals output CSVs that vary in column names but are consistently structured around: account/meter identifier, billing period, total consumption, read type.

### What I learned

Real complexity points:
- **Estimated reads:** Meter not read this period; the utility estimated based on historical consumption. Must be flagged — actual reading in next period will settle it.
- **Billing period ≠ calendar month:** Commercial meters are read on fixed schedules (e.g., every 28 days, or quarterly). A bill for 22 Jan – 20 Feb is 29 days. If we're reporting Q1 (Jan-Mar), we need to decide whether this bill goes to January or February, or is pro-rated.
- **Multi-meter sites:** A large facility may have multiple meters (sub-metering). Each meter gets its own row in the export and its own EmissionsRecord.
- **Zero consumption:** A meter reporting 0 kWh is suspicious — possibly a vacant property, possibly a missing read. We flag it.
- **MWh vs kWh:** Large industrial meters are sometimes reported in MWh. We normalise to kWh.
- **Market-based vs location-based:** Emission factor depends on whether the client has renewable energy contracts. We use the UK grid average (0.2078 kgCO2e/kWh, DEFRA 2023) — location-based. Market-based would require knowing their supplier mix.

### What my sample data looks like and why

```
Account Reference,Meter Serial Number,Read Date,Period Start,Period End,Read Type,Consumption (kWh),Cost (GBP),Tariff,Site
ACC-001,MSN-BHM-01,31/01/2024,01/01/2024,31/01/2024,Actual,45230,4752.15,Business Standard,Birmingham Plant
```

- **Three sites, two meters for Birmingham** — MSN-BHM-01 and MSN-BHM-02 (Birmingham Annex) to demonstrate multi-meter handling
- **Mix of Actual and Estimated reads** — March Birmingham row is Estimated, which triggers `estimated_read` flag
- **Zero consumption row** — Birmingham Annex MSN-BHM-02 reads 0 kWh, triggering `zero_or_missing_co2e` flag
- **UK date format DD/MM/YYYY** — different from SAP to test that both parsers handle their native formats
- **Real-scale kWh figures** — 45,230 kWh/month for a manufacturing plant is realistic (mid-size industrial building)

### What would break in a real deployment

1. **Billing period pro-ration** — we don't split bills across reporting periods. A bill for Jan 22 – Feb 20 is assigned to `activity_date = 2024-01-31` (read date). If the client's reporting year is Jan-Dec, this is fine. If it's Apr-Mar, bills straddling year-end need splitting.
2. **Multiple utilities / different formats** — a multi-site client may have different utilities for different sites, each with a different CSV format. Our parser handles one format; additional format variants would require extending `HEADER_ALIASES`.
3. **Gas and water on the same bill** — some utility portals export multi-commodity bills. We only handle electricity. Gas would need a separate commodity column and a different emission factor.
4. **Half-hourly data** — if the client has smart meters and exports 48 readings/day, our billing period model doesn't apply. Would need a time-series model.
5. **Negative consumption** — solar export to grid can produce negative rows. Not handled.

---

## Source 3: Corporate Travel

### What real-world format I researched

**SAP Concur:** The dominant enterprise T&E platform. The Concur developer portal (developer.concur.com) documents REST APIs including `/api/v4/travelallowance/`, `/api/v4/expense/reports/`, and trip-related endpoints. The flat export (available via Reports → Download) produces a CSV with columns including: Report Name, Trip ID, Employee Name, Departure City, Arrival City, Departure Date, Transport Mode, Class of Service, Amount, Currency.

**Navan (formerly TripActions):** API-first platform. Documented booking API and expense API at developer.navan.com. Better structured than Concur but less common in established enterprises.

**What both have in common:** Expense reports aggregate all travel categories (Air, Hotel, Car, Rail) into one file. Not all trips include distance — platforms typically store cost and booking details, not calculated distance, which is why we need to derive it from airport codes.

Research source: SAP Concur Developer Center (developer.concur.com/api-reference), Navan integration documentation, and Concur's standard report field definitions.

### What I learned

Key findings:
- **Distance is often absent:** Concur records what was booked and at what cost, not the great-circle distance. Distance must be computed from origin/destination for flight emissions.
- **IATA codes are the standard origin/destination format for flights.** But hotel and car records use city names or addresses, not codes.
- **Class of service matters significantly:** Business class emits ~2.8x economy per km (DEFRA 2023). This data is present in Concur but not always in exports — depends on which report template the client uses.
- **Currency conversion:** Enterprise clients travel internationally; expenses are in multiple currencies. We store raw amount + currency in `extra` but do not normalise to a base currency (no FX rate data source wired up).
- **Hotel emission factors are property-independent:** Without hotel-specific energy data (some chains publish this, e.g. Marriott's Environmental and Social Responsibility Report), we use a per-night average. DEFRA 2023 gives 31 kgCO2e/night for UK hotels. International hotels would need country-specific factors.

### What my sample data looks like and why

```
Trip ID,Employee ID,Travel Date,Origin,Destination,Travel Type,Class of Service,Distance (km),Nights,Amount,Currency,Vendor,Cost Centre
TRP-2024-001,EMP001,15/01/2024,LHR,JFK,Air,Economy,,0,1250.00,GBP,British Airways,SALES
```

- **Mixed flight classes** — Economy (EMP001 SALES trips) and Business (EMP002 EXEC trips) to exercise both emission factors
- **Distance field empty for flights** — intentional. Most Concur exports don't include distance. Our parser falls back to IATA coordinate lookup + Haversine.
- **Hotels as separate rows** — `TRP-2024-003` is the hotel stay for EMP001's JFK trip. Concur separates flights and accommodation, so multi-segment trips produce multiple rows.
- **Unknown airport code** — `TRP-2024-010` uses `ZZZ` (not a real IATA code) to trigger the `distance_unknown_airport_not_in_lookup` flag
- **Multi-currency** — USD for NYC hotel, SGD for Singapore hotel, GBP for UK-booked trips
- **Ground transport** — `TRP-2024-008` (Uber Business BHX→LHR) to test the ground transport category with a provided distance

### What would break in a real deployment

1. **IATA code coverage:** Our lookup table has 35 airports. A production deployment would use the full OurAirports.com dataset (~9,000 airports with coordinates). Any airport not in the table produces a `distance_unknown` flag and no CO2e.
2. **Hotel vs city name matching:** Hotel expenses in Concur list property names ("Marriott NYC"), not city codes. We don't attempt geocoding from property names — those rows rely on the analyst to verify the destination context.
3. **Connecting flights:** A LHR→DXB→BOM itinerary may appear as one Concur row (LHR→BOM) or two rows depending on how it was booked. Our parser treats it as a single direct flight (computing LHR→BOM great circle distance), which underestimates emissions for a routed flight.
4. **Radiative forcing multiplier:** DEFRA now recommends applying a multiplier (1.9x) to flight emissions to account for contrail and non-CO2 warming effects at altitude. We use the direct CO2e factor only (matching the GHG Protocol Scope 3 standard, which excludes RF). This is a documented decision, not an oversight.
5. **Personal vs. business travel mix-ups:** Concur exports can include out-of-policy personal expenses if an employee routes them through the system. No automated detection for this — flagged anomalies need analyst judgment.
