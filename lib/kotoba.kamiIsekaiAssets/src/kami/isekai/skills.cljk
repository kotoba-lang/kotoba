(ns kami.isekai.skills
  "Skill/magic catalog — each entry is a kami.audio synth recipe (same shape
   as every game's :audio block: {:wave :freq :to :dur :gain}, no asset
   files) plus a kami :fx :burst particle spec. Drop an entry's :audio/:fx
   straight into a game's scene.edn under the matching key; :sfx-key names
   the key to use for both.")

(def skills
  {:fireball
   {:label "Fireball" :element :fire :sfx-key :fireball
    :audio {:wave "sawtooth" :freq 180 :to 620 :dur 0.22 :gain 0.22}
    :fx    {:n 22 :spd 3.4 :grav 0.10 :life 30 :size 6
            :colors ["#ff6a3d" "#ffae4a" "#ffe14a" "#3a1a0a"] :spark 0.5}}

   :ice-lance
   {:label "Ice Lance" :element :ice :sfx-key :ice-lance
    :audio {:wave "triangle" :freq 880 :to 1320 :dur 0.14 :gain 0.16}
    :fx    {:n 14 :spd 2.6 :grav 0.02 :life 34 :size 4
            :colors ["#bfe9ff" "#eaffff" "#5aa0e0"] :spark 0.4}}

   :holy-heal
   {:label "Holy Heal" :element :holy :sfx-key :holy-heal
    :audio {:wave "sine" :freq 660 :to 990 :dur 0.30 :gain 0.14}
    :fx    {:n 18 :spd 1.2 :grav -0.06 :life 46 :size 5
            :colors ["#fff7d0" "#ffe9a8" "#ffffff"] :spark 0.5}}

   :curse
   {:label "Curse" :element :dark :sfx-key :curse
    :audio {:wave "sawtooth" :freq 140 :to 60 :dur 0.40 :gain 0.20}
    :fx    {:n 16 :spd 1.4 :grav 0.03 :life 40 :size 5
            :colors ["#4a1a6a" "#1a0a2a" "#8a4ac0"] :spark 0.3}}

   :cheat-aura
   {:label "Cheat Aura" :element :op :sfx-key :cheat-aura
    :audio {:wave "sine" :freq 523 :to 1046 :dur 0.5 :gain 0.18}
    :fx    {:n 26 :spd 1.6 :grav -0.02 :life 60 :size 6
            :colors ["#ffe14a" "#ffffff" "#ffd27a"] :spark 0.6}}

   :wind-blade
   {:label "Wind Blade" :element :wind :sfx-key :wind-blade
    :audio {:wave "triangle" :freq 440 :to 720 :dur 0.10 :gain 0.15}
    :fx    {:n 12 :spd 4.2 :grav 0.0 :life 18 :size 3
            :colors ["#dff5e6" "#a8e0b8" "#ffffff"] :spark 0.35}}

   :earth-spike
   {:label "Earth Spike" :element :earth :sfx-key :earth-spike
    :audio {:wave "square" :freq 90 :to 200 :dur 0.26 :gain 0.24}
    :fx    {:n 16 :spd 1.8 :grav 0.16 :life 32 :size 6
            :colors ["#8a6a3a" "#5a4022" "#c9a86a"] :spark 0.2}}

   :teleport
   {:label "Teleport" :element :arcane :sfx-key :teleport
    :audio {:wave "sine" :freq 1200 :to 300 :dur 0.18 :gain 0.14}
    :fx    {:n 20 :spd 2.2 :grav -0.04 :life 24 :size 4
            :colors ["#c9a8ff" "#eaddff" "#ffffff"] :spark 0.6}}

   :summon
   {:label "Summon" :element :arcane :sfx-key :summon
    :audio {:wave "sawtooth" :freq 100 :to 500 :dur 0.6 :gain 0.16}
    :fx    {:n 24 :spd 1.0 :grav -0.03 :life 70 :size 6
            :colors ["#8a4ac0" "#c9a8ff" "#1a0a2a"] :spark 0.4}}})

(defn skill [id] (get skills id))
