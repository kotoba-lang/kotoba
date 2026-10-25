(ns watchlist.adapters.aml-port
  "aml.ports/IAmlScreening implementation backed by a watchlist.ports/
   IWatchlistIndex. Mirrors aml.adapters.etzhayyim/screening-port's shape
   and, critically, its fail-closed discipline (that ns's own doc:
   ':clear must never be the default for we don't actually know' — an
   AML/sanctions clearance requires a positive observed signal, not merely
   the absence of one').

   NOT YET WIRED into aml.core/screen's routing — aml.model/routes is
   [:yabai :malak], a closed vector this repo does not own; adding
   :watchlist requires a small follow-up PR to kotoba-lang/aml itself (see
   README.md). This port is directly callable standalone in the meantime
   (`(screen! port request :watchlist)`)."
  (:require [aml.model :as aml-model]
            [aml.ports :as aml-ports]
            [watchlist.core :as core]))

(defn- subject-name
  "Extract a screenable name string from an aml.model request's
   :aml/subject. Watchlist screening is NAME matching -- a subject that's
   only an opaque did/wallet-address with no name attached has nothing to
   screen against (returns nil; the caller fails closed on that, see
   `result-level`), unlike aml.adapters.etzhayyim's subject-id which
   extracts an opaque id for a downstream risk-scoring API that doesn't
   need a name at all."
  [request]
  (let [subject (:aml/subject request)]
    (cond
      (string? subject) subject
      (map? subject) (or (:subject/name subject) (:identity.subject/name subject) (:name subject))
      :else nil)))

(defn- tier->level
  [tier]
  (case tier
    :exact :deny
    :fuzzy-high :challenge
    :fuzzy-low :review
    :review))

(defn- result-level
  "Fail-closed: an absent name, a stale/absent index, and zero candidates
   are three DIFFERENT states and must not collapse to the same :clear --
   only 'we actually screened a name against current data and found
   nothing' may clear."
  [screen-result has-name?]
  (cond
    (not has-name?) :review
    (nil? screen-result) :review
    (:watchlist/stale? screen-result) :review
    :else (if-let [top (core/highest-confidence-candidate screen-result)]
            (tier->level (:tier top))
            :clear)))

(defn screening-port
  "`index` is a watchlist.ports/IWatchlistIndex (e.g.
   watchlist.adapters.edn-index/edn-index). `now-ms-fn` defaults to the
   system clock -- a param so tests can inject a fixed clock, matching
   watchlist.core/screen's own 'now-ms is a param, not read internally'
   convention one level up."
  ([index] (screening-port index #(#?(:clj System/currentTimeMillis :cljs (.getTime (js/Date.))))))
  ([index now-ms-fn]
   (reify aml-ports/IAmlScreening
     (screen! [_ request route]
       (when (not= :watchlist route)
         (throw (ex-info "watchlist.adapters.aml-port only handles the :watchlist route"
                          {:route route})))
       (let [subject (subject-name request)
             result (when subject (core/screen index subject (now-ms-fn)))
             level (result-level result (some? subject))
             top (some-> result core/highest-confidence-candidate)]
         (aml-model/result request route level
                            {:score (some-> top :confidence (* 1000) long)
                             :categories (set (some-> top :entity :entity/programs))
                             :evidence-ref (some-> top :entity :entity/id)
                             :asserter "watchlist-screen"
                             :observed-at (:watchlist/checked-at result)}))))))
