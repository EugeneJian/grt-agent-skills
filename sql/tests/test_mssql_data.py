import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import query_data as client
import mssql_data as data

class IntranetContracts(unittest.TestCase):
    def setUp(self):
        self.profile={'engine':'mssql_rd_delivery','delivery_scope':{'from_month':'2026-01-01','through_month':'2026-09-01','sales_unit':'UNSPECIFIED'}}
    def q(self,spec):return client.normalize(spec,self.profile)
    def test_native_totals_never_invent_unit_or_source_count(self):
        sql,args,_,_=data.sql_for(self.q({'dataset':'shipment_monthly'}),self.profile)
        self.assertIn("'UNSPECIFIED' AS sales_unit",sql)
        self.assertIn('CAST(NULL AS bigint) AS source_rows',sql)
        self.assertIn("m.ZJXXL IS NULL OR m.ZJXXL<>'Z0090'",sql)
        self.assertEqual(args[:2],['2026-01-01','2026-09-01'])
    def test_values_are_bound_not_sql(self):
        value="PN'; DELETE FROM x;--"
        sql,args,_,_=data.sql_for(self.q({'dataset':'delivery_by_pn_month','filters':[{'column':'pn','op':'eq','value':value}]}),self.profile)
        self.assertNotIn(value,sql);self.assertIn(value,args)
    def test_unverified_unit_cannot_be_filtered_as_pcs(self):
        with self.assertRaisesRegex(ValueError,'no unit'):
            data.sql_for(self.q({'dataset':'shipment_monthly','filters':[{'column':'sales_unit','op':'eq','value':'PCS'}]}),self.profile)
    def test_coverage_error_is_not_zero_data(self):
        with self.assertRaisesRegex(ValueError,'coverage'):
            data.sql_for(self.q({'dataset':'shipment_monthly','filters':[{'column':'month','op':'gte','value':'2027-01-01'}]}),self.profile)
    def test_day_detail_is_not_fabricated(self):
        with self.assertRaisesRegex(ValueError,'monthly totals only'):
            data.sql_for(self.q({'dataset':'shipment_detail'}),self.profile)
    def test_housing_only_when_requested(self):
        sql,_,_,_=data.sql_for(self.q({'dataset':'shipment_monthly_including_housing'}),self.profile)
        self.assertNotIn('Z0090',sql)
    def test_pcs_needs_verification(self):
        self.profile['delivery_scope']['sales_unit']='PCS'
        with self.assertRaisesRegex(ValueError,'reconciled PCS'):
            data.sql_for(self.q({'dataset':'shipment_monthly'}),self.profile)
    def test_material_is_live_source_not_fake_snapshot(self):
        sql,_,_,_=data.sql_for(self.q({'dataset':'material'}),self.profile)
        self.assertIn('FROM dbo.sap_material',sql)
        self.assertIn('CAST(NULL AS datetimeoffset) AS [synced_at]',sql)

if __name__=='__main__':unittest.main()
