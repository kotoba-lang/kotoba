-- Iryo bed occupancy now: current bed utilization per ward.
MODEL (
  name dev.mv_iryo_bed_occupancy_now,
  kind FULL,
  dialect postgres,
  description 'Per (hospital_slug, ward_slug): total beds, occupied beds, utilization ratio (active beds).',
  grain [hospital_slug, ward_slug],
  tags [iryo, bed, occupancy]
);

SELECT
  hospital_slug,
  ward_slug,
  COUNT(*) AS total_beds,
  SUM(CASE WHEN occupied THEN 1 ELSE 0 END) AS occupied_beds,
  safe_divide(
    SUM(CASE WHEN occupied THEN 1.0 ELSE 0.0 END),
    COUNT(*)::DOUBLE PRECISION,
    0.0
  ) AS utilization
FROM vertex_iryo_bed
WHERE status = 'active'
GROUP BY hospital_slug, ward_slug
