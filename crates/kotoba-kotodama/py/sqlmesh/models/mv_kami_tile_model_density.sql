-- Kami tile model density: model instance counts and bbox per H3 tile and model kind.
MODEL (
  name dev.mv_kami_tile_model_density,
  kind FULL,
  dialect postgres,
  description 'Per (tile_h3, model_kind): instance count, distinct model_def count, and world bbox.',
  grain [tile_h3, model_kind],
  tags [kami, tile, model, density]
);

SELECT
  tile_h3,
  model_kind,
  COUNT(*) AS instance_count,
  COUNT(DISTINCT model_def_id) AS model_def_count,
  MIN(world_x) AS min_x,
  MAX(world_x) AS max_x,
  MIN(world_z) AS min_z,
  MAX(world_z) AS max_z
FROM vertex_kami_model_instance mi
JOIN vertex_kami_model_def md ON md.vertex_id = mi.model_def_id
GROUP BY tile_h3, model_kind
