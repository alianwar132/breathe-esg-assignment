"""
SAP flat-file parser for fuel & procurement exports.

Format choice: SAP ALV Grid Export (tab-separated .txt / .csv)
This is what sustainability teams actually get when they ask their SAP admin
for an FI document extract or MM purchasing report. It's not IDoc (which is
EDI between systems) and not OData (requires API setup most clients haven't
done). The ALV export is the "just give me the data" path that works without
SAP BASIS involvement.

Typical SAP column headers in German/English mixed configs:
  Buchungsdatum = Posting Date
  Belegdatum    = Document Date  
  Werk          = Plant (our facility code)
  Material      = Material number
  Menge         = Quantity
  Mengeneinheit = Unit of Measure
  Wert          = Value (monetary)
  Waehrung      = Currency
  Belegart      = Document type (e.g. WE = goods receipt, RE = invoice)

Unit mapping covers SAP's internal UoM codes:
  L   = litre
  LT  = litre (alternate)
  KG  = kilogram
  TO  = metric tonne
  M3  = cubic metre
  GAL = US gallon
  PC  = piece (for procurement items — no energy conversion)
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator

# SAP internal UoM → (canonical_unit, multiplier_to_litres_or_kg)
SAP_UNIT_MAP = {
    'L':   ('litre',        Decimal('1')),
    'LT':  ('litre',        Decimal('1')),
    'GL':  ('litre',        Decimal('3.78541')),   # US gallon
    'GAL': ('litre',        Decimal('3.78541')),
    'M3':  ('litre',        Decimal('1000')),       # cubic metre → litres
    'KG':  ('kg',           Decimal('1')),
    'TO':  ('kg',           Decimal('1000')),       # metric tonne
    'T':   ('kg',           Decimal('1000')),
    'LB':  ('kg',           Decimal('0.453592')),
}

# Material groups we consider "fuel" vs "procurement"
FUEL_MATERIAL_GROUPS = {'0001', '0002', '0003', 'FUEL', 'PETRL', 'DIESEL', 'LNG', 'CNG', 'HFO'}

# Column header aliases (handles German, English, mixed)
HEADER_ALIASES = {
    'activity_date': ['Belegdatum', 'Document Date', 'DocumentDate', 'Posting Date',
                      'Buchungsdatum', 'BLDAT', 'BUDAT'],
    'plant':         ['Werk', 'Plant', 'WERKS'],
    'material':      ['Material', 'Materialnummer', 'Material Number', 'MATNR'],
    'material_group':['Materialgruppe', 'Material Group', 'MATKL'],
    'quantity':      ['Menge', 'Quantity', 'MENGE'],
    'unit':          ['Mengeneinheit', 'Unit of Measure', 'Base Unit', 'MEINS', 'BSTME'],
    'description':   ['Bezeichnung', 'Description', 'Material Description', 'MAKTX'],
    'doc_number':    ['Belegnummer', 'Document Number', 'BELNR', 'Purchasing Document'],
    'doc_type':      ['Belegart', 'Document Type', 'BLART'],
    'cost_centre':   ['Kostenstelle', 'Cost Centre', 'Cost Center', 'KOSTL'],
    'vendor':        ['Lieferant', 'Vendor', 'LIFNR'],
    'fuel_type':     ['Kraftstoffart', 'Fuel Type', 'Fuel Category'],
}


def _resolve_headers(raw_headers: list[str]) -> dict[str, int]:
    """Map canonical field names to column indices, tolerating header variants."""
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


def _parse_sap_date(raw: str) -> datetime | None:
    """Try multiple date formats SAP exports use."""
    raw = raw.strip()
    for fmt in ('%d.%m.%Y', '%Y%m%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _infer_fuel_type(material: str, material_group: str, description: str) -> str:
    """Best-effort fuel type inference from SAP material data."""
    combined = f"{material} {material_group} {description}".upper()
    if any(k in combined for k in ['DIESEL', 'DIES']):
        return 'diesel'
    if any(k in combined for k in ['PETROL', 'GASOLINE', 'BENZIN', 'UNLEADED']):
        return 'petrol'
    if 'LNG' in combined:
        return 'lng'
    if 'CNG' in combined:
        return 'cng'
    if 'HFO' in combined or 'HEAVY FUEL' in combined:
        return 'hfo'
    if 'LPG' in combined:
        return 'lpg'
    return 'unknown'


def parse_sap_file(file_content: bytes, filename: str) -> Iterator[dict]:
    """
    Parse a SAP ALV export file and yield normalised row dicts.
    Yields both successful rows and error dicts (check row['_error']).
    """
    # SAP exports can be tab or semicolon separated
    text = file_content.decode('utf-8-sig', errors='replace')  # strip BOM
    
    # Detect delimiter
    first_line = text.split('\n')[0]
    delimiter = '\t' if '\t' in first_line else (';' if first_line.count(';') > first_line.count(',') else ',')
    
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return
    
    header_map = _resolve_headers(rows[0])
    
    for row_num, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue  # skip blank rows
        
        def get(field: str) -> str:
            idx = header_map.get(field)
            if idx is None or idx >= len(row):
                return ''
            return row[idx].strip()
        
        # Date
        raw_date = get('activity_date')
        parsed_date = _parse_sap_date(raw_date)
        if not parsed_date:
            yield {'_error': True, '_row': row_num, '_field': 'activity_date',
                   '_raw': raw_date, '_msg': f"Cannot parse date: '{raw_date}'"}
            continue
        
        # Quantity
        raw_qty = get('quantity').replace(',', '.').replace(' ', '')
        try:
            quantity = Decimal(raw_qty)
        except InvalidOperation:
            yield {'_error': True, '_row': row_num, '_field': 'quantity',
                   '_raw': raw_qty, '_msg': f"Cannot parse quantity: '{raw_qty}'"}
            continue
        
        # Unit normalisation
        raw_unit = get('unit').strip().upper()
        unit_entry = SAP_UNIT_MAP.get(raw_unit)
        quantity_litres = None
        quantity_kg = None
        if unit_entry:
            canonical_unit, multiplier = unit_entry
            if canonical_unit == 'litre':
                quantity_litres = quantity * multiplier
            elif canonical_unit == 'kg':
                quantity_kg = quantity * multiplier
        
        material = get('material')
        material_group = get('material_group')
        description = get('description')
        fuel_type = get('fuel_type') or _infer_fuel_type(material, material_group, description)
        is_fuel = (
            material_group.upper() in FUEL_MATERIAL_GROUPS or
            fuel_type != 'unknown' or
            any(k in description.upper() for k in ['DIESEL', 'PETROL', 'FUEL', 'BENZIN'])
        )

        yield {
            '_error': False,
            '_row': row_num,
            'activity_date': parsed_date.date(),
            'category': 'fuel' if is_fuel else 'procurement',
            'scope': 1 if is_fuel else 3,
            'raw_quantity': raw_qty,
            'raw_unit': raw_unit,
            'raw_description': description,
            'quantity_litres': float(quantity_litres) if quantity_litres else None,
            'source_row_id': get('doc_number'),
            'extra': {
                'sap_plant': get('plant'),
                'sap_material': material,
                'sap_material_group': material_group,
                'sap_doc_type': get('doc_type'),
                'sap_cost_centre': get('cost_centre'),
                'sap_vendor': get('vendor'),
                'fuel_type': fuel_type,
                'unit_normalisation': f"{raw_unit} → litres via ×{unit_entry[1]}" if unit_entry else 'no mapping',
            }
        }
