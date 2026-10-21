#!/usr/bin/env python3
"""Read-only difference preview: validated local PCS totals versus SQL Server rd_delivery."""
import argparse
import csv
from datetime import date,datetime,timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import uuid
import maintenance as maint


def canonical(rows):
    result=[]
    for r in rows:
        result.append([int(r['zyear']),int(r['zmonth']),r['matnr'],r['country'],format(Decimal(str(r['doqty'])).normalize(),'f')])
    return sorted(result)


def digest(rows):
    return hashlib.sha256(maint.text_json(canonical(rows)).encode()).hexdigest()


def months(first,last):
    a=date.fromisoformat(first);b=date.fromisoformat(last)
    if a.day!=1 or b.day!=1 or a>b or (b.year-a.year)*12+b.month-a.month>119:
        raise ValueError('Use month starts and a range of at most 120 months')
    return a.year*100+a.month,b.year*100+b.month


def source(runtime,first,last):
    low,high=months(first,last)
    sql=f"""SELECT coalesce(jsonb_agg(to_jsonb(x)),'[]') FROM (
      SELECT extract(year FROM date)::int zyear,extract(month FROM date)::int zmonth,
      upper(btrim(pn)) matnr,coalesce(nullif(country_name,''),'通用') country,sum(amount)::text doqty
      FROM shipping.shipments WHERE sales_unit='PCS'
      AND extract(year FROM date)*100+extract(month FROM date) BETWEEN {low} AND {high}
      GROUP BY 1,2,3,4) x;"""
    rows=runtime.pg(sql,readonly=True)[0]
    if not rows or len(rows)>100000:raise ValueError('Empty or oversized source scope; narrow the report period')
    # Decimal(18,6) must be exact; never silently truncate codes, countries or quantities.
    for row in rows:
        n=Decimal(row['doqty'])
        if not n.is_finite() or n!=n.quantize(Decimal('0.000001')) or abs(n)>=Decimal('1000000000000'):
            raise ValueError('Quantity cannot be represented exactly in decimal(18,6)')
    return rows


def target(conn,first,last):
    low,high=months(first,last)
    cur=conn.cursor()
    cur.execute('SELECT zyear,zmonth,matnr,country,doqty FROM dbo.rd_delivery'+
                ('')+' WHERE zyear*100+zmonth BETWEEN %s AND %s',(low,high))
    return cur.fetchall()


def modules(runtime):
    import mssql_data
    cfg=maint.load(runtime.config.get('query_config','~/.config/company-sql/profiles.json'))
    profile=runtime.client.configured_profile(cfg,runtime.config.get('intranet_profile','intranet'))
    if profile['engine']!='mssql_rd_delivery':raise ValueError('Configure intranet_profile as mssql_rd_delivery')
    return mssql_data,profile


def check_strings(conn,rows):
    cur=conn.cursor()
    for field,size in [('matnr',18),('country',20)]:
        values=sorted({r[field] for r in rows})
        for start in range(0,len(values),500):
            chunk=values[start:start+500]
            sql='SELECT v.input AS original,CONVERT(nvarchar(max),CONVERT(varchar(max),v.input)) AS roundtrip,DATALENGTH(CONVERT(varchar(max),v.input)) AS size FROM (VALUES '+','.join('(%s)' for _ in chunk)+') v(input)'
            cur.execute(sql,tuple(chunk))
            for item in cur.fetchall():
                if item['roundtrip']!=item['original'] or item['size']>size:
                    raise ValueError('Target varchar cannot preserve '+field+' exactly; no truncation is allowed')
    # SQL Server ignores trailing spaces and uses case-insensitive keys on this deployment.
    keys=[(r['zyear'],r['zmonth'],r['matnr'].rstrip().casefold(),r['country'].rstrip().casefold()) for r in rows]
    if len(set(keys))!=len(keys):raise ValueError('Source keys collide under SQL Server comparison semantics')


def differences(expected,before):
    key=lambda r:(r['zyear'],r['zmonth'],r['matnr'],r['country'])
    left={key(r):Decimal(str(r['doqty'])) for r in expected}
    right={key(r):Decimal(str(r['doqty'])) for r in before}
    result=[]
    for k in sorted(left.keys()|right.keys()):
        status='same' if k in left and k in right and left[k]==right[k] else 'quantity_diff' if k in left and k in right else 'local_only' if k in left else 'target_only'
        result.append({'zyear':k[0],'zmonth':k[1],'pn':k[2],'country':k[3],
          'local_pcs':str(left[k]) if k in left else '', 'intranet_unit_unverified':str(right[k]) if k in right else '',
          'candidate_delta':str(left.get(k,Decimal(0))-right.get(k,Decimal(0))),'status':status})
    return result


