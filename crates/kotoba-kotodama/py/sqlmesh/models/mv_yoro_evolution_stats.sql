-- Yoro evolution stats: browser-sourced activity counts across evolution dimensions.
MODEL (
  name dev.mv_yoro_evolution_stats,
  kind FULL,
  dialect postgres,
  description 'Aggregate counts: koji discoveries, kyumei validations, shinka evolutions, hinshitsu assessments, shinka knowledge (all from browser source).',
  grain [],
  tags [yoro, evolution, koji, kyumei, shinka]
);

SELECT
  (SELECT COUNT(*) FROM vertex_yoro_koji_discovery WHERE source = 'browser') AS koji_count,
  (SELECT COUNT(*) FROM vertex_yoro_kyumei_validation WHERE source = 'browser') AS kyumei_count,
  (SELECT COUNT(*) FROM vertex_yoro_shinka_evolution WHERE source = 'browser') AS shinka_count,
  (SELECT COUNT(*) FROM vertex_yoro_hinshitsu_assessment WHERE source = 'browser') AS hinshitsu_count,
  (SELECT COUNT(*) FROM vertex_yoro_shinka_knowledge WHERE source = 'browser') AS shinka_knowledge_count
