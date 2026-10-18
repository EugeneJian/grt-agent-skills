-- Shared by local PostgreSQL and Supabase. No real project coordinates or data.
CREATE SCHEMA IF NOT EXISTS shipping_maintenance;
REVOKE ALL ON SCHEMA shipping_maintenance FROM PUBLIC,anon,authenticated;

CREATE TABLE IF NOT EXISTS shipping_maintenance.import_audit (
  source_sha256 text PRIMARY KEY REFERENCES shipping.source_files(source_sha256),
  payload_digest text NOT NULL,
  actor text NOT NULL,
  overlap_review text,
  potential_overlap_rows bigint NOT NULL DEFAULT 0,
  completed_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE shipping_maintenance.import_audit ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON shipping_maintenance.import_audit FROM PUBLIC,anon,authenticated;

CREATE OR REPLACE FUNCTION shipping_maintenance.receipt(p_sha text)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
WITH rows AS (
  SELECT f.*,jsonb_build_array(f.source_sheet,f.source_row,f.date::text,f.pn,
    trim_scale(f.amount)::text,f.country_name,f.sales_unit,f.country_code)::text AS exact_row,
    jsonb_build_array(f.date::text,upper(btrim(f.pn)),trim_scale(f.amount)::text,
      f.country_name,f.sales_unit,f.country_code)::text AS business_row
  FROM shipping.shipment_facts f WHERE f.source_sha256=p_sha
), sums AS (SELECT sales_unit,trim_scale(sum(amount))::text AS total FROM rows GROUP BY sales_unit)
SELECT jsonb_build_object('source_sha256',s.source_sha256,'filename',s.filename,
 'is_complete',s.is_complete,'input_rows',s.input_rows,'expected_rows',s.expected_rows,
 'rows',(SELECT count(*) FROM rows),'min_date',(SELECT min(date) FROM rows),
 'max_date',(SELECT max(date) FROM rows),
 'totals',coalesce((SELECT jsonb_object_agg(sales_unit,total) FROM sums),'{}'::jsonb),
 'payload_digest',(SELECT encode(sha256(convert_to(coalesce(string_agg(exact_row,E'\n' ORDER BY exact_row COLLATE "C"),''),'UTF8')),'hex') FROM rows),
 'business_digest',(SELECT encode(sha256(convert_to(coalesce(string_agg(business_row,E'\n' ORDER BY business_row COLLATE "C"),''),'UTF8')),'hex') FROM rows))
FROM shipping.source_files s WHERE s.source_sha256=p_sha;
$$;

CREATE OR REPLACE FUNCTION shipping_maintenance.inventory()
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
SELECT jsonb_build_object('protocol',1,
 'rules',(SELECT rules FROM shipping.dataset_config WHERE id),
 'rules_sha256',(SELECT rules_sha256 FROM shipping.dataset_config WHERE id),
 'material',(SELECT jsonb_build_object('digest',content_digest_md5,'rows',expected_rows)
    FROM master_data.material_sync_runs WHERE status='complete' ORDER BY source_extracted_at DESC LIMIT 1),
 'files',coalesce((SELECT jsonb_agg(shipping_maintenance.receipt(source_sha256) ORDER BY filename)
    FROM shipping.source_files),'[]'::jsonb));
$$;

CREATE OR REPLACE FUNCTION shipping_maintenance.apply_file(p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' SET lock_timeout='10s' AS $$
DECLARE
  doc jsonb; rowdoc jsonb; src text; name text; rule_hash text; material_hash text;
  actual jsonb; previous jsonb; payload_hash text; business_hash text;
  n bigint; first_date date; last_date date; totals jsonb; new_rows integer;
  review text; r record; duplicate_file text; overlap_count bigint; created boolean;
BEGIN
  IF jsonb_typeof(p_payload)<>'object' OR octet_length(p_payload::text)>20000000 THEN
    RAISE EXCEPTION 'Invalid or oversized import payload';
  END IF;
  src:=p_payload->>'source_sha256'; name:=p_payload->>'filename';
  IF src IS NULL OR src!~'^[0-9a-f]{64}$' OR name IS NULL OR length(name) NOT BETWEEN 1 AND 255
     OR name~'[/\\]' THEN RAISE EXCEPTION 'Invalid source identity'; END IF;
  PERFORM pg_advisory_xact_lock(hashtext('shipping_maintenance.append'));
  PERFORM pg_advisory_xact_lock(hashtext('master_data.sap_material.full_sync'));
  LOCK TABLE shipping.source_files IN SHARE ROW EXCLUSIVE MODE;
  SELECT rules_sha256 INTO rule_hash FROM shipping.dataset_config WHERE id;
  SELECT content_digest_md5 INTO material_hash FROM master_data.material_sync_runs
    WHERE status='complete' ORDER BY source_extracted_at DESC LIMIT 1;
  IF rule_hash IS DISTINCT FROM p_payload->>'rules_sha256'
     OR material_hash IS NULL OR material_hash IS DISTINCT FROM p_payload->>'material_digest' THEN
    RAISE EXCEPTION 'Rules or material snapshot changed; validate again';
  END IF;
  previous:=shipping_maintenance.receipt(src);
  IF previous IS NOT NULL THEN
    IF (previous->>'is_complete')::boolean AND previous->>'payload_digest'=p_payload->>'expected_payload_digest' THEN
      RETURN previous||jsonb_build_object('already_complete',true,'inserted_rows',0);
    END IF;
    RAISE EXCEPTION 'Existing source is incomplete or has a different payload';
  END IF;
  IF EXISTS(SELECT FROM shipping.source_files WHERE filename=name) THEN
    RAISE EXCEPTION 'Filename already exists with different bytes; revision requires review';
  END IF;
  IF jsonb_typeof(p_payload->'rows')<>'array' OR jsonb_array_length(p_payload->'rows') NOT BETWEEN 1 AND 50000
     OR coalesce((p_payload->>'input_rows')::integer,0)<jsonb_array_length(p_payload->'rows') THEN
    RAISE EXCEPTION 'Expected 1..50000 validated rows and a valid input row count';
  END IF;
  FOR rowdoc IN SELECT value FROM jsonb_array_elements(p_payload->'rows') LOOP
    IF jsonb_typeof(rowdoc)<>'array' OR jsonb_array_length(rowdoc)<>8
       OR coalesce(length(rowdoc->>0),0) NOT BETWEEN 1 AND 255
       OR coalesce((rowdoc->>1)::integer,0)<2
       OR coalesce(rowdoc->>2,'')!~'^\d{4}-\d{2}-\d{2}$'
       OR coalesce(length(rowdoc->>3),0) NOT BETWEEN 1 AND 255
       OR rowdoc->>4 IS NULL OR (rowdoc->>4)::numeric::text IN ('NaN','Infinity','-Infinity')
       OR coalesce(length(rowdoc->>6),0) NOT BETWEEN 1 AND 64
       OR coalesce(length(rowdoc->>5),0)>2048 OR coalesce(length(rowdoc->>7),0)>255 THEN
      RAISE EXCEPTION 'Invalid shipment row';
    END IF;
    PERFORM (rowdoc->>2)::date;
  END LOOP;
  IF EXISTS(SELECT FROM jsonb_array_elements(p_payload->'rows') j
      GROUP BY j->>0,(j->>1)::integer HAVING count(*)>1) THEN
    RAISE EXCEPTION 'Duplicate sheet/row identity in payload';
  END IF;
  IF EXISTS(SELECT FROM jsonb_array_elements(p_payload->'rows') j
     LEFT JOIN master_data.sap_material m ON m.pn_key=upper(btrim(j->>3))
     WHERE m.pn_key IS NULL OR NOT m.source_present) THEN
    RAISE EXCEPTION 'Unknown PN or stale material snapshot; update master data first';
  END IF;
  IF EXISTS(SELECT FROM jsonb_array_elements(p_payload->'rows') j
     JOIN master_data.sap_material m ON m.pn_key=upper(btrim(j->>3))
     WHERE m.mtart='Z001' AND (j->>4)::numeric<>trunc((j->>4)::numeric)) THEN
    RAISE EXCEPTION 'Z001 fractional quantity cannot enter the integer report';
  END IF;
  WITH rows AS (SELECT jsonb_build_array(j->>0,(j->>1)::integer,(j->>2)::date::text,j->>3,
     trim_scale((j->>4)::numeric)::text,j->>5,j->>6,j->>7)::text AS exact_row,
     jsonb_build_array((j->>2)::date::text,upper(btrim(j->>3)),trim_scale((j->>4)::numeric)::text,
     j->>5,j->>6,j->>7)::text AS business_row FROM jsonb_array_elements(p_payload->'rows') j)
  SELECT encode(sha256(convert_to(string_agg(exact_row,E'\n' ORDER BY exact_row COLLATE "C"),'UTF8')),'hex'),
         encode(sha256(convert_to(string_agg(business_row,E'\n' ORDER BY business_row COLLATE "C"),'UTF8')),'hex')
    INTO payload_hash,business_hash FROM rows;
  IF p_payload ? 'expected_payload_digest' AND payload_hash IS DISTINCT FROM p_payload->>'expected_payload_digest' THEN
    RAISE EXCEPTION 'Payload changed after local validation';
  END IF;
  SELECT min((j->>2)::date),max((j->>2)::date) INTO first_date,last_date
    FROM jsonb_array_elements(p_payload->'rows') j;
  -- A whole-file multiset match is suspicious even when a workbook was resaved or reordered.
  FOR r IN SELECT source_sha256 FROM shipping.source_files
       WHERE expected_rows=jsonb_array_length(p_payload->'rows') AND min_date=first_date AND max_date=last_date LOOP
    IF shipping_maintenance.receipt(r.source_sha256)->>'business_digest'=business_hash THEN
      RAISE EXCEPTION 'Duplicate business content from another source file';
    END IF;
  END LOOP;
  SELECT count(*) INTO overlap_count FROM jsonb_array_elements(p_payload->'rows') j
  WHERE EXISTS(SELECT FROM shipping.shipment_facts f
      WHERE f.date=(j->>2)::date AND upper(btrim(f.pn))=upper(btrim(j->>3))
      AND f.amount=(j->>4)::numeric AND f.sales_unit=j->>6
      AND f.country_name IS NOT DISTINCT FROM j->>5 AND f.country_code IS NOT DISTINCT FROM j->>7);
  review:=p_payload->>'overlap_review';
  IF overlap_count>0 AND coalesce(length(btrim(review)),0)<16 THEN
    RAISE EXCEPTION 'Potential overlapping shipment rows: %. Explicit business review required',overlap_count;
  END IF;
  SELECT jsonb_object_agg(unit,total) INTO totals FROM (
    SELECT j->>6 AS unit,trim_scale(sum((j->>4)::numeric))::text AS total
    FROM jsonb_array_elements(p_payload->'rows') j GROUP BY j->>6) t;
  INSERT INTO shipping.source_files(source_sha256,filename,rules_sha256,input_rows,expected_rows,expected_totals,min_date,max_date)
    VALUES(src,name,rule_hash,(p_payload->>'input_rows')::integer,jsonb_array_length(p_payload->'rows'),totals,first_date,last_date);
  INSERT INTO shipping.shipment_facts(source_sha256,source_sheet,source_row,date,pn,amount,country_name,sales_unit,country_code)
    SELECT src,j->>0,(j->>1)::integer,(j->>2)::date,j->>3,(j->>4)::numeric,j->>5,j->>6,j->>7
    FROM jsonb_array_elements(p_payload->'rows') j;
  GET DIAGNOSTICS new_rows=ROW_COUNT;
  actual:=shipping_maintenance.receipt(src);
  IF new_rows<>jsonb_array_length(p_payload->'rows') OR actual->>'payload_digest'<>payload_hash
     OR actual->'totals'<>totals THEN RAISE EXCEPTION 'Post-insert reconciliation failed'; END IF;
  UPDATE shipping.source_files SET is_complete=true,completed_at=now() WHERE source_sha256=src;
  INSERT INTO shipping_maintenance.import_audit(source_sha256,payload_digest,actor,overlap_review,potential_overlap_rows)
    VALUES(src,payload_hash,coalesce(nullif(p_payload->>'actor',''),session_user),review,overlap_count);
  RETURN shipping_maintenance.receipt(src)||jsonb_build_object('already_complete',false,'inserted_rows',new_rows,'potential_overlap_rows',overlap_count);
END;
$$;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA shipping_maintenance FROM PUBLIC,anon,authenticated;
