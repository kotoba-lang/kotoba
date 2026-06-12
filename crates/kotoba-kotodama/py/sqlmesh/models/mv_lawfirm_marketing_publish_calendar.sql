-- Lawfirm marketing publish calendar: approved and pending marketing assets with schedule.
MODEL (
  name dev.mv_lawfirm_marketing_publish_calendar,
  kind FULL,
  dialect postgres,
  description 'Approved/pending marketing assets: kind, brand, schedule, target/published URLs.',
  grain [target_url, scheduled_at],
  tags [lawfirm, marketing, publish, calendar]
);

SELECT
  asset_kind,
  brand,
  compliance_check,
  scheduled_at,
  published_at,
  title,
  target_url,
  published_url
FROM vertex_lawfirm_marketing_asset
WHERE compliance_check IN ('approved', 'pending')
