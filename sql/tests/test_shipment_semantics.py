"""Offline synthetic contracts; no private records or live-database assertions.

Business specification: ../references/shipping-analysis.md.
"""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_data as client
spec = importlib.util.spec_from_file_location('drilldown', ROOT/'references/drilldown_example.py')
drilldown = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drilldown)


def row(pn=' 00a ', line='LINE-A', series='SHARED', unit='PCS', amount='2.5', **extra):
    return dict(pn=pn, product_line_code=line, model_series_code=series,
                sales_unit=unit, amount=amount, date='2026-09-02',
                country_name='通用', power_kw=None, **extra)


class ShipmentSemanticsTests(unittest.TestCase):
    def test_all_query_examples_validate_against_current_catalog(self):
        examples = list((ROOT/'references').glob('*.json'))
        queries = [json.loads(path.read_text()) for path in examples]
        queries = [q for q in queries if 'dataset' in q]
        self.assertGreaterEqual(len(queries), 4)
        for q in queries:
            client.normalize(q, {})

    def test_detail_and_material_contract_support_two_stage_join(self):
        q = client.normalize(json.loads((ROOT/'references/shipment-drilldown.json').read_text()), {})
        self.assertEqual(q['data']['relation'], 'shipping.report_shipments')
        material = client.normalize({'dataset':'material', 'select':['pn_key','zmodel','source_present'],
                                    'filters':[{'column':'pn_key','op':'in','value':['00A']},
                                               {'column':'source_present','op':'eq','value':True}]}, {})
        self.assertIn('"pn_key" IN (\'00A\')', client.pg_sql(material))
        self.assertNotIn('DISTINCT', client.pg_sql(q))
        for name in ('zmodel','zggxh'):
            with self.assertRaises(client.QueryError):
                client.normalize({'dataset':'shipment_detail','select':[name]}, {})
        self.assertEqual(client.catalog()['shipment_detail']['columns']['power_kw'], 'number')

    def test_no_invented_datasets_or_monthly_drilldown(self):
        for dataset in ('shipment_detail_deduplicated','report_shipments_including_housing'):
            with self.assertRaises(client.QueryError):
                client.normalize({'dataset':dataset}, {})
        q = client.normalize({'dataset':'shipment_detail_including_housing'}, {})
        self.assertEqual(q['data']['relation'], 'shipping.report_shipments_including_housing')
        for column in ('model_series_code','pn','country_name','power_kw','zmodel'):
            with self.assertRaises(client.QueryError):
                client.normalize({'dataset':'shipment_monthly','select':[column]}, {})

    def test_left_join_preserves_overlap_unknowns_units_and_totals(self):
        rows = [row(), row(), row('00B', line='LINE-B'),
                row('00C', series=None, amount='-1'), row('00D', unit='SET', amount='7')]
        materials = [{'pn_key':'00A','zmodel':'PLATE','source_present':True},
                     {'pn_key':'00B','zmodel':'PLATE','source_present':True},
                     {'pn_key':'00C','zmodel':' ','source_present':True}]
        joined = drilldown.attach_nameplates(rows, materials)
        self.assertEqual(len(joined), len(rows))
        self.assertEqual([r['nameplate'] for r in joined], ['PLATE','PLATE','PLATE',None,None])
        self.assertEqual(drilldown.aggregate(joined, []), {('PCS',):Decimal('6.5'), ('SET',):Decimal('7')})
        for dims in [('product_line_code',), ('product_line_code','model_series_code'),
                     ('product_line_code','model_series_code','nameplate','power_kw','pn','country_name')]:
            child = drilldown.aggregate(joined, dims)
            for unit in ('PCS','SET'):
                self.assertEqual(sum(v for k,v in child.items() if k[-1] == unit),
                                 drilldown.aggregate(rows, [])[unit,])
        self.assertEqual(drilldown.aggregate(joined, ['product_line_code','model_series_code'])['LINE-A','SHARED','PCS'], Decimal('5'))
        # Fold the deepest children back to EACH parent, not just a grand total.
        deepest = drilldown.aggregate(joined, ['product_line_code','model_series_code','nameplate','power_kw','pn'])
        for parent_dims in [('product_line_code',), ('product_line_code','model_series_code')]:
            folded = {}
            for key, amount in deepest.items():
                parent_key = key[:len(parent_dims)] + (key[-1],)
                folded[parent_key] = folded.get(parent_key, Decimal(0)) + amount
            self.assertEqual(folded, drilldown.aggregate(joined, parent_dims))


    def test_same_period_country_unit_filters_reconcile_at_each_level(self):
        rows = [row(amount='3'), row('00B', line='LINE-B', amount='4'),
                {**row(), 'date':'2026-10-01'},
                {**row(), 'country_name':'SYNTHETIC-COUNTRY'}, row(unit='SET')]
        selected = [r for r in rows if '2026-09-01' <= r['date'] < '2026-10-01'
                    and r['country_name']=='通用' and r['sales_unit']=='PCS']
        joined = drilldown.attach_nameplates(selected, [])
        parent = drilldown.aggregate(joined, [])['PCS',]
        self.assertEqual(parent, Decimal('7'))
        for dims in [('product_line_code',), ('product_line_code','model_series_code'),
                     ('product_line_code','model_series_code','nameplate','power_kw','pn')]:
            self.assertEqual(sum(drilldown.aggregate(joined, dims).values()), parent)

    def test_join_keys_are_full_normalized_text_and_conflicts_fail(self):
        self.assertEqual(drilldown.pn_key(' 00a '), '00A')
        self.assertNotEqual(drilldown.pn_key('00A'), drilldown.pn_key('0A'))
        with self.assertRaises(ValueError):
            drilldown.attach_nameplates([row()], [{'pn_key':k,'source_present':True} for k in ['00a',' 00A ']])
        with self.assertRaises(ValueError):
            drilldown.aggregate([row()], ['model_series_code'])

    def test_optional_filter_is_explicit_and_month_gaps_are_not_zero(self):
        rows = drilldown.attach_nameplates([row(), row('00B')], [{'pn_key':'00A','zmodel':'P','source_present':True}])
        selected = [r for r in rows if r['nameplate']=='P']
        self.assertEqual(drilldown.aggregate(selected, []), {('PCS',):Decimal('2.5')})
        self.assertEqual(len(drilldown.aggregate(rows, ['date'])), 1)
        self.assertNotIn(('2026-08-01','PCS'), drilldown.aggregate(rows, ['date']))
        for amount in (2.5, True, 'NaN'):
            with self.assertRaises(ValueError):
                drilldown.aggregate([row(amount=amount)], [])


if __name__ == '__main__':
    unittest.main()
