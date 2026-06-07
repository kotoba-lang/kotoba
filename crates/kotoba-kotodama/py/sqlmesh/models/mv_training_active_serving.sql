-- Training active serving: active checkpoint promotions to serving targets.
MODEL (
  name dev.mv_training_active_serving,
  kind FULL,
  dialect postgres,
  description 'Per active promotion: alias, checkpoint vertex_id, serving target, promoted_at/by.',
  grain [alias, checkpoint_vertex_id],
  tags [training, serving, active]
);

SELECT
  alias,
  src_vid AS checkpoint_vertex_id,
  serving_target,
  promoted_at,
  promoted_by
FROM edge_training_promoted_to
WHERE status = 'active'
