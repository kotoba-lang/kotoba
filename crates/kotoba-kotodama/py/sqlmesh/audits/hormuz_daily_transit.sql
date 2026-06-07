-- SQLMesh audit: mv_open_hormuz_daily_transit invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_hormuz_laden_le_passage,
  model dev.mv_open_hormuz_daily_transit,
  dialect postgres,
  description 'laden_count must not exceed passage_count.'
);
SELECT *
FROM dev.mv_open_hormuz_daily_transit
WHERE laden_count > passage_count;

---

AUDIT (
  name assert_hormuz_passage_count_positive,
  model dev.mv_open_hormuz_daily_transit,
  dialect postgres,
  description 'passage_count must be > 0 (group rows imply at least one recorded passage).'
);
SELECT *
FROM dev.mv_open_hormuz_daily_transit
WHERE passage_count <= 0;
