"""
Corporate travel parser.

Format choice: Concur Expense / Travel export CSV.

Why Concur flat export over Navan API or SAP Concur API:
- Most enterprises have Concur but their IT team hasn't configured API access
  for sustainability reporting. The "Download to Excel/CSV" button exists in
  every Concur deployment.
- Navan's API is well-documented but Navan is newer; many mid-large enterprises
  are still on Concur.
- The flat export gives us all the fields we need without OAuth setup.

Fields in a Concur Travel Export:
  Trip ID, Employee ID, Employee Name, Booking Date, Travel Date,
  Origin, Destination, Travel Type (Air/Rail/Car/Hotel),
  Class of Service (Economy/Business/First), Distance (mi or km),
  Nights (hotel), Amount, Currency, Vendor, Carbon (if Concur calculates it)

Gap: distances aren't always present for flights.
When missing, we use the Haversine formula on IATA airport coordinates.
This is documented in SOURCES.md.
"""

import csv
import io
import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator

# Subset of major IATA airport coordinates (lat, lon)
# In production this would be a full database table loaded from OurAirports.com
AIRPORT_COORDS = {
    'LHR': (51.477, -0.461), 'LGW': (51.148, -0.190), 'MAN': (53.353, -2.275),
    'JFK': (40.640, -73.778), 'LAX': (33.943, -118.408), 'ORD': (41.978, -87.905),
    'DXB': (25.253, 55.364), 'SIN': (1.359, 103.989), 'HKG': (22.309, 113.915),
    'CDG': (49.009, 2.548), 'AMS': (52.309, 4.764), 'FRA': (50.033, 8.571),
    'SYD': (-33.946, 151.177), 'NRT': (35.765, 140.386), 'BOM': (19.088, 72.868),
    'DEL': (28.556, 77.100), 'BLR': (13.197, 77.706), 'CCU': (22.654, 88.447),
    'MAA': (12.990, 80.169), 'HYD': (17.231, 78.430), 'PAT': (25.591, 85.087),
    'DFW': (32.897, -97.038), 'ATL': (33.641, -84.427), 'MIA': (25.796, -80.287),
    'YYZ': (43.677, -79.631), 'GRU': (-23.432, -46.469), 'EZE': (-34.822, -58.536),
    'JNB': (-26.134, 28.242), 'NBO': (-1.319, 36.928), 'CAI': (30.122, 31.406),
    'PEK': (40.080, 116.584), 'PVG': (31.143, 121.805), 'ICN': (37.460, 126.441),
    'MEL': (-37.673, 144.843), 'AKL': (-37.008, 174.792),
}

# kg CO2e per passenger km by class
# Source: DEFRA 2023 GHG Conversion Factors (we store these in EmissionFactor
# table; these are defaults for when we don't hit the DB during parsing)
FLIGHT_FACTORS = {
    'economy':  Decimal('0.1551'),   # kgCO2e / pax-km
    'business': Decimal('0.4286'),
    'first':    Decimal('0.5147'),
    'premium':  Decimal('0.2872'),
    'unknown':  Decimal('0.1551'),
}

HOTEL_FACTOR_PER_NIGHT = Decimal('31.0')   # kgCO2e per night (DEFRA 2023)
RAIL_FACTOR_PER_KM = Decimal('0.0370')     # national rail average
CAR_FACTOR_PER_KM = Decimal('0.1709')      # average car

HEADER_ALIASES = {
    'trip_id':      ['Trip ID', 'TripID', 'Booking Reference', 'Itinerary'],
    'employee_id':  ['Employee ID', 'EmployeeID', 'Employee Number', 'Staff ID'],
    'travel_date':  ['Travel Date', 'Departure Date', 'Date', 'Travel Start Date', 'Check-In Date'],
    'origin':       ['Origin', 'From', 'Departure', 'Origin Airport', 'Origin City'],
    'destination':  ['Destination', 'To', 'Arrival', 'Destination Airport', 'Destination City'],
    'travel_type':  ['Travel Type', 'Mode', 'Expense Type', 'Category', 'Transport Mode'],
    'service_class':['Class of Service', 'Class', 'Cabin Class', 'Seat Class'],
    'distance':     ['Distance', 'Distance (km)', 'Distance (mi)', 'Miles', 'Kilometres'],
    'distance_unit':['Distance Unit', 'Unit'],
    'nights':       ['Nights', 'Number of Nights', 'Hotel Nights', 'Duration (nights)'],
    'amount':       ['Amount', 'Cost', 'Spend', 'Total Amount'],
    'currency':     ['Currency', 'Ccy', 'CCY'],
    'vendor':       ['Vendor', 'Supplier', 'Hotel', 'Airline', 'Carrier'],
    'cost_centre':  ['Cost Centre', 'Cost Center', 'Department', 'Business Unit'],
}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _infer_distance_km(origin: str, destination: str) -> tuple[float | None, str]:
    """Return (distance_km, method) or (None, reason)."""
    o = origin.upper().strip()
    d = destination.upper().strip()
    if o in AIRPORT_COORDS and d in AIRPORT_COORDS:
        gc = _haversine_km(*AIRPORT_COORDS[o], *AIRPORT_COORDS[d])
        # Add 9% uplift for actual flight paths vs great circle (DEFRA guidance)
        return gc * 1.09, 'haversine+9%uplift'
    return None, f"airport_not_in_lookup:{o},{d}"


