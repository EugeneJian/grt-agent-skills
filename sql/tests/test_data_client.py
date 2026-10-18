"""Synthetic transport contract fixtures; HTTP is mocked, not a live cloud test."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import tempfile
import time

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
import query_data as client
import compare_profiles as compare
import api_session
import auth_login
import auth_callback


def jwt(role):
    payload = base64.urlsafe_b64encode(json.dumps({'role': role}).encode()).decode().rstrip('=')
    return 'test.' + payload + '.signature'


class Response(io.BytesIO):
    def __init__(self, rows, count):
        super().__init__(json.dumps(rows).encode())
        self.headers = {'Content-Range': count}


class ClientTests(unittest.TestCase):
    def query(self, **fields):
        return client.normalize({'dataset': 'shipment_monthly', **fields}, {})

    def test_rejects_sql_and_unknown_columns(self):
        for spec in ({'sql': 'select 1'}, {'select': ['amount;drop table x']},
                     {'select': [['amount']]}, {'dataset': {}},
                     {'filters': [{'column': [], 'op': 'eq', 'value': 1}]}):
            with self.subTest(spec=spec), self.assertRaises(client.QueryError):
                self.query(**spec)

    def test_invalid_filter_values(self):
        for column, op, value in [('month','gte','2026-02-30'),('amount','eq',True),
                                  ('amount','eq','NaN'),('product_line','in',[]),
                                  ('product_line','eq',None),('month','isnull','true')]:
            with self.subTest(value=value), self.assertRaises((ValueError, client.decimal.InvalidOperation)):
                self.query(filters=[{'column':column,'op':op,'value':value}])

    def test_limits_are_enforced(self):
        for spec in ({'limit': 1001}, {'offset': -1}, {'limit': True}):
            with self.assertRaises(client.QueryError):
                self.query(**spec)

    def test_pg_text_is_one_escaped_literal(self):
        value = "A'\\; DROP TABLE shipping.shipment_facts;--"
        sql = client.pg_sql(self.query(filters=[{'column':'product_line','op':'eq','value':value}]))
        self.assertIn("\"product_line\"='A''\\; DROP TABLE shipping.shipment_facts;--'", sql)
        self.assertNotIn('SELECT DISTINCT', sql)

    def test_api_repeated_filters_and_quoted_in(self):
        q = self.query(filters=[{'column':'month','op':'gte','value':'2026-01-01'},
                               {'column':'month','op':'lt','value':'2026-10-01'},
                               {'column':'product_line','op':'in','value':['A,B','C"D','E\\F']}])
        pairs = client.api_parameters(q)
        self.assertEqual([v for k,v in pairs if k == 'month'], ['gte.2026-01-01','lt.2026-10-01'])
        self.assertIn(('product_line', 'in.("A,B","C\\"D","E\\\\F")'), pairs)

    def test_pg_service_and_tls(self):
        conn = client.pg_connection({'service':'company_shipping_ro', 'connection':{'sslrootcert':'/company/ca.pem'}})
        self.assertIn("service='company_shipping_ro'", conn)
        self.assertIn("sslmode='verify-full'", conn)
        self.assertIn("sslrootcert='/company/ca.pem'", conn)
        with self.assertRaises(client.QueryError):
            client.pg_connection({'connection':{'host':'example.com','sslmode':'disable'}})
        with self.assertRaises(client.QueryError):
            client.pg_connection({'connection':{'password':'not-allowed'}})

    def test_inline_credentials_refused(self):
        with self.assertRaises(client.QueryError):
            client.configured_profile({'profiles':{'x':{'engine':'supabase_api','jwt':'secret'}}}, 'x')

    def test_api_missing_auth_and_admin_rejected(self):
        profile = {'url':'https://project.example'}
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(client.QueryError):
            client.run_api(self.query(), profile)
        for key, token in [('sb_secret_test',jwt('authenticated')),('publishable',jwt('service_role')),
                           ('publishable',jwt('postgres')),('publishable',jwt('anon'))]:
            with patch.dict(os.environ, {'COMPANY_SUPABASE_API_KEY':key,'COMPANY_SUPABASE_USER_JWT':token}, clear=True):
                with self.assertRaises(client.QueryError):
                    client.run_api(self.query(), profile)

    def test_redirect_refused(self):
        with self.assertRaises(client.QueryError):
            client.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example')

    def test_http_contract_and_exact_count(self):
        rows = [{'month':'2026-09-01','amount':123}]
        with patch.dict(os.environ, {'COMPANY_SUPABASE_API_KEY':'sb_publishable_test',
                                    'COMPANY_SUPABASE_USER_JWT':jwt('authenticated')}, clear=True):
            with patch.object(client.urllib.request,'build_opener') as factory:
                factory.return_value.open.return_value = Response(rows, '0-0/1')
                q = self.query(select=['month','amount'])
                result = client.run_api(q, {'url':'https://project.example','api_schema':'agent_api'})
                request = factory.return_value.open.call_args.args[0]
                self.assertEqual(request.method, 'GET')
                self.assertEqual(request.get_header('Accept-profile'), 'agent_api')
                self.assertEqual(request.get_header('Prefer'), 'count=exact')
                self.assertEqual(result, {'rows':rows,'total':1})
                self.assertTrue(request.full_url.startswith('https://project.example/rest/v1/shipment_monthly?'))
                factory.return_value.open.return_value = Response([], '*/0')
                self.assertEqual(client.run_api(q, {'url':'https://project.example'})['total'], 0)
                factory.return_value.open.return_value = Response([], '*/*')
                with self.assertRaises(client.QueryError):
                    client.run_api(q, {'url':'https://project.example'})

    def test_http_auth_failure_is_not_empty_data(self):
        with patch.dict(os.environ, {'COMPANY_SUPABASE_API_KEY':'publishable',
                                    'COMPANY_SUPABASE_USER_JWT':jwt('authenticated')}, clear=True):
            with patch.object(client.urllib.request,'build_opener') as factory:
                factory.return_value.open.side_effect = urllib.error.HTTPError('https://project.example',403,'denied',{},None)
                with self.assertRaisesRegex(client.QueryError, 'HTTP 403'):
                    client.run_api(self.query(), {'url':'https://project.example'})

    def test_compare_collects_pages_and_preserves_duplicates(self):
        spec = {'dataset':'shipment_monthly','select':['month','amount'],'limit':2}
        row = {'month':'2026-09-01','amount':1}
        with patch.object(client,'run_postgres', side_effect=[{'rows':[row,row],'total':3},{'rows':[row],'total':3}]):
            counts, meta = compare.collect(spec, {'engine':'postgres'}, 2)
            self.assertEqual(meta['rows'], 3)
            self.assertEqual(meta['pages'], 2)
            self.assertEqual(list(counts.values()), [3])

    def test_compare_detects_changing_snapshot_and_page_limit(self):
        spec = {'dataset':'shipment_monthly','limit':1}
        with patch.object(client,'run_postgres', side_effect=[{'rows':[{}],'total':2},{'rows':[{}],'total':3}]):
            with self.assertRaisesRegex(client.QueryError, 'count changed'):
                compare.collect(spec, {'engine':'postgres'}, 2)
        with patch.object(client,'run_postgres', return_value={'rows':[{}],'total':2}):
            with self.assertRaisesRegex(client.QueryError, 'Page limit'):
                compare.collect(spec, {'engine':'postgres'}, 1)

    def test_numeric_comparison_is_exact(self):
        kinds = {'amount':'number','pn':'text'}
        self.assertEqual(compare.canonical({'amount':'1.000','pn':'001'},kinds),
                         compare.canonical({'amount':1,'pn':'001'},kinds))
        self.assertNotEqual(compare.canonical({'amount':1,'pn':'001'},kinds),
                            compare.canonical({'amount':1,'pn':'1'},kinds))

    def test_timestamp_comparison_normalizes_timezone(self):
        kinds = {'source_extracted_at':'timestamp'}
        self.assertEqual(compare.canonical({'source_extracted_at':'2026-10-18T16:23:38+08:00'},kinds),
                         compare.canonical({'source_extracted_at':'2026-10-18T08:23:38Z'},kinds))

    def test_private_session_load_and_project_binding(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{},clear=True):
            profile={'credentials_file':str(Path(folder)/'auth.json')}
            value={'project_url':'https://project.example','apikey':'sb_publishable_test',
                   'access_token':jwt('authenticated'),'refresh_token':'private-refresh'}
            api_session.write_session(profile,value)
            if os.name != 'nt':
                self.assertEqual(Path(profile['credentials_file']).stat().st_mode & 0o777,0o600)
            self.assertEqual(api_session.read_session(profile,'https://project.example'),value)
            with self.assertRaises(api_session.SessionError):
                api_session.read_session(profile,'https://another.example')
            if os.name != 'nt':
                os.chmod(profile['credentials_file'],0o644)
                with self.assertRaises(api_session.SessionError):
                    api_session.read_session(profile,'https://project.example')

    def test_refresh_rotates_session_without_saving_password(self):
        def token(exp):
            body=base64.urlsafe_b64encode(json.dumps({'role':'authenticated','exp':exp}).encode()).decode().rstrip('=')
            return 'test.'+body+'.signature'
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{},clear=True):
            profile={'credentials_file':str(Path(folder)/'auth.json')}
            api_session.write_session(profile,{'project_url':'https://project.example','apikey':'sb_publishable_test',
                                               'access_token':token(0),'refresh_token':'old-refresh'})
            refreshed={'access_token':token(time.time()+3600),'refresh_token':'new-refresh',
                       'user':{'id':'reader-id','email':'reader@agent.invalid'}}
            with patch.object(api_session,'auth_token',return_value=refreshed) as request:
                key,access=api_session.credentials(profile,'https://project.example')
                request.assert_called_once_with('https://project.example','sb_publishable_test','refresh_token',{'refresh_token':'old-refresh'})
                self.assertEqual(access,refreshed['access_token'])
                # A second caller reuses the refreshed token rather than rotating again.
                api_session.credentials(profile,'https://project.example')
                self.assertEqual(request.call_count,1)
            saved=api_session.read_session(profile,'https://project.example')
            self.assertEqual(saved['refresh_token'],'new-refresh')
            self.assertNotIn('password',saved)
            self.assertFalse(Path(profile['credentials_file']+'.refresh-lock').exists())

    def test_explicit_environment_session_does_not_borrow_local_session(self):
        with patch.dict(os.environ,{'COMPANY_SUPABASE_API_KEY':'publishable','COMPANY_SUPABASE_USER_JWT':'explicit-token'},clear=True):
            with patch.object(api_session,'read_session') as local:
                self.assertEqual(api_session.credentials({},'https://project.example'),('publishable','explicit-token'))
                local.assert_not_called()

    def test_email_proof_is_project_bound(self):
        base='https://project.example'
        self.assertEqual(auth_login.email_proof(base,'reader@company.example','123456'),
                         {'email':'reader@company.example','token':'123456','type':'email'})
        self.assertEqual(auth_login.email_proof(base,'reader@company.example',base+'/auth/v1/verify?token=opaque&type=magiclink'),
                         {'token_hash':'opaque','type':'magiclink'})
        for bad in ('https://other.example/auth/v1/verify?token=x',base+'/not-verify?token=x'):
            with self.assertRaises(ValueError):
                auth_login.email_proof(base,'reader@company.example',bad)

    def test_auth_rejects_admin_key_before_network(self):
        with patch.object(api_session.urllib.request,'build_opener') as network:
            with self.assertRaises(api_session.SessionError):
                api_session.auth_request('https://project.example','sb_secret_admin','/otp',{'email':'reader@example.com'})
            network.assert_not_called()

    def test_callback_saves_only_verified_matching_employee(self):
        session={'access_token':jwt('authenticated'),'refresh_token':'rotated-refresh',
                 'user':{'id':'reader-id','email':'reader@company.example','email_confirmed_at':'2026-10-18T00:00:00Z'}}
        with patch.object(api_session,'auth_token',return_value=session), patch.object(api_session,'write_session') as save:
            auth_callback.complete_session({},'https://project.example','publishable','reader@company.example','original-refresh')
            self.assertEqual(save.call_args.args[1]['refresh_token'],'rotated-refresh')
            self.assertEqual(save.call_args.args[1]['email'],'reader@company.example')
            save.reset_mock()
            with self.assertRaises(ValueError):
                auth_callback.complete_session({},'https://project.example','publishable','another@company.example','original-refresh')
            save.assert_not_called()
            session['user']['email_confirmed_at']=None
            with self.assertRaises(ValueError):
                auth_callback.complete_session({},'https://project.example','publishable','reader@company.example','original-refresh')
            save.assert_not_called()

    def test_callback_rejects_privileged_session(self):
        session={'access_token':jwt('service_role'),'refresh_token':'rotated-refresh',
                 'user':{'email':'reader@company.example','email_confirmed_at':'2026-10-18T00:00:00Z'}}
        with patch.object(api_session,'auth_token',return_value=session), patch.object(api_session,'write_session') as save:
            with self.assertRaises(ValueError):
                auth_callback.complete_session({},'https://project.example','publishable','reader@company.example','original-refresh')
            save.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
