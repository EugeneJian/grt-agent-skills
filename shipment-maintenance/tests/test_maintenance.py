"""Synthetic fixtures only. Workbooks are minimal OOXML test inputs."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from xml.sax.saxutils import escape
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import maintenance as m

RULES={'delivery_types':['销售交货单'],'customer_reference_first_character':'G',
       'customer_reference_excluded_character_index':3,'customer_reference_excluded_character':'S'}
HEADERS=m.REQUIRED+['运抵国']


def workbook(rows,headers=HEADERS):
    buffer=io.BytesIO()
    cells=[]
    for number,row in enumerate([headers]+rows,1):
        items=[]
        for col,value in enumerate(row,1):
            if value is None:continue
            cell=chr(64+col)+str(number)
            if isinstance(value,str) and value.startswith('='):
                items.append(f'<c r="{cell}"><f>{escape(value[1:])}</f></c>')
            elif isinstance(value,(int,float)):
                items.append(f'<c r="{cell}" t="n"><v>{value}</v></c>')
            else:items.append(f'<c r="{cell}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        cells.append(f'<row r="{number}">'+''.join(items)+'</row>')
    files={
      '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
      '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
      'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>',
      'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
      'xl/worksheets/sheet1.xml':'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(cells)+'</sheetData></worksheet>'}
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        for name,text in files.items():z.writestr(name,text)
    return buffer.getvalue()


def raw_row(**changes):
    row={'客户参考':'G001','过账日期':'2030-01-02','物料编码':'000TEST-PN','交货数量':2,
         '销售单位':'PCS','运抵国描述':'Example','交货类型描述':'销售交货单','运抵国':'ZZ'}
    row.update(changes)
    return [row[k] for k in HEADERS]


class ExtractionTests(unittest.TestCase):
    def test_reference_uses_fourth_character_and_preserves_repeated_rows(self):
        row=raw_row()
        payload,report=m.extract(workbook([row,row,raw_row(客户参考='G00S'),raw_row(客户参考='X001')]),'synthetic.xlsx',RULES)
        self.assertEqual(len(payload['rows']),2)
        self.assertEqual(payload['rows'][0][3],'000TEST-PN')
        self.assertEqual(payload['rows'][0][2],'2030-01-02')
        self.assertEqual(report['excluded_rows'],2)

    def test_numeric_pn_formula_and_bad_amount_fail(self):
        for change in ({'物料编码':123},{'交货数量':'=1+1'},{'交货数量':'NaN'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                m.extract(workbook([raw_row(**change)]),'synthetic.xlsx',RULES)

    def test_unknown_country_retained_and_units_not_converted(self):
        payload,_=m.extract(workbook([raw_row(运抵国描述=None,交货数量='2.125',销售单位='M')]),'synthetic.xlsx',RULES)
        self.assertIsNone(payload['rows'][0][5])
        self.assertEqual(payload['rows'][0][4:7],['2.125',None,'M'])

    def test_footer_not_imported_and_headers_required(self):
        footer=[None]*len(HEADERS);footer[HEADERS.index('交货数量')]=99
        payload,report=m.extract(workbook([raw_row(),footer]),'synthetic.xlsx',RULES)
        self.assertEqual(payload['input_rows'],1)
        self.assertEqual(report['footer_rows'],1)
        with self.assertRaises(ValueError):m.extract(workbook([],headers=['wrong']),'synthetic.xlsx',RULES)


class ContractTests(unittest.TestCase):
    def test_multiline_postgres_json_and_multiple_results(self):
        values=m.pg_results('[{"amount":1},\n {"amount":2.125}]\n{"ok":true}\n')
        self.assertEqual(len(values[0]),2)
        self.assertEqual(str(values[0][1]['amount']),'2.125')
        self.assertTrue(values[1]['ok'])

    def test_modified_payload_cannot_resume(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);(p/'source_workbooks.zip').write_bytes(b'synthetic backup')
            m.save(p/'payload.json',{'rows':[]})
            run={'source_backup_sha256':m.checksum(p/'source_workbooks.zip'),'local_receipts':[],
                 'files':[{'payload':'payload.json','source_sha256':'a','prepared_sha256':m.checksum(p/'payload.json')}]}
            m.read_payloads(p,run)
            m.save(p/'payload.json',{'rows':['modified']})
            with self.assertRaises(ValueError):m.read_payloads(p,run)

    def test_material_mismatch_and_unrelated_baseline_difference_fail(self):
        base={'protocol':1,'rules_sha256':'rules','material':{'digest':'one'},'files':[]}
        other={**base,'material':{'digest':'two'}}
        with self.assertRaises(ValueError):m.align(base,other)
        other={**base,'files':[{'source_sha256':'unknown'}]}
        with self.assertRaises(ValueError):m.align(base,other)
        m.align(base,other,allowed=['unknown'])

    def test_receipt_comparison_ignores_json_object_order(self):
        r={k:None for k in ('source_sha256','is_complete','expected_rows','rows','min_date','max_date','payload_digest','business_digest')}
        self.assertEqual(m.receipt_signature({**r,'totals':{'PCS':'1','M':'2'}}),m.receipt_signature({**r,'totals':{'M':'2','PCS':'1'}}))


if __name__=='__main__':unittest.main()
