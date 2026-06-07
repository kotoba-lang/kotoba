-- Webya generation queue: pending and running generation jobs.
MODEL (
  name dev.mv_webya_generation_queue,
  kind FULL,
  dialect postgres,
  description 'Generation jobs with status pending or running, with LangGraph run details.',
  grain [vertex_id],
  tags [webya, generation, queue, langgraph]
);

SELECT
  j.vertex_id,
  j.job_id,
  j.site_id,
  j.status,
  j.langgraph_run_id,
  j.llm_calls_count,
  j.started_at
FROM vertex_webya_generation_job j
WHERE j.status IN ('pending', 'running')
