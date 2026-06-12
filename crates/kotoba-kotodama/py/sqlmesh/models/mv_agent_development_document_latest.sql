-- Latest agent development document rows (flat projection).
MODEL (
  name dev.mv_agent_development_document_latest,
  kind FULL,
  dialect postgres,
  description 'Flat projection of vertex_agent_development_document for efficient read queries.',
  grain [doc_id],
  tags [agent, development, document, latest]
);

SELECT doc_id, doc_type, title, topic, status, updated_at, agent_did, related_ref
FROM vertex_agent_development_document
