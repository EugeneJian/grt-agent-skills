#!/usr/bin/env python3
"""Bounded, resumable Excel -> local PostgreSQL -> Supabase maintenance."""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

DEFAULT_CONFIG = Path.home()/'.config/company-sql/maintenance.json'
REQUIRED = ['客户参考','过账日期','物料编码','交货数量','销售单位','运抵国描述','交货类型描述']


def text_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str)


def load(path):
    return json.loads(Path(path).expanduser().read_text(encoding='utf-8'))


def pg_results(output):
    def reject(value):
        raise ValueError('Non-finite PostgreSQL JSON value: '+value)
    decoder=json.JSONDecoder(parse_float=Decimal,parse_constant=reject)
    values=[];remaining=output.lstrip()
    while remaining:
        value,index=decoder.raw_decode(remaining)
        values.append(value);remaining=remaining[index:].lstrip()
    return values


def checksum(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        stream.write(text_json(value)+'\n'); stream.flush(); os.fsync(stream.fileno()); temp = stream.name
    os.chmod(temp, 0o600); os.replace(temp, path)


def now():
    return datetime.now(timezone.utc).isoformat()


def literal(value):
    return "'"+str(value).replace("'", "''")+"'"


def import_client(config):
    folder = Path(config.get('sql_skill', '~/.agents/skills/sql')).expanduser()/'scripts'
    sys.path.insert(0, str(folder))
    import query_data, api_session, compare_profiles
    return query_data, api_session, compare_profiles


class Runtime:
    def __init__(self, config):
        self.config = config
        self.root = Path(config['workspace']).expanduser().resolve()
        self.area = self.root/config.get('source_area', 'Excel资料')
        self.inbox = self.area/'00_新增待处理'
        self.batches = self.area/'02_导入批次'
        self.registry = self.area/'04_台账/文件台账.json'
        self.client, self.auth, self.compare = import_client(config)
        self.admin = config['local_admin']
        self.psql = self.admin.get('psql_path', shutil.which('psql'))
        if not self.psql:
            raise ValueError('psql is required for local validation')
        self.connection = self.client.pg_connection(self.admin)
        query_config = load(config.get('query_config', '~/.config/company-sql/profiles.json'))
        self.cloud = self.client.configured_profile(query_config, config.get('cloud_profile', 'cloud'))
        if self.cloud['engine'] != 'supabase_api':
            raise ValueError('The maintenance cloud profile must use supabase_api')

    def pg(self, sql, readonly=False):
        env = dict(os.environ)
        env['PGOPTIONS'] = '-c standard_conforming_strings=on -c statement_timeout=120000 -c lock_timeout=10000 -c default_transaction_read_only='+('on' if readonly else 'off')
        result = subprocess.run([self.psql,'-X','-qAt','-w','-v','ON_ERROR_STOP=1','--dbname',self.connection],
                                input=sql, text=True, capture_output=True, env=env)
        if result.returncode:
            raise ValueError('Local PostgreSQL: '+result.stderr.strip()[:1500])
        return pg_results(result.stdout)

    def rpc(self, method, payload=None):
        if method not in ('shipment_maintenance_status', 'shipment_append'):
            raise ValueError('Unsupported maintenance RPC')
        base = self.cloud.get('url') or os.environ.get(self.cloud.get('url_env','COMPANY_SUPABASE_URL'),'')
        parsed = urllib.parse.urlsplit(base)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in ('','/') or parsed.query or parsed.fragment):
            raise ValueError('Use an HTTPS project origin')
        key, token = self.auth.credentials(self.cloud, base)
        if (not key or key.startswith('sb_secret_') or self.client.jwt_role(key) not in (None,'anon')
                or self.client.jwt_role(token) != 'authenticated'):
            raise ValueError('Use the admitted employee Auth session, not an administrator key')
        body = text_json({'p_payload': payload} if payload is not None else {}).encode()
        request = urllib.request.Request(base.rstrip('/')+'/rest/v1/rpc/'+method, data=body, method='POST',
            headers={'apikey':key,'Authorization':'Bearer '+token,'Content-Type':'application/json',
                     'Accept-Profile':self.cloud.get('api_schema','agent_api'),
                     'Content-Profile':self.cloud.get('api_schema','agent_api')})
        try:
            with urllib.request.build_opener(self.auth.NoRedirect()).open(request, timeout=120) as response:
                return self.client.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            detail = error.read(4096).decode(errors='replace')
            try: detail = json.loads(detail).get('message', 'Request rejected')
            except ValueError: detail = 'Request rejected'
            raise ValueError(f'Cloud HTTP {error.code}: {detail}. Keep this batch and resume after resolving the cause.') from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError('Cloud request did not complete. Commit status is unknown; resume the same batch, never start a replacement batch.') from None

    def inventory(self):
        return self.pg('SELECT shipping_maintenance.inventory();', readonly=True)[0]

    def apply(self, payloads, commit):
        statements = ['BEGIN;']+[f'SELECT shipping_maintenance.apply_file({literal(text_json(p))}::jsonb);' for p in payloads]
        statements += ['COMMIT;' if commit else 'ROLLBACK;']
        return self.pg('\n'.join(statements))

    def backup(self, batch):
        binary = self.admin.get('pg_dump_path') or str(Path(self.psql).with_name('pg_dump'))
        restore = self.admin.get('pg_restore_path') or str(Path(self.psql).with_name('pg_restore'))
        dest = batch/'local_before.dump'
        if dest.exists():
            raise ValueError('Backup already exists without a recorded digest; inspect before resuming')
        temp = dest.with_suffix('.dump.partial')
        result = subprocess.run([binary,'-w','--format=custom','--file',str(temp),'--dbname',self.connection],capture_output=True,text=True)
        if result.returncode:
            raise ValueError('Local backup failed: '+result.stderr[:1000])
        os.chmod(temp,0o600)
        subprocess.run([restore,'--list',str(temp)],check=True,capture_output=True)
        os.replace(temp,dest)
        return checksum(dest)


