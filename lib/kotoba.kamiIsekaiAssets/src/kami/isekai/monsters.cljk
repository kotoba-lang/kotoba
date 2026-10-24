(ns kami.isekai.monsters
  "Monster/enemy archetypes — reuses kami.isekai.chargen's humanoid body plan
   for goblin/orc/troll/dragon (recoloured menacing: less watercolor wash,
   hotter eye accent) and adds standalone plans (:slime, :wolf, :ghost) for
   monsters with no humanoid silhouette to compose onto."
  (:require [kami.isekai.chargen :as chargen]
            [kami.isekai.palette :as pal]))

(defn- eyes [r fill]
  [[:circle {:dx (- (* r 0.32)) :dy (- (* r 0.05)) :r (* r 0.14) :fill fill}]
   [:circle {:dx    (* r 0.32)  :dy (- (* r 0.05)) :r (* r 0.14) :fill fill}]])

(defn compose-slime
  "A single gooey blob — the archetypal isekai starter monster. `hue` picks
   the elemental flavour (green default, red=fire, blue=ice, purple=poison)."
  ([] (compose-slime [0.42 0.78 0.40]))
  ([hue]
   (let [r 130]
     {:sprite [[:ellipse {:dx 0 :dy 0 :rx r :ry (* r 0.82) :fill (conj (pal/watercolor hue 0.08) 0.88)
                          :anim {:pulse [0.10 1.6]}}]
               [:ellipse {:dx 0 :dy (* r -0.18) :rx (* r 0.55) :ry (* r 0.30) :fill (conj (pal/watercolor hue -0.1) 0.5)}]
               [:circle  {:dx (- (* r 0.28)) :dy (- (* r 0.05)) :r (* r 0.10) :fill [0.08 0.08 0.10]}]
               [:circle  {:dx    (* r 0.28)  :dy (- (* r 0.05)) :r (* r 0.10) :fill [0.08 0.08 0.10]}]]
      :render/profile {:color hue :w 1.0 :h 0.7 :emissive 0.25}
      :tags ["slime" "monster"]})))

;; named elemental variants — every isekai has a slime dungeon with a colour
;; per floor. Same compose-slime plan, a fixed hue + an element tag.
(defn compose-slime-fire   [] (update (compose-slime [0.85 0.30 0.18]) :tags conj "fire" "elemental"))
(defn compose-slime-ice    [] (update (compose-slime [0.35 0.65 0.90]) :tags conj "ice" "elemental"))
(defn compose-slime-poison [] (update (compose-slime [0.55 0.30 0.75]) :tags conj "poison" "elemental"))

(defn- menacing [base]
  (assoc base :sprite
    (into (:sprite base) (eyes 70 [0.90 0.16 0.12]))))

(defn compose-goblin-raider [{:keys [seed] :or {seed 0}}]
  (-> (chargen/compose-character {:race :goblin :class :adventurer :seed seed :variant :watercolor})
      menacing
      (update :tags conj "monster" "raider")))

(defn compose-orc-brute [{:keys [seed] :or {seed 0}}]
  (-> (chargen/compose-character {:race :orc :class :adventurer :seed seed :variant :watercolor})
      menacing
      (update :tags conj "monster" "brute")))

(defn compose-dragon [{:keys [seed] :or {seed 0}}]
  ;; :equip? false — a dragon has claws and a breath weapon, not a knight's
  ;; sword+shield (chargen's default loadout follows :class, which here is
  ;; just reused for the crown+cloak silhouette, not a literal knight).
  (-> (chargen/compose-character {:race :dragon-kin :class :knight :seed seed :variant :watercolor :equip? false})
      menacing
      (update :tags conj "monster" "boss" "dragon")))

(defn compose-kobold-scout [{:keys [seed] :or {seed 0}}]
  (-> (chargen/compose-character {:race :kobold :class :adventurer :seed seed :variant :watercolor})
      menacing
      (update :tags conj "monster" "scout")))

(defn compose-wyvern
  "A leaner, feral dragon-kin — no crown/cloak (bare :adventurer class), just
   the wings/tail/horns silhouette. A mid-tier flyer, not a boss."
  [{:keys [seed] :or {seed 0}}]
  (-> (chargen/compose-character {:race :dragon-kin :class :adventurer :seed seed :variant :watercolor :equip? false})
      menacing
      (update :tags conj "monster" "flyer" "wyvern")))

(defn- undead
  "Recolours a composed character's torso/head fills to a pale bone tone and
   swaps the menacing red eyes for a cold glow — the isekai dungeon staple."
  [base]
  (let [bone [0.82 0.80 0.72]
        glow [0.45 0.92 0.72]
        recolor (fn [[kind opts]]
                   [kind (cond-> opts (:fill opts) (assoc :fill (conj (vec bone) (nth (:fill opts) 3 1.0))))])]
    (-> base
        (update :sprite (fn [sprite] (into (mapv recolor sprite) (eyes 70 glow))))
        (assoc-in [:render/profile :color] bone))))

