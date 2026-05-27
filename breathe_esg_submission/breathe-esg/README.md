# Breathe ESG — Emissions Ingestion Platform

A Django REST + React prototype for ingesting, normalising, and reviewing emissions data from three enterprise source types: SAP fuel & procurement, utility portal CSV, and corporate travel (Concur).

## Live App

**URL:** [deployed on Railway / Render]  
**Login:** `analyst` / `breathe2024`  
**Also:** `admin` / `breathe2024` (Django admin access)

---

## Local Setup (< 5 minutes)

### Prerequisites
- Python 3.11+
- Node 18+

### Backend

```bash
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers whitenoise

cd breathe-esg
python manage.py migrate
python seed_data.py        # creates demo org, users, emission factors, sample data
python manage.py runserver 8000
```

### Frontend

```bash
cd frontend
REACT_APP_API_URL=http://localhost:8000 npm install
npm start                  # dev server on :3000
# OR
npm run build              # production build (served by Django via whitenoise)
```

When `frontend/build/` exists, Django serves the React app at `/` and all API routes under `/api/`.

---

## What's in the Sample Data

The seed script creates one organisation (Acme Manufacturing Ltd) with three ingestion batches representing Q1 2024:

| Source | File | Records | Parse errors |
|--------|------|---------|--------------|
| SAP ALV export | `acme_sap_export_q1_2024.txt` | 9 | 1 (intentional bad row) |
| Utility portal CSV | `electricity_q1_2024.csv` | 9 | 0 |
| Concur travel export | `concur_travel_export_q1_2024.csv` | 12 | 0 |

Several records are intentionally flagged as suspicious (estimated meter reads, unknown airport codes, zero consumption) to demonstrate the analyst review workflow.

---

## Uploading Your Own Files

### SAP Format
Tab-separated `.txt` or `.csv`. Required columns (German and English headers both accepted):

```
Belegdatum  Werk    Material    Materialgruppe  Menge   Mengeneinheit   Bezeichnung   Belegnummer
15.01.2024  P001    DIESEL001   FUEL            5000    L               Diesel EN590  4500001234
```

Parser handles: German/English mixed headers, DD.MM.YYYY and YYYYMMDD dates, SAP unit codes (L, LT, KG, TO, M3, GL/GAL).

### Utility Format
Comma-separated `.csv` from any UK commercial utility portal:

```
Account Reference, Meter Serial Number, Read Date, Period Start, Period End, Read Type, Consumption (kWh), Cost (GBP), Tariff, Site
ACC-001, MSN-BHM-01, 31/01/2024, 01/01/2024, 31/01/2024, Actual, 45230, 4752.15, Business Standard, Birmingham Plant
```

### Travel Format
Concur Travel export `.csv`:

```
Trip ID, Employee ID, Travel Date, Origin, Destination, Travel Type, Class of Service, Distance (km), Nights, Amount, Currency, Vendor, Cost Centre
TRP-2024-001, EMP001, 15/01/2024, LHR, JFK, Air, Economy, , 0, 1250.00, GBP, British Airways, SALES
```

Distance is optional for flights — computed from IATA airport coordinates if absent.

---

## Architecture

```
breathe_esg/        Django project settings + URLs
accounts/           (reserved for future SSO/SAML)
ingestion/
  models.py         Core schema: Organization, User, IngestionBatch,
                    EmissionsRecord, AuditLog, EmissionFactor, FacilityLookup
  views.py          DRF ViewSets + upload endpoint + dashboard stats
  serializers.py    API serializers
  ingest.py         Orchestrator: calls parser, applies emission factors,
                    runs quality checks, creates EmissionsRecord rows
  parsers/
    sap_parser.py   SAP ALV flat file → normalised rows
    utility_parser.py  Utility portal CSV → normalised rows
    travel_parser.py   Concur travel CSV → normalised rows
frontend/
  src/
    pages/
      Login.jsx     JWT login
      Dashboard.jsx Scope/category/review status charts
      Records.jsx   Filterable records table + review modal + audit trail
      Upload.jsx    Drag-drop file upload with source type selector
      Batches.jsx   Ingestion batch history with error details
    api.js          Axios client with JWT refresh interceptor
    index.css       Design system (CSS variables, dark theme)
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/token/` | Get JWT tokens |
| POST | `/api/auth/refresh/` | Refresh access token |
| GET | `/api/dashboard/` | Aggregated stats for org |
| GET | `/api/records/` | Paginated emissions records (filterable) |
| POST | `/api/records/{id}/review/` | Approve / flag / reject a record |
| GET | `/api/records/{id}/audit_trail/` | Full action history for a record |
| GET | `/api/batches/` | Ingestion batch list |
| POST | `/api/upload/` | Upload a source file |
| GET | `/health/` | Health check (unauthenticated) |

Records endpoint filter params: `scope`, `category`, `review_status`, `source_type`, `flagged=true`

---

## Deployment (Railway)

1. Connect GitHub repo to Railway
2. Add service: **Python** (auto-detects Django)
3. Set environment variables:
   ```
   SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
   DEBUG=False
   ALLOWED_HOSTS=your-app.railway.app
   ```
4. Start command: `gunicorn breathe_esg.wsgi`
5. Build frontend first: `cd frontend && npm run build`
6. Run seed: `python seed_data.py`

The app uses SQLite in development. For production on Railway, add a Postgres plugin and update `DATABASES` to read `DATABASE_URL` from env.

---

## Key Design Decisions

See `MODEL.md`, `DECISIONS.md`, `TRADEOFFS.md`, `SOURCES.md` for full documentation.

Short version:
- **SAP:** ALV Grid Export (tab-separated) over IDoc or OData — zero IT setup required
- **Utility:** Portal CSV over PDF or API — facilities teams already export this
- **Travel:** Concur flat export over REST API — no OAuth setup needed
- **Immutable records:** Edits create new versions; old records get `superseded_by` set
- **Unit normalisation:** Raw values preserved forever; `quantity_litres`, `quantity_kwh`, `quantity_km` computed once at ingest
- **Scope assignment:** Explicit at parse time (SAP fuel → Scope 1, electricity → Scope 2, travel → Scope 3)
