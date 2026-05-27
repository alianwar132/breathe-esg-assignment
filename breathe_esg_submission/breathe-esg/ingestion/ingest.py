"""
Ingestion orchestrator: parses a file, creates EmissionsRecords,
links them to a batch, handles emission factor lookup.
"""
from decimal import Decimal
from .models import EmissionsRecord, IngestionBatch, IngestionError, EmissionFactor
from .parsers.sap_parser import parse_sap_file
from .parsers.utility_parser import parse_utility_file
from .parsers.travel_parser import parse_travel_file

# Emission factors by category/fuel type
# In production these come from the EmissionFactor table, seeded from DEFRA/EPA.
# We hardcode defaults here so the app works without a seeding step.
DEFAULT_FACTORS = {
    # fuel type → kg CO2e per litre
    'diesel':   Decimal('2.6869'),
    'petrol':   Decimal('2.3135'),
    'lng':      Decimal('2.7372'),
    'cng':      Decimal('2.0403'),
    'lpg':      Decimal('1.5554'),
    'hfo':      Decimal('3.1780'),
    # electricity → kg CO2e per kWh (UK 2023 grid average)
    'electricity': Decimal('0.2078'),
    # travel: already calculated in parser using per-km factors
}


def _apply_emission_factor(row: dict) -> tuple[float | None, str]:
    """Return (co2e_kg, method) for a parsed row."""
    if row.get('co2e_kg') is not None:
        # Travel parser already computed it
        return row['co2e_kg'], row.get('calculation_method', 'pre_calculated')
    
    category = row.get('category')
    extra = row.get('extra', {})
    
    if category == 'fuel':
        fuel_type = extra.get('fuel_type', 'diesel')
        factor = DEFAULT_FACTORS.get(fuel_type, DEFAULT_FACTORS['diesel'])
        qty_l = row.get('quantity_litres')
        if qty_l:
            return float(Decimal(str(qty_l)) * factor), f'fuel_factor:{fuel_type}:{factor}kgCO2e/L'
    
    elif category == 'electricity':
        factor = DEFAULT_FACTORS['electricity']
        kwh = row.get('quantity_kwh')
        if kwh:
            return float(Decimal(str(kwh)) * factor), f'grid_factor:uk2023:{factor}kgCO2e/kWh'
    
    return None, 'no_factor_applied'


def process_upload(content: bytes, filename: str, source_type: str,
                   batch: IngestionBatch, org, user) -> dict:
    parser_map = {
        'sap':     parse_sap_file,
        'utility': parse_utility_file,
        'travel':  parse_travel_file,
    }
    parser = parser_map[source_type]
    rows_created = 0
    errors = []
    
    for parsed_row in parser(content, filename):
        if parsed_row.get('_error'):
            IngestionError.objects.create(
                batch=batch,
                row_number=parsed_row.get('_row'),
                field_name=parsed_row.get('_field', ''),
                raw_value=str(parsed_row.get('_raw', '')),
                error_message=parsed_row.get('_msg', ''),
            )
            errors.append(parsed_row)
            continue
        
        co2e_kg, method = _apply_emission_factor(parsed_row)
        
        # Suspicious value checks
        flags = list(parsed_row.get('flag_reasons') or [])
        is_suspicious = parsed_row.get('is_flagged_suspicious', False)
        if co2e_kg and co2e_kg > 100000:
            flags.append('unusually_high_co2e')
            is_suspicious = True
        if co2e_kg == 0 or co2e_kg is None:
            flags.append('zero_or_missing_co2e')
        
        EmissionsRecord.objects.create(
            organization=org,
            batch=batch,
            source_type=source_type,
            source_row_id=parsed_row.get('source_row_id', ''),
            scope=parsed_row.get('scope', 3),
            category=parsed_row.get('category', 'fuel'),
            activity_date=parsed_row['activity_date'],
            billing_period_start=parsed_row.get('billing_period_start'),
            billing_period_end=parsed_row.get('billing_period_end'),
            raw_quantity=str(parsed_row.get('raw_quantity', '')),
            raw_unit=str(parsed_row.get('raw_unit', '')),
            raw_description=parsed_row.get('raw_description', ''),
            quantity_kwh=parsed_row.get('quantity_kwh'),
            quantity_litres=parsed_row.get('quantity_litres'),
            quantity_km=parsed_row.get('quantity_km'),
            quantity_nights=parsed_row.get('quantity_nights'),
            co2e_kg=co2e_kg,
            calculation_method=method,
            extra=parsed_row.get('extra', {}),
            is_flagged_suspicious=is_suspicious,
            flag_reasons=flags,
        )
        rows_created += 1
    
    batch.row_count = rows_created
    batch.error_count = len(errors)
    batch.status = IngestionBatch.STATUS_COMPLETE
    batch.save()
    
    return {'rows_created': rows_created, 'errors': errors}
