(ns kototama.life
  "kototama · life — joucho (mood) + metabolism, distilled from
  kototama.unspsc.life / ibuki organism.cljc + metabolism.cljc. Both are
  deterministic FOLDS over the append-only log: an organism's inner state is not
  stored, it EMERGES from its lived history (replay → same mood, byte-identical
  crash-resume; 'mood at beat N' = fold over the first N txs)."
  (:require [kototama.kotoba :as kt]))

;; ───────────────────────── joucho (mood) ─────────────────────────

(def ^:private mood-delta
  "Closed event vocabulary → mood valence. Unknown events contribute 0 (no
  silent drift)."
  {:event/flourishing 2 :event/joyful 2 :event/served 1 :event/connected 1
   :event/idle 0 :event/uncertain -1 :event/stressed -2 :event/starved -2})

(defn- valence->mood [v]
  (cond (>= v 3) :flourishing (>= v 1) :content (>= v -1) :steady
        (>= v -3) :strained :else :depleted))

(defn fold-mood
  "Fold the log's :organism/event datoms into a mood keyword, starting from a
  baseline valence (personality). Replay-deterministic."
  ([conn] (fold-mood conn 0))
  ([conn baseline]
   (->> (kt/datoms conn)
        (filter (fn [[op _ a _]] (and (= op :db/add) (= a :organism/event))))
        (reduce (fn [v [_ _ _ ev]] (+ v (get mood-delta ev 0))) baseline)
        valence->mood)))

;; ───────────────────────── metabolism ─────────────────────────

(defn metabolism
  "Fold energy facts (:organism/intake, :organism/dissipation,
  :organism/exported, :organism/consumed) → {:phi :eta :surprise}.
    Φ = intake − dissipation        (net free-energy budget)
    η = exported ÷ consumed         (symbiosis: ≥1.0 = not a net taker)
    surprise = |intake − dissipation| normalized (variational proxy)"
  [conn]
  (let [ds (kt/datoms conn)
        sum (fn [a] (->> ds (filter (fn [[op _ at _]] (and (= op :db/add) (= at a))))
                         (map (fn [[_ _ _ v]] (or v 0))) (reduce + 0)))
        intake (sum :organism/intake) diss (sum :organism/dissipation)
        exported (sum :organism/exported) consumed (sum :organism/consumed)
        phi (- intake diss)]
    {:phi phi
     :eta (if (pos? consumed) (double (/ exported consumed)) 0.0)
     :surprise (if (pos? intake) (double (/ (abs phi) intake)) 0.0)}))

(defn net-taker?
  "An organism is a net taker (parasitic) when η < 1.0 — the 共生 gate. The
  catastrophe term vetoes persistence strategies that deepen this."
  [conn] (< (:eta (metabolism conn)) 1.0))
