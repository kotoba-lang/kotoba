-- Open smartphone supply chain trace: OCEL event log from BPMN audit commits for openSmartphone.
MODEL (
  name dev.mv_open_smartphone_supply_chain_trace,
  kind FULL,
  dialect postgres,
  description 'BPMN audit events for openSmartphone activities from vertex_repo_commit (case_id, activity, layer, status, duration).',
  grain [case_id, ts_ms],
  tags [open_smartphone, supply_chain, trace, ocel]
);

SELECT
  (value_json::JSONB ->> 'case_id') AS case_id,
  (value_json::JSONB ->> 'action') AS activity,
  (value_json::JSONB ->> 'layer') AS layer,
  repo AS actor_did,
  ts_ms,
  created_at AS timestamp,
  ((value_json::JSONB ->> 'duration_ms'))::BIGINT AS duration_ms,
  (value_json::JSONB ->> 'status') AS status,
  (value_json::JSONB ->> 'objectRefs') AS object_refs_json,
  value_json AS payload_json
FROM vertex_repo_commit
WHERE collection = 'com.etzhayyim.bpmn.audit'
  AND (
    (value_json::JSONB ->> 'action') LIKE 'openSmartphone%'
    OR (value_json::JSONB ->> 'action') LIKE 'open-smartphone%'
    OR (value_json::JSONB ->> 'layer') LIKE 'open-smartphone%'
  )
