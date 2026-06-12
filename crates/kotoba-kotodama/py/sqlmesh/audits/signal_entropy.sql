-- SQLMesh audit: mv_signal_entropy invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_signal_entropy_h_ordered,
  model dev.mv_signal_entropy,
  dialect postgres,
  description 'h_avg must not exceed h_max.'
);
SELECT *
FROM dev.mv_signal_entropy
WHERE h_avg > h_max;

---

AUDIT (
  name assert_signal_entropy_eta_bounded,
  model dev.mv_signal_entropy,
  dialect postgres,
  description 'eta (Shannon efficiency) must be in [0, 1].'
);
SELECT *
FROM dev.mv_signal_entropy
WHERE eta < 0 OR eta > 1;
