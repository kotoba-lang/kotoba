(ns kami.isekai.chargen
  "EDN character composer — `compose-character` turns {:race :class :seed} into
   a kami.sprite2d primitive vector (the exact `:sprites` shape every
   network-isekai game already uses: [:circle/:rect/:ellipse/:arc {...}]) plus
   a :render/profiles fallback map for the 3D renderer. This is an AUTHORING-
   TIME generator (plain Clojure/ClojureScript, run in a REPL/babashka script
   or at build time) — its OUTPUT is plain EDN you paste into a game's
   scene.edn :sprites map. It does not run inside the kototama guest sandbox.

   No external asset files (no PNG/GLB/WAV) — every character is composed
   primitives + a synthesised palette, same as the rest of the kami-engine
   catalog (\"view source + fork\", CodePen-for-games)."
  (:require [kami.isekai.palette :as pal]
            [kami.isekai.races :as races]
            [kami.isekai.classes :as classes]
            [kami.isekai.equipment :as equip]))

(defn- rgb->fill
  ([rgb] (vec rgb))
  ([rgb alpha] (conj (vec rgb) alpha)))

(defn- accessory-primitives
  "Small silhouette read for a class accessory, positioned above the head."
  [{:keys [accessory cloak]} head-r accent-rgb]
  (cond-> []
    (= accessory :helm)    (conj [:arc    {:dx 0 :dy (- (* head-r 1.55)) :r (* head-r 0.9)
                                            :a0 3.4 :a1 6.02 :w (* head-r 0.5) :stroke accent-rgb}])
    (= accessory :hood)    (conj [:arc    {:dx 0 :dy (- (* head-r 1.4)) :r (* head-r 1.05)
                                            :a0 3.3 :a1 6.12 :w (* head-r 0.6) :stroke accent-rgb}])
    (= accessory :crown)   (conj [:rect   {:dx 0 :dy (- (* head-r 2.05)) :w (* head-r 1.3) :h (* head-r 0.5) :fill accent-rgb}]
                                  [:circle {:dx 0 :dy (- (* head-r 2.35)) :r (* head-r 0.22) :fill accent-rgb}])
    (= accessory :tiara)   (conj [:arc    {:dx 0 :dy (- (* head-r 1.9)) :r (* head-r 0.7)
                                            :a0 3.6 :a1 5.82 :w (* head-r 0.22) :stroke accent-rgb}])
    (= accessory :satchel) (conj [:rect   {:dx (* head-r 1.1) :dy (* head-r 1.4) :w (* head-r 0.9) :h (* head-r 0.7) :fill accent-rgb}])
    (= accessory :emblem)  (conj [:circle {:dx 0 :dy (* head-r 0.2) :r (* head-r 0.4) :fill accent-rgb}])
    (= accessory :holy-symbol) (into [[:rect {:dx 0 :dy (* head-r 0.5) :w (* head-r 0.16) :h (* head-r 0.6)
                                               :fill accent-rgb :anim {:pulse [0.06 1.6]}}]
                                       [:rect {:dx 0 :dy (* head-r 0.4) :w (* head-r 0.5) :h (* head-r 0.16)
                                               :fill accent-rgb :anim {:pulse [0.06 1.6]}}]])
    cloak                  (conj [:rect   {:dx 0 :dy (* head-r 1.6) :w (* head-r 3.4) :h (* head-r 2.6) :fill accent-rgb}])))

(defn- race-accent-primitives
  "Ears/tusks/tail/horns/wings — the small race-silhouette tells."
  [{:keys [ears stature tail wings horns tusked]} head-r torso-r skin-rgb accent-rgb]
  (let [hr (* head-r stature)]
    (cond-> []
      (= ears :pointed) (into [[:arc {:dx (- (* hr 0.95)) :dy (- (* hr 1.1)) :r (* hr 0.4)
                                       :a0 0.6 :a1 2.4 :w (* hr 0.16) :stroke skin-rgb}]
                                [:arc {:dx    (* hr 0.95)  :dy (- (* hr 1.1)) :r (* hr 0.4)
                                       :a0 0.6 :a1 2.4 :w (* hr 0.16) :stroke skin-rgb}]])
      (= ears :long)    (into [[:ellipse {:dx (- (* hr 1.05)) :dy (- (* hr 1.05)) :rx (* hr 0.22) :ry (* hr 0.55) :fill skin-rgb}]
                                [:ellipse {:dx    (* hr 1.05)  :dy (- (* hr 1.05)) :rx (* hr 0.22) :ry (* hr 0.55) :fill skin-rgb}]])
      tusked            (into [[:rect {:dx (- (* hr 0.3)) :dy (* hr 0.35) :w (* hr 0.16) :h (* hr 0.34) :fill [0.95 0.93 0.85]}]
                                [:rect {:dx    (* hr 0.3)  :dy (* hr 0.35) :w (* hr 0.16) :h (* hr 0.34) :fill [0.95 0.93 0.85]}]])
      tail              (conj [:arc {:dx 0 :dy (* torso-r 0.9) :r (* torso-r 0.7)
                                      :a0 1.0 :a1 2.6 :w (* torso-r 0.22) :stroke accent-rgb}])
      horns             (into [[:rect {:dx (- (* hr 0.45)) :dy (- (* hr 1.7)) :w (* hr 0.18) :h (* hr 0.5) :fill accent-rgb}]
                                [:rect {:dx    (* hr 0.45)  :dy (- (* hr 1.7)) :w (* hr 0.18) :h (* hr 0.5) :fill accent-rgb}]])
      wings             (into [[:ellipse {:dx (- (* torso-r 1.3)) :dy (- (* torso-r 0.2)) :rx (* torso-r 0.7) :ry (* torso-r 0.34)
                                           :fill (rgb->fill accent-rgb 0.75) :anim {:pulse [0.04 1.4]}}]
                                [:ellipse {:dx    (* torso-r 1.3)  :dy (- (* torso-r 0.2)) :rx (* torso-r 0.7) :ry (* torso-r 0.34)
                                           :fill (rgb->fill accent-rgb 0.75) :anim {:pulse [0.04 1.4]}}]]))))

(defn cheat-aura
  "The isekai 'overpowered protagonist' tell — a soft golden halo behind the
   character. Composable: prepend the result onto any character's sprite
   vector. Purely decorative, no gameplay coupling."
  ([sprite] (cheat-aura sprite 1.0))
  ([sprite scale]
   (into [[:circle {:dx 0 :dy 0 :r (* 210 scale) :fill [1.0 0.86 0.35 0.32] :anim {:pulse [0.10 1.1]}}]
          [:circle {:dx 0 :dy 0 :r (* 175 scale) :fill [1.0 0.92 0.55 0.22] :anim {:pulse [0.14 1.5]}}]]
         sprite)))

(defn walk-cycle
  "Layers a walking-in-place motion onto an already-composed :sprite vector,
   using ONLY the :bob/:sway keys kami.sprite2d's real :anim interpreter
   already understands (see orgs/kotoba-lang/sprite2d's kami.sprite2d/prim!)
   — no new :anim keys invented here, so this is drawn correctly by the
   existing renderer with zero renderer-side changes.

   The torso primitive is normally sprite[0] (compose-character's body
   vector starts [torso head ...]) — but when the caller composed with
   :cheat? true, cheat-aura has already PREPENDED two already-:anim'd (:pulse)
   halo circles in front of it, so the torso is no longer at a fixed index.
   Rather than hardcode index 0 and get this wrong for cheat characters,
   walk-cycle finds the first primitive that doesn't already carry an :anim
   — that's the torso whether or not an aura sits in front of it — and gives
   IT a vertical :bob (a stride's up-down bounce) at a walking cadence
   noticeably faster than the idle head :pulse [0.04 2.0] breathing rate, so
   the two read as genuinely different motions instead of the same wobble at
   a different amplitude. Every OTHER primitive that doesn't already carry
   its own :anim (accessories, race-accent tells, equipment) gets a small
   horizontal :sway at a different phase/frequency than the torso's bob, so
   accessories don't move in exact lockstep with the torso — a real walk has
   limbs/accessories swinging out of phase with the body, not one rigid
   silhouette translating up and down as a unit. Anything that already had
   its own :anim (the head's breathing :pulse, a cheat-aura halo, a
   holy-symbol glow, ...) is left exactly as it was — walk-cycle only fills
   in gaps, it doesn't override existing motion.

   Composable like cheat-aura: takes a sprite vector, returns a sprite
   vector, so callers pipe it in after compose-character (`(update
   (compose-character ...) :sprite walk-cycle)`)."
  ([sprite] (walk-cycle sprite 1.0))
  ([sprite scale]
   (let [torso-i (or (first (keep-indexed (fn [i [_ o]] (when-not (:anim o) i)) sprite)) 0)]
     (vec (map-indexed
            (fn [i [kind o]]
              (cond
                (= i torso-i) [kind (assoc o :anim {:bob [(* 8 scale) 4.8]})]
                (:anim o)     [kind o]
                :else         [kind (assoc o :anim {:sway [(* 4 scale) 4.2]})]))
            sprite)))))

(defn compose-character
  "{:race kw :class kw :seed int? :cheat? bool? :variant :watercolor|:brainrot|:pixel8
    :equip? bool?}
   → {:sprite [...primitives...] :render/profile {...} :tags [...]}.

   :equip? (default true) appends kami.isekai.equipment/class->weapons'
   default loadout for `class` (a knight draws a sword+shield, a mage a
   staff, ...) — a bare-handed 'knight' reads as an unfinished sprite, not a
   restrained one. Pass :equip? false to opt out."
  [{:keys [race class seed cheat? variant equip?] :or {seed 0 cheat? false variant :watercolor equip? true}}]
  (let [rc        (races/race race)
        cl        (classes/class class)
        hues      (get pal/race-hues race (:human pal/race-hues))
        class-hue (get-in pal/class-hues [class :accent] (:garment hues))
        tone      (case variant :brainrot pal/brainrot :pixel8 pal/pixel8 pal/watercolor)
        skin      (-> (:skin hues) tone (pal/jitter-color seed))
        accent    (-> class-hue tone)
        stature   (:stature rc 1.0)
        head-r    (* 78 stature)
        torso-r   (* 150 stature)
        body      [[:circle {:dx 0 :dy 0 :r torso-r :fill (rgb->fill (tone (:garment hues)))}]
                    [:circle {:dx 0 :dy (- (* head-r 1.35)) :r head-r :fill (rgb->fill skin) :anim {:pulse [0.04 2.0]}}]]
        sprite    (-> body
                      (into (race-accent-primitives rc head-r torso-r skin accent))
                      (into (accessory-primitives cl head-r accent)))
        sprite    (if cheat? (cheat-aura sprite) sprite)
        base      {:sprite sprite
                    :render/profile {:color (tone (:garment hues)) :w (* 0.8 stature) :h (* 1.7 stature)
                                      :emissive (if cheat? 0.5 0.15)}
                    :tags (cond-> [(name race) (name class)] cheat? (conj "cheat" "op-protagonist"))}]
    (if equip? (equip/equip-for-class base class) base)))