def write_report(batch,expected,before,first,last):
    rows=differences(expected,before)
    counts={status:sum(r['status']==status for r in rows) for status in ('same','quantity_diff','local_only','target_only')}
    with (batch/'逐键差异.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for ym in sorted({(r['zyear'],r['zmonth']) for r in rows}):
        group=[r for r in rows if (r['zyear'],r['zmonth'])==ym]
        summary.append({'month':f'{ym[0]:04d}-{ym[1]:02d}',**{status:sum(r['status']==status for r in group) for status in counts},
          'local_pcs_total':str(sum((Decimal(r['local_pcs']) for r in group if r['local_pcs']!=''),Decimal(0))),
          'intranet_unverified_unit_total':str(sum((Decimal(r['intranet_unit_unverified']) for r in group if r['intranet_unit_unverified']!=''),Decimal(0)))})
    with (batch/'按月汇总.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    text=f'''# 内网交货差异报告

仅检查，不写入本机 PostgreSQL、内网 SQL Server 或 Supabase；未更新来源台账、未归档新文件。
比较期间：{first} 至 {last}（含结束月份）。粒度：年月＋完整 PN＋运抵国。

| 项目 | 月度键数 |
|---|---:|
| 本机 PCS 汇总 | {len(expected):,} |
| 内网现有原值 | {len(before):,} |
| 两边数值相同 | {counts['same']:,} |
| 同键数量不同 | {counts['quantity_diff']:,} |
| 仅本机存在 | {counts['local_only']:,} |
| 仅内网存在 | {counts['target_only']:,} |

内网 rd_delivery 没有单位字段，因此数量差异只是“本机 PCS 对旧表原值”的候选比较，不等于已经确认旧数据错误。仅内网存在的键不得自动删除；同键差异不得自动覆盖。

2026 年若内网对应月份为空，则只能说明该表尚未提供这些月的数据，不能解释成公司零出货。按月明细见 [按月汇总.csv](按月汇总.csv)，逐键证据见 [逐键差异.csv](逐键差异.csv)。

本机候选只取 PCS，但包含所有已完成来源的物料类型及机壳，不混入 M/KG/ROL；其他单位与日级来源仍完整保留本机。分析默认另以 sap_material 的 Z001 且机型系列非 Z0090 为口径，不将这张全类型候选总量当作默认成品出货量。

现表 varchar(18) PN、varchar(20) 国家及 decimal(18,6) 已做无损兼容检查。后续同步还须确定期间、单位、旧数据冲突处理及审计方式；本报告没有执行同步。
'''
    (batch/'差异报告.md').write_text(text,encoding='utf-8')
    for path in (batch/'逐键差异.csv',batch/'按月汇总.csv',batch/'差异报告.md'):path.chmod(0o600)
    return counts


def prepare(runtime,first,last):
    expected=source(runtime,first,last)
    module,profile=modules(runtime);conn=module.connect(profile)
    try:
        cur=conn.cursor();cur.execute("SELECT HAS_PERMS_BY_NAME('dbo.rd_delivery','OBJECT','INSERT') AS can_insert,HAS_PERMS_BY_NAME('dbo.rd_delivery','OBJECT','UPDATE') AS can_update")
        permissions=cur.fetchone()

        check_strings(conn,expected)
        before=target(conn,first,last)
    finally:conn.rollback();conn.close()
    key=lambda r:(r['zyear'],r['zmonth'],r['matnr'],r['country'])
    left={key(r):Decimal(str(r['doqty'])) for r in expected};right={key(r):Decimal(str(r['doqty'])) for r in before}

    batch=runtime.batches/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_intranet_'+uuid.uuid4().hex[:8])
    batch.mkdir(parents=True,mode=0o700)
    payload={'version':1,'created_at':maint.now(),'from_month':first,'through_month':last,'sales_unit':'PCS',
       'profile':runtime.config.get('intranet_profile','intranet'),'expected':expected,'target_before':before,
       'expected_sha256':digest(expected),'before_sha256':digest(before),'unit_comparison':'Candidate local PCS versus unverified target unit; not an approved repair','phase':'difference_report_only',
       'insert_rows':len(left.keys()-right.keys()),'update_rows':sum(left[k]!=right[k] for k in right.keys() & left.keys()),
       'unchanged_rows':sum(left[k]==right[k] for k in right.keys() & left.keys()),'target_only_rows':len(right.keys()-left.keys())}
    maint.save(batch/'delivery_diff.json',payload)
    maint.save(batch/'plan_hash.json',{'sha256':maint.checksum(batch/'delivery_diff.json')})
    write_report(batch,expected,before,first,last)
    return {'status':'difference_report_only','batch':str(batch),'monthly_keys':len(expected),
            'insert_rows':payload['insert_rows'],'update_rows':payload['update_rows'],
            'unchanged_rows':payload['unchanged_rows'],'permissions':permissions,'target_only_rows':payload['target_only_rows'],'database_modified':False}



def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',default=str(maint.DEFAULT_CONFIG))
    p.add_argument('--from-month',required=True);p.add_argument('--through-month',required=True)
    args=p.parse_args()
    try:
        runtime=maint.Runtime(maint.load(args.config))
        with maint.workspace_lock(runtime):result=prepare(runtime,args.from_month,args.through_month)
        print(maint.text_json(result));return 0
    except Exception as error:
        if isinstance(error,(ValueError,OSError,ImportError)):print('delivery_diff: '+str(error),file=sys.stderr)
        else:print('delivery_diff: Read-only SQL Server inspection failed; check connection and permissions.',file=sys.stderr)
        return 2


if __name__=='__main__':sys.exit(main())
