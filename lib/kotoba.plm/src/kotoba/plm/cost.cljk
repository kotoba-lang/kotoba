(ns kotoba.plm.cost
  "Phase 4 — standard-cost roll-up over the released MBOM.

   rolled(item) = std-unit-cost                              when :buy
                = Σ rolled(child) × qty [+ own process-cost]  when :make / :phantom

   Bottom-up recursion with cycle detection; throws on a :buy item missing its
   std-unit-cost so a half-defined product can't silently roll up to zero.

   The optional BOP process-cost term (ADR-2607141000) is opt-in via
   `:include-process?` — items with no routing (kotoba.plm.routing) contribute
   0, so existing 2/3-arity call sites are byte-identical to before."
  (:require [kotoba.plm.item :as plm]
            [kotoba.plm.routing :as routing]))

(defn rolled-cost
  "Standard cost of `iid`. With `asof` (java.util.Date) the roll-up only walks
   MBOM edges effective at that date; arity-2 rolls the whole structure.
   4-arity `opts` supports `:include-process?` (default false) to fold each
   :make/:phantom level's own kotoba.plm.routing/process-cost into the
   roll-up alongside its rolled material cost."
  ([d iid] (rolled-cost d iid nil))
  ([d iid asof] (rolled-cost d iid asof nil))
  ([d iid asof {:keys [include-process?]}]
   (letfn [(roll [iid seen]
             (when (contains? seen iid)
               (throw (ex-info "BOM cycle detected" {:item iid :seen seen})))
             (case (plm/make-buy d iid)
               :buy (or (plm/unit-cost d iid)
                        (throw (ex-info "buy item missing :std-unit-cost" {:item iid})))
               (:make :phantom)
               (cond-> (reduce (fn [acc {:keys [child qty]}]
                                 (+ acc (* (roll child (conj seen iid)) qty)))
                               0M
                               (plm/mbom-children d iid asof))
                 include-process? (+ (routing/process-cost d iid)))
               (throw (ex-info "unknown / unmastered item" {:item iid}))))]
     (roll iid #{}))))
