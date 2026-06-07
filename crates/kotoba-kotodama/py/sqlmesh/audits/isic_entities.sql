-- SQLMesh audit: mv_open_isic_entities_by_class invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_isic_avg_confidence_bounded,
  model dev.mv_open_isic_entities_by_class,
  dialect postgres,
  description 'avg_confidence must be in [0, 1] when present.'
);
SELECT *
FROM dev.mv_open_isic_entities_by_class
WHERE avg_confidence IS NOT NULL
  AND (avg_confidence < 0 OR avg_confidence > 1);

---

AUDIT (
  name assert_isic_entity_count_positive,
  model dev.mv_open_isic_entities_by_class,
  dialect postgres,
  description 'entity_count must be > 0 (group rows imply at least one confirmed entity).'
);
SELECT *
FROM dev.mv_open_isic_entities_by_class
WHERE entity_count <= 0;
