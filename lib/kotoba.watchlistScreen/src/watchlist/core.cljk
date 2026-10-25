(ns watchlist.core
  "Screening orchestration: index + query -> candidates + staleness, always
   together. `screen` never returns a bare candidate list without also
   saying how fresh (or absent) the data behind it was -- a caller must not
   be able to mistake 'checked against a 6-month-stale list' for 'checked
   against a fresh one', and must not be able to mistake 'the index failed
   to load' for 'the index loaded and found nothing' (see
   watchlist.adapters.aml-port for how this maps into a hard fail-closed
   AML level, mirroring aml.adapters.etzhayyim's own documented
   'never :clear on an unrecognized/absent signal' discipline)."
  (:require [watchlist.match :as match]
            [watchlist.model :as model]
            [watchlist.ports :as ports]))

(defn screen
  "Screen `query` (a plain name string) against every entity `index`
   currently holds. `now-ms` is a param, not read internally, so this stays
   clock-free/pure (matches watchlist.model/stale?'s own convention) --
   only `index`'s own entities/manifests calls are impure (file I/O in
   watchlist.adapters.edn-index)."
  [index query now-ms]
  (let [ents (ports/entities index)
        manifests (ports/manifests index)
        candidates (->> ents
                        (keep (fn [ent]
                                (when-let [m (match/best-entity-match query ent)]
                                  (assoc m :entity ent))))
                        (sort-by :confidence >)
                        vec)
        ages (keep #(model/list-age-days % now-ms) manifests)]
    {:watchlist/candidates candidates
     :watchlist/checked-sources (mapv :manifest/source manifests)
     ;; no manifest at all (index never loaded/refreshed) is treated the
     ;; same as every loaded source being past its staleness threshold --
     ;; both mean "we cannot vouch for this result being checked against
     ;; current data".
     :watchlist/stale? (or (empty? manifests) (boolean (some #(model/stale? % now-ms) manifests)))
     :watchlist/list-age-days (when (seq ages) (apply max ages))
     :watchlist/checked-at now-ms}))

(defn highest-confidence-candidate
  [result] (first (:watchlist/candidates result)))
