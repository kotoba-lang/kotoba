(ns game.addons
  "KAMI Addons: game platform services refactored from Godot C5-C15.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/addons.rs`.

  All addons communicate via KNP Channel 1 (reliable ordered).
  Server-authoritative — client sends commands, server validates +
  broadcasts state. C7 (Economy) lives in `game.economy`; C9 (Inventory)
  lives in `game.inventory`. C13/C14/C15 are KAMI-specific and handled
  elsewhere (kami-knp session + trigger.rs / kami-core actor.rs +
  physics.rs / kami-render mesh.rs — outside this cluster).")

;; ── C5: Social ──
;; PresenceStatus: {:user-id :status :island-id}
;; ChatMessage: {:sender-id :channel :content :tick}

(def presence-states
  "Rust `PresenceState` enum values."
  #{:online :away :in-game :offline})

;; ── C6: Leaderboard ──
;; LeaderboardEntry: {:user-id :display-name :score :rank}
;; Leaderboard: {:entries [LeaderboardEntry ...]}

(defn leaderboard-new [] {:entries []})

(defn leaderboard-submit
  "Submit/raise `user-id`'s score, then re-rank all entries by score desc.
  Returns updated leaderboard."
  [lb user-id display-name score]
  (let [entries (:entries lb)
        idx (some (fn [[i e]] (when (= (:user-id e) user-id) i))
                  (map-indexed vector entries))
        entries' (if idx
                   (if (> score (:score (nth entries idx)))
                     (assoc-in entries [idx :score] score)
                     entries)
                   (conj entries {:user-id user-id :display-name display-name :score score :rank 0}))
        sorted (vec (sort-by (comp - :score) entries'))
        ranked (vec (map-indexed (fn [i e] (assoc e :rank (inc i))) sorted))]
    (assoc lb :entries ranked)))

(defn leaderboard-top
  "Top `n` leaderboard entries."
  [lb n]
  (subvec (:entries lb) 0 (min n (count (:entries lb)))))

;; ── C7: Economy (-> game.economy) ──
;; See game.economy for Wallet.

;; ── C8: Engagement ──
;; DailyBonus: {:day-streak :last-claim-date :gems-reward}

(defn daily-bonus-new
  []
  {:day-streak 0 :last-claim-date "" :gems-reward 10})

(defn daily-bonus-claim
  "Claim daily bonus for `today` (a date string). Returns [gems-awarded bonus']."
  [bonus today]
  (if (= (:last-claim-date bonus) today)
    [0 bonus]
    (let [streak' (inc (:day-streak bonus))
          reward (+ 10 (* (- streak' 1) 5))]
      [reward (assoc bonus :day-streak streak' :last-claim-date today :gems-reward reward)])))

;; Mission: {:id :title :progress :target :reward-gems :completed?}

(defn mission-advance
  "Advance mission progress by `amount`. Returns [completed? mission']."
  [mission amount]
  (if (:completed? mission)
    [false mission]
    (let [progress' (min (+ (:progress mission) amount) (:target mission))
          completed'? (>= progress' (:target mission))]
      [completed'? (assoc mission :progress progress' :completed? completed'?)])))

;; ── C9: Inventory (-> game.inventory) ──
;; ── C10: Gacha ──
;; GachaResult: {:item-id :item-name :rarity}

(defn- string->seed
  "Deterministic hash of `banner`'s bytes (mirrors Rust's u64
  wrapping_mul/wrapping_add fold without needing exact 64-bit wraparound —
  only the final `% 100` roll matters). `unchecked-add`/`unchecked-multiply`
  rather than `+'`/`*'`: the latter auto-promote to bigint (no cljs
  equivalent, and no wraparound), whereas `unchecked-*` actually wraps on
  the JVM (long two's-complement) and is a plain portable op on cljs
  (JS numbers never overflow-check)."
  [banner]
  (reduce (fn [acc b] (unchecked-add (unchecked-multiply acc 31) b))
          0
          #?(:clj (map int banner) :cljs (map #(.charCodeAt % 0) banner))))

(defn gacha-draw
  "Deterministic pseudo-random gacha draw of `count` items based on
  `banner`'s name hash."
  [banner count]
  (let [seed (string->seed banner)]
    (vec
     (for [i (range count)]
       (let [roll (mod (unchecked-multiply seed (inc i)) 100)
             [rarity item-id item-name]
             (cond
               (< roll 3) ["legendary" "sword-legendary" "Legendary Blade"]
               (< roll 15) ["epic" "armor-epic" "Epic Armor"]
               (< roll 35) ["rare" "gem-blue" "Blue Gem"]
               :else ["common" "potion-hp" "Health Potion"])]
         {:item-id item-id :item-name item-name :rarity rarity})))))

;; ── C11: Energy ──
;; EnergySystem: {:current :maximum :recovery-rate}

(defn energy-system-new
  [max]
  {:current max :maximum max :recovery-rate 1})

(defn energy-spend
  "Spend `amount` energy. Returns [spent? energy']."
  [energy amount]
  (if (< (:current energy) amount)
    [false energy]
    [true (update energy :current - amount)]))

(defn energy-recover
  "Recover energy over `minutes-elapsed`, capped at maximum."
  [energy minutes-elapsed]
  (update energy :current
          (fn [cur] (min (+ cur (* minutes-elapsed (:recovery-rate energy))) (:maximum energy)))))

;; ── C12: Telemetry ──
;; GameEvent: {:event-type :entity-id :payload :tick}
;; TelemetryBuffer: {:events [GameEvent ...] :max-buffer}

(defn telemetry-buffer-new
  [max-buffer]
  {:events [] :max-buffer max-buffer})

(defn telemetry-track
  "Track a GameEvent, dropping the oldest if the buffer is full."
  [tbuf event]
  (let [events (:events tbuf)
        events' (if (>= (count events) (:max-buffer tbuf)) (vec (rest events)) events)]
    (assoc tbuf :events (conj events' event))))

(defn telemetry-drain
  "Drain all buffered events. Returns [events tbuf']."
  [tbuf]
  [(:events tbuf) (assoc tbuf :events [])])

(defn telemetry-len [tbuf] (count (:events tbuf)))

;; ── C13: World (KAMI-specific) ──
;; Portal traversal + Island connection — handled by kami-knp session + trigger.rs (game.trigger)

;; ── C14: Actor Binding (KAMI-specific) ──
;; Server-authoritative entity state — handled by kami-core actor.rs + physics.rs

;; ── C15: AssetHub Runtime Loader (KAMI-specific) ──
;; CDN fetch + cache — handled by kami-render mesh.rs + MeshRef::Asset