def receipt_signature(item):
    fields = ('source_sha256','is_complete','expected_rows','rows','min_date','max_date',
              'totals','payload_digest','business_digest')
    return json.dumps({k:item[k] for k in fields},ensure_ascii=False,sort_keys=True,default=str)


def align(local, cloud, allowed=()):
    if local['protocol'] != 1 or cloud['protocol'] != 1:
        raise ValueError('Maintenance protocol mismatch')
    if local['rules_sha256'] != cloud['rules_sha256'] or local['material'] != cloud['material']:
        raise ValueError('Local/cloud rules or material snapshots differ; synchronize them first')
    left = {r['source_sha256']:r for r in local['files']}
    right = {r['source_sha256']:r for r in cloud['files']}
    for key in left.keys() | right.keys():
        if key in allowed:
            if key in left and key in right and receipt_signature(left[key]) != receipt_signature(right[key]):
                raise ValueError('Existing batch source differs between local and cloud')
            continue
        if key not in left or key not in right or receipt_signature(left[key]) != receipt_signature(right[key]):
            raise ValueError('Baseline differs outside this batch; do not automatically copy or delete history')


def candidates(runtime):
    if not runtime.inbox.is_dir():
        raise ValueError('Missing 新增待处理 directory; configure the workspace')
    locks = [p.name for p in runtime.inbox.iterdir() if p.name.startswith('~$')]
    if locks:
        raise ValueError('Close workbooks before processing; Excel lock files are present')
    files = sorted(p for p in runtime.inbox.iterdir() if p.is_file() and p.suffix.casefold() in ('.xlsx','.xls','.xlsm','.xlsb'))
    for path in files:
        if path.is_symlink() or path.suffix.casefold() != '.xlsx' or path.stat().st_size > 64000000:
            raise ValueError('Review unsupported, linked or oversized source: '+path.name)
    return files


