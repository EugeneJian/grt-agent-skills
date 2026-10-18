#!/usr/bin/env python3
"""Agent-neutral, read-only dataset queries over PostgreSQL or Supabase Data API."""
import argparse
import base64
import datetime
import decimal
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import api_session

ROOT=Path(__file__).resolve().parents[1]
class QueryError(ValueError):pass
def reject_constant(value):raise QueryError('Non-finite JSON numbers are not allowed')
def loads(value):return json.loads(value,parse_float=decimal.Decimal,parse_constant=reject_constant)
def json_text(value):return json.dumps(value,ensure_ascii=False,default=lambda x:format(x,'f') if isinstance(x,decimal.Decimal) else str(x))
def read_json(path):return loads(Path(path).expanduser().read_text(encoding='utf-8-sig'))

def configured_profile(config,name):
    if not isinstance(config,dict) or not isinstance(config.get('profiles'),dict):raise QueryError('Invalid profile configuration')
    profile=config['profiles'].get(name)
    if not isinstance(profile,dict):raise QueryError('Unknown profile; use --list-profiles')
    if {'password','token','jwt','apikey','service_role_key'} & set(profile):raise QueryError('Profile contains a credential; use external secret storage or environment variables')
    if profile.get('engine') not in ('postgres','supabase_api'):raise QueryError('Unsupported profile engine')
    return profile

def catalog():
    raw=read_json(ROOT/'references/datasets.json');result={}
    for name,item in raw.items():
        result[name]={**raw.get(item.get('inherits'),{}),**item}
    return result

def value_of(value,kind):
    if kind in ('text','date','timestamp'):
        if not isinstance(value,str) or len(value)>2048 or '\x00' in value:raise QueryError('Invalid string filter')
        if kind=='date':
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise QueryError('Use date YYYY-MM-DD')
            datetime.date.fromisoformat(value)
        if kind=='timestamp':
            if datetime.datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo is None:raise QueryError('Timestamp requires a timezone')
        return value
    if kind=='number':
        if isinstance(value,bool):raise QueryError('Boolean is not a numeric filter')
        num=decimal.Decimal(str(value))
        if not num.is_finite():raise QueryError('Invalid numeric filter')
        return num
    if kind=='boolean' and isinstance(value,bool):return value
    raise QueryError('Invalid filter type')

def normalize(spec,profile):
    if not isinstance(spec,dict) or set(spec)-{'dataset','select','filters','order','limit','offset'}:raise QueryError('Unsupported query fields')
    if not isinstance(spec.get('dataset'),str):raise QueryError('dataset must be a name')
    data=catalog().get(spec.get('dataset'))
    if data is None:raise QueryError('Unknown dataset; see references/datasets.json')
    columns=spec.get('select',list(data['columns']))
    if not isinstance(columns,list) or not columns or any(not isinstance(c,str) or c not in data['columns'] for c in columns) or len(columns)!=len(set(columns)):raise QueryError('Unknown or duplicate selected columns')
    max_rows=profile.get('max_rows',1000)
    if type(max_rows) is not int or not 1<=max_rows<=10000:raise QueryError('max_rows must be an integer from 1-10000')
    limit=spec.get('limit',min(500,max_rows));offset=spec.get('offset',0)
    cap=max_rows
    if type(limit) is not int or not 1<=limit<=cap or type(offset) is not int or offset<0:raise QueryError('Invalid result limit or offset')
    filters=spec.get('filters',[])
    if not isinstance(filters,list) or len(filters)>30:raise QueryError('Too many filters')
    normalized=[]
    for f in filters:
        if not isinstance(f,dict) or set(f)!={'column','op','value'} or not isinstance(f['column'],str) or f['column'] not in data['columns'] or not isinstance(f['op'],str):raise QueryError('Invalid filter column or fields')
        op=f['op'];kind=data['columns'][f['column']]
        if op=='in':
            if not isinstance(f['value'],list) or not 1<=len(f['value'])<=100:raise QueryError('IN requires 1-100 values')
            value=[value_of(v,kind) for v in f['value']]
        elif op=='isnull':
            if type(f['value']) is not bool:raise QueryError('isnull expects true or false')
            value=f['value']
        elif op in ('eq','gt','gte','lt','lte'):value=value_of(f['value'],kind)
        else:raise QueryError('Unsupported filter operator')
        normalized.append({'column':f['column'],'op':op,'value':value})
    order=spec.get('order',[{'column':c,'direction':'asc'} for c in data['order'] if c in columns])
    if not isinstance(order,list) or any(not isinstance(o,dict) or set(o)!={'column','direction'} or o['column'] not in columns or o['direction'] not in ('asc','desc') for o in order):raise QueryError('Order columns must be selected columns, direction asc/desc')
    # Complete ties with selected fields. Identical result rows remain repeated.
    order=order+[{'column':c,'direction':'asc'} for c in columns if c not in [o['column'] for o in order]]
    return {'dataset':spec['dataset'],'data':data,'columns':columns,'filters':normalized,'order':order,'limit':limit,'offset':offset}

