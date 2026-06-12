-- OWL EL vs DL diff: agreement analysis between EL and DL profile inferences.
MODEL (
  name dev.mv_owl_el_dl_diff,
  kind FULL,
  dialect postgres,
  description 'Per inferred triple: agreed / el_only / dl_only status comparing EL and DL profile inferences.',
  grain [subject, predicate, object, status],
  tags [owl, el, dl, diff, benchmark]
);

SELECT
  el.subject,
  el.predicate,
  el.object,
  CASE
    WHEN dl.vertex_id IS NOT NULL THEN 'agreed'
    ELSE 'el_only'
  END AS status
FROM vertex_owl_inferred el
LEFT JOIN vertex_owl_inferred dl
  ON dl.subject = el.subject
  AND dl.predicate = el.predicate
  AND dl.object = el.object
  AND dl.profile = 'DL'
WHERE el.profile = 'EL'
UNION ALL
SELECT
  dl.subject,
  dl.predicate,
  dl.object,
  'dl_only' AS status
FROM vertex_owl_inferred dl
LEFT JOIN vertex_owl_inferred el
  ON el.subject = dl.subject
  AND el.predicate = dl.predicate
  AND el.object = dl.object
  AND el.profile = 'EL'
WHERE dl.profile = 'DL'
  AND el.vertex_id IS NULL
