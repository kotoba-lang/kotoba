-- Airline FFP active member count and average total miles per carrier and tier.
MODEL (
  name dev.mv_air_member_tier_summary,
  kind FULL,
  dialect postgres,
  description 'Active member count and avg total_miles per carrier_code and tier from vertex_air_ffp_member.',
  grain [carrier_code, tier],
  tags [air, ffp, member, tier, miles, loyalty]
);

SELECT
  carrier_code,
  tier,
  COUNT(*) AS member_count,
  AVG(total_miles) AS avg_total_miles
FROM vertex_air_ffp_member
WHERE status = 'active'
GROUP BY carrier_code, tier
