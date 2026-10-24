(ns kotoba.car-sim.ground
  "Ground surface table + multi-zone surface map — ported from
  `kami-app-car-sim`'s public demo (`driver.etzhayyim.com`) and the shared
  `kami-vehicle-scene/data/ground.edn` CONFIG (ADR-2607010000: hot physics
  stays out of scope here, only the init-time surface/grip DATA and the
  pure `surface-at` zone lookup move to `.cljc`).

  Pure data in, pure data out: no network, no I/O. Portable across
  JVM / ClojureScript / SCI / GraalVM.

  The 8 surface kinds and the `:demo-circuit` zone map below are the exact
  values shipped by the Rust `kami-vehicle`/`kami-vehicle-scene` crates
  (`SurfaceKind::coefficients/tint/display_name`, `MapGround::demo_circuit`)
  — kept as parity fixtures against ADR-2607010000's Rust source of truth."
  (:require [kotoba.lang.text :as str]))

;; ── Surface table ───────────────────────────────────────────────────────────
;; id -> {:friction-mu .. :grip-modifier .. :tint [r g b] :name ".." :renderer-id N}
;; `:renderer-id` mirrors the Rust `surface_id()` fn (0..7), kept for host
;; adapters (e.g. a WGSL renderer) that need a numeric surface id.

(def surfaces
  {:asphalt-dry {:friction-mu 1.00 :grip-modifier 1.00 :tint [0.20 0.20 0.22] :name "Dry Asphalt" :renderer-id 0}
   :asphalt-wet {:friction-mu 0.70 :grip-modifier 0.70 :tint [0.16 0.18 0.24] :name "Wet Asphalt" :renderer-id 1}
   :gravel      {:friction-mu 0.55 :grip-modifier 0.55 :tint [0.45 0.42 0.38] :name "Gravel"      :renderer-id 2}
   :sand        {:friction-mu 0.40 :grip-modifier 0.45 :tint [0.85 0.75 0.55] :name "Sand"        :renderer-id 3}
   :snow        {:friction-mu 0.30 :grip-modifier 0.35 :tint [0.95 0.95 0.98] :name "Snow"        :renderer-id 4}
   :ice         {:friction-mu 0.10 :grip-modifier 0.10 :tint [0.75 0.85 0.95] :name "Ice"         :renderer-id 5}
   :mud         {:friction-mu 0.35 :grip-modifier 0.40 :tint [0.30 0.22 0.15] :name "Mud"         :renderer-id 6}
   :grass       {:friction-mu 0.55 :grip-modifier 0.60 :tint [0.30 0.55 0.25] :name "Grass"       :renderer-id 7}})

(def default-surface :asphalt-dry)

(defn surface-id
  "Resolve any of a keyword, hyphenated string, or underscored string to a
  canonical surface keyword. Unknown ids fall back to `default-surface`
  (mirrors Rust `SurfaceKind::from_id`)."
  [id]
  (let [kw (cond
             (keyword? id) id
             (string? id) (keyword (str/replace id "_" "-"))
             :else nil)]
    (if (contains? surfaces kw) kw default-surface)))

(defn coefficients
  "`[friction-mu grip-modifier]` for a surface id."
  [id]
  (let [{:keys [friction-mu grip-modifier]} (get surfaces (surface-id id))]
    [friction-mu grip-modifier]))

(defn tint [id] (:tint (get surfaces (surface-id id))))
(defn display-name [id] (:name (get surfaces (surface-id id))))
(defn renderer-id [id] (:renderer-id (get surfaces (surface-id id))))

;; ── Multi-zone ground map ───────────────────────────────────────────────────

(defn zone
  "Build one rectangular surface zone `[x-min x-max] x [z-min z-max]`."
  [x-min x-max z-min z-max surface]
  {:x-min x-min :x-max x-max :z-min z-min :z-max z-max :surface (surface-id surface)})

(def demo-circuit
  "Reference test track: a long asphalt road through the centre with
  off-road patches of sand / snow / ice / mud / gravel on either side.
  Ported verbatim from `kami-vehicle::ground::MapGround::demo_circuit` /
  `kami-vehicle-scene/data/ground.edn`."
  {:default :grass
   :zones
   [(zone -4.0 4.0 -100.0 100.0 :asphalt-dry)   ; main road, centre strip
    (zone -4.0 4.0 8.0 20.0 :asphalt-wet)        ; wet patch on the road
    (zone -4.0 4.0 30.0 42.0 :ice)               ; ice patch further down
    (zone -4.0 4.0 55.0 75.0 :snow)              ; snow patch at the far end
    (zone 8.0 30.0 -20.0 20.0 :sand)             ; sand area, right
    (zone 8.0 30.0 25.0 60.0 :gravel)            ; gravel area, right/forward
    (zone -30.0 -8.0 -20.0 20.0 :mud)            ; mud area, left
    (zone -30.0 -8.0 25.0 60.0 :snow)            ; snow area, left/forward
    (zone -4.0 4.0 -45.0 -30.0 :mud)]})          ; reverse bay behind

(defn in-zone?
  [{:keys [x-min x-max z-min z-max]} x z]
  (and (>= x x-min) (<= x x-max) (>= z z-min) (<= z z-max)))

(defn surface-at
  "Surface kind at world position `(x, z)` for `ground-map` (a map shaped
  like `demo-circuit`: `{:default kw :zones [zone ..]}`). Returns the first
  matching zone's `:surface`, else `:default`. Mirrors Rust
  `MapGround::surface_at` (first match wins — zones are not required to be
  disjoint)."
  [ground-map x z]
  (or (some #(when (in-zone? % x z) (:surface %)) (:zones ground-map))
      (:default ground-map)))

(defn sample
  "Ground contact sample at `(x, z)`: `{:normal [0 1 0] :height 0.0
  :friction-mu .. :grip-modifier ..}` — the pure data mirror of Rust
  `MapGround::sample` / `Ground::sample` (flat map ground, height always
  0.0; a heightmap-backed host adapter overrides `:height`/`:normal`)."
  [ground-map x z]
  (let [surface (surface-at ground-map x z)
        [mu grip] (coefficients surface)]
    {:normal [0.0 1.0 0.0]
     :height 0.0
     :surface surface
     :friction-mu mu
     :grip-modifier grip}))