def _normalise_class(raw: str) -> str:
    r = raw.upper().strip()
    if any(k in r for k in ['ECON', 'Y', 'COACH']):
        return 'economy'
    if any(k in r for k in ['BUS', 'C', 'EXEC']):
        return 'business'
    if any(k in r for k in ['FIRST', 'F']):
        return 'first'
    if 'PREM' in r:
        return 'premium'
    return 'unknown'


def _normalise_travel_type(raw: str) -> str:
    r = raw.upper()
    if any(k in r for k in ['AIR', 'FLIGHT', 'FLY']):
        return 'flight'
    if any(k in r for k in ['HOTEL', 'ACCOMMODATION', 'LODG']):
        return 'hotel'
    if any(k in r for k in ['RAIL', 'TRAIN']):
        return 'rail'
    if any(k in r for k in ['CAR', 'TAXI', 'UBER', 'GROUND', 'HIRE']):
        return 'ground_transport'
    return 'unknown'


def _resolve_headers(raw_headers):
    resolved = {}
    lower_raw = [h.strip().lower() for h in raw_headers]
    for canonical, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            try:
                idx = lower_raw.index(alias.lower())
                resolved[canonical] = idx
                break
            except ValueError:
                continue
    return resolved


def _parse_date(raw):
    raw = raw.strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%d %b %Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_travel_file(file_content: bytes, filename: str) -> Iterator[dict]:
    text = file_content.decode('utf-8-sig', errors='replace')
    first_line = text.split('\n')[0]
    delimiter = ',' if first_line.count(',') >= first_line.count(';') else ';'
    
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return
    
    header_map = _resolve_headers(rows[0])
    
    for row_num, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        
        def get(field):
            idx = header_map.get(field)
            if idx is None or idx >= len(row):
                return ''
            return row[idx].strip()
        
        raw_date = get('travel_date')
        travel_date = _parse_date(raw_date)
        if not travel_date:
            yield {'_error': True, '_row': row_num, '_field': 'travel_date',
                   '_raw': raw_date, '_msg': f"Cannot parse date: '{raw_date}'"}
            continue
        
        travel_type = _normalise_travel_type(get('travel_type'))
        origin = get('origin')
        destination = get('destination')
        
        # Distance resolution
        distance_raw = get('distance')
        distance_km = None
        distance_method = 'not_applicable'
        
        if travel_type in ('flight', 'rail', 'ground_transport'):
            if distance_raw:
                try:
                    dist_val = Decimal(distance_raw.replace(',', ''))
                    dist_unit = get('distance_unit').upper()
                    if 'MI' in dist_unit or dist_unit in ('MI', 'MILE', 'MILES'):
                        distance_km = float(dist_val * Decimal('1.60934'))
                        distance_method = 'provided_converted_from_miles'
                    else:
                        distance_km = float(dist_val)
                        distance_method = 'provided_km'
                except InvalidOperation:
                    pass
            if distance_km is None and travel_type == 'flight':
                distance_km, distance_method = _infer_distance_km(origin, destination)
        
        # Hotel nights
        nights = None
        if travel_type == 'hotel':
            nights_raw = get('nights')
            try:
                nights = int(nights_raw) if nights_raw else 1
            except ValueError:
                nights = 1
        
        # Emissions estimate
        service_class = _normalise_class(get('service_class'))
        co2e_kg = None
        calculation_method = 'none'
        flags = []
        
        if travel_type == 'flight' and distance_km:
            factor = FLIGHT_FACTORS.get(service_class, FLIGHT_FACTORS['unknown'])
            co2e_kg = float(Decimal(str(distance_km)) * factor)
            calculation_method = f'distance_based:{service_class}:{factor}kgCO2e_per_km'
        elif travel_type == 'hotel' and nights:
            co2e_kg = float(HOTEL_FACTOR_PER_NIGHT * nights)
            calculation_method = f'nights_based:{nights}nights'
        elif travel_type in ('rail', 'ground_transport') and distance_km:
            factor = RAIL_FACTOR_PER_KM if travel_type == 'rail' else CAR_FACTOR_PER_KM
            co2e_kg = float(Decimal(str(distance_km)) * factor)
            calculation_method = f'distance_based:{factor}kgCO2e_per_km'
        
        if travel_type == 'flight' and distance_km is None:
            flags.append('distance_unknown_airport_not_in_lookup')
        if travel_type == 'unknown':
            flags.append('travel_type_unrecognised')
        if service_class == 'unknown' and travel_type == 'flight':
            flags.append('cabin_class_unknown_using_economy_factor')
        
        yield {
            '_error': False,
            '_row': row_num,
            'activity_date': travel_date,
            'category': travel_type if travel_type in ('flight', 'hotel', 'ground_transport') else 'flight',
            'scope': 3,
            'raw_quantity': distance_raw or (str(nights) if nights else '1'),
            'raw_unit': get('distance_unit') or ('nights' if travel_type == 'hotel' else 'km'),
            'raw_description': f"{travel_type}: {origin} → {destination}" if origin else travel_type,
            'quantity_km': distance_km,
            'quantity_nights': nights,
            'co2e_kg': co2e_kg,
            'calculation_method': calculation_method,
            'is_flagged_suspicious': bool(flags),
            'flag_reasons': flags,
            'source_row_id': get('trip_id'),
            'extra': {
                'origin': origin,
                'destination': destination,
                'travel_type': travel_type,
                'service_class': service_class,
                'vendor': get('vendor'),
                'employee_id': get('employee_id'),
                'cost_centre': get('cost_centre'),
                'distance_method': distance_method,
                'amount': get('amount'),
                'currency': get('currency'),
            }
        }
