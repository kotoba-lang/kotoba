(ns commoncrawl.report
  "Human-readable rendering of this actor's own append-only ledger/tick log
  — the operator-facing view of `commoncrawl.store/ledger` /
  `commoncrawl.store/tick-log`, same role `talent.store/ledger-line` plays
  for that actor."
  (:require [kotoba.lang.text :as str]))

(defn ledger-line
  "One ledger fact -> a one-line human-readable string."
  [{:keys [t domain url category confidence basis ingest-ok?] :as fact}]
  (case t
    :committed (str "commit  · " domain " · " url " · category=" (pr-str category)
                    " · confidence=" confidence " · net-kotobase-ok=" (boolean ingest-ok?))
    :policy-hold (str "hold    · " domain " · " url " · basis=" (pr-str basis))
    :fetch-miss (str "hold    · " domain " · " url " · basis=[:fetch-miss] (no capture / no usable text)")
    (str "?       · " (pr-str fact))))

(defn tick-line
  "One tick-log fact -> a one-line human-readable string."
  [{:keys [tick-id started-at attempted committed held budget-used budget-cap]}]
  (str "tick " tick-id " @ " started-at
       " · attempted=" attempted " · committed=" committed " · held=" held
       " · budget=" budget-used "/" budget-cap))

(defn render-ledger [facts] (str/join "\n" (map ledger-line facts)))
(defn render-ticks [facts] (str/join "\n" (map tick-line facts)))