def extract(blob, filename, rules):
    import openpyxl
    with zipfile.ZipFile(io.BytesIO(blob)) as zip_file:
        if sum(i.file_size for i in zip_file.infolist()) > 512000000 or len(zip_file.infolist()) > 10000:
            raise ValueError('Workbook expansion exceeds the intake limit')
    required = set(REQUIRED)
    rows, input_rows, excluded, footer = [], 0, 0, 0
    book = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=False, keep_links=False)
    try:
        for sheet in book:
            iterator = sheet.iter_rows(values_only=True)
            headers = list(next(iterator, ()))
            if len(headers) != len(set(headers)) or not required <= set(headers):
                raise ValueError('Missing or duplicate headers: '+filename+'/'+sheet.title)
            for number, values in enumerate(iterator, 2):
                if not any(v is not None and str(v).strip() for v in values): continue
                row = dict(zip(headers, values))
                nonempty = {k for k,v in row.items() if v is not None and str(v).strip()}
                if nonempty == {'交货数量'}: footer += 1; continue
                input_rows += 1
                if any(isinstance(row.get(k),str) and row[k].startswith('=') for k in REQUIRED):
                    raise ValueError(f'Formula in a required field: {filename}/{sheet.title}/{number}')
                ref = '' if row['客户参考'] is None else str(row['客户参考'])
                index = rules['customer_reference_excluded_character_index']
                if (row['交货类型描述'] not in rules['delivery_types'] or len(ref)<=index
                        or ref[0] != rules['customer_reference_first_character']
                        or ref[index] == rules['customer_reference_excluded_character']):
                    excluded += 1; continue
                if not isinstance(row['物料编码'],str) or not row['物料编码'].strip():
                    raise ValueError('PN must remain nonempty text; never reconstruct numeric part numbers')
                when = row['过账日期']
                if isinstance(when,datetime): when = when.date()
                elif not isinstance(when,date): when = datetime.fromisoformat(str(when).replace('/','-')).date()
                amount = Decimal(str(row['交货数量']))
                if not amount.is_finite(): raise ValueError('Non-finite quantity')
                unit = str(row['销售单位'] or '').strip()
                if not unit: raise ValueError('Missing sales unit')
                country = None if row['运抵国描述'] is None else str(row['运抵国描述']).strip() or None
                code = None if row.get('运抵国') is None else str(row['运抵国']).strip() or None
                rows.append([sheet.title,number,when.isoformat(),row['物料编码'].strip(),format(amount,'f'),country,unit,code])
                if len(rows)>50000: raise ValueError('More than 50000 selected rows; use a separately reviewed large-file workflow')
    finally: book.close()
    if not rows: raise ValueError('No rows passed the business rules; review instead of marking this file imported')
    return {'filename':filename,'source_sha256':hashlib.sha256(blob).hexdigest(),'input_rows':input_rows,'rows':rows}, {'excluded_rows':excluded,'footer_rows':footer}


@contextmanager
def workspace_lock(runtime):
    lock = runtime.area/'.maintenance-lock'
    try: lock.mkdir(mode=0o700)
    except FileExistsError: raise ValueError('Another maintenance process holds the workspace lock; inspect its owner before retrying')
    save(lock/'owner.json',{'pid':os.getpid(),'started_at':now()})
    try: yield
    finally: (lock/'owner.json').unlink(); lock.rmdir()


def prepare(runtime, overlap_review=None):
    paths = candidates(runtime)
    if not paths: return {'status':'no_new_files','database_modified':False}
    local, cloud = runtime.inventory(), runtime.rpc('shipment_maintenance_status')
    align(local, cloud)
    imported = {r['source_sha256']:r for r in local['files']}
    names = {r['filename'] for r in local['files']}
    new, skipped, seen = [], [], set()
    for path in paths:
        key = checksum(path)
        if key in imported:
            if not imported[key]['is_complete']: raise ValueError('An existing source is incomplete; resolve it before appending')
            skipped.append({'filename':path.name,'reason':'identical_already_imported'}); continue
        if key in seen: skipped.append({'filename':path.name,'reason':'identical_in_inbox'}); continue
        if path.name in names: raise ValueError('Same filename, changed bytes: '+path.name+'; revisions cannot be appended automatically')
        seen.add(key); new.append((path,key))
    if not new: return {'status':'only_duplicates','skipped':skipped,'database_modified':False}
    batch = runtime.batches/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8])
    batch.mkdir(parents=True,mode=0o700)
    backup = batch/'source_workbooks.zip'
    with zipfile.ZipFile(backup,'x',zipfile.ZIP_DEFLATED) as archive:
        for path,key in new:
            if checksum(path)!=key: raise ValueError('Source changed while taking the batch backup')
            archive.write(path,path.name)
    os.chmod(backup,0o600)
    save(batch/'run.json',{'version':1,'created_at':now(),'phase':'preparing',
                          'source_backup_sha256':checksum(backup),'files':[],'skipped':skipped})
    items = []
    try:
        with zipfile.ZipFile(backup) as archive:
            if archive.testzip(): raise ValueError('Source backup CRC failed')
            for path,key in new:
                blob = archive.read(path.name)
                if hashlib.sha256(blob).hexdigest()!=key: raise ValueError('Source backup fingerprint failed')
                payload, extraction = extract(blob,path.name,local['rules'])
                payload.update(rules_sha256=local['rules_sha256'],material_digest=local['material']['digest'])
                if overlap_review: payload['overlap_review'] = overlap_review
                target = batch/(key+'.json'); save(target,payload)
                items.append({'filename':path.name,'source_sha256':key,'payload':target.name,
                              'prepared_sha256':checksum(target),'extraction':extraction})
    except (ValueError,OSError,KeyError,ImportError,InvalidOperation,zipfile.BadZipFile) as error:
        save(batch/'run.json',{'version':1,'created_at':now(),'phase':'preparation_failed',
                              'source_backup_sha256':checksum(backup),'error':str(error)})
        raise ValueError('Preparation failed; original backup retained at '+str(batch)+': '+str(error)) from None
    run = {'version':1,'created_at':now(),'phase':'prepared','files':items,'skipped':skipped,
           'source_backup_sha256':checksum(backup),'local_receipts':[], 'cloud_receipts':[]}
    save(batch/'run.json',run)
    return {'status':'prepared','batch':str(batch),'selected_files':len(items),'skipped':skipped}


