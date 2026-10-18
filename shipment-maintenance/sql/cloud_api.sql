-- Apply after core.sql. Only an administrator may admit an employee separately.
DO $$ BEGIN
  IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='shipping_import_executor') THEN
    CREATE ROLE shipping_import_executor NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
END $$;
GRANT shipping_import_executor TO CURRENT_USER WITH SET TRUE, INHERIT FALSE;
CREATE TABLE IF NOT EXISTS agent_access.shipment_importers (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  enabled boolean NOT NULL DEFAULT true,
  admitted_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE agent_access.shipment_importers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON agent_access.shipment_importers FROM PUBLIC,anon,authenticated;
GRANT USAGE ON SCHEMA shipping,master_data,shipping_maintenance,agent_access,auth TO shipping_import_executor;
GRANT SELECT ON shipping.dataset_config,master_data.sap_material,master_data.material_sync_runs,
  agent_access.readers,agent_access.shipment_importers TO shipping_import_executor;
GRANT SELECT,INSERT,UPDATE ON shipping.source_files TO shipping_import_executor;
GRANT SELECT,INSERT ON shipping.shipment_facts,shipping_maintenance.import_audit TO shipping_import_executor;
CREATE POLICY maintenance_sources ON shipping.source_files TO shipping_import_executor USING(true) WITH CHECK(true);
CREATE POLICY maintenance_facts_select ON shipping.shipment_facts FOR SELECT TO shipping_import_executor USING(true);
CREATE POLICY maintenance_facts_insert ON shipping.shipment_facts FOR INSERT TO shipping_import_executor WITH CHECK(true);
CREATE POLICY maintenance_material ON master_data.sap_material FOR SELECT TO shipping_import_executor USING(true);
CREATE POLICY maintenance_material_runs ON master_data.material_sync_runs FOR SELECT TO shipping_import_executor USING(true);
CREATE POLICY maintenance_config ON shipping.dataset_config FOR SELECT TO shipping_import_executor USING(true);
CREATE POLICY maintenance_readers ON agent_access.readers FOR SELECT TO shipping_import_executor USING(true);
CREATE POLICY maintenance_importers ON agent_access.shipment_importers FOR SELECT TO shipping_import_executor USING(true);
CREATE POLICY maintenance_audit ON shipping_maintenance.import_audit TO shipping_import_executor USING(true) WITH CHECK(true);
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA shipping_maintenance TO shipping_import_executor;
GRANT EXECUTE ON FUNCTION auth.uid() TO shipping_import_executor;

CREATE OR REPLACE FUNCTION shipping_maintenance.employee_request(p_operation text,p_payload jsonb DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE uid uuid;
BEGIN
 uid:=auth.uid();
 IF uid IS NULL OR NOT EXISTS(SELECT FROM agent_access.shipment_importers WHERE user_id=uid AND enabled)
    OR NOT EXISTS(SELECT FROM agent_access.readers WHERE user_id=uid AND enabled) THEN
   RAISE EXCEPTION 'Employee is not authorized for shipment maintenance' USING ERRCODE='42501';
 END IF;
 IF p_operation='status' THEN RETURN shipping_maintenance.inventory(); END IF;
 IF p_operation='append' THEN
   IF coalesce(p_payload->>'expected_payload_digest','')!~'^[0-9a-f]{64}$' THEN
     RAISE EXCEPTION 'A locally validated payload digest is required';
   END IF;
   RETURN shipping_maintenance.apply_file(p_payload||jsonb_build_object('actor',uid::text));
 END IF;
 RAISE EXCEPTION 'Unsupported maintenance operation';
END $$;
GRANT CREATE ON SCHEMA shipping_maintenance TO shipping_import_executor;
ALTER FUNCTION shipping_maintenance.employee_request(text,jsonb) OWNER TO shipping_import_executor;
REVOKE CREATE ON SCHEMA shipping_maintenance FROM shipping_import_executor;
REVOKE ALL ON FUNCTION shipping_maintenance.employee_request(text,jsonb) FROM PUBLIC,anon;
GRANT USAGE ON SCHEMA shipping_maintenance TO authenticated;
GRANT EXECUTE ON FUNCTION shipping_maintenance.employee_request(text,jsonb) TO authenticated;

CREATE OR REPLACE FUNCTION agent_api.shipment_maintenance_status()
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
 SELECT shipping_maintenance.employee_request('status',NULL);
$$;
CREATE OR REPLACE FUNCTION agent_api.shipment_append(p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
 SELECT shipping_maintenance.employee_request('append',p_payload);
$$;
REVOKE ALL ON FUNCTION agent_api.shipment_maintenance_status(),agent_api.shipment_append(jsonb) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION agent_api.shipment_maintenance_status(),agent_api.shipment_append(jsonb) TO authenticated;
NOTIFY pgrst,'reload schema';
