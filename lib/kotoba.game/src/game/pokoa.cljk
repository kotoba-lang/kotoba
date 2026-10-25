(ns game.pokoa
  "Pokoa (ぽこあポケモン): brainrot-meme x Pokemon-style battle system, restored
  from the deleted kami-game Rust crate (kotoba-lang/kami-engine, PR #82) as
  zero-dependency portable CLJC (ADR-2607010930, com-junkawasaki/root).

  Turn-based creature-collector battle sim: 18 elemental types with a full
  type-effectiveness chart, IV/EV/nature stat rolls, a 12-species dex (4
  evolution lines + 2 legendaries) with brainrot-themed names (Skibidi
  toilet, sigma/gigachad, Ohio, Grimace shake, rizz, fanum tax), a move
  catalog, deterministic xorshift32-driven battle turns (damage/accuracy/
  crit rolls), catch/flee mechanics, trainer team management, and an item
  catalog (balls/potions/revives/evolution items).

  Ported 1:1 from `kami-game/src/pokoa.rs` as pure data + pure functions:
  mutating `&mut self` methods become functions that return updated state
  (often as a map like `{:battle ... :events [...]}` when the original also
  returned a value). `SimpleRng` (kami-game/src/common.rs, owned by another
  restoration cluster) is inlined here as a minimal xorshift32 duck-type
  (seed threaded explicitly as data, matching the original algorithm bit for
  bit) so this namespace has zero cross-cluster dependency. No platform
  divergence was needed: everything is pure integer/float arithmetic using
  portable `clojure.core` bit ops, so no `#?(:clj/:cljs)` conditionals
  appear in this file.")

;; =============================================================================
;; Types
;; =============================================================================

(def pokoa-types
  "The 18 Pokoa elemental types (Pokemon-compatible)."
  #{:normal :fire :water :electric :grass :ice :fighting :poison :ground
    :flying :psychic :bug :rock :ghost :dragon :dark :steel :fairy})

(def ^:private super-effective
  "attacker-type -> set of defender-types it is super effective (2.0x) against."
  {:fire     #{:grass :ice :bug :steel}
   :water    #{:fire :ground :rock}
   :electric #{:water :flying}
   :grass    #{:water :ground :rock}
   :ice      #{:grass :ground :flying :dragon}
   :fighting #{:normal :ice :rock :dark :steel}
   :poison   #{:grass :fairy}
   :ground   #{:fire :electric :poison :rock :steel}
   :flying   #{:grass :fighting :bug}
   :psychic  #{:fighting :poison}
   :bug      #{:grass :psychic :dark}
   :rock     #{:fire :ice :flying :bug}
   :ghost    #{:psychic :ghost}
   :dragon   #{:dragon}
   :dark     #{:psychic :ghost}
   :steel    #{:ice :rock :fairy}
   :fairy    #{:fighting :dragon :dark}})

(def ^:private not-very-effective
  "attacker-type -> set of defender-types it is not very effective (0.5x) against."
  {:fire     #{:fire :water :rock :dragon}
   :water    #{:water :grass :dragon}
   :electric #{:electric :grass :dragon}
   :grass    #{:fire :grass :poison :flying :bug :dragon :steel}
   :ice      #{:fire :water :ice :steel}
   :fighting #{:poison :flying :psychic :bug :fairy}
   :poison   #{:poison :ground :rock :ghost}
   :ground   #{:grass :bug}
   :flying   #{:electric :rock :steel}
   :psychic  #{:psychic :steel}
   :bug      #{:fire :fighting :poison :flying :ghost :steel :fairy}
   :rock     #{:fighting :ground :steel}
   :ghost    #{:dark}
   :dark     #{:fighting :dark :fairy}
   :steel    #{:fire :water :electric :steel}
   :fairy    #{:fire :poison :steel}})

(def ^:private immune
  "attacker-type -> set of defender-types it has no effect (0.0x) against."
  {:normal   #{:ghost}
   :ghost    #{:normal}
   :electric #{:ground}
   :fighting #{:ghost}
   :poison   #{:steel}
   :ground   #{:flying}
   :psychic  #{:dark}
   :dragon   #{:fairy}})

(defn effectiveness
  "Type effectiveness multiplier: attacker type vs defender type."
  [atk def]
  (cond
    (contains? (get immune atk #{}) def)           0.0
    (contains? (get super-effective atk #{}) def)  2.0
    (contains? (get not-very-effective atk #{}) def) 0.5
    :else 1.0))

(defn calc-effectiveness
  "Combined effectiveness against a (possibly dual-type) defender.
  `defender-types` is `[type1 type2-or-nil]`."
  [atk [def1 def2]]
  (let [m1 (effectiveness atk def1)]
    (if def2 (* m1 (effectiveness atk def2)) m1)))

;; =============================================================================
;; Stats
;; =============================================================================

(defn stats-total
  "Sum of all 6 base stats."
  [stats]
  (+ (:hp stats) (:atk stats) (:def stats) (:spa stats) (:spd stats) (:spe stats)))

(def zero-stats {:hp 0 :atk 0 :def 0 :spa 0 :spd 0 :spe 0})

;; Nature modifies two stats (+10%/-10%). Represented as keyword stat ids
;; (:atk :def :spa :spd :spe) rather than the Rust original's numeric
;; 0..4 indices, for readability; behavior is identical.
(def natures
  #{:hardy :lonely :brave :adamant :naughty :bold :docile :relaxed :impish
    :lax :timid :hasty :serious :jolly :naive :modest :mild :quiet :bashful
    :rash :calm :gentle :sassy :careful :quirky})

(def ^:private nature-modifiers-table
  "nature -> [boosted-stat lowered-stat], or absent for neutral natures
  (hardy docile serious bashful quirky)."
  {:lonely  [:atk :def] :brave   [:atk :spe] :adamant [:atk :spa] :naughty [:atk :spd]
   :bold    [:def :atk] :relaxed [:def :spe] :impish  [:def :spa] :lax     [:def :spd]
   :timid   [:spe :atk] :hasty   [:spe :def] :jolly   [:spe :spa] :naive   [:spe :spd]
   :modest  [:spa :atk] :mild    [:spa :def] :quiet   [:spa :spe] :rash    [:spa :spd]
   :calm    [:spd :atk] :gentle  [:spd :def] :sassy   [:spd :spe] :careful [:spd :spa]})

(defn nature-modifiers
  "Returns `[boosted-stat lowered-stat]` or nil for a neutral nature."
  [nature]
  (get nature-modifiers-table nature))

;; =============================================================================
;; Moves
;; =============================================================================

(def move-categories #{:physical :special :status})

(defn move-slot-new
  "Wrap a move-def in a slot with full PP remaining."
  [move-def]
  {:def move-def :pp-remaining (:pp move-def)})

(defn move-can-use? [slot] (pos? (:pp-remaining slot)))

(defn move-use-pp
  "Pure PP decrement, floored at 0."
  [slot]
  (if (pos? (:pp-remaining slot)) (update slot :pp-remaining dec) slot))

;; =============================================================================
;; Species (Pokoa Dex)
;; =============================================================================

;; EvolutionTrigger is `[:level n]` or `[:item "item-id"]`.
;; SpeciesDef `:evolves-to` is `[target-species-id trigger]` or nil.

(defn pokoa-dex
  "12 Brainrot Pokoa species (4 evolution lines + 2 legendaries)."
  []
  [;; --- Line 1: Toilettle -> Skibidrain -> MegaSkibidi ---
   {:id 1 :name "Toilettle" :types [:water :dark]
    :base-stats {:hp 44 :atk 48 :def 65 :spa 50 :spd 64 :spe 43}
    :catch-rate 45 :exp-yield 63 :evolves-to [2 [:level 16]]
    :learnable-moves [[1 "splash"] [1 "leer"] [5 "flush-cannon"] [9 "dark-pulse"] [13 "aqua-jet"]]
    :description "A tiny toilet creature. Makes 'dop dop' sounds when happy."}
   {:id 2 :name "Skibidrain" :types [:water :dark]
    :base-stats {:hp 59 :atk 63 :def 80 :spa 65 :spd 80 :spe 58}
    :catch-rate 45 :exp-yield 142 :evolves-to [3 [:level 36]]
    :learnable-moves [[1 "flush-cannon"] [1 "dark-pulse"] [16 "plumber-slam"] [22 "sewage-wave"] [28 "yes-yes-beam"]]
    :description "Rises from toilets to ambush prey. Head rotates 360 degrees."}
   {:id 3 :name "MegaSkibidi" :types [:water :dark]
    :base-stats {:hp 79 :atk 83 :def 100 :spa 85 :spd 105 :spe 78}
    :catch-rate 45 :exp-yield 236 :evolves-to nil
    :learnable-moves [[1 "yes-yes-beam"] [36 "hydro-pump"] [42 "dop-dop-cannon"] [50 "mega-flush"]]
    :description "The ultimate Skibidi boss. Its 'dop dop yes yes' cry terrifies opponents."}
   ;; --- Line 2: Sigpup -> Sigmachu -> Gigachad ---
   {:id 4 :name "Sigpup" :types [:electric :fighting]
    :base-stats {:hp 35 :atk 55 :def 40 :spa 50 :spd 50 :spe 90}
    :catch-rate 190 :exp-yield 112 :evolves-to [5 [:level 20]]
    :learnable-moves [[1 "thunder-shock"] [1 "leer"] [5 "sigma-stare"] [10 "quick-attack"] [15 "grindset-punch"]]
    :description "A lone wolf pup. Refuses to follow the pack."}
   {:id 5 :name "Sigmachu" :types [:electric :fighting]
    :base-stats {:hp 60 :atk 90 :def 55 :spa 90 :spd 80 :spe 110}
    :catch-rate 75 :exp-yield 218 :evolves-to [6 [:item "protein-shake"]]
    :learnable-moves [[1 "grindset-punch"] [20 "thunderbolt"] [28 "bulk-up"] [36 "sigma-barrage"]]
    :description "Trains alone at the gym. Its electric punches never miss leg day."}
   {:id 6 :name "Gigachad" :types [:electric :fighting]
    :base-stats {:hp 75 :atk 130 :def 70 :spa 95 :spd 85 :spe 120}
    :catch-rate 45 :exp-yield 270 :evolves-to nil
    :learnable-moves [[1 "sigma-barrage"] [1 "thunderbolt"] [42 "gigachad-flex"] [50 "thunder"]]
    :description "The ultimate sigma male. Its jawline alone can deflect attacks."}
   ;; --- Line 3: Ohiolet -> Ohiodon ---
   {:id 7 :name "Ohiolet" :types [:dark :ghost]
    :base-stats {:hp 45 :atk 65 :def 40 :spa 80 :spd 40 :spe 68}
    :catch-rate 120 :exp-yield 87 :evolves-to [8 [:level 28]]
    :learnable-moves [[1 "shadow-sneak"] [1 "confusion"] [7 "ohio-glitch"] [14 "teleport-strike"]]
    :description "'Only in Ohio' -- this creature IS the anomaly."}
   {:id 8 :name "Ohiodon" :types [:dark :ghost]
    :base-stats {:hp 65 :atk 95 :def 60 :spa 120 :spd 60 :spe 98}
    :catch-rate 45 :exp-yield 227 :evolves-to nil
    :learnable-moves [[1 "ohio-glitch"] [28 "shadow-ball"] [35 "reality-warp"] [42 "ohio-final-form"]]
    :description "The Ohio Final Boss. Teleports through dimensions at will."}
   ;; --- Line 4: Grimini -> Grimaceon ---
   {:id 9 :name "Grimini" :types [:poison :fairy]
    :base-stats {:hp 70 :atk 45 :def 50 :spa 65 :spd 65 :spe 40}
    :catch-rate 120 :exp-yield 66 :evolves-to [10 [:level 25]]
    :learnable-moves [[1 "absorb"] [1 "growl"] [6 "purple-shake"] [12 "sludge"] [18 "moonblast"]]
    :description "A cute purple blob. Don't drink its shake."}
   {:id 10 :name "Grimaceon" :types [:poison :fairy]
    :base-stats {:hp 130 :atk 65 :def 60 :spa 110 :spd 95 :spe 30}
    :catch-rate 45 :exp-yield 230 :evolves-to nil
    :learnable-moves [[1 "purple-shake"] [25 "sludge-bomb"] [32 "dazzling-gleam"] [40 "grimace-shake-doom"]]
    :description "It IS the Grimace Shake. Area-denial specialist with toxic puddles."}
   ;; --- Legendary: Rizzlord ---
   {:id 11 :name "Rizzlord" :types [:fire :psychic]
    :base-stats {:hp 100 :atk 100 :def 100 :spa 130 :spd 100 :spe 100}
    :catch-rate 3 :exp-yield 306 :evolves-to nil
    :learnable-moves [[1 "flamethrower"] [1 "psychic"] [50 "rizz-beam"] [65 "infinite-rizz"]]
    :description "Legendary W rizz incarnate. Its charm transcends type matchups."}
   ;; --- Legendary: Fanumoth ---
   {:id 12 :name "Fanumoth" :types [:normal :steel]
    :base-stats {:hp 100 :atk 130 :def 100 :spa 80 :spd 100 :spe 100}
    :catch-rate 3 :exp-yield 306 :evolves-to nil
    :learnable-moves [[1 "iron-head"] [1 "body-slam"] [50 "fanum-tax"] [65 "yoink"]]
    :description "Legendary tax collector. It takes 30% of everything you own."}])

(defn move-catalog
  "Full move catalog for Pokoa, keyed by move id."
  []
  (into {}
        (map (fn [m] [(:id m) m]))
        [{:id "splash" :name "Splash" :type :water :category :status :power 0 :accuracy 100 :pp 40}
         {:id "leer" :name "Leer" :type :normal :category :status :power 0 :accuracy 100 :pp 30}
         {:id "growl" :name "Growl" :type :normal :category :status :power 0 :accuracy 100 :pp 40}
         {:id "quick-attack" :name "Quick Attack" :type :normal :category :physical :power 40 :accuracy 100 :pp 30}
         {:id "absorb" :name "Absorb" :type :grass :category :special :power 20 :accuracy 100 :pp 25}
         {:id "confusion" :name "Confusion" :type :psychic :category :special :power 50 :accuracy 100 :pp 25}
         {:id "shadow-sneak" :name "Shadow Sneak" :type :ghost :category :physical :power 40 :accuracy 100 :pp 30}
         {:id "thunder-shock" :name "Thunder Shock" :type :electric :category :special :power 40 :accuracy 100 :pp 30}
         {:id "thunderbolt" :name "Thunderbolt" :type :electric :category :special :power 90 :accuracy 100 :pp 15}
         {:id "thunder" :name "Thunder" :type :electric :category :special :power 110 :accuracy 70 :pp 10}
         {:id "flamethrower" :name "Flamethrower" :type :fire :category :special :power 90 :accuracy 100 :pp 15}
         {:id "psychic" :name "Psychic" :type :psychic :category :special :power 90 :accuracy 100 :pp 10}
         {:id "sludge" :name "Sludge" :type :poison :category :special :power 65 :accuracy 100 :pp 20}
         {:id "sludge-bomb" :name "Sludge Bomb" :type :poison :category :special :power 90 :accuracy 100 :pp 10}
         {:id "shadow-ball" :name "Shadow Ball" :type :ghost :category :special :power 80 :accuracy 100 :pp 15}
         {:id "moonblast" :name "Moonblast" :type :fairy :category :special :power 95 :accuracy 100 :pp 15}
         {:id "dazzling-gleam" :name "Dazzling Gleam" :type :fairy :category :special :power 80 :accuracy 100 :pp 10}
         {:id "body-slam" :name "Body Slam" :type :normal :category :physical :power 85 :accuracy 100 :pp 15}
         {:id "iron-head" :name "Iron Head" :type :steel :category :physical :power 80 :accuracy 100 :pp 15}
         {:id "hydro-pump" :name "Hydro Pump" :type :water :category :special :power 110 :accuracy 80 :pp 5}
         {:id "aqua-jet" :name "Aqua Jet" :type :water :category :physical :power 40 :accuracy 100 :pp 20}
         {:id "dark-pulse" :name "Dark Pulse" :type :dark :category :special :power 80 :accuracy 100 :pp 15}
         {:id "bulk-up" :name "Bulk Up" :type :fighting :category :status :power 0 :accuracy 100 :pp 20}
         {:id "flush-cannon" :name "Flush Cannon" :type :water :category :special :power 65 :accuracy 95 :pp 15}
         {:id "plumber-slam" :name "Plumber Slam" :type :fighting :category :physical :power 75 :accuracy 100 :pp 15}
         {:id "sewage-wave" :name "Sewage Wave" :type :poison :category :special :power 85 :accuracy 90 :pp 10}
         {:id "yes-yes-beam" :name "Yes Yes Beam" :type :dark :category :special :power 90 :accuracy 90 :pp 10}
         {:id "dop-dop-cannon" :name "Dop Dop Cannon" :type :water :category :special :power 100 :accuracy 85 :pp 5}
         {:id "mega-flush" :name "Mega Flush" :type :water :category :special :power 130 :accuracy 75 :pp 5}
         {:id "sigma-stare" :name "Sigma Stare" :type :psychic :category :status :power 0 :accuracy 100 :pp 20}
         {:id "grindset-punch" :name "Grindset Punch" :type :fighting :category :physical :power 60 :accuracy 100 :pp 20}
         {:id "sigma-barrage" :name "Sigma Barrage" :type :fighting :category :physical :power 90 :accuracy 90 :pp 10}
         {:id "gigachad-flex" :name "Gigachad Flex" :type :fighting :category :physical :power 120 :accuracy 80 :pp 5}
         {:id "ohio-glitch" :name "Ohio Glitch" :type :ghost :category :special :power 70 :accuracy 100 :pp 15}
         {:id "teleport-strike" :name "Teleport Strike" :type :dark :category :physical :power 80 :accuracy 90 :pp 10}
         {:id "reality-warp" :name "Reality Warp" :type :psychic :category :special :power 100 :accuracy 85 :pp 5}
         {:id "ohio-final-form" :name "Ohio Final Form" :type :dark :category :special :power 130 :accuracy 75 :pp 5}
         {:id "purple-shake" :name "Purple Shake" :type :poison :category :special :power 55 :accuracy 100 :pp 20}
         {:id "grimace-shake-doom" :name "Grimace Shake Doom" :type :poison :category :special :power 120 :accuracy 80 :pp 5}
         {:id "rizz-beam" :name "Rizz Beam" :type :fire :category :special :power 110 :accuracy 90 :pp 5}
         {:id "infinite-rizz" :name "Infinite Rizz" :type :psychic :category :special :power 140 :accuracy 70 :pp 5}
         {:id "fanum-tax" :name "Fanum Tax" :type :dark :category :physical :power 100 :accuracy 100 :pp 5}
         {:id "yoink" :name "Yoink" :type :steel :category :physical :power 130 :accuracy 85 :pp 5}]))

;; =============================================================================
;; Pokemon Instance
;; =============================================================================

(defn- ivs-from-seed
  "Deterministic pseudo-random IVs (0-31) derived from a u32 seed via bit
  slicing, matching the Rust original exactly."
  [seed]
  {:hp  (bit-and (unsigned-bit-shift-right seed 0) 31)
   :atk (bit-and (unsigned-bit-shift-right seed 5) 31)
   :def (bit-and (unsigned-bit-shift-right seed 10) 31)
   :spa (bit-and (unsigned-bit-shift-right seed 15) 31)
   :spd (bit-and (unsigned-bit-shift-right seed 20) 31)
   :spe (bit-and (unsigned-bit-shift-right seed 25) 31)})

(defn exp-for-level [level] (* level level level))

(defn level-from-exp [exp]
  (loop [lv 1]
    (if (and (< lv 100) (<= (exp-for-level (inc lv)) exp))
      (recur (inc lv))
      lv)))

(defn- calc-stats
  "Standard Pokemon stat formula. All Rust arithmetic here is integer (u32)
  arithmetic with truncating division before the final f32 cast, so this
  uses `quot` throughout to match exactly."
  [base iv ev level nature]
  (let [[boosted lowered] (nature-modifiers nature)
        stat-mod (fn [k] (cond (= boosted k) 1.1 (= lowered k) 0.9 :else 1.0))
        hp (+ (quot (* (+ (* 2 (:hp base)) (:hp iv) (quot (:hp ev) 4)) level) 100) level 10)
        calc-stat (fn [k]
                    (let [raw (+ (quot (* (+ (* 2 (get base k)) (get iv k) (quot (get ev k) 4)) level) 100) 5)]
                      (int (* raw (stat-mod k)))))]
    {:hp hp :atk (calc-stat :atk) :def (calc-stat :def)
     :spa (calc-stat :spa) :spd (calc-stat :spd) :spe (calc-stat :spe)}))

(defn pokoa-new
  "Create a new Pokoa at a given level with deterministic IVs from `seed`."
  [species level nature seed]
  (let [ivs (ivs-from-seed seed)
        evs zero-stats
        stats (calc-stats (:base-stats species) ivs evs level nature)
        catalog (move-catalog)
        moves (->> (:learnable-moves species)
                   (filter (fn [[lv _]] (<= lv level)))
                   reverse
                   (take 4)
                   (keep (fn [[_ mid]] (when-let [m (get catalog mid)] (move-slot-new m))))
                   vec)]
    {:species-id (:id species)
     :nickname nil
     :level level
     :exp (exp-for-level level)
     :nature nature
     :ivs ivs
     :evs evs
     :current-hp (:hp stats)
     :max-hp (:hp stats)
     :stats stats
     :moves moves}))

(defn is-fainted? [pokoa] (zero? (:current-hp pokoa)))

(defn take-damage [pokoa damage] (update pokoa :current-hp #(max 0 (- % damage))))

(defn heal [pokoa amount] (update pokoa :current-hp #(min (:max-hp pokoa) (+ % amount))))

(defn heal-full
  "Full heal + restore all move PP."
  [pokoa]
  (-> pokoa
      (assoc :current-hp (:max-hp pokoa))
      (update :moves (fn [moves] (mapv #(assoc % :pp-remaining (:pp (:def %))) moves)))))

(defn gain-exp
  "Add experience. Returns `{:pokoa updated-pokoa :new-level level-or-nil}`."
  [pokoa amount species]
  (let [exp' (+ (:exp pokoa) amount)
        new-level (level-from-exp exp')]
    (if (> new-level (:level pokoa))
      (let [level' (min 100 new-level)
            stats' (calc-stats (:base-stats species) (:ivs pokoa) (:evs pokoa) level' (:nature pokoa))
            old-max (:max-hp pokoa)
            max-hp' (:hp stats')
            ;; A fainted Pokoa (current-hp 0) must STAY at 0 through a level-up
            ;; -- max HP can still grow, but current HP rising off the floor
            ;; without an explicit heal/heal-full/:revive-item call would
            ;; silently un-faint it, bypassing is-fainted?/first-alive's
            ;; load-bearing invariant that 0 HP means out of the battle.
            current-hp' (if (zero? (:current-hp pokoa))
                          0
                          (min max-hp' (+ (:current-hp pokoa) (- max-hp' old-max))))]
        {:pokoa (assoc pokoa :exp exp' :level level' :stats stats' :max-hp max-hp' :current-hp current-hp')
         :new-level level'})
      {:pokoa (assoc pokoa :exp exp') :new-level nil})))

(defn can-evolve?
  "Whether this Pokoa can evolve (level-trigger only, matching the Rust original
  which only checks the `Level` trigger variant here)."
  [pokoa species]
  (if-let [[_ trigger] (:evolves-to species)]
    (boolean (and (= (first trigger) :level) (>= (:level pokoa) (second trigger))))
    false))

(defn hp-pct
  "HP percentage (0.0-1.0)."
  [pokoa]
  (if (zero? (:max-hp pokoa)) 0.0 (/ (double (:current-hp pokoa)) (:max-hp pokoa))))

;; =============================================================================
;; Deterministic RNG (minimal local xorshift32; canonical copy owned by the
;; game.common cluster in kami-game/src/common.rs -- inlined here so this
;; namespace has zero cross-cluster dependency, matching the algorithm bit
;; for bit).
;; =============================================================================

(defn- rng-seed [seed] (if (zero? seed) 1 seed))

(defn- xorshift32-step [seed]
  (let [mask (fn [n] (bit-and n 0xffffffff))
        seed (mask (bit-xor seed (bit-shift-left seed 13)))
        seed (mask (bit-xor seed (unsigned-bit-shift-right seed 17)))
        seed (mask (bit-xor seed (bit-shift-left seed 5)))]
    seed))

(defn rng-next-f32
  "Returns `[new-seed value-in-0-1]`."
  [seed]
  (let [seed' (xorshift32-step seed)]
    [seed' (/ (double seed') 4294967295.0)]))

(defn rng-range
  "Returns `[new-seed value-in-min-max)]`."
  [seed min max]
  (let [[seed' v] (rng-next-f32 seed)]
    [seed' (+ min (* v (- max min)))]))

;; =============================================================================
;; Battle System
;; =============================================================================

(def battle-types #{:wild :trainer :gym :legendary})
(def battle-outcomes #{:player-win :opponent-win :caught :fled})

(defn battle-new
  [battle-type player opponent]
  {:battle-type battle-type
   :turn 0
   :player player
   :opponent opponent
   :player-team []
   :opponent-team []
   :log []
   :outcome nil
   :rng-seed (rng-seed 42)})

(defn calc-damage
  "Pure damage calc for one attack. Returns
  `{:damage :effectiveness :critical :rng-seed}`."
  [battle attacker move-def defender defender-types]
  (if (or (= (:category move-def) :status) (zero? (:power move-def)))
    {:damage 0 :effectiveness 1.0 :critical false :rng-seed (:rng-seed battle)}
    (let [level (:level attacker)
          [atk-stat def-stat] (case (:category move-def)
                                 :physical [(:atk (:stats attacker)) (:def (:stats defender))]
                                 :special  [(:spa (:stats attacker)) (:spd (:stats defender))])
          step1 (+ (/ (* 2.0 level) 5.0) 2.0)
          step2 (/ (* step1 (:power move-def) atk-stat) def-stat)
          base (+ (/ step2 50.0) 2.0)
          ;; STAB: ported verbatim from the Rust original, including its
          ;; `// TODO: check attacker types` comment -- this compares the
          ;; move's type to the *defender's* primary type, not the
          ;; attacker's, which looks like an upstream bug. Kept as-is.
          stab (if (= (:type move-def) (first defender-types)) 1.0 1.5)
          effectiveness (calc-effectiveness (:type move-def) defender-types)
          [seed1 crit-roll] (rng-next-f32 (:rng-seed battle))
          critical (< crit-roll 0.0625)
          crit-mult (if critical 1.5 1.0)
          [seed2 random] (rng-range seed1 0.85 1.0)
          damage (int (max 1.0 (* base stab effectiveness crit-mult random)))]
      {:damage damage :effectiveness effectiveness :critical critical :rng-seed seed2})))

(defn- update-move-pp [pokoa move-idx]
  (if (get (:moves pokoa) move-idx)
    (update-in pokoa [:moves move-idx] move-use-pp)
    pokoa))

(defn- attack-phase
  "Execute one Pokoa's attack. Returns `{:battle battle' :events [...]}`."
  [battle is-player? move-idx]
  (let [attacker-key (if is-player? :player :opponent)
        defender-key (if is-player? :opponent :player)
        attacker-name (if is-player? "Your Pokoa" "Wild Pokoa")
        attacker (get battle attacker-key)
        move-slot (get (:moves attacker) move-idx)]
    (cond
      (nil? move-slot)
      {:battle battle
       :events [{:message (str attacker-name " has no move to use!")
                 :effectiveness 1.0 :damage 0 :critical false}]}

      (not (move-can-use? move-slot))
      {:battle battle
       :events [{:message (str attacker-name " has no PP left for " (:name (:def move-slot)) "!")
                 :effectiveness 1.0 :damage 0 :critical false}]}

      :else
      (let [move-def (:def move-slot)
            [seed1 acc-roll] (rng-next-f32 (:rng-seed battle))
            acc-pct (* acc-roll 100.0)]
        (if (> acc-pct (:accuracy move-def))
          ;; Miss.
          {:battle (-> battle
                       (assoc :rng-seed seed1)
                       (update attacker-key update-move-pp move-idx))
           :events [{:message (str attacker-name " used " (:name move-def) " but it missed!")
                     :effectiveness 1.0 :damage 0 :critical false}]}
          ;; Hit.
          (let [defender (get battle defender-key)
                ;; Ported verbatim: the Rust original never looks up the
                ;; real defender types from the dex here (`// TODO: look up
                ;; from dex`); it hardcodes Normal/no-secondary-type.
                defender-types [:normal nil]
                {:keys [damage effectiveness critical rng-seed]}
                (calc-damage (assoc battle :rng-seed seed1) attacker move-def defender defender-types)
                battle' (-> battle
                            (assoc :rng-seed rng-seed)
                            (update defender-key take-damage damage)
                            (update attacker-key update-move-pp move-idx))
                eff-msg (cond (> effectiveness 1.5) " It's super effective!"
                              (and (< effectiveness 0.5) (> effectiveness 0.0)) " It's not very effective..."
                              (zero? effectiveness) " It had no effect!"
                              :else "")
                crit-msg (if critical " Critical hit!" "")
                hit-event {:message (str attacker-name " used " (:name move-def) "! " damage " damage." eff-msg crit-msg)
                           :effectiveness effectiveness :damage damage :critical critical}
                fainted? (is-fainted? (get battle' defender-key))
                battle'' (if fainted?
                           (assoc battle' :outcome (if is-player? :player-win :opponent-win))
                           battle')
                faint-event (when fainted?
                              (if is-player?
                                {:message "Wild Pokoa fainted! You win!" :effectiveness 1.0 :damage 0 :critical false}
                                {:message "Your Pokoa fainted! You blacked out..." :effectiveness 1.0 :damage 0 :critical false}))]
            {:battle battle''
             :events (cond-> [hit-event] faint-event (conj faint-event))}))))))

(defn select-opponent-move
  "Simple AI: pick first usable move, else 0."
  [battle]
  (or (some (fn [[i m]] (when (move-can-use? m) i))
            (map-indexed vector (:moves (:opponent battle))))
      0))

(defn execute-turn
  "Execute one turn: player uses move at `player-move-idx`, opponent AI
  selects. Returns `{:battle battle' :events [...]}`; `:battle`'s `:log`
  has the events appended."
  [battle player-move-idx]
  (if (:outcome battle)
    {:battle battle :events []}
    (let [battle (update battle :turn inc)
          player-first? (>= (get-in battle [:player :stats :spe]) (get-in battle [:opponent :stats :spe]))
          {battle1 :battle events1 :events}
          (if player-first?
            (attack-phase battle true player-move-idx)
            (attack-phase battle false (select-opponent-move battle)))
          {battle2 :battle events2 :events}
          (if (:outcome battle1)
            {:battle battle1 :events []}
            (if player-first?
              (attack-phase battle1 false (select-opponent-move battle1))
              (attack-phase battle1 true player-move-idx)))
          all-events (into (vec events1) events2)]
      {:battle (update battle2 :log into all-events)
       :events all-events})))

(defn attempt-catch
  "Attempt to catch the wild opponent. Returns `{:battle battle' :caught bool}`."
  [battle ball-modifier catch-rate]
  (if-not (contains? #{:wild :legendary} (:battle-type battle))
    {:battle (update battle :log conj {:message "Can't catch a trainer's Pokoa!"
                                        :effectiveness 1.0 :damage 0 :critical false})
     :caught false}
    (let [opponent (:opponent battle)
          hp-factor (/ (- (* 3.0 (:max-hp opponent)) (* 2.0 (:current-hp opponent)))
                       (* 3.0 (:max-hp opponent)))
          catch-chance (/ (* catch-rate ball-modifier hp-factor) 255.0)
          [seed roll] (rng-next-f32 (:rng-seed battle))]
      (if (< roll catch-chance)
        {:battle (-> battle
                     (assoc :rng-seed seed :outcome :caught)
                     (update :log conj {:message "Gotcha! Pokoa was caught!"
                                        :effectiveness 1.0 :damage 0 :critical false}))
         :caught true}
        (let [shakes (cond (< roll (* catch-chance 1.5)) 3
                            (< roll (* catch-chance 2.0)) 2
                            :else 1)]
          {:battle (-> battle
                       (assoc :rng-seed seed)
                       (update :log conj {:message (str "The ball shook " shakes " time(s)... but the Pokoa broke free!")
                                          :effectiveness 1.0 :damage 0 :critical false}))
           :caught false})))))

(defn attempt-flee
  "Attempt to flee from a wild battle. Returns `{:battle battle' :fled bool}`."
  [battle]
  (if (contains? #{:trainer :gym} (:battle-type battle))
    {:battle (update battle :log conj {:message "Can't run from a trainer battle!"
                                        :effectiveness 1.0 :damage 0 :critical false})
     :fled false}
    (let [player (:player battle)
          opponent (:opponent battle)
          flee-chance (min 1.0
                           (/ (+ (/ (* (:spe (:stats player)) 128.0) (:spe (:stats opponent)))
                                 (* 30.0 (:turn battle)))
                              256.0))
          [seed roll] (rng-next-f32 (:rng-seed battle))]
      (if (< roll flee-chance)
        {:battle (-> battle
                     (assoc :rng-seed seed :outcome :fled)
                     (update :log conj {:message "Got away safely!" :effectiveness 1.0 :damage 0 :critical false}))
         :fled true}
        {:battle (-> battle
                     (assoc :rng-seed seed)
                     (update :log conj {:message "Can't escape!" :effectiveness 1.0 :damage 0 :critical false}))
         :fled false}))))

;; =============================================================================
;; Trainer
;; =============================================================================

(defn trainer-new
  [name]
  {:name name :team [] :money 3000 :badges [] :pokedex-seen [] :pokedex-caught []})

(defn- dex-conj [v id] (if (some #{id} v) v (conj v id)))

(defn add-pokoa
  "Returns `{:trainer trainer' :added bool}`."
  [trainer pokoa]
  (if (>= (count (:team trainer)) 6)
    {:trainer trainer :added false}
    (let [species-id (:species-id pokoa)]
      {:trainer (-> trainer
                    (update :team conj pokoa)
                    (update :pokedex-caught dex-conj species-id)
                    (update :pokedex-seen dex-conj species-id))
       :added true})))

(defn see-pokoa [trainer species-id]
  (update trainer :pokedex-seen dex-conj species-id))

(defn heal-all [trainer]
  (update trainer :team #(mapv heal-full %)))

(defn first-alive
  "Index of the first non-fainted team member, or nil."
  [trainer]
  (first (keep-indexed (fn [i p] (when-not (is-fainted? p) i)) (:team trainer))))

;; =============================================================================
;; Items
;; =============================================================================

;; ItemType is a tagged map: {:kind :pokeball :catch-modifier n}
;;                          | {:kind :potion :heal-amount n}
;;                          | {:kind :revive :hp-pct n}
;;                          | {:kind :evolution-item :item-id s}
;;                          | {:kind :key-item :name s}

(defn pokoa-items []
  [{:id "pokoa-ball" :name "Pokoa Ball" :item-type {:kind :pokeball :catch-modifier 1} :price 200}
   {:id "great-ball" :name "Great Ball" :item-type {:kind :pokeball :catch-modifier 2} :price 600}
   {:id "ultra-ball" :name "Ultra Ball" :item-type {:kind :pokeball :catch-modifier 3} :price 1200}
   {:id "master-ball" :name "Master Ball" :item-type {:kind :pokeball :catch-modifier 255} :price 0}
   {:id "potion" :name "Potion" :item-type {:kind :potion :heal-amount 20} :price 300}
   {:id "super-potion" :name "Super Potion" :item-type {:kind :potion :heal-amount 50} :price 700}
   {:id "hyper-potion" :name "Hyper Potion" :item-type {:kind :potion :heal-amount 200} :price 1200}
   {:id "revive" :name "Revive" :item-type {:kind :revive :hp-pct 50} :price 1500}
   {:id "protein-shake" :name "Protein Shake" :item-type {:kind :evolution-item :item-id "protein-shake"} :price 5000}
   {:id "grimace-shake-item" :name "Grimace Shake" :item-type {:kind :potion :heal-amount 999} :price 0}])
