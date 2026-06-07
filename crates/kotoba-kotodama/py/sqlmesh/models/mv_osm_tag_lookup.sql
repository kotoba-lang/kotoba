-- OSM tag lookup: exploded (key, value) pairs from current OSM elements.
MODEL (
  name dev.mv_osm_tag_lookup,
  kind FULL,
  dialect postgres,
  description 'Per OSM element with valid_to IS NULL: exploded jsonb tags into (key, value, vertex_id, s2_cell_id).',
  grain [vertex_id, key],
  tags [osm, tag, lookup]
);

SELECT
  v.vertex_id,
  v.osm_type,
  t.key,
  t.value,
  v.s2_cell_id
FROM vertex_osm_element AS v,
     jsonb_each_text(v.tags) AS t(key, value)
WHERE v.valid_to IS NULL
