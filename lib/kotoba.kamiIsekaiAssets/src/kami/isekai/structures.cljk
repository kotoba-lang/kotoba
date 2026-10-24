(ns kami.isekai.structures
  "World-decoration structures — the isekai staples that aren't characters:
   castle (a keep + flanking turrets + banner) and guild hall (the
   adventurer's-guild storefront every starting town has). Same composed-
   primitive philosophy and output shape as chargen/monsters ({:sprite [...]
   :render/profile {...} :tags [...]}) — these are static world props (like
   network-isekai's nocturne :lamp/:bench), not characters, so there's no
   :race/:class/:seed, just an optional palette override."
  (:require [kami.isekai.palette :as pal]))

(defn compose-castle
  "A keep: a tall central tower, two flanking turrets, a banner, and a wall
   base. `hue` is the stone tone (cool grey default)."
  ([] (compose-castle [0.52 0.52 0.58]))
  ([hue]
   (let [stone (pal/watercolor hue)
         dark  (pal/watercolor (mapv #(* % 0.6) hue))
         banner [0.70 0.20 0.24]]
     {:sprite
      [[:rect {:dx 0 :dy 60 :w 440 :h 90 :fill dark}]                            ;; wall base
       [:rect {:dx -160 :dy -60 :w 90 :h 220 :fill stone}]                       ;; left turret
       [:rect {:dx  160 :dy -60 :w 90 :h 220 :fill stone}]                       ;; right turret
       [:rect {:dx -160 :dy -190 :w 100 :h 30 :fill dark}]                       ;; left crenellation
       [:rect {:dx  160 :dy -190 :w 100 :h 30 :fill dark}]                       ;; right crenellation
       [:rect {:dx 0 :dy -100 :w 150 :h 330 :fill stone}]                        ;; central keep
       [:arc  {:dx 0 :dy -270 :r 80 :a0 3.3 :a1 6.12 :w 20 :stroke dark}]        ;; keep roof arc
       [:rect {:dx 0 :dy -340 :w 8 :h 60 :fill dark}]                            ;; flagpole
       [:rect {:dx 18 :dy -365 :w 40 :h 26 :fill banner :anim {:sway [0.05 1.2]}}]]  ;; banner
      :render/profile {:color stone :w 3.0 :h 3.6 :emissive 0.0}
      :tags ["castle" "keep" "structure" "isekai"]})))

(defn compose-guild-hall
  "The adventurer's-guild storefront — a warm timber building with a peaked
   roof, a door, and an emblem sign. `hue` is the wood/wall tone (warm
   amber default, echoes kami.isekai.palette's :guild-master class accent)."
  ([] (compose-guild-hall [0.62 0.46 0.28]))
  ([hue]
   (let [wood (pal/watercolor hue)
         roof (pal/watercolor (mapv #(* % 0.55) hue))
         emblem [0.22 0.46 0.34]]
     {:sprite
      [[:rect    {:dx 0 :dy 40 :w 360 :h 220 :fill wood}]                        ;; body
       [:arc     {:dx 0 :dy -70 :r 210 :a0 3.4 :a1 6.02 :w 40 :stroke roof}]      ;; peaked roof
       [:rect    {:dx 0 :dy 110 :w 90 :h 120 :fill roof}]                        ;; door
       [:circle  {:dx 0 :dy -10 :r 46 :fill emblem :anim {:pulse [0.05 1.6]}}]   ;; guild emblem sign
       [:rect    {:dx -140 :dy 40 :w 30 :h 220 :fill roof}]                      ;; left post
       [:rect    {:dx  140 :dy 40 :w 30 :h 220 :fill roof}]]                     ;; right post
      :render/profile {:color wood :w 2.4 :h 2.0 :emissive 0.0}
      :tags ["guild" "guild-hall" "structure" "isekai"]})))
