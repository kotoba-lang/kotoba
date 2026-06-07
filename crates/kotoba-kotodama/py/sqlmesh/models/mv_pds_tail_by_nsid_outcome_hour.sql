-- PDS tail by NSID/outcome/hour: per-(NSID, outcome, hour) event counts.
MODEL (
  name dev.mv_pds_tail_by_nsid_outcome_hour,
  kind FULL,
  dialect postgres,
  description 'Per (nsid, outcome, event_hour): count of PDS tail events.',
  grain [nsid, outcome, event_hour],
  tags [pds, tail, observability, nsid]
);

SELECT
  nsid,
  outcome,
  date_trunc('hour', event_ts) AS event_hour,
  COUNT(*) AS cnt
FROM vertex_pds_tail_event
WHERE nsid IS NOT NULL
GROUP BY nsid, outcome, date_trunc('hour', event_ts)
