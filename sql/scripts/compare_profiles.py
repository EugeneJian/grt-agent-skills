#!/usr/bin/env python3
"""Compare a complete, bounded dataset query across two connection profiles."""
import argparse
from collections import Counter, defaultdict
import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import query_data as client


def canonical(row, columns):
    result = {}
    for key, value in row.items():
        if value is not None and columns[key] == 'number':
            number = Decimal(str(value))
            value = format(number.normalize(), 'f') if number else '0'
        elif value is not None and columns[key] == 'timestamp':
            value = datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(datetime.timezone.utc).isoformat()
        result[key] = value
    return json.dumps(result, sort_keys=True, ensure_ascii=False)


def collect(spec, profile, max_pages):
    request = dict(spec)
    if request.get('offset', 0) != 0:
        raise client.QueryError('Comparison must start at offset 0')
    offset = 0
    expected = None
    rows = []
    start = time.perf_counter()
    for _ in range(max_pages):
        request['offset'] = offset
        q = client.normalize(request, profile)
        result = (client.run_postgres(q, profile) if profile['engine'] == 'postgres'
                  else client.run_api(q, profile))
        if not isinstance(result['rows'], list) or len(result['rows']) > q['limit']:
            raise client.QueryError('Invalid result page')
        if expected is None:
            expected = result['total']
        if type(expected) is not int or expected < 0 or result['total'] != expected:
            raise client.QueryError('Result count changed during pagination; retry on a stable snapshot')
        rows.extend(result['rows'])
        offset += len(result['rows'])
        if offset == expected:
            break
        if not result['rows'] or offset > expected:
            raise client.QueryError('Pagination did not match the exact result count')
    else:
        raise client.QueryError('Page limit reached; narrow the query or raise --max-pages')
    elapsed = round((time.perf_counter() - start) * 1000, 1)
    kinds = q['data']['columns']
    counts = Counter(canonical(row, kinds) for row in rows)
    digest = hashlib.sha256(json.dumps(sorted(counts.items()), ensure_ascii=False).encode()).hexdigest()
    totals = defaultdict(Decimal)
    if {'amount', 'sales_unit'} <= set(q['columns']):
        for row in rows:
            if row['amount'] is not None:
                totals[row['sales_unit']] += Decimal(str(row['amount']))
    return counts, {'rows': expected, 'pages': _ + 1, 'elapsed_ms': elapsed,
                    'sha256': digest, 'amount_by_unit': dict(totals)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', help='Query JSON or @path.json')
    parser.add_argument('--config', default=os.environ.get('COMPANY_SQL_CONFIG', str(Path.home()/'.config/company-sql/profiles.json')))
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--max-pages', type=int, default=100)
    args = parser.parse_args()
    try:
        if not 1 <= args.max_pages <= 1000:
            raise client.QueryError('--max-pages must be 1-1000')
        config = client.read_json(args.config)
        spec = client.read_json(args.query[1:]) if args.query.startswith('@') else client.loads(args.query)
        left, left_meta = collect(spec, client.configured_profile(config, args.left), args.max_pages)
        right, right_meta = collect(spec, client.configured_profile(config, args.right), args.max_pages)
        same = left == right
        print(client.json_text({'match': same, 'dataset': spec['dataset'],
                                'left': {'profile': args.left, **left_meta},
                                'right': {'profile': args.right, **right_meta},
                                'unmatched_left_rows': sum((left-right).values()),
                                'unmatched_right_rows': sum((right-left).values())}))
        return 0 if same else 1
    except (ValueError, KeyError, OSError, InvalidOperation) as exc:
        print('compare_profiles: '+str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
