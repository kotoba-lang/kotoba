-- Actor belief karma: JOIN edge_constrained_by × vertex_belief_system.
MODEL (
  name dev.mv_actor_belief_karma,
  kind FULL,
  dialect postgres,
  description 'Per-actor belief karma rows joining edge_constrained_by with vertex_belief_system.',
  grain [actor_vid, belief_vertex_id],
  tags [actor, belief, karma, spirit]
);

SELECT
  ec.src_vid                              AS actor_vid,
  bs.vertex_id                            AS belief_vertex_id,
  bs.name                                 AS belief_name,
  bs.display_name                         AS belief_display_name,
  bs.tradition                            AS tradition,
  bs.self_other_separation                AS self_other_separation,
  bs.individual_primacy                   AS individual_primacy,
  bs.time_structure                       AS time_structure,
  bs.consent_model                        AS consent_model,
  bs.approx_followers                     AS approx_followers,
  bs.description                          AS belief_description,
  COALESCE(ec.binding_strength, 0.5)      AS binding_strength,
  ec.constraint_type                      AS constraint_type,
  ec.evidence_type                        AS evidence_type,
  ec.epoch                                AS epoch,
  ec.created_date                         AS edge_created_date
FROM edge_constrained_by ec
JOIN vertex_belief_system bs ON bs.vertex_id = ec.dst_vid
WHERE ec.dst_vid LIKE 'belief:%'
