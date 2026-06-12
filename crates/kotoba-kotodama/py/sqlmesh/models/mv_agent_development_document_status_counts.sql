-- Agent development document counts grouped by topic, doc_type, and status.
MODEL (
  name dev.mv_agent_development_document_status_counts,
  kind FULL,
  dialect postgres,
  description 'Count of agent development documents grouped by topic, doc_type, and status.',
  grain [topic, doc_type, status],
  tags [agent, development, document, status]
);

SELECT topic, doc_type, status, COUNT(*)::BIGINT AS document_count
FROM vertex_agent_development_document
GROUP BY topic, doc_type, status
