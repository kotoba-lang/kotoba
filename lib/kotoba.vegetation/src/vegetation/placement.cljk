(ns vegetation.placement
  "Placement: scatter instances over terrain using Poisson-disk + biome filter.

  Restored from `kami-vegetation/src/placement.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  The original Rust module depends on `kami_terrain::{Heightmap, Splatmap}`.
  To keep this crate zero-dependency and portable, `place-instances` takes
  the heightmap/splatmap as plain CLJC data + sampling functions instead
  of a hard dependency on another repo's terrain types:

    heightmap = {:width w :depth d
                 :sample  (fn [hx hz] height)          ; bilinear/point sample
                 :normal  (fn [gx gz] [nx ny nz])}      ; grid-index normal
    splatmap  = {:width w :data [{:weights [g r s sn]} ...]}  ; row-major, len = width*depth

  This mirrors `hm.sample(hx, hz)` / `hm.normal(nj, ni)` /
  `splat.data[idx].weights` from the original Rust call sites 1:1.

  The deterministic PRNG mirrors the original `xorshift32`, and species
  placement order/density/Poisson-disk dart-throwing logic are ported
  1:1 so that, given equivalent heightmap/splatmap sampling functions,
  the output is deterministic per seed exactly as in the Rust original."
  (:require [vegetation.species :as species]
            [vegetation.instance :as instance]))

(def ^:private TAU (* 2.0 #?(:clj Math/PI :cljs js/Math.PI)))

(defn default-placement-config
  []
  {:seed 42
   :extent 256.0
   :density-scale 1.0
   :species-filter []})

;; ---------------------------------------------------------------------
;; Deterministic PRNG — xorshift32 (matches the original Rust `Rng`)
;; ---------------------------------------------------------------------
;; u32 arithmetic emulated via bit-and with 0xffffffff after each shift/xor,
;; since CLJC has no native unsigned 32-bit type.

(def ^:private U32-MASK 0xffffffff)

(defn- u32 [x] (bit-and x U32-MASK))

(defn rng-new
  "New xorshift32 RNG state (a plain integer, 0 seed maps to 1 as in Rust)."
  [seed]
  (u32 (if (zero? (u32 seed)) 1 seed)))

(defn rng-next-u32
  "Advance the RNG; returns [next-u32-value new-state]."
  [state]
  (let [x state
        x (u32 (bit-xor x (bit-shift-left x 13)))
        x (u32 (bit-xor x (unsigned-bit-shift-right x 17)))
        x (u32 (bit-xor x (bit-shift-left x 5)))]
    [x x]))

(defn rng-next-f32
  "Returns [f32-in-[0,1) new-state]."
  [state]
  (let [[x state'] (rng-next-u32 state)]
    [(/ (double (bit-and x 0x7fffffff)) (double 0x7fffffff)) state']))

(defn rng-range
  "Returns [value-in-[min,max) new-state]."
  [state mn mx]
  (let [[f state'] (rng-next-f32 state)]
    [(+ mn (* (- mx mn) f)) state']))

;; ---------------------------------------------------------------------
;; Placement
;; ---------------------------------------------------------------------

(defn- clamp [x lo hi] (max lo (min hi x)))

(defn- too-close?
  "True if (x,z) is closer than sqrt(min-dist-sq) to any point already placed."
  [placed x z min-dist-sq]
  (boolean
   (some (fn [[px pz]]
           (let [dx (- x px) dz (- z pz)]
             (< (+ (* dx dx) (* dz dz)) min-dist-sq)))
         placed)))

(defn- sample-slope
  "Slope (0 = flat, 1 = vertical) at grid indices (nj, ni)."
  [hm nj ni]
  (- 1.0 (nth ((:normal hm) nj ni) 1)))

(defn- splat-affinity
  "Weighted material affinity at grid indices (nj, ni)."
  [splat nj ni sp]
  (let [splat-idx (+ (* ni (:width splat)) nj)
        sw (:weights (nth (:data splat) splat-idx))
        aff (:material-affinity sp)]
    (+ (* (nth sw 0) (nth aff 0))
       (* (nth sw 1) (nth aff 1))
       (* (nth sw 2) (nth aff 2))
       (* (nth sw 3) (nth aff 3)))))

(defn- try-place-one
  "One dart-throw attempt. Returns {:accepted? bool :x :z :inst :rng} —
   `:inst`/`:x`/`:z` only present when accepted."
  [hm splat origin-x origin-z sp rng extent min-dist-sq placed]
  (let [[x rng] (rng-range rng (* extent -0.5) (* extent 0.5))
        [z rng] (rng-range rng (* extent -0.5) (* extent 0.5))]
    (if (too-close? placed x z min-dist-sq)
      {:accepted? false :rng rng}
      (let [hx (clamp (- x origin-x) 0.0 (double (dec (:width hm))))
            hz (clamp (- z origin-z) 0.0 (double (dec (:depth hm))))
            height ((:sample hm) hx hz)]
        (if (or (< height (:min-height sp)) (> height (:max-height sp)))
          {:accepted? false :rng rng}
          (let [ni (min (long hz) (dec (:depth hm)))
                nj (min (long hx) (dec (:width hm)))
                slope (sample-slope hm nj ni)]
            (if (> slope (:max-slope sp))
              {:accepted? false :rng rng}
              (let [affinity (splat-affinity splat nj ni sp)]
                (if (< affinity 0.2)
                  {:accepted? false :rng rng}
                  (let [[scale rng] (rng-range rng (nth (:scale-range sp) 0) (nth (:scale-range sp) 1))
                        [rotation rng] (rng-range rng 0.0 TAU)
                        [wind-phase rng] (rng-range rng 0.0 TAU)
                        [color-tint rng] (rng-range rng -0.15 0.15)
                        inst (instance/make-instance
                              {:position [x height z]
                               :scale scale
                               :rotation rotation
                               :species (double (species/species-id->index (:id sp)))
                               :wind-phase wind-phase
                               :color-tint color-tint})]
                    {:accepted? true :x x :z z :inst inst :rng rng}))))))))))

(defn- place-species
  "Dart-throwing Poisson-disk placement (simplified, ~6 attempts / desired
   point) for a single species."
  [hm splat origin-x origin-z sp seed extent density-scale]
  (let [rng0 (rng-new seed)
        target-count (long (* (:density sp) density-scale
                               (let [r (/ extent 100.0)] (* r r))))
        min-dist-sq (* (:min-distance sp) (:min-distance sp))
        max-attempts (* target-count 6)]
    (loop [placed [] attempts 0 rng rng0 out []]
      (if (or (>= (count placed) target-count) (>= attempts max-attempts))
        out
        (let [{:keys [accepted? x z inst rng]}
              (try-place-one hm splat origin-x origin-z sp rng extent min-dist-sq placed)]
          (if accepted?
            (recur (conj placed [x z]) (inc attempts) rng (conj out inst))
            (recur placed (inc attempts) rng out)))))))

(defn place-instances
  "Place instances for all configured species.
   `hm`    — {:width :depth :sample (fn [hx hz]) :normal (fn [gx gz])}
   `splat` — {:width :data [{:weights [g r s sn]} ...]}
   Returns a flat vector of instance maps (see `vegetation.instance`),
   grouped by species (species iteration order matches
   `vegetation.species/species-table`, for batched draws)."
  [hm splat origin-x origin-z config]
  (let [table (species/species-table)
        {:keys [species-filter seed extent density-scale]} config
        active (if (empty? species-filter)
                 table
                 (filterv #(some #{(:id %)} species-filter) table))]
    (vec
     (mapcat (fn [idx sp]
               (place-species hm splat origin-x origin-z sp
                               (u32 (+ seed (* idx 7919))) extent density-scale))
             (range)
             active))))