def ident(value):
    if not re.fullmatch(r'[a-z_][a-z_0-9]*',value):raise QueryError('Invalid catalog identifier')
    return '"'+value+'"'
def literal(value):
    if isinstance(value,bool):return 'TRUE' if value else 'FALSE'
    if isinstance(value,decimal.Decimal):return format(value,'f')
    return "'"+value.replace("'","''")+"'"

def pg_sql(q):
    cols=','.join(ident(c) for c in q['columns']);where=[]
    for f in q['filters']:
        col=ident(f['column']);op=f['op'];v=f['value']
        if op=='isnull':where.append(col+(' IS NULL' if v else ' IS NOT NULL'))
        elif op=='in':where.append(col+' IN ('+','.join(literal(x) for x in v)+')')
        else:where.append(col+{'eq':'=','gt':'>','gte':'>=','lt':'<','lte':'<='}[op]+literal(v))
    ordering=','.join(ident(o['column'])+' '+o['direction'].upper()+' NULLS LAST' for o in q['order'])
    order=(' ORDER BY '+ordering) if ordering else ''
    aggregate_order=(','.join('p.'+ident(o['column'])+' '+o['direction'].upper()+' NULLS LAST' for o in q['order']))
    aggregate_order=(' ORDER BY '+aggregate_order) if aggregate_order else ''
    relation='.'.join(ident(x) for x in q['data']['relation'].split('.'))
    return (f'WITH filtered AS (SELECT {cols} FROM {relation}'+(' WHERE '+' AND '.join(where) if where else '')+
        f'), page AS (SELECT * FROM filtered{order} LIMIT {q["limit"]} OFFSET {q["offset"]}) '+
        "SELECT jsonb_build_object('rows',COALESCE((SELECT jsonb_agg(to_jsonb(p)"+aggregate_order+
        ") FROM page p),'[]'::jsonb),'total',(SELECT count(*) FROM filtered))::text;")

def pg_connection(profile):
    allowed={'host','port','dbname','user','sslmode','sslrootcert','connect_timeout'}
    conn=profile.get('connection',{})
    if not isinstance(conn,dict) or set(conn)-allowed:raise QueryError('Only non-secret PostgreSQL connection metadata belongs in the profile')
    parts={'service':profile['service']} if profile.get('service') else {}
    parts.update(conn)
    if not parts:raise QueryError('Set a PostgreSQL service or connection profile')
    local=str(parts.get('host','')).startswith('/')
    parts.setdefault('sslmode','disable' if local else 'verify-full');parts.setdefault('connect_timeout','10')
    if not local and parts['sslmode']!='verify-full':raise QueryError('Network PostgreSQL profiles require sslmode=verify-full')
    def quote(v):return "'"+str(v).replace('\\','\\\\').replace("'","\\'")+"'"
    return ' '.join(k+'='+quote(v) for k,v in parts.items())

def timeout_of(profile):
    value=profile.get('timeout_seconds',30)
    if type(value) is not int or not 1<=value<=120:raise QueryError('timeout_seconds must be an integer from 1-120')
    return value

def run_postgres(q,profile):
    psql=profile.get('psql_path') or shutil.which('psql')
    if not psql or not Path(psql).is_file():raise QueryError('psql not found; install a PostgreSQL client or set psql_path')
    timeout=timeout_of(profile)
    env=os.environ.copy()
    env['PGOPTIONS']=f'-c default_transaction_read_only=on -c standard_conforming_strings=on -c statement_timeout={timeout*1000} -c lock_timeout=3000'
    env['PGAPPNAME']='company-sql-skill'
    args=[psql,'-X','-q','-w','-A','-t','-v','ON_ERROR_STOP=1','--dbname',pg_connection(profile),'--command',pg_sql(q)]
    try:p=subprocess.run(args,capture_output=True,text=True,env=env,timeout=timeout+12)
    except subprocess.TimeoutExpired:raise QueryError('PostgreSQL query timed out')
    if p.returncode:raise QueryError('PostgreSQL query failed: '+p.stderr.strip())
    try:return loads(p.stdout)
    except (ValueError,decimal.InvalidOperation):raise QueryError('Unexpected PostgreSQL result')

def jwt_role(value):
    try:
        token=value.split('.')[1];return json.loads(base64.urlsafe_b64decode(token+'='*(-len(token)%4))).get('role')
    except Exception:return None

