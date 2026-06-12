-- Crystal coverage: structure count and first timestamp per crystal system.
MODEL (
  name dev.mv_crystal_coverage,
  kind FULL,
  dialect postgres,
  description 'Per crystal system: structure count and earliest created_at from vertex_crystal_structure.',
  grain [crystal_system],
  tags [crystal, chemistry, coverage, structure]
);

SELECT
  cs.crystal_system,
  COUNT(*) AS structure_count,
  MIN(cs.created_at) AS first_at
FROM vertex_crystal_structure cs
GROUP BY cs.crystal_system
