(ns watchlist.model
  "Sanctions/PEP watchlist entity records, list-source metadata, and match
   tiers — pure data + validators, no I/O, no matching logic (that's
   watchlist.match) and no screening orchestration (that's watchlist.core).")

(def sources #{:ofac-sdn :un-consolidated :jp-mof})
;; :jp-mof is Japan's MOF 資産凍結等対象者一覧 (asset-freeze targets under the
;; 外為法). It is a SANCTIONS list, the same subject as the other two -- not a
;; 反社会的勢力 (organised-crime) list. No Japanese authority publishes one of
;; those in machine-readable form, and this repo must not be described as
;; screening for one.
;; EU Consolidated Financial Sanctions List is NOT in `sources` — the EU's
;; machine-readable source (the FSD/FSF API) requires a registered access
;; token to fetch, a real owner action this repo cannot script around.
;; watchlist.adapters.eu-consolidated exists as a stub documenting exactly
;; this gap; adding :eu-consolidated to `sources` is the follow-up once a
;; token is provisioned. See README.md / MATURITY.md.

(def entity-types #{:individual :entity})

(def match-tiers #{:exact :fuzzy-high :fuzzy-low})
;; :exact       -- normalized full-name string equality, confidence 1.0
;; :fuzzy-high  -- Jaro-Winkler >= 0.92, or all query tokens present in the
;;                 candidate name (order-independent) -- confidence in [0.75 0.92)
;; :fuzzy-low   -- Jaro-Winkler in [0.80 0.92), or partial token overlap
;;                 >= 0.6 -- confidence in [0.55 0.75), :review-required true
;; Below these thresholds is NOT a match candidate at all (see watchlist.match's
;; module doc for the explicit false-negative risk this bound accepts).

(defn entity
  "A normalized watchlist entity, folded from any source's native schema by
   that source's adapter. `id` is source-namespaced (e.g. \"ofac-sdn:2674\",
   \"un-consolidated:6907993\") so ids never collide across sources."
  [id source opts]
  {:entity/id id
   :entity/source source
   :entity/type (:type opts)
   :entity/primary-name (:primary-name opts)
   :entity/aliases (vec (:aliases opts))
   :entity/dob (:dob opts)
   :entity/nationality (vec (:nationality opts))
   :entity/programs (vec (:programs opts))
   :entity/source-updated-at (:source-updated-at opts)})

(defn valid-entity?
  [e]
  (and (string? (:entity/id e))
       (contains? sources (:entity/source e))
       (contains? entity-types (:entity/type e))
       (string? (:entity/primary-name e))
       (seq (:entity/primary-name e))))

(defn list-manifest
  "One source's fetch/ingestion provenance — every screening result carries
   this so a caller can tell how fresh the data behind a 'no match' actually
   was (see watchlist.core/screen and this ns's staleness fields)."
  [source opts]
  {:manifest/source source
   :manifest/fetched-at (:fetched-at opts)
   :manifest/source-published-at (:source-published-at opts)
   :manifest/entity-count (:entity-count opts)
   :manifest/sha256 (:sha256 opts)})

(def default-stale-after-days 14)

(defn stale?
  "Whether `manifest` is older than `max-age-days` (default
   `default-stale-after-days`) as of `now-ms`. `now-ms` is a param, not
   read internally, so this stays clock-free/pure like isekai.fork-stats'
   convention for the same reason (caller controls the clock)."
  ([manifest now-ms] (stale? manifest now-ms default-stale-after-days))
  ([manifest now-ms max-age-days]
   (let [fetched-at (:manifest/fetched-at manifest)]
     (or (nil? fetched-at)
         (> (- now-ms fetched-at) (* max-age-days 86400000))))))

(defn list-age-days
  [manifest now-ms]
  (when-let [fetched-at (:manifest/fetched-at manifest)]
    (double (/ (- now-ms fetched-at) 86400000))))
