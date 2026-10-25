(ns ooyake.cells.reconcile.cell
  "LangGraph Pregel wrapper for the ooyake (公) reconcile cell — R0 scaffold.
  1:1 port of cells/reconcile/cell.py (ADR-2606021600 §5).

  ReconcileCell reconciles each :gov.unit against external authorities and promotes
    :representative / :unverified-seed → :authoritative / :maintainer-verified
  ONLY when :gov.unit/wikidata AND :gov.unit/official-url AGREE with the authority record
  (G5: agreement = verification; disagreement → kept unverified + reported). This cell is
  READ-SIDE (G9): it produces a promotion *report*; it never files, submits, or mutates a
  government record, and it never writes to the canonical seed.

  The offline, deterministic bundled-mode reconcile (parse-edn / load-units / load-authority /
  reconcile) is ported to cells/reconcile/state_machine.cljc. .solve() stays Council-gated at R0;
  live authority fetch (Wikidata / 行政機関コード / 全国地方公共団体コード / GeoNames) is
  public-data-only + ToS/rate-limit-disciplined and requires Council Lv6+ ratify + operator
  enablement.")

(defn solve
  [_input-state]
  (throw (ex-info (str "ooyake reconcile R0 cljc scaffold: cell .solve() disabled "
                       "(offline bundled-mode reconcile is ported to cells/reconcile/state_machine.cljc; "
                       "live authority fetch is Council Lv6+ + operator gated, ADR-2606021600)")
                  {:scaffold true :cell :reconcile})))
