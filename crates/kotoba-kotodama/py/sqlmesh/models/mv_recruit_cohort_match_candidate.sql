-- Recruit cohort match candidate: job postings joined with talent cohort + demand forecast for match scoring.
MODEL (
  name dev.mv_recruit_cohort_match_candidate,
  kind FULL,
  dialect postgres,
  description 'Per (posting, cohort, demand_forecast): match_score driven by employer/source/cohort/demand signals.',
  grain [posting_vid, cohort_vid],
  tags [recruit, cohort, match, candidate]
);

SELECT
  p.vertex_id AS posting_vid,
  COALESCE(p.source_id, p.vertex_id) AS posting_id,
  p.title,
  p.employer_did,
  p.employer_name,
  p.source,
  p.source_url,
  p.isco_code,
  p.country,
  p.location,
  p.remote_allowed,
  p.employment_type,
  p.salary_min,
  p.salary_max,
  p.salary_currency,
  p.posted_at,
  c.vertex_id AS cohort_vid,
  c.source AS cohort_source,
  c.size_thousands AS supply_size_thousands,
  c.time_period AS cohort_period,
  d.vertex_id AS demand_forecast_vid,
  COALESCE(d.demand_score, 0.0) AS demand_score,
  COALESCE(d.press_signal_count, 0) AS press_signal_count,
  COALESCE(d.posting_count, 0) AS demand_posting_count,
  d.typical_salary,
  d.top_skills,
  (
    CASE WHEN p.employer_did IS NOT NULL AND p.employer_did <> '' THEN 20.0 ELSE 0.0 END
    + CASE WHEN p.source_url IS NOT NULL AND p.source_url <> '' THEN 10.0 ELSE 0.0 END
    + CASE WHEN c.size_thousands IS NOT NULL THEN 20.0 ELSE 0.0 END
    + LEAST(40.0, COALESCE(d.demand_score, 0.0) * 40.0)
    + LEAST(10.0, COALESCE(d.posting_count, 0)::DOUBLE PRECISION)
  ) AS match_score
FROM vertex_job_posting p
JOIN vertex_talent_cohort c
  ON c.isco_code = p.isco_code
  AND c.country = p.country
LEFT JOIN vertex_demand_forecast d
  ON d.isco_code = p.isco_code
  AND d.country = p.country
WHERE p.isco_code IS NOT NULL
  AND p.isco_code <> ''
  AND p.country IS NOT NULL
  AND p.country <> ''