def api_parameters(q):
    params=[('select',','.join(q['columns']))]
    for f in q['filters']:
        v=f['value'];op=f['op']
        if op=='isnull':value='is.null' if v else 'not.is.null'
        elif op=='in':
            def quoted(x):
                if isinstance(x,bool):return str(x).lower()
                if isinstance(x,decimal.Decimal):return format(x,'f')
                return '"'+x.replace('\\','\\\\').replace('"','\\"')+'"'
            value='in.('+','.join(quoted(x) for x in v)+')'
        else:value=op+'.'+(str(v).lower() if isinstance(v,bool) else str(v))
        params.append((f['column'],value))
    if q['order']:params.append(('order',','.join(o['column']+'.'+o['direction']+'.nullslast' for o in q['order'])))
    params += [('limit',str(q['limit'])),('offset',str(q['offset']))]
    return params

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):raise QueryError('API redirects are refused to protect authorization headers')

def run_api(q,profile):
    timeout=timeout_of(profile)
    base=profile.get('url') or os.environ.get(profile.get('url_env','COMPANY_SUPABASE_URL'),'')
    parsed=urllib.parse.urlsplit(base)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise QueryError('Supabase URL must be an HTTPS project origin')
    key,token=api_session.credentials(profile,base)
    if not key or not token:raise QueryError('Missing API key or employee/read-only JWT; set the profile environment variables')
    allowed_roles=profile.get('allowed_jwt_roles',['authenticated'])
    if not isinstance(allowed_roles,list) or not allowed_roles or any(not isinstance(r,str) for r in allowed_roles):raise QueryError('allowed_jwt_roles must be a nonempty role list')
    privileged={'service_role','supabase_admin','postgres','anon'}
    if key.startswith('sb_secret_') or jwt_role(key) not in (None,'anon') or jwt_role(token) in privileged:
        raise QueryError('Administrative or service_role credentials are not accepted by this query client')
    if jwt_role(token) not in allowed_roles:raise QueryError('JWT role is not permitted by this profile; use an employee/read-only identity')
    schema=profile.get('api_schema','agent_api')
    ident(schema);resource=q['data']['api_resource'];ident(resource)
    url=base.rstrip('/')+'/rest/v1/'+resource+'?'+urllib.parse.urlencode(api_parameters(q))
    request=urllib.request.Request(url,method='GET',headers={'apikey':key,'Authorization':'Bearer '+token,'Accept-Profile':schema,'Prefer':'count=exact','Accept':'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=timeout) as response:
            rows=loads(response.read().decode('utf-8'));content_range=response.headers.get('Content-Range','')
    except urllib.error.HTTPError as exc:raise QueryError(f'Data API returned HTTP {exc.code}; check API publication, employee authorization and RLS')
    except (urllib.error.URLError,TimeoutError):raise QueryError('Data API connection failed; check DNS, TLS and network reachability')
    if not isinstance(rows,list):raise QueryError('Unexpected Data API response')
    total=content_range.rsplit('/',1)[-1]
    if not total.isdigit():raise QueryError('Data API did not return the requested exact result count')
    return {'rows':rows,'total':int(total)}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query',nargs='?',help='Query JSON or @path.json; stdin also accepted')
    parser.add_argument('--config',default=os.environ.get('COMPANY_SQL_CONFIG',str(Path.home()/'.config/company-sql/profiles.json')))
    parser.add_argument('--profile')
    parser.add_argument('--list-profiles',action='store_true')
    args=parser.parse_args(argv)
    try:
        config=read_json(args.config)
        if not isinstance(config,dict) or not isinstance(config.get('profiles'),dict):raise QueryError('Invalid profile configuration')
        if args.list_profiles:
            print(json_text({name:p['engine'] for name,p in config['profiles'].items()}));return 0
        name=args.profile or config.get('default_profile');profile=configured_profile(config,name)
        if args.query is None and sys.stdin.isatty():raise QueryError('Provide query JSON, @path.json or stdin')
        raw=Path(args.query[1:]).read_text(encoding='utf-8-sig') if args.query and args.query.startswith('@') else args.query or sys.stdin.read()
        q=normalize(loads(raw),profile);start=time.perf_counter()
        if profile['engine']=='postgres':result=run_postgres(q,profile)
        elif profile['engine']=='supabase_api':result=run_api(q,profile)
        else:raise QueryError('Unsupported profile engine')
        if not isinstance(result['rows'],list) or len(result['rows'])>q['limit'] or type(result['total']) is not int or result['total']<0:raise QueryError('Invalid result size or count')
        answer={'profile':name,'dataset':q['dataset'],'rows':result['rows'],'returned_rows':len(result['rows']),
            'total_rows':result['total'],'offset':q['offset'],'has_more':q['offset']+len(result['rows'])<result['total'],
            'elapsed_ms':round((time.perf_counter()-start)*1000,1)}
        print(json_text(answer));return 0
    except (QueryError,ValueError,KeyError,OSError,decimal.InvalidOperation) as exc:
        print('query_data: '+str(exc),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
