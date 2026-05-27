"""
Seed script: creates a demo org, analyst user, emission factors,
and realistic sample data for all three source types.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breathe_esg.settings')
django.setup()

from decimal import Decimal
from datetime import date
from ingestion.models import Organization, User, EmissionFactor, FacilityLookup, IngestionBatch
from ingestion.ingest import process_upload

# --- Organisation & Users ---
org, _ = Organization.objects.get_or_create(name='Acme Manufacturing Ltd', slug='acme')
analyst, _ = User.objects.get_or_create(username='analyst', defaults={
    'email': 'analyst@acme.com', 'organization': org, 'role': 'analyst',
    'first_name': 'Sarah', 'last_name': 'Chen',
})
analyst.set_password('breathe2024')
analyst.save()

admin_user, _ = User.objects.get_or_create(username='admin', defaults={
    'email': 'admin@acme.com', 'organization': org, 'role': 'admin',
    'is_staff': True, 'is_superuser': True,
    'first_name': 'James', 'last_name': 'Webb',
})
admin_user.set_password('breathe2024')
admin_user.save()

print("✓ Users created: analyst / breathe2024, admin / breathe2024")

# --- Emission Factors ---
factors = [
    ('diesel', 1, Decimal('2.6869'), 'litre', 'DEFRA 2023', date(2023,1,1)),
    ('petrol', 1, Decimal('2.3135'), 'litre', 'DEFRA 2023', date(2023,1,1)),
    ('electricity_uk', 2, Decimal('0.2078'), 'kWh', 'DEFRA 2023 UK Grid', date(2023,1,1)),
    ('flight_economy', 3, Decimal('0.1551'), 'pax_km', 'DEFRA 2023', date(2023,1,1)),
    ('flight_business', 3, Decimal('0.4286'), 'pax_km', 'DEFRA 2023', date(2023,1,1)),
    ('hotel_night', 3, Decimal('31.0'), 'night', 'DEFRA 2023', date(2023,1,1)),
]
for act, scope, factor, unit, source, vfrom in factors:
    EmissionFactor.objects.get_or_create(
        activity_type=act, scope=scope,
        defaults={'factor_kg_co2e_per_unit': factor, 'unit': unit,
                  'source': source, 'valid_from': vfrom}
    )

# --- Facility Lookup ---
plants = [
    ('P001', 'Birmingham Plant', 'GBR', 'West Midlands'),
    ('P002', 'Manchester Warehouse', 'GBR', 'North West'),
    ('P003', 'Glasgow Office', 'GBR', 'Scotland'),
]
for code, name, country, region in plants:
    FacilityLookup.objects.get_or_create(
        organization=org, sap_plant_code=code,
        defaults={'site_name': name, 'country_code': country, 'region': region}
    )

print("✓ Reference data seeded")

# --- Sample SAP data ---
sap_csv = b"""Belegdatum\tWerk\tMaterial\tMaterialgruppe\tMenge\tMengeneinheit\tBezeichnung\tBelegnummer\tBelegart\tKostenstelle\tLieferant
15.01.2024\tP001\tDIESEL001\tFUEL\t5000\tL\tDiesel EN590\t4500001234\tWE\tCC001\tBP Fuels Ltd
22.01.2024\tP001\tDIESEL001\tFUEL\t3500\tL\tDiesel EN590\t4500001235\tWE\tCC001\tBP Fuels Ltd
05.02.2024\tP002\tDIESEL001\tFUEL\t2000\tL\tDiesel EN590\t4500001240\tWE\tCC002\tShell UK
12.02.2024\tP001\tPETROL001\tFUEL\t800\tL\tUnleaded Petrol\t4500001241\tWE\tCC001\tBP Fuels Ltd
28.02.2024\tP003\tDIESEL001\tFUEL\t1200\tL\tDiesel EN590\t4500001250\tWE\tCC003\tTotal Energies
10.03.2024\tP001\tOFFICE001\t0010\t50\tPC\tOffice Supplies Box\t4500001260\tRE\tCC001\tStaples UK
15.03.2024\tP001\tDIESEL001\tFUEL\t6000\tL\tDiesel EN590\t4500001265\tWE\tCC001\tBP Fuels Ltd
20.03.2024\tP002\tLPG001\tFUEL\t500\tKG\tLPG Bulk\t4500001270\tWE\tCC002\tCalor Gas
05.04.2024\tP001\tDIESEL001\tFUEL\t4500\tL\tDiesel EN590\t4500001280\tWE\tCC001\tBP Fuels Ltd
invalid_date\tP001\tDIESEL001\tFUEL\tXXX\tL\tBad Row\t9999\tWE\tCC001\tTest
"""

# --- Sample Utility data ---
utility_csv = b"""Account Reference,Meter Serial Number,Read Date,Period Start,Period End,Read Type,Consumption (kWh),Cost (GBP),Tariff,Site
ACC-001,MSN-BHM-01,31/01/2024,01/01/2024,31/01/2024,Actual,45230,4752.15,Business Standard,Birmingham Plant
ACC-001,MSN-BHM-01,29/02/2024,01/02/2024,29/02/2024,Actual,41800,4389.00,Business Standard,Birmingham Plant
ACC-001,MSN-BHM-01,31/03/2024,01/03/2024,31/03/2024,Estimated,43100,4525.50,Business Standard,Birmingham Plant
ACC-002,MSN-MAN-01,31/01/2024,01/01/2024,31/01/2024,Actual,22100,2320.50,Business Standard,Manchester Warehouse
ACC-002,MSN-MAN-01,29/02/2024,01/02/2024,29/02/2024,Actual,19800,2079.00,Business Standard,Manchester Warehouse
ACC-002,MSN-MAN-01,31/03/2024,01/03/2024,31/03/2024,Actual,21500,2257.50,Business Standard,Manchester Warehouse
ACC-003,MSN-GLA-01,31/01/2024,01/01/2024,31/01/2024,Actual,8900,934.50,SME Flex,Glasgow Office
ACC-003,MSN-GLA-01,29/02/2024,01/02/2024,29/02/2024,Actual,9200,966.00,SME Flex,Glasgow Office
ACC-004,MSN-BHM-02,31/01/2024,01/01/2024,31/01/2024,Actual,0,0.00,Business Standard,Birmingham Annex
"""

# --- Sample Travel data ---
travel_csv = b"""Trip ID,Employee ID,Travel Date,Origin,Destination,Travel Type,Class of Service,Distance (km),Nights,Amount,Currency,Vendor,Cost Centre
TRP-2024-001,EMP001,15/01/2024,LHR,JFK,Air,Economy,,0,1250.00,GBP,British Airways,SALES
TRP-2024-002,EMP002,18/01/2024,LHR,CDG,Air,Business,,0,890.00,GBP,Air France,EXEC
TRP-2024-003,EMP001,16/01/2024,JFK,JFK,Hotel,,0,3,450.00,USD,Marriott NYC,SALES
TRP-2024-004,EMP003,22/01/2024,MAN,LHR,Air,Economy,320,0,220.00,GBP,EasyJet,SALES
TRP-2024-005,EMP003,22/01/2024,LHR,DXB,Air,Economy,,0,680.00,GBP,Emirates,SALES
TRP-2024-006,EMP002,10/02/2024,LHR,SIN,Air,Business,,0,4200.00,GBP,Singapore Airlines,EXEC
TRP-2024-007,EMP004,12/02/2024,LHR,SIN,Hotel,,0,2,380.00,SGD,Shangri-La,EXEC
TRP-2024-008,EMP005,14/02/2024,BHX,LHR,Car,,,150,0,85.00,GBP,Uber Business,OPS
TRP-2024-009,EMP001,20/02/2024,LHR,BOM,Air,Economy,,0,870.00,GBP,British Airways,SALES
TRP-2024-010,EMP006,25/02/2024,ZZZ,ZZZ,Air,Economy,,0,200.00,GBP,Unknown Airline,OPS
TRP-2024-011,EMP002,05/03/2024,LHR,FRA,Air,Business,,0,1100.00,GBP,Lufthansa,EXEC
TRP-2024-012,EMP003,08/03/2024,LHR,FRA,Hotel,,0,1,280.00,EUR,Marriott Frankfurt,EXEC
"""

for source_type, content, filename in [
    ('sap', sap_csv, 'acme_sap_export_q1_2024.txt'),
    ('utility', utility_csv, 'electricity_q1_2024.csv'),
    ('travel', travel_csv, 'concur_travel_export_q1_2024.csv'),
]:
    batch = IngestionBatch.objects.create(
        organization=org, source_type=source_type,
        original_filename=filename, uploaded_by=admin_user,
        status=IngestionBatch.STATUS_PROCESSING,
    )
    result = process_upload(content, filename, source_type, batch, org, admin_user)
    print(f"✓ {source_type}: {result['rows_created']} rows, {len(result['errors'])} errors")

print("\n✅ Seed complete. Login: analyst / breathe2024")
