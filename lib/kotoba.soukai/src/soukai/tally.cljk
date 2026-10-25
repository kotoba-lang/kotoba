(ns soukai.tally
  "Pure deterministic vote tally — ZERO LLM/governor/store dependency, just
  data in, data out. This is the single source of truth for 'did a
  resolution pass'; `soukai.governor`'s `resolution-mismatch` HARD check
  exists specifically to force the secretary-LLM to agree with this
  namespace's output, never invent a different one (ADR-2607121700 §4.5 —
  'a single unbreakable invariant: secretary-LLM never rewrites the
  tally').

  All quorum/threshold comparisons use EXACT rational comparison via
  cross-multiplication (`(>= (* a d) (* b n))` instead of `(>= (/ a b) (/ n
  d))`), never floating-point division — this is a legally-binding
  computation and must never be subject to float rounding at a boundary
  (e.g. exactly 1/2 or exactly 2/3).

  **R0 modeling choices, stated honestly (not silently asserted as the only
  correct reading of 会社法):**

  1. Votes referencing a shareholder-id NOT present in the meeting's
     record-date snapshot are structurally excluded from every sum
     (record-date-consistency enforcement, 会社法第124条 the underlying
     principle — only shareholders of record as of the record date may
     exercise voting rights) and reported separately in `:invalid-votes`,
     never silently counted. This is a `soukai.tally` responsibility, not
     the governor's — filtering happens before any hard/soft check runs.

  2. **Abstentions (:abstain) are excluded from the approval threshold's
     denominator** for `:ordinary-resolution`/`:special-resolution` (i.e.
     approval = for / (for + against) >= threshold, NOT for / attending).
     This matches the convention most Japanese companies use in practice
     for 普通決議/特別決議 vote-counting, but it is NOT the only
     interpretation in circulation — some readings include abstentions in
     the base (treating a non-vote-for as effectively counting against
     approval via a larger denominator). This repo picks the
     exclude-abstentions convention as R0's default and flags it here
     explicitly rather than presenting it as the single correct reading of
     会社法309条; an operator with a different house convention must treat
     this as a known, documented simplification to override, not a bug to
     quietly patch around.

  3. `:special-resolution-2`'s (会社法第309条3項/4項) headcount AND
     voting-rights thresholds are BOTH measured against the meeting's
     TOTAL shareholder universe (`snapshot`'s full keyset / the sum of ALL
     its voting-rights), never against attendance — this is precisely what
     makes 特殊決議 structurally stricter than 特別決議 (which measures
     against attendance). Concretely: `:for-headcount` / `:total-headcount`
     and `:for` / `:total-voting-rights` are the two ratios that must each
     clear their threshold, not `:for-headcount` / `:attending-headcount`
     or `:for` / `:attending-voting-rights`."
  (:require [soukai.facts :as facts]))

(defn outcome-of
  "agenda: {:resolution-type kw, optionally :aoi/quorum-num :aoi/quorum-den
    :aoi/threshold-num :aoi/threshold-den} — the FULL agenda map (not just
    :resolution-type), so this can honor a legally-bounded AOI override
    via `soukai.facts/effective-resolution-requirements` rather than
    always reading the raw statutory-default `soukai.facts/
    resolution-requirements` catalog directly (an AOI-customized agenda
    must produce an AOI-customized TALLY, not just an AOI-customized
    report about the tally).
    resolution-type (inside agenda): :ordinary-resolution |
    :special-resolution | :special-resolution-2
   snapshot: {shareholder-id -> voting-rights}, as of the meeting's record
    date (see `soukai.store/snapshot-of`).
   votes: seq of {:shareholder-id :agenda-id :voting-rights :choice :method}
    maps — may reference shareholder-ids NOT in `snapshot`; those are
    structurally filtered out (see namespace docstring #1) and reported in
    `:invalid-votes`, never silently counted toward any sum below.

  Returns:
   {:total-voting-rights     (sum of every value in `snapshot`)
    :attending-voting-rights (sum of :voting-rights over valid votes)
    :invalid-votes           [vote ...] ; excluded, shareholder-id not in snapshot
    :for :against :abstain   (sums of :voting-rights per :choice, valid votes only)
    :attending-headcount     (count of distinct valid voting shareholder-ids)
    :quorum-met?             bool — always true for :special-resolution-2
                              (no quorum requirement, 会社法309条3項/4項)
    :outcome                 :approved | :rejected | :no-quorum
    ;; :special-resolution-2 only (see namespace docstring #3):
    :total-headcount         (count of ALL shareholders in `snapshot`)
    :for-headcount}          (count of distinct shareholder-ids who voted :for)"
  [agenda snapshot votes]
  (let [resolution-type (:resolution-type agenda)
        total        (reduce + 0 (vals snapshot))
        {valid true invalid false} (group-by #(contains? snapshot (:shareholder-id %)) votes)
        valid        (vec (or valid []))
        invalid      (vec (or invalid []))
        attending    (reduce + 0 (map :voting-rights valid))
        by-choice    (group-by :choice valid)
        for-sum      (reduce + 0 (map :voting-rights (get by-choice :for [])))
        against-sum  (reduce + 0 (map :voting-rights (get by-choice :against [])))
        abstain-sum  (reduce + 0 (map :voting-rights (get by-choice :abstain [])))
        attending-hc (count (distinct (map :shareholder-id valid)))
        req          (facts/effective-resolution-requirements agenda)
        base         {:total-voting-rights total
                      :attending-voting-rights attending
                      :invalid-votes invalid
                      :for for-sum :against against-sum :abstain abstain-sum
                      :attending-headcount attending-hc}]
    (case resolution-type
      :special-resolution-2
      (let [{:keys [headcount-threshold-num headcount-threshold-den
                    rights-threshold-num rights-threshold-den]} req
            total-hc      (count snapshot)
            for-hc        (count (distinct (map :shareholder-id (get by-choice :for []))))
            headcount-ok? (>= (* for-hc headcount-threshold-den) (* total-hc headcount-threshold-num))
            rights-ok?    (>= (* for-sum rights-threshold-den) (* total rights-threshold-num))]
        (assoc base
               :total-headcount total-hc
               :for-headcount   for-hc
               :quorum-met?     true
               :outcome         (if (and headcount-ok? rights-ok?) :approved :rejected)))

      (:ordinary-resolution :special-resolution)
      (let [{:keys [quorum-num quorum-den threshold-num threshold-den]} req
            quorum-met? (>= (* attending quorum-den) (* total quorum-num))]
        (if-not quorum-met?
          (assoc base :quorum-met? false :outcome :no-quorum)
          (let [denom      (+ for-sum against-sum)
                approved?  (and (pos? denom) (>= (* for-sum threshold-den) (* denom threshold-num)))]
            (assoc base :quorum-met? true :outcome (if approved? :approved :rejected))))))))