def read_payloads(batch, run):
    if checksum(batch/'source_workbooks.zip')!=run['source_backup_sha256']:
        raise ValueError('Source backup changed')
    result = []
    for item in run['files']:
        path = batch/item['payload']
        if checksum(path)!=item['prepared_sha256']: raise ValueError('Prepared payload changed; do not resume this batch')
        payload = load(path)
        receipt = next((r for r in run['local_receipts'] if r['source_sha256']==item['source_sha256']), None)
        if receipt: payload['expected_payload_digest'] = receipt['payload_digest']
        result.append(payload)
    return result


def compare_months(runtime, payloads):
    days = [row[2] for p in payloads for row in p['rows']]
    first, last = min(days)[:7]+'-01', max(days)[:7]+'-01'
    query = {'dataset':'shipment_monthly','filters':[{'column':'month','op':'gte','value':first},
             {'column':'month','op':'lte','value':last}],'limit':500}
    sql = f"SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM (SELECT * FROM shipping.report_product_line_monthly WHERE month>={literal(first)}::date AND month<={literal(last)}::date) t;"
    rows = runtime.pg(sql,readonly=True)[0]
    counts, meta = runtime.compare.collect(query,runtime.cloud,1000)
    kinds = runtime.client.normalize(query,runtime.cloud)['data']['columns']
    actual = Counter(runtime.compare.canonical(row,kinds) for row in rows)
    if actual != counts: raise ValueError('Product-line/month/unit totals differ; do not archive or mark the batch complete')
    return {'from_month':first,'through_month':last,'matched':True,'cloud':meta}


def archive_complete(runtime, batch, run, payloads):
    registry = load(runtime.registry)
    by_hash = {r['source_sha256']:r for r in registry['files']}
    for item,payload in zip(run['files'],payloads):
        key = item['source_sha256']; days = [r[2] for r in payload['rows']]
        group = min(days)[:4] if min(days)[:4]==max(days)[:4] else '历史合并'
        dest = runtime.area/'01_已入库归档'/group/item['filename']
        source = runtime.inbox/item['filename']
        if dest.exists():
            if checksum(dest)!=key: raise ValueError('Archive destination conflicts with a different workbook')
        else:
            if not source.exists() or checksum(source)!=key:
                raise ValueError('Input workbook changed or moved; keep the successful database batch and inspect before archiving')
            dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700); source.rename(dest)
        if checksum(dest)!=key: raise ValueError('Archived workbook fingerprint mismatch')
        if key not in by_hash:
            record = {'original_filename':item['filename'],'original_path':str(source.relative_to(runtime.root)),
                      'archive_path':str(dest.relative_to(runtime.root)),'source_sha256':key,'bytes':dest.stat().st_size,
                      'min_date':min(days),'max_date':max(days),'local_import_status':'complete_verified',
                      'cloud_status':'complete_verified','batch':str(batch.relative_to(runtime.root)),
                      'backup_zip':str((batch/'source_workbooks.zip').relative_to(runtime.root)),
                      'backup_entry':item['filename'],'backup_sha256':run['source_backup_sha256']}
            registry['files'].append(record); by_hash[key]=record
            save(runtime.registry,registry)
    registry['last_maintenance']={'batch':str(batch.relative_to(runtime.root)),'verified_at':now()}
    save(runtime.registry,registry)
    lines=['出货 Excel 文件台账','逐文件指纹及双端完成状态；业务数据不随 Skill 分发。','']
    for item in sorted(registry['files'],key=lambda r:(r['min_date'],r['original_filename'])):
        lines += [item['archive_path'],'  数据日期：'+item['min_date']+' 至 '+item['max_date'],
                  '  SHA-256：'+item['source_sha256'],'  本机：'+item['local_import_status'],
                  '  云端：'+item.get('cloud_status','not_rechecked'),'']
    runtime.registry.with_suffix('.txt').write_text('\n'.join(lines),encoding='utf-8')
    run['phase']='archived'; run['completed_at']=now(); save(batch/'run.json',run)


