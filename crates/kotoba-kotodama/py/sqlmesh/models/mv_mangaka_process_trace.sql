-- Mangaka process trace: OCEL audit events for mangaka BPMN activities.
MODEL (
  name dev.mv_mangaka_process_trace,
  kind FULL,
  dialect postgres,
  description 'Per OCEL audit commit: case_id, activity, actor_did, timestamp, duration, status, object refs.',
  grain [case_id, ts_ms],
  tags [mangaka, process, ocel, audit]
);

SELECT
  (value_json::JSONB -> 'case_id')::VARCHAR AS case_id,
  (value_json::JSONB -> 'action')::VARCHAR AS activity,
  repo AS actor_did,
  ts_ms,
  created_at AS timestamp,
  ((value_json::JSONB -> 'duration_ms')::VARCHAR)::BIGINT AS duration_ms,
  (value_json::JSONB -> 'status')::VARCHAR AS status,
  (value_json::JSONB -> 'objectRefs')::VARCHAR AS object_refs_json,
  value_json AS payload_json
FROM vertex_repo_commit
WHERE collection = 'com.etzhayyim.bpmn.audit'
  AND (value_json::JSONB -> 'action')::VARCHAR LIKE 'mangaka.%'
