(ns game.gameshell
  "GameShell: KAMI-specific game UI layer.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/gameshell.rs`.

  HUD overlay rendered on top of WebGPU canvas: HP bar, gems counter,
  ammo, minimap (top-right), chat panel (bottom-left), portal indicator,
  scoreboard (Tab), inventory grid (I). GameShell is data-only —
  rendering is done by kami-render (wgpu) or a Svelte overlay (web)."
  (:require [kotoba.lang.text]))

;; -----------------------------------------------------------------------
;; Data shapes (plain maps, keyword keys):
;;
;; HudState        {:hp :gems :ammo :minimap :chat :portal-indicator
;;                   :scoreboard :inventory-open? :inventory-slots
;;                   :fps :ping-ms :player-count}
;; HpBar            {:current :max}
;; MinimapState     {:player-x :player-z :entities :map-size}
;; MinimapEntity    {:x :z :kind}          kind ∈ minimap-entity-kinds
;; ChatLine         {:sender :content :tick}
;; PortalIndicator  {:island-name :distance :direction-angle}
;; ScoreRow         {:name :kills :deaths :gems}
;; InventorySlotView {:item-name :quantity :equipped? :rarity}
;; -----------------------------------------------------------------------

(def minimap-entity-kinds
  "Rust `MinimapEntityKind` enum values."
  #{:player :other-player :npc :item :portal :enemy})

(defn hp-bar-ratio
  "Ratio of current/max HP, 0.0 if max is 0."
  [{:keys [current max]}]
  (if (zero? max)
    0.0
    (/ (double current) (double max))))

(defn hud-state-new
  "Create an empty HUD state."
  []
  {:hp {:current 100 :max 100}
   :gems 0
   :ammo 0
   :minimap {:player-x 0.0 :player-z 0.0 :entities [] :map-size 60.0}
   :chat []
   :portal-indicator nil
   :scoreboard []
   :inventory-open? false
   :inventory-slots []
   :fps 60
   :ping-ms 0
   :player-count 1})

(defn push-chat
  "Add a chat message to the HUD state, keeping only the last 20."
  [hud sender content tick]
  (let [chat' (conj (:chat hud) {:sender sender :content content :tick tick})
        chat' (if (> (count chat') 20) (vec (rest chat')) chat')]
    (assoc hud :chat chat')))

;; -----------------------------------------------------------------------
;; Minimal zero-dependency JSON codec, sufficient for HudState's shape
;; (nested maps/vectors of strings, numbers, bools, nil). Keys become
;; snake_case-free keyword names as-is (kebab-case with leading colon
;; stripped); this is a local round-trip format, not intended to match
;; the original Rust serde_json field names exactly.
;; -----------------------------------------------------------------------

(defn- json-escape [s]
  (-> s
      (kotoba.lang.text/replace "\\" "\\\\")
      (kotoba.lang.text/replace "\"" "\\\"")
      (kotoba.lang.text/replace "\n" "\\n")))

(declare ->json)

(defn- kv->json [[k v]]
  (str "\"" (json-escape (name k)) "\":" (->json v)))

(defn ->json
  "Encode a plain CLJC value (map/vector/string/number/bool/nil) as JSON."
  [v]
  (cond
    (nil? v) "null"
    (map? v) (str "{" (kotoba.lang.text/join "," (map kv->json v)) "}")
    (sequential? v) (str "[" (kotoba.lang.text/join "," (map ->json v)) "]")
    (string? v) (str "\"" (json-escape v) "\"")
    (boolean? v) (str v)
    (keyword? v) (str "\"" (name v) "\"")
    :else (str v)))

(defn hud-state->json
  "Serialize HUD state to a JSON string (Svelte overlay / wgpu text
  rendering)."
  [hud]
  (->json hud))

;; A tiny recursive-descent JSON reader, paired with `->json` above so
;; `hud-state->json` / `json->hud-state` round-trip without any external
;; JSON library dependency. Implemented with `subs`/`get` only (no Java
;; interop) so it works identically under :clj and :cljs.

(def ^:private ws-chars #{\space \tab \newline \return})
(def ^:private digit-chars #{\0 \1 \2 \3 \4 \5 \6 \7 \8 \9})
(def ^:private num-chars (into digit-chars #{\- \+ \. \e \E}))

(defn- ch [s i] (get s i))

(defn- skip-ws [s i]
  (let [n (count s)]
    (loop [i i]
      (if (and (< i n) (contains? ws-chars (ch s i)))
        (recur (inc i))
        i))))

(declare parse-value)

(defn- parse-string [s i]
  (let [n (count s)]
    (loop [i (inc i) acc ""]
      (let [c (ch s i)]
        (cond
          (= c \") [acc (inc i)]
          (= c \\) (let [nc (ch s (inc i))
                         rc (case nc \n \newline \\ \\ \" \" nc)]
                     (recur (+ i 2) (str acc rc)))
          :else (recur (inc i) (str acc c)))))))

(defn- parse-number [s i]
  (let [n (count s)]
    (loop [j i]
      (if (and (< j n) (contains? num-chars (ch s j)))
        (recur (inc j))
        (let [tok (subs s i j)]
          [(if (or (kotoba.lang.text/includes? tok ".")
                    (kotoba.lang.text/includes? tok "e")
                    (kotoba.lang.text/includes? tok "E"))
             #?(:clj (Double/parseDouble tok) :cljs (js/parseFloat tok))
             #?(:clj (Long/parseLong tok) :cljs (js/parseInt tok 10)))
           j])))))

(defn- parse-array [s i]
  (loop [i (skip-ws s (inc i)) acc []]
    (if (= (ch s i) \])
      [acc (inc i)]
      (let [[v i'] (parse-value s i)
            i' (skip-ws s i')]
        (if (= (ch s i') \,)
          (recur (skip-ws s (inc i')) (conj acc v))
          [(conj acc v) (inc i')])))))

(defn- parse-object [s i]
  (loop [i (skip-ws s (inc i)) acc {}]
    (if (= (ch s i) \})
      [acc (inc i)]
      (let [[k i'] (parse-string s i)
            i' (skip-ws s i')
            i' (inc i') ; ':'
            i' (skip-ws s i')
            [v i''] (parse-value s i')
            i'' (skip-ws s i'')]
        (if (= (ch s i'') \,)
          (recur (skip-ws s (inc i'')) (assoc acc (keyword k) v))
          [(assoc acc (keyword k) v) (inc i'')])))))

(defn parse-value [s i]
  (let [i (skip-ws s i)
        c (ch s i)]
    (cond
      (= c \{) (parse-object s i)
      (= c \[) (parse-array s i)
      (= c \") (parse-string s i)
      (= (subs s i (min (count s) (+ i 4))) "null") [nil (+ i 4)]
      (= (subs s i (min (count s) (+ i 4))) "true") [true (+ i 4)]
      (= (subs s i (min (count s) (+ i 5))) "false") [false (+ i 5)]
      :else (parse-number s i))))

(defn json->hud-state
  "Parse a JSON string produced by `hud-state->json` back into a HudState map."
  [s]
  (first (parse-value s 0)))
