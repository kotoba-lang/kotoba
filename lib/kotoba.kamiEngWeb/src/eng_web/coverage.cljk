(ns eng-web.coverage
  "Coverage-report summary statistics, restored from `kami-eng-web/src/lib.rs`
  (`verify_coverage_report` wasm entry point), part of the legacy
  `kami-engine` Rust workspace deleted in kotoba-lang/kami-engine PR #82.
  See ADR-2607010930 (`com-junkawasaki/root`).

  The original built `total` synthetic `CoveragePoint`s (the first `hit` of
  them marked hit) and called `kami_verify::coverage::CoverageReport`'s
  `total_coverage()`/`uncovered_points()` methods (unported `kami-verify`
  crate). Those two aggregate statistics are simple arithmetic over
  `total`/`hit` and are reproduced here directly, without needing the
  point-by-point struct machinery.")

(defn coverage-stats
  "Compute the coverage summary for `total` coverage points of which `hit`
  (the first `hit`, by construction) are covered. Returns
  `total-coverage-pct` as a percentage in [0, 100]."
  [total hit]
  {:total-coverage-pct (if (pos? total) (* 100.0 (/ (double hit) total)) 0.0)
   :total-points total
   :hit-points hit
   :uncovered-count (max 0 (- total hit))})
