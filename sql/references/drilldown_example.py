"""Offline example for shipping-analysis.md; inputs must be fully paginated.

The caller supplies rows from shipment_detail (or the explicit housing variant)
with a single consistent period/filter/profile snapshot. This is not a fetcher.
None represents unknown; display labels must not replace grouping keys.
"""
from collections import defaultdict
from decimal import Decimal


def pn_key(value):
    return value.strip().upper() if value is not None else None


def known(value):
    return None if value is None or isinstance(value, str) and not value.strip() else value


def attach_nameplates(rows, materials):
    """Left join once per source row; fail rather than multiply duplicate keys."""
    lookup = {}
    for material in materials:
        if material.get('source_present') is not True:
            continue
        key = pn_key(material['pn_key'])
        if not key:
            raise ValueError('Missing material PN key')
        if key in lookup:
            raise ValueError('Duplicate normalized material PN key')
        lookup[key] = known(material.get('zmodel'))
    return [{**row, 'nameplate': lookup.get(pn_key(row['pn']))} for row in rows]


def aggregate(rows, dimensions):
    """Sum amount by dimensions AND unit; preserve unknowns and repeated rows."""
    dimensions = tuple(dimensions)
    if 'model_series_code' in dimensions and 'product_line_code' not in dimensions:
        raise ValueError('Series keys must include ancestor product line')
    totals = defaultdict(Decimal)
    for row in rows:
        unit = known(row['sales_unit'])
        if unit is None:
            raise ValueError('Unknown unit must be resolved before quantity comparison')
        key = tuple(known(pn_key(row[d]) if d == 'pn' else row[d]) for d in dimensions) + (unit,)
        value = row['amount']
        if isinstance(value, (bool, float)):
            raise ValueError('Use exact JSON integers or decimal strings')
        amount = Decimal(value)
        if not amount.is_finite():
            raise ValueError('Non-finite quantity')
        totals[key] += amount
    return dict(totals)
