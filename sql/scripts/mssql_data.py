"""Fixed read-only datasets for the existing intranet SQL Server delivery table."""
import datetime
from decimal import Decimal
import os
import re


def connect(profile):
    import query
    query.load_local_env()
    # Credentials are loaded only from the host's existing environment / excluded .env.
    import pymssql
    user=os.environ.get(profile.get('user_env','OA_USER'))
    password=os.environ.get(profile.get('password_env','OA_PWD'))
    if not user or not password:
        raise ValueError('Missing intranet SQL credentials; configure this computer, do not copy cloud Auth')
    return pymssql.connect(server=os.environ.get(profile.get('host_env','OA_HOST'),'10.5.5.163'),
        port=int(os.environ.get(profile.get('port_env','OA_PORT'),'1433')),user=user,password=password,
        database=profile.get('database','oa_report'),charset='UTF-8',as_dict=True,
        timeout=profile.get('timeout_seconds',30),login_timeout=15,autocommit=False)


def coverage(profile):
    scope=profile.get('delivery_scope',{})
    if not {'from_month','through_month','sales_unit'}<=set(scope) or scope['sales_unit'] not in ('PCS','UNSPECIFIED'):
        raise ValueError('rd_delivery requires a discovered month scope and explicit unit status')
    if scope['sales_unit']=='PCS' and scope.get('unit_verified') is not True:
        raise ValueError('Only a reconciled PCS scope may be labelled PCS')
    for field in ('from_month','through_month'):
        if not re.fullmatch(r'\d{4}-\d{2}-01',scope[field]):raise ValueError('Scope months must be YYYY-MM-01')
        datetime.date.fromisoformat(scope[field])
    if scope['from_month']>scope['through_month']:raise ValueError('Invalid delivery scope')
    return scope


def base_query(q,profile):
    dataset=q['dataset']
    if dataset=='material':
        pairs={'matnr':'MATNR','pn_key':'UPPER(LTRIM(RTRIM(MATNR)))','maktx':'MAKTX','matkl':'MATKL',
          'wgbez':'WGBEZ','mtart':'MTART','mstae':'MSTAE','zcpx':'ZCPX','cpx_txt':'CPX_TXT','zjxxl':'ZJXXL',
          'jxxl_txt':'JXXL_TXT','zcpfl':'ZCPFL','cpfl_txt':'CPFL_TXT','zcpxl':'ZCPXL','cpxl_txt':'CPXL_TXT',
          'zcpxf':'ZCPXF','cpxf_txt':'CPXF_TXT','cpxh':'CPXH','zmodel':'ZMODEL','zgl':'ZGL','ersda':'ERSDA','laeda':'LAEDA',
          'synced_at':'CAST(NULL AS datetimeoffset)','source_present':'CAST(1 AS bit)'}
        return 'SELECT '+','.join(v+' AS ['+k+']' for k,v in pairs.items())+' FROM dbo.sap_material',[]
    if dataset not in ('shipment_monthly','shipment_monthly_including_housing','delivery_by_pn_month','delivery_by_pn_month_including_housing'):
        raise ValueError('Intranet rd_delivery has monthly totals only; use delivery_by_pn_month for PN/country. Daily detail and material_sync require an explicit local/cloud profile')
    scope=coverage(profile)
    for f in q['filters']:
        if f['column']!='month' or f['op']=='isnull':continue
        values=f['value'] if f['op']=='in' else [f['value']]
        for value in values:
            if f['op']=='lt':
                end=datetime.date.fromisoformat(scope['through_month']);end=(end.replace(day=28)+datetime.timedelta(days=4)).replace(day=1)
                if value>end.isoformat():raise ValueError('Requested months exceed intranet coverage '+scope['from_month']+' through '+scope['through_month'])
            elif value<scope['from_month'] or value>scope['through_month']:
                raise ValueError('Requested months exceed intranet coverage '+scope['from_month']+' through '+scope['through_month']+'; explicit local/cloud may have another scope')
    for f in q['filters']:
        if f['column']=='sales_unit' and scope['sales_unit']=='UNSPECIFIED':
            raise ValueError('rd_delivery has no unit column; legacy units are unverified. Remove the unit filter to inspect legacy totals, or use explicit local/cloud for PCS')
    args=[scope['from_month'],scope['through_month']]
    unit=scope['sales_unit']
    where="m.MTART='Z001' AND DATEFROMPARTS(d.zyear,d.zmonth,1) BETWEEN %s AND %s"
    if not dataset.endswith('_including_housing'):where+=" AND (m.ZJXXL IS NULL OR m.ZJXXL<>'Z0090')"
    month='DATEFROMPARTS(d.zyear,d.zmonth,1)'
    if dataset.startswith('shipment_monthly'):
        return ("SELECT "+month+" AS [month],m.ZCPX AS product_line_code,m.CPX_TXT AS product_line,'"+unit+"' AS sales_unit,"
          "SUM(d.doqty) AS amount,CAST(NULL AS bigint) AS source_rows FROM dbo.rd_delivery d "
          "JOIN dbo.sap_material m ON m.MATNR=d.matnr WHERE "+where+' GROUP BY '+month+',m.ZCPX,m.CPX_TXT'),args
    return ("SELECT "+month+" AS [month],d.matnr AS pn,d.country AS country_name,'"+unit+"' AS sales_unit,d.doqty AS amount,"
      "m.ZCPX AS product_line_code,m.CPX_TXT AS product_line,m.ZJXXL AS model_series_code,m.JXXL_TXT AS model_series "
      "FROM dbo.rd_delivery d JOIN dbo.sap_material m ON m.MATNR=d.matnr WHERE "+where),args


