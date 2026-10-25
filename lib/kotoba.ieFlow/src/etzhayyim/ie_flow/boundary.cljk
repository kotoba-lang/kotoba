(ns etzhayyim.ie-flow.boundary
  "etzhayyim.ie-flow.boundary — every actor is a BOUNDED dissipative system. ADR-2606211200.

  The user's design: each actor must carry its OWN system-of-systems-dynamics AND its OWN system
  boundary. A boundary is a MEMBRANE that partitions the world into the actor's interior and its
  environment, and meters what crosses:

    IMPORT  free energy drawn IN across the membrane (env → inside): donated compute, public data,
            attention (Wellbecoming-capped), donations, members, or an UPSTREAM actor's output.
    INSIDE  the actor's own stations (the shared core kotoba-ledger/react-loop/co-scientist +
            the actor's role-specific organs) where imported flow is RECTIFIED.
    EXPORT  low-entropy ORDER returned OUT across the membrane (inside → commons / 子孫 / members /
            a downstream actor): a release-map, provisioned value, a leverage-map, food-web commons…

  So an actor's net-gain (did the metabolism pay for itself) and order-index (was scattered intake
  rectified to concentrated outcome = 負エントロピー輸出) are computed over ITS OWN boundary-crossing
  events, and its system-dynamics stocks evolve under ITS OWN import/export rates. The colony is then
  a SYSTEM OF these bounded systems (kaname synthesises across them; the ABM couples them).

  Per-actor flow is a deterministic REPRESENTATIVE seed (role-derived) until the actor's live `embed`
  measurement (record!/beat!) populates 80-data/ie-flow/<actor>/flow.kotoba.edn. Pure, stdlib +
  ie-flow.metrics only — no I/O, no held key."
  (:require [etzhayyim.ie-flow.metrics :as metrics]))

;; ── per-actor role descriptors: the membrane (imports/exports) + interior organs ──
;; Numbers are REPRESENTATIVE (same unit as the repo-git flow, e.g. JPY-analog) and deterministic —
;; they encode each actor's characteristic metabolism, not a live measurement. An import carries a
;; :volume (throughput) and :cost (free energy spent to draw it); an export carries the :value
;; (order returned). :agent-costs feeds agent-efficiency (the 課金される魔法陣 test).

(def actor-roles
  {"ibuki"
   {:role "artificial organism — metabolism IS an IE-flow"
    :inside ["ledger" "react-loop" "co-scientist" "metabolism" "food-web"]
    :imports [{:kind "donated-compute" :from "donors" :volume 800 :cost 600}
              {:kind "attention-capped" :from "society" :volume 300 :cost 80}
              {:kind "donation" :from "donors" :volume 200 :cost 0}
              {:kind "members" :from "members" :volume 250 :cost 40}
              {:kind "moyai" :from "commons" :volume 120 :cost 10}]
    :exports [{:kind "food-web-commons" :to "commons" :value 1400}
              {:kind "narration" :to "society" :value 300}]
    :agent-costs {:gross-profit 1700 :api-cost 220 :human-cost 60 :failure-cost 40}}

   "tsumugi"
   {:role "power-entity 取-concentration mirror → RELEASE"
    :inside ["ledger" "react-loop" "co-scientist" "weave" "karma"]
    :imports [{:kind "public-data" :from "society" :volume 900 :cost 120}
              {:kind "compute" :from "Murakumo" :volume 400 :cost 300}]
    :exports [{:kind "取-release-map" :to "commons" :value 1600}]
    :agent-costs {:gross-profit 1600 :api-cost 300 :human-cost 30 :failure-cost 20}}

   "shionome"
   {:role "cross-asset capital-flow observatory"
    :inside ["ledger" "react-loop" "co-scientist" "flow-graph" "rotation"]
    :imports [{:kind "market-data" :from "society" :volume 700 :cost 100}
              {:kind "compute" :from "Murakumo" :volume 350 :cost 260}]
    :exports [{:kind "flow-map" :to "commons" :value 1100}]
    :agent-costs {:gross-profit 1100 :api-cost 260 :human-cost 20 :failure-cost 30}}

   "kaname"
   {:role "system-of-systems leverage synthesizer (multiplex)"
    :inside ["ledger" "react-loop" "co-scientist" "multiplex-join" "centrality"]
    :imports [{:kind "actor-outputs" :from "other-actors" :volume 1200 :cost 80}
              {:kind "compute" :from "Murakumo" :volume 300 :cost 220}]
    :exports [{:kind "leverage-map" :to "ossekai" :value 900}
              {:kind "おせっかい" :to "commons" :value 250}]
    :agent-costs {:gross-profit 1150 :api-cost 220 :human-cost 25 :failure-cost 35}}

   "okaimono"
   {:role "provisioning commons — value returned to members"
    :inside ["ledger" "react-loop" "co-scientist" "ring0-commons" "checkout"]
    :imports [{:kind "member-checkout" :from "members" :volume 1500 :cost 30}
              {:kind "catalog-data" :from "society" :volume 600 :cost 90}]
    :exports [{:kind "provisioned-value" :to "members" :value 1800}]
    :agent-costs {:gross-profit 1800 :api-cost 90 :human-cost 40 :failure-cost 10}}})

(defn adopters [] (vec (sort (keys actor-roles))))

;; ── boundary → flow events (the partition the metrics read) ──────────────────

(defn boundary-events
  "Project an actor's membrane into measured flow EVENTS. Each IMPORT is an env→inside draw
  (cost-bearing, value 0); each EXPORT is an inside→commons return (value-bearing, cost 0). The
  partition IS the boundary. Deterministic ids. Pure."
  [actor]
  (let [r (actor-roles actor)
        inside (str actor "·inside")]
    (vec
      (concat
        (map-indexed
          (fn [i im] {:id (str actor "-in-" i) :actor actor
                      :source (:from im) :target inside :type (str "import:" (:kind im))
                      :volume (:volume im 0) :cost (:cost im 0) :value 0 :risk 0 :agent? false})
          (:imports r))
        (map-indexed
          (fn [i ex] {:id (str actor "-out-" i) :actor actor
                      :source inside :target (:to ex) :type (str "export:" (:kind ex))
                      :volume (:value ex 0) :cost 0 :value (:value ex 0) :risk 0 :agent? true})
          (:exports r))))))

(defn measure
  "Fold an actor's boundary-crossing events into ITS OWN IE-flow state (net-gain / order-index /
  agent-efficiency …), using the actor's representative agent-costs. Pure."
  [actor]
  (let [r (actor-roles actor)]
    (metrics/flow-state (boundary-events actor) {:agent-costs (:agent-costs r)})))

(defn boundary
  "The full per-actor system boundary descriptor: interior stations + the metered membrane (imports
  in / exports out) + the measured IE-flow state. `representative` = not yet a live measurement."
  [actor]
  (let [r (actor-roles actor)]
    {:id actor
     :role (:role r)
     :representative true
     :inside (:inside r)
     :imports (vec (:imports r))
     :exports (vec (:exports r))
     :state (measure actor)}))
