(ns kami.isekai.tensei
  "転生 (tensei) — the genre's namesake moment: dying/being summoned into
   another world. `compose-summoning-circle` is a static ground prop (a
   composed :sprite, same shape as kami.isekai.structures); `transition` is
   the flash itself, a kami.audio + kami :fx recipe (same shape as a
   kami.isekai.skills entry) — a game staging the reincarnation moment wants
   both a prop to stand the character on and a beat to fire when they
   arrive."
  (:require [kami.isekai.palette :as pal]))

(defn compose-summoning-circle
  "A ground-level magic circle — a flattened ring (drawn as an ellipse, same
   ground-plane convention network-isekai's :ice/:mud patches use), two
   static concentric rings, and 8 radial rune ticks that share one :rot
   (pivoted at the circle's own centre) so the whole rune ring turns as one
   unit — a static magic circle reads as a diagram, not a spell in progress;
   this is the one place in the catalog a slow continuous :rot (not
   goriketsu's back-and-forth arm-swing usage) is the right call. `hue`
   picks the glow tone (ethereal blue-white default)."
  ([] (compose-summoning-circle [0.55 0.70 0.95]))
  ([hue]
   (let [glow  (conj (pal/watercolor hue -0.15) 0.85)
         faint (conj (pal/watercolor hue 0.05) 0.30)
         spin  {:rot [6.28 0.12] :pivot [0 0]}
         rune  (fn [angle] [:arc {:dx 0 :dy 0 :r 180 :a0 angle :a1 (+ angle 0.12) :w 20 :stroke glow :anim spin}])]
     {:sprite (into
                [[:ellipse {:dx 0 :dy 0 :rx 220 :ry 90 :fill faint :anim {:pulse [0.06 1.2]}}]
                 [:arc {:dx 0 :dy 0 :r 200 :a0 0.0 :a1 6.28 :w 8 :stroke glow}]
                 [:arc {:dx 0 :dy 0 :r 140 :a0 0.0 :a1 6.28 :w 6 :stroke glow}]]
                (map rune (range 0.0 6.28 (/ 6.28 8))))
      :render/profile {:color hue :w 3.6 :h 0.2 :emissive 0.6}
      :tags ["tensei" "summoning-circle" "portal" "isekai"]})))

(def transition
  "The reincarnation/summoning flash — kami.audio + kami :fx, the same shape
   as a kami.isekai.skills entry (:audio :fx :label :sfx-key). Bright,
   rising, ethereal: the 'you wake up in another world' beat. Fire it when a
   character spawns onto a compose-summoning-circle."
  {:label "Isekai Tensei" :element :arcane :sfx-key :tensei
   :audio {:wave "sine" :freq 200 :to 1600 :dur 1.2 :gain 0.20}
   :fx    {:n 40 :spd 1.4 :grav -0.05 :life 90 :size 7
           :colors ["#ffffff" "#bcd9ff" "#ffe9a8"] :spark 0.7}})
