-- JP corp finance process trace: OCEL event log from BPMN audit commits.
MODEL (
  name dev.mv_jp_corp_finance_process_trace,
  kind FULL,
  dialect postgres,
  description 'BPMN audit events for jpCorpFinance.* activities from vertex_repo_commit.',
  grain [case_id, ts_ms],
  tags [jp, corp_finance, process, trace, ocel]
);

SELECT
  COALESCE(
    value_json::JSONB ->> 'case_id',
    value_json::JSONB ->> 'runId',
    rkey
  ) AS case_id,
  value_json::JSONB ->> 'action' AS activity,
  repo AS actor_did,
  ts_ms,
  created_at AS timestamp,
  NULLIF(value_json::JSONB ->> 'duration_ms', '')::BIGINT AS duration_ms,
  COALESCE(value_json::JSONB ->> 'status', 'ok') AS status,
  value_json::JSONB ->> 'sourceId' AS source_id,
  value_json::JSONB ->> 'targetDate' AS target_date,
  value_json::JSONB ->> 'jcn' AS jcn,
  value_json::JSONB ->> 'edinetCode' AS edinet_code,
  NULLIF(value_json::JSONB ->> 'recordsPrepared', '')::BIGINT AS records_prepared,
  NULLIF(value_json::JSONB ->> 'recordsWritten', '')::BIGINT AS records_written,
  NULLIF(value_json::JSONB ->> 'recordsVisible', '')::BIGINT AS records_visible,
  NULLIF(value_json::JSONB ->> 'invalidCount', '')::BIGINT AS invalid_count,
  value_json AS payload_json
FROM vertex_repo_commit
WHERE collection = 'com.etzhayyim.bpmn.audit'
  AND (value_json::JSONB ->> 'action') LIKE 'jpCorpFinance.%'
