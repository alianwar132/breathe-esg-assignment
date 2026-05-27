"""
Utility / electricity parser.

Format choice: Portal CSV export (e.g. from EDF, British Gas Business,
Octopus, or US utilities via Green Button format).

Why CSV over PDF or API:
- PDF bills require OCR; layout varies by utility, fragile in production.
- Utility APIs (Green Button / ESPI) exist but almost no UK/Indian facility
  teams have API credentials — they just log in and click "Export".
- CSV export is what *actually happens* in enterprise sustainability workflows.
  The facilities manager downloads it monthly and drops it in a shared drive.

Real-world CSV shapes encountered:
  - UK supplier exports: Account Reference, Meter Serial Number, Read Date,
    Read Type (Actual/Estimated), Units, kWh, Cost, Tariff
  - Green Button (US): start_time, duration_seconds, value, unit
  - Generic: Date, Meter ID, Reading, Unit, Consumption, Cost

We handle the UK-style format (most common in enterprise UK/EU clients).
"""

import csv
import io
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterator

HEADER_ALIASES = {
    'account_ref':      ['Account Reference', 'Account Number', 'Account Ref', 'Account'],
    'meter_id':         ['Meter Serial Number', 'Meter ID', 'Meter Number', 'MPAN', 'Meter'],
    'read_date':        ['Read Date', 'Reading Date', 'Date', 'Period End', 'Bill Date'],
    'period_start':     ['Period Start', 'From Date', 'Start Date', 'Billing Start'],
    'period_end':       ['Period End', 'To Date', 'End Date', 'Billing End'],
    'read_type':        ['Read Type', 'Reading Type', 'Type', 'Meter Read Type'],
    'consumption':      ['Consumption (kWh)', 'kWh', 'Consumption', 'Units', 'Energy kWh', 'Usage kWh'],
    'raw_unit':         ['Unit', 'UOM', 'Unit of Measure'],
    'cost':             ['Cost (£)', 'Cost (GBP)', 'Cost', 'Amount', 'Charge (£)'],
    'tariff':           ['Tariff', 'Rate', 'Tariff Name', 'Rate Code'],
    'site':             ['Site', 'Site Name', 'Property', 'Address', 'Location'],
}

UNIT_TO_KWH = {
    'KWH': Decimal('1'),
    'MWH': Decimal('1000'),
    'GWH': Decimal('1000000'),
    'THERM': Decimal('29.3071'),    # for gas bills sometimes included
    'GJ':   Decimal('277.778'),
    'MJ':   Decimal('0.277778'),
}


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


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y',
                '%d %b %Y', '%d %B %Y', '%Y%m%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_utility_file(file_content: bytes, filename: str) -> Iterator[dict]:
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
        
        # Period resolution: prefer explicit period_start/period_end,
        # fall back to inferring a monthly period from read_date
        raw_read_date = get('read_date') or get('period_end')
        read_date = _parse_date(raw_read_date)
        if not read_date:
            yield {'_error': True, '_row': row_num, '_field': 'read_date',
                   '_raw': raw_read_date, '_msg': f"Cannot parse date: '{raw_read_date}'"}
            continue
        
        period_start_raw = get('period_start')
        period_end_raw = get('period_end') or raw_read_date
        period_start = _parse_date(period_start_raw) if period_start_raw else None
        period_end = _parse_date(period_end_raw) if period_end_raw else read_date
        
        # Consumption
        raw_consumption = get('consumption').replace(',', '')
        try:
            consumption = Decimal(raw_consumption)
        except InvalidOperation:
            yield {'_error': True, '_row': row_num, '_field': 'consumption',
                   '_raw': raw_consumption, '_msg': f"Cannot parse consumption: '{raw_consumption}'"}
            continue
        
        # Unit normalisation to kWh
        raw_unit = (get('raw_unit') or 'KWH').upper().replace(' ', '')
        multiplier = UNIT_TO_KWH.get(raw_unit, Decimal('1'))
        kwh = consumption * multiplier
        
        # Suspicious: estimated readings, extremely high/zero consumption
        flags = []
        read_type = get('read_type').upper()
        if 'ESTIM' in read_type or read_type == 'E':
            flags.append('estimated_meter_read')
        if kwh == 0:
            flags.append('zero_consumption')
        if kwh > Decimal('500000'):  # 500 MWh in one bill period is unusual
            flags.append('unusually_high_consumption')
        
        yield {
            '_error': False,
            '_row': row_num,
            'activity_date': period_end or read_date,
            'billing_period_start': period_start,
            'billing_period_end': period_end,
            'category': 'electricity',
            'scope': 2,
            'raw_quantity': raw_consumption,
            'raw_unit': raw_unit,
            'raw_description': f"Electricity consumption {period_start or read_date} to {period_end or read_date}",
            'quantity_kwh': float(kwh),
            'is_flagged_suspicious': bool(flags),
            'flag_reasons': flags,
            'extra': {
                'account_ref': get('account_ref'),
                'meter_id': get('meter_id'),
                'read_type': get('read_type'),
                'tariff': get('tariff'),
                'site': get('site'),
                'cost': get('cost'),
                'unit_normalisation': f"{raw_unit} → kWh via ×{multiplier}",
            }
        }
