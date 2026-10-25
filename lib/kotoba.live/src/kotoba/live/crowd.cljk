(ns kotoba.live.crowd
  "Crowd — instanced fan agents that react to the show.

  Lightweight CPU sim. Each fan has a position, a baseline mood, and a
  y-offset driven by the beat (jumps on Pit/Floor/drop). [[snapshot]] yields
  one `FanSnapshot` per fan per tick for the renderer.

  Placement uses a small deterministic PRNG (mulberry32 — chosen for a tiny,
  dependency-free, cljc-portable 32-bit generator) seeded from `:seed`, so the
  same seed always yields the same crowd layout on any platform. This is a
  *different* generator from the original Rust SplitMix64 (bit-identical
  cross-language RNG output isn't a goal — determinism-per-seed is)."
  (:require [kotoba.live.mathx :as mathx]
            [kotoba.live.stage :as stage]))

(def moods #{:bob :jump :sway :hush})

(def ^:private tau mathx/tau)

(def ^:private palette
  [[1.0 0.4 0.5] [0.4 0.7 1.0] [1.0 0.85 0.3]
   [0.5 1.0 0.6] [0.85 0.5 1.0] [1.0 1.0 1.0]])

;; ── deterministic PRNG (mulberry32) ─────────────────────────────────────────

#?(:clj
   (defn- imul32 [a b]
     (bit-and (unchecked-multiply-int (unchecked-int a) (unchecked-int b)) 0xffffffff))
   :cljs
   (defn- imul32 [a b]
     (bit-and (js/Math.imul a b) 0xffffffff)))

(defn- rng-init [seed] (bit-and seed 0xffffffff))

(defn- rng-next-u32
  "`[state' u32]` — one mulberry32 step."
  [state]
  (let [a (bit-and (+ state 0x6D2B79F5) 0xffffffff)
        t1 (imul32 (bit-xor a (unsigned-bit-shift-right a 15)) (bit-or a 1))
        add-term (imul32 (bit-xor t1 (unsigned-bit-shift-right t1 7)) (bit-or t1 61))
        t2 (bit-and (bit-xor t1 (bit-and (+ t1 add-term) 0xffffffff)) 0xffffffff)
        result (bit-and (bit-xor t2 (unsigned-bit-shift-right t2 14)) 0xffffffff)]
    [a result]))

(defn- rng-next-f32
  "`[state' f]` — next value in [0,1)."
  [state]
  (let [[s u] (rng-next-u32 state)]
    [s (/ u 4294967296.0)]))

;; ── config / construction ───────────────────────────────────────────────────

(defn default-config []
  {:fans-target 600 :cap 4096 :pit-bias 0.65 :seed 1})

(defn- sample-point [rng-state zone-box]
  (let [[s1 f1] (rng-next-f32 rng-state)
        [s2 f2] (rng-next-f32 s1)
        [cx cy cz] (:centre zone-box)
        [hx _ hz] (:half-size zone-box)
        dx (* (- (* f1 2.0) 1.0) hx)
        dz (* (- (* f2 2.0) 1.0) hz)]
    [s2 [(+ cx dx) cy (+ cz dz)]]))

(defn new-crowd
  "Build a crowd of up to `(min fans-target cap)` fans, placed deterministically
  by `:seed` across the stage's `:pit` / `:floor` zones (biased by
  `:pit-bias`)."
  [cfg stage]
  (let [{:keys [fans-target cap pit-bias seed]} (merge (default-config) cfg)
        n (min fans-target cap)
        pit (stage/zone stage :pit)
        floor (stage/zone stage :floor)]
    (loop [i 0 rng (rng-init seed) fans []]
      (if (or (>= i n) (and (nil? pit) (nil? floor)))
        {:fans fans :config {:fans-target fans-target :cap cap :pit-bias pit-bias :seed seed} :decay 0.95}
        (let [[r0 pick] (rng-next-f32 rng)
              zone-box (cond
                         (and pit floor) (if (< pick pit-bias) pit floor)
                         pit pit
                         :else floor)
              [r1 home] (sample-point r0 zone-box)
              [r2 phase-offset] (rng-next-f32 r1)
              [r3 pick2] (rng-next-f32 r2)
              color-idx (min (dec (count palette)) (long (* pick2 (count palette))))]
          (recur (inc i) r3
                 (conj fans {:home home
                             :phase-offset phase-offset
                             :stick-color (nth palette color-idx)
                             :energy 0.25
                             :mood :bob})))))))

(defn set-mood-all
  "Switch every fan to a new mood (e.g. on a Drop / Breakdown cue)."
  [crowd mood]
  (update crowd :fans (fn [fans] (mapv #(assoc % :mood mood) fans))))

(defn react
  "Apply a discrete cheer `kind` to every fan for which `(zones-of home)` is
  truthy."
  [crowd kind zones-of]
  (let [bump (case kind :clap 0.15 :yell 0.30 :light-stick 0.10 :jump 0.50 0.0)]
    (update crowd :fans
            (fn [fans]
              (mapv (fn [f]
                      (if (zones-of (:home f))
                        (cond-> (update f :energy #(min 1.0 (+ % bump)))
                          (= kind :jump) (assoc :mood :jump))
                        f))
                    fans)))))

(defn snapshot
  "Per-frame render snapshot: `[crowd' fan-snapshots]`. Fan energy decays
  toward baseline 0.2 after each call."
  [crowd phase]
  (let [decay (:decay crowd)
        beat-frac (:beat-frac phase)]
    (loop [fans (:fans crowd) out [] acc []]
      (if (empty? fans)
        [(assoc crowd :fans acc) out]
        (let [f (first fans)
              p (mod (+ beat-frac (:phase-offset f)) 1.0)
              height (case (:mood f)
                       :bob (* 0.05 (mathx/abs (mathx/sin (* p tau))))
                       :jump (if (< p 0.4)
                               (let [q (/ p 0.4)] (* 0.6 (- 1.0 (mathx/pow (- 1.0 q) 2))))
                               0.0)
                       :sway (* 0.02 (mathx/cos (* p tau)))
                       :hush 0.0
                       0.0)
              [hx hy hz] (:home f)
              raised (or (contains? #{:sway :jump} (:mood f)) (> (:energy f) 0.6))
              snap {:position [hx (+ hy height) hz]
                    :stick-color (:stick-color f)
                    :stick-raised raised
                    :body-height 1.6}
              f' (update f :energy #(max 0.2 (* % decay)))]
          (recur (rest fans) (conj out snap) (conj acc f')))))))