(defn compose-skeleton
  "An undead humanoid — the archetypal isekai dungeon-tier monster. Reuses the
   human body plan (bare, no class accessory) recoloured bone-pale with a
   cold glowing eye accent instead of the menacing red used elsewhere."
  [{:keys [seed] :or {seed 0}}]
  (-> (chargen/compose-character {:race :human :class :adventurer :seed seed :variant :watercolor})
      undead
      (update :tags conj "monster" "undead" "skeleton")))

(defn compose-troll [{:keys [seed] :or {seed 0}}]
  ;; :equip? false — a troll swings its fists, not a knight's dagger; the
  ;; :adventurer class here is just reused for the bare (no accessory)
  ;; silhouette, same reasoning as compose-skeleton.
  (-> (chargen/compose-character {:race :troll :class :adventurer :seed seed :variant :watercolor :equip? false})
      menacing
      (update :tags conj "monster" "brute" "regenerating")))

(defn compose-ghost
  "A standalone ethereal plan (no humanoid silhouette — it floats, no legs):
   a soft outer glow, a round translucent body, a wavy trailing hem (3
   swaying arcs), dark hollow eyes. `hue` picks the glow tone (pale
   blue-white default).

   The whole silhouette (glow/head/body/eyes) shares one :bob amplitude+
   speed so it floats as a single rigid unit — :pulse (a glow/breathe
   effect, used everywhere else in the catalog) reads as 'alive and
   breathing', which is exactly wrong for something that floats because it
   has no legs. The hem arcs keep their own :sway (a trailing-wisp motion
   independent of the body's float, not a second float)."
  ([] (compose-ghost [0.75 0.85 0.95]))
  ([hue]
   (let [tone (conj (pal/watercolor hue -0.05) 0.55)
         glow (conj (pal/watercolor hue -0.15) 0.30)
         float {:bob [10 0.9]}]
     {:sprite [[:circle  {:dx 0 :dy -40 :r 130 :fill glow :anim float}]
               [:circle  {:dx 0 :dy -40 :r 100 :fill tone :anim float}]
               [:ellipse {:dx 0 :dy 60 :rx 100 :ry 70 :fill tone :anim float}]
               [:arc {:dx -40 :dy 120 :r 40 :a0 0.5 :a1 2.6 :w 14 :stroke tone :anim {:sway [0.10 1.0]}}]
               [:arc {:dx 0   :dy 128 :r 40 :a0 0.5 :a1 2.6 :w 14 :stroke tone :anim {:sway [0.12 1.1]}}]
               [:arc {:dx 40  :dy 120 :r 40 :a0 0.5 :a1 2.6 :w 14 :stroke tone :anim {:sway [0.10 1.0]}}]
               [:circle {:dx -26 :dy -50 :r 14 :fill [0.05 0.05 0.08] :anim float}]
               [:circle {:dx  26 :dy -50 :r 14 :fill [0.05 0.05 0.08] :anim float}]]
      :render/profile {:color tone :w 0.9 :h 1.6 :emissive 0.4}
      :tags ["ghost" "monster" "undead" "ethereal"]})))

(defn compose-wolf
  "A standalone quadruped plan (no humanoid silhouette to compose onto, same
   reasoning as compose-slime) — a lean body, two ears, and a tail, iconic
   rather than anatomical. `hue` picks the pelt tone (grey default)."
  ([] (compose-wolf [0.42 0.40 0.44]))
  ([hue]
   (let [tone (pal/watercolor hue)
         dark (pal/watercolor (mapv #(* % 0.5) hue))]
     {:sprite [[:ellipse {:dx 0 :dy 10 :rx 150 :ry 78 :fill tone}]
               [:circle  {:dx 118 :dy -34 :r 58 :fill tone}]
               [:arc     {:dx 96  :dy -78 :r 22 :a0 0.2 :a1 2.6 :w 10 :stroke dark}]
               [:arc     {:dx 148 :dy -78 :r 22 :a0 0.2 :a1 2.6 :w 10 :stroke dark}]
               [:arc     {:dx -128 :dy 6 :r 60 :a0 0.9 :a1 2.6 :w 16 :stroke dark
                          :anim {:sway [0.06 1.2]}}]
               [:circle  {:dx 136 :dy -40 :r 8 :fill [0.92 0.86 0.30]}]]
      :render/profile {:color tone :w 1.4 :h 0.7 :emissive 0.1}
      :tags ["wolf" "monster" "pack"]})))
