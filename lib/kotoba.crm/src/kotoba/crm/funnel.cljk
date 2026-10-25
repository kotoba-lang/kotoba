(ns kotoba.crm.funnel
  "Aggregate cross-record pipeline funnel/conversion analytics for
  dashboards -- point-in-time snapshot distribution, cumulative
  'how far did entities get' counts, and stage-to-stage conversion
  rates, all derived from a plain collection of entities plus the same
  `ordered-stages` vector `kotoba.crm.pipeline` uses.

  This is a DISTINCT concept from each actor's own `crm.report`/
  `report.cljc` (GOVERNED single-record disclosure rendering for one
  entity at a time). `funnel` never renders or discloses a single
  record; it only aggregates counts across many records for a
  dashboard-style rollup. Like `revrec` and `leadscore`, this is a PURE,
  storage-agnostic namespace: no I/O, no platform interop, entities are
  plain maps supplied by the caller.

  Honest scope (R0, see `coverage` below): a point-in-time snapshot only
  -- there is no time dimension, no stage-history log, and no cohort
  tracking. `reached-counts` relies on the invariant
  `kotoba.crm.pipeline/valid-transition?` enforces elsewhere in this
  fleet (forward-only, no-skip stage progression): an entity's CURRENT
  ordered-stage rank is proof it passed through every lower rank, so no
  history log is needed for entities still in an ordered stage. Entities
  currently in an exit stage (e.g. `:closed-lost`) are a genuine
  ambiguity this namespace does NOT guess through -- see `reached-counts`
  and `coverage`."
  (:require [kotoba.crm.pipeline :as pipeline]))

(defn stage-counts
  "Point-in-time snapshot distribution: a map of `stage -> count` of
  `entities` CURRENTLY at that stage right now (by each entity's plain
  `:stage` key). Always computable from a snapshot alone -- no
  stage-history log required -- so this is the honest R0 baseline every
  other function in this namespace builds on.

  Every stage in `ordered-stages` is included in the result even when its
  count is zero (a caller building a funnel chart should see the full
  shape of the pipeline, not just the stages that happen to be
  occupied). Entities whose `:stage` is something OTHER than an ordered
  stage (e.g. an exit stage like `:closed-lost`, or any other value) are
  still counted, under that stage's own key -- this function never
  drops or silently reclassifies an entity's stage, it only guarantees
  the ordered stages are present even at zero."
  [entities ordered-stages]
  (let [zero-filled (zipmap ordered-stages (repeat 0))
        actual      (frequencies (map :stage (or entities [])))]
    (merge zero-filled actual)))

(defn- effective-reached-rank
  "The ordered-stage rank to credit `entity` with having REACHED, for
  `reached-counts` purposes. If `entity`'s current `:stage` is itself an
  ordered stage, its rank is used directly (per the forward-only,
  no-skip invariant, reaching stage N means having passed through every
  stage below N). If `:stage` is NOT an ordered stage (most likely an
  exit stage, e.g. `:closed-lost`, reached from any non-terminal stage
  per `kotoba.crm.pipeline/valid-transition?`), the last ordered stage
  actually passed through before exiting is NOT recoverable from
  `:stage` alone -- this function does not guess it. It only recovers a
  rank in that case from an explicit `:reached-stage` fact on the
  entity (the caller's own record of the last ordered stage passed
  through before exit), if present and itself a valid ordered stage.
  Otherwise returns nil, meaning the entity is excluded from
  `reached-counts` entirely (see `coverage`)."
  [ordered-stages {:keys [stage reached-stage]}]
  (or (pipeline/stage-rank ordered-stages stage)
      (when (some? reached-stage)
        (pipeline/stage-rank ordered-stages reached-stage))))

