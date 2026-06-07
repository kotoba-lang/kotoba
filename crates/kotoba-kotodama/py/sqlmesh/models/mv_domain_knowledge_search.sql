-- Domain knowledge search: chunk text joined with document metadata for RAG queries.
MODEL (
  name dev.mv_domain_knowledge_search,
  kind FULL,
  dialect postgres,
  description 'Chunk-level search view: joins vertex_domain_knowledge_chunk with active vertex_domain_knowledge_document; includes search_text for full-text matching.',
  grain [chunk_vid],
  tags [domain, knowledge, rag, search, chunk, embedding]
);

SELECT
  c.vertex_id AS chunk_vid,
  c.document_vid,
  d.domain,
  d.actor_did,
  d.canonical_work_id,
  d.game_slug,
  d.title,
  d.lang,
  c.chunk_index,
  c.chunk_text,
  c.keywords,
  c.embedding,
  c.embedding_norm,
  d.confidence,
  d.updated_at,
  LOWER(
    COALESCE(d.title, '') || ' ' || COALESCE(c.chunk_text, '') || ' ' || COALESCE(c.keywords, '')
  ) AS search_text
FROM vertex_domain_knowledge_chunk c
JOIN vertex_domain_knowledge_document d ON d.vertex_id = c.document_vid
WHERE d.status = 'active'