def resume(runtime, batch):
    batch = Path(batch).expanduser().resolve()
    if runtime.batches.resolve() not in batch.parents:
        raise ValueError('Batch must be inside the configured 导入批次 directory')
    run = load(batch/'run.json')
    if run['phase'] not in ('prepared','local_validated','local_committed','cloud_synced','verified','archived'):
        raise ValueError('Unknown batch phase; inspect instead of guessing a continuation')
    payloads = read_payloads(batch,run)
    keys = [p['source_sha256'] for p in payloads]
    local, cloud = runtime.inventory(),runtime.rpc('shipment_maintenance_status')
    align(local,cloud,allowed=keys)
    if run['phase']=='archived': return {'status':'already_complete','batch':str(batch)}
    if run['phase']=='prepared':
        run['local_receipts'] = runtime.apply(payloads,commit=False)
        run['phase']='local_validated'; save(batch/'run.json',run)
        payloads = read_payloads(batch,run)
    if run['phase']=='local_validated':
        if not run.get('database_backup_sha256'):
            run['database_backup_sha256']=runtime.backup(batch); save(batch/'run.json',run)
        if checksum(batch/'local_before.dump')!=run['database_backup_sha256']:
            raise ValueError('Database backup changed')
        runtime.apply(payloads,commit=True)
        run['phase']='local_committed'; save(batch/'run.json',run)
    if run['phase']=='local_committed':
        for payload in payloads:
            result = runtime.rpc('shipment_append',payload)
            expected = next(r for r in run['local_receipts'] if r['source_sha256']==payload['source_sha256'])
            if receipt_signature(result)!=receipt_signature(expected):
                raise ValueError('Cloud receipt differs from the locally validated payload')
            run['cloud_receipts']=[r for r in run['cloud_receipts'] if r['source_sha256']!=payload['source_sha256']]+[result]
            save(batch/'run.json',run)
        run['phase']='cloud_synced'; save(batch/'run.json',run)
    if run['phase']=='cloud_synced':
        align(runtime.inventory(),runtime.rpc('shipment_maintenance_status'))
        run['comparison']=compare_months(runtime,payloads)
        run['phase']='verified'; save(batch/'run.json',run)
    if run['phase']=='verified': archive_complete(runtime,batch,run,payloads)
    return {'status':run['phase'],'batch':str(batch),'files':len(payloads)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['scan','prepare','resume','run','doctor'])
    parser.add_argument('--config',default=os.environ.get('COMPANY_SHIPMENT_MAINTENANCE_CONFIG',str(DEFAULT_CONFIG)))
    parser.add_argument('--batch')
    parser.add_argument('--overlap-review',help='Only after explicit business review; records why matching rows are distinct deliveries')
    args=parser.parse_args()
    try:
        runtime=Runtime(load(args.config))
        if args.overlap_review and len(args.overlap_review.strip())<16: raise ValueError('Record a specific overlap review, at least 16 characters')
        if args.operation=='scan':
            print(text_json({'candidates':[{'filename':p.name,'source_sha256':checksum(p)} for p in candidates(runtime)],'database_modified':False})); return 0
        if args.operation=='doctor':
            local,cloud=runtime.inventory(),runtime.rpc('shipment_maintenance_status'); align(local,cloud)
            print(text_json({'local_connected':True,'cloud_connected':True,'baseline_matches':True,'files':len(local['files'])})); return 0
        with workspace_lock(runtime):
            if args.operation=='resume':
                if not args.batch: raise ValueError('resume requires --batch')
                result=resume(runtime,args.batch)
            else:
                result=prepare(runtime,args.overlap_review)
                if args.operation=='run' and result['status']=='prepared': result=resume(runtime,result['batch'])
            print(text_json(result))
        return 0
    except (ValueError,OSError,KeyError,ImportError,InvalidOperation,zipfile.BadZipFile,subprocess.CalledProcessError) as error:
        print('shipment-maintenance: '+str(error),file=sys.stderr); return 2


if __name__=='__main__': sys.exit(main())