(defn reached-counts
  "For each stage `S` in `ordered-stages`, the count of `entities` that
  got AT LEAST as far as `S` -- the classic funnel-view metric ('how
  many entities reached this stage'), valid only under this fleet's
  established invariant that `kotoba.crm.pipeline/valid-transition?`
  enforces strictly forward, no-skip stage progression: an entity's
  current ordered-stage rank is proof it passed through every lower
  rank, with no stage-history log required.

  EXIT-STAGE POLICY (read before using): an entity currently in an exit
  stage (e.g. `:closed-lost`, reachable from any non-terminal stage) is
  a genuine ambiguity -- which forward stage it exited FROM is not
  recoverable from its current `:stage` alone. This function does NOT
  guess. By default such entities are EXCLUDED from `reached-counts`
  entirely (they do not contribute to any stage's count, including
  stage 0). If the caller's entity carries an explicit `:reached-stage`
  fact (the last ordered stage it actually passed through before
  exiting -- the caller's own record, e.g. captured at the moment of
  the exit transition), that stage's rank is used instead, so the exited
  entity IS counted as having reached every stage up to and including
  `:reached-stage`. There is no implicit default for `:reached-stage`;
  omitting it means exclusion, not a guessed rank of 0 or of the last
  ordered stage.

  Entities whose `:stage` (and, if present, `:reached-stage`) are
  neither a valid ordered stage are likewise excluded rather than
  guessed."
  [entities ordered-stages]
  (let [ranks (keep #(effective-reached-rank ordered-stages %) (or entities []))]
    (into {}
          (map (fn [stage]
                 (let [r (pipeline/stage-rank ordered-stages stage)]
                   [stage (count (filter #(>= % r) ranks))])))
          ordered-stages)))

(defn conversion-rate
  "Stage-to-stage conversion rate between every consecutive pair of
  `ordered-stages`, keyed by a `[from-stage to-stage]` vector: the
  fraction of entities that reached `from-stage` which also reached
  `to-stage` (`(reached to-stage) / (reached from-stage)`, as a double).

  `stage-counts-or-entities` may be EITHER an already-computed
  `reached-counts` map (`stage -> count`) OR a raw entity collection, in
  which case `reached-counts` is computed internally first -- either
  calling convention is accepted so a caller who already has counts
  (e.g. from a cached dashboard query) doesn't pay to recompute them.

  Division-by-zero (no entity ever reached `from-stage`) returns `nil`
  for that pair specifically, never a crash and never a fabricated 0%
  or Infinity -- `nil` here means 'no data', not 'zero conversion'."
  [stage-counts-or-entities ordered-stages]
  (let [reached (if (map? stage-counts-or-entities)
                  stage-counts-or-entities
                  (reached-counts stage-counts-or-entities ordered-stages))]
    (into {}
          (map (fn [[from to]]
                 (let [from-n (get reached from 0)
                       to-n   (get reached to 0)]
                   [[from to] (when (pos? from-n) (double (/ to-n from-n)))])))
          (partition 2 1 ordered-stages))))

(defn coverage
  "Honest, machine-checkable report of what R0 actually covers."
  []
  {:model :point-in-time-snapshot-funnel
   :note (str "R0 scope: a single point-in-time snapshot only, derived "
              "entirely from entities' CURRENT :stage (plus an optional "
              "caller-supplied :reached-stage fact for exited entities) "
              "-- there is no stage-history log, no time dimension, and "
              "no cohort tracking. stage-counts is a plain snapshot "
              "distribution (always computable, zero-fills every "
              "ordered stage). reached-counts and conversion-rate rely "
              "on kotoba.crm.pipeline/valid-transition?'s forward-only, "
              "no-skip invariant to treat current ordered-stage rank as "
              "proof of having passed every lower rank. EXIT-STAGE "
              "POLICY: entities currently in an exit stage (e.g. "
              "\":closed-lost\") are EXCLUDED from reached-counts / "
              "conversion-rate by default, because which forward stage "
              "they exited from is not recoverable from :stage alone -- "
              "this is never guessed. An entity is only credited past "
              "exit via an explicit :reached-stage fact the caller "
              "supplies (the last ordered stage passed through before "
              "exit). NOT modeled at all: time-in-stage / velocity "
              "metrics (how LONG entities dwell in a stage), "
              "cohort-over-time trending (this is one snapshot, not a "
              "time series -- comparing snapshots across time is the "
              "caller's job), multi-touch attribution, and exit-stage "
              "sub-classification (e.g. distinguishing WHY an exit "
              "happened, such as won vs lost reasons) beyond whatever "
              "distinct exit-stage keywords the caller's own pipeline "
              "already encodes. Extend only by adding a genuinely new, "
              "documented metric, never by guessing.")})