def sql_for(q,profile):
    base,args=base_query(q,profile)
    clauses=[]
    for f in q['filters']:
        col='['+f['column']+']';op=f['op'];value=f['value']
        if op=='isnull':clauses.append(col+(' IS NULL' if value else ' IS NOT NULL'))
        elif op=='in':
            clauses.append(col+' IN ('+','.join('%s' for _ in value)+')');args+=value
        else:clauses.append(col+{'eq':'=','gt':'>','gte':'>=','lt':'<','lte':'<='}[op]+'%s');args.append(value)
    filtered='WITH dataset AS ('+base+'), filtered AS (SELECT * FROM dataset'+(' WHERE '+' AND '.join(clauses) if clauses else '')+') '
    ordering=','.join('CASE WHEN ['+o['column']+'] IS NULL THEN 1 ELSE 0 END,['+o['column']+'] '+o['direction'].upper() for o in q['order'])
    selected=','.join('['+c+']' for c in q['columns'])
    page=filtered+'SELECT '+selected+',COUNT_BIG(*) OVER() AS __total FROM filtered ORDER BY '+ordering+' OFFSET %s ROWS FETCH NEXT %s ROWS ONLY'
    return page,args+[q['offset'],q['limit']],filtered+'SELECT COUNT_BIG(*) AS n FROM filtered',args


def run(q,profile):
    conn=connect(profile)
    try:
        cur=conn.cursor()
        effective=dict(profile)
        if q['dataset']!='material':
            cur.execute('SELECT MIN(DATEFROMPARTS(zyear,zmonth,1)) AS first_month,MAX(DATEFROMPARTS(zyear,zmonth,1)) AS last_month FROM dbo.rd_delivery')
            limits=cur.fetchone()
            if not limits['first_month']:raise ValueError('rd_delivery has no visible coverage')
            scope=dict(profile.get('delivery_scope',{'sales_unit':'UNSPECIFIED'}))
            scope.setdefault('sales_unit','UNSPECIFIED')
            scope.setdefault('from_month',limits['first_month'].isoformat());scope.setdefault('through_month',limits['last_month'].isoformat())
            effective['delivery_scope']=scope
        sql,args,count_sql,count_args=sql_for(q,effective)
        cur.execute(sql,tuple(args));rows=cur.fetchall()
        if rows:total=rows[0]['__total']
        else:cur.execute(count_sql,tuple(count_args));total=cur.fetchone()['n']
        for row in rows:
            row.pop('__total',None)
            for key,value in row.items():
                if isinstance(value,(datetime.date,datetime.datetime)):row[key]=value.isoformat()
                if q['data']['columns'][key]=='boolean' and value is not None:row[key]=bool(value)
        return {'rows':rows,'total':int(total),'source_coverage':effective.get('delivery_scope'),'unit_verified':effective.get('delivery_scope',{}).get('unit_verified',False)}
    finally:
        conn.rollback();conn.close()
