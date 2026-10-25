(ns character.space
  "Coordinate-space-safety convention, without Rust (ADR-0048 §1,
  `kotoba-lang/kami-engine`, `90-docs/adr/0048-global-format-standards-
  kotoba-clj-wasm-no-rust.md`, `com-junkawasaki/root`).

  kotoba-clj has no static type system, so this org cannot get Rust
  `euclid`'s zero-cost COMPILE-TIME phantom-type guarantee for
  `Point3D<T, Space>`. This namespace is the honest, adoptable equivalent:
  a **tagged point** — `{:space <keyword> :xyz [x y z]}` — plus a
  **checked-at-runtime** contract enforced by `kotoba.lang.spec`, not a
  compile-time one. Space names (`:world` / `:head-local` / `:bind-pose`,
  ...) are the vocabulary borrowed directly from OpenUSD's `UsdSkel` schema
  (world-space `bindTransforms`, joint-local rest pose, `geomBindTransform`)
  — reusing USD's NAMING only, no USD runtime dependency.

  Rules (ADR-0048 §1, verbatim):
  - Every position value that crosses a function boundary in a geometry-
    producing library is a tagged map, never a bare `[x y z]` vector.
  - A single conversion function per space pair (`world->head-local`,
    `head-local->world`, ...) is the ONLY sanctioned way to change a
    value's `:space` tag.
  - No function may read `:xyz` off a tagged point without checking
    `:space` first — `xyz` (below) is that check, and it THROWS (with both
    the expected and actual space in the error) on a mismatch, matching
    this org's 'no silent fallback' convention.

  ## Retrofit scope in THIS repo (v0 — see `character/generate-character-
  tagged`)

  Tagging is applied at MESH-PART granularity (every vertex within one
  `MeshPart` shares one space in every generator this repo has today), not
  rewritten into every internal per-vertex math function
  (`character.base-mesh`/`character.hair`/`character.body`/
  `character.blendshape`/... keep operating on bare `[x y z]` vectors
  internally, unchanged). This is a deliberate v0 scope cut, not an
  oversight: the actual bug this ADR exists to prevent (`kami-gen-hybrid`
  commit 848012e — head-local eye/hair vertices fed into world-space
  skin-weighting as if they shared one frame) happened at the point where
  DIFFERENT PARTS get merged into one list, not inside any part's own
  internal vertex math. Tagging every one of `character`'s thousands of
  per-vertex math call sites across ~15 files would touch this whole
  repo's hot geometry-generation code for no additional protection at that
  bug's actual granularity. `tag-part`/`untag-part`/`retag-part` (below)
  work on individual vertices too, if a future generator ever needs to mix
  spaces WITHIN one part."
  (:require [kotoba.lang.spec :as spec]))

;; ---------------------------------------------------------------------------
;; Tagged points
;; ---------------------------------------------------------------------------

(defn point
  "Construct a tagged point: `{:space space :xyz [x y z]}`."
  [space xyz]
  {:space space :xyz xyz})

(def ^:private point-spec
  {:type :map
   :keys {:space {:type :keyword}
          :xyz   {:type :vector}}})

(defn- assert-tagged-point!
  [context pt]
  (when (= spec/invalid (spec/validate point-spec pt))
    (throw (ex-info (str context ": not a tagged point (need {:space <keyword> :xyz [x y z]})")
                     {:point pt :problems (spec/explain point-spec pt)}))))

(defn xyz
  "The ONLY sanctioned way to read `:xyz` off a tagged point `pt`. Asserts
  (via `kotoba.lang.spec`) that `pt` is shaped like a tagged point AND that
  its `:space` is exactly `expected-space`, throwing with BOTH the expected
  and actual space on any mismatch — a checked RUNTIME contract, not a
  compile-time guarantee (this ADR says so plainly rather than overclaiming
  Rust-`euclid`-equivalent safety)."
  [expected-space pt]
  (assert-tagged-point! "character.space/xyz" pt)
  (when (not= expected-space (:space pt))
    (throw (ex-info "character.space/xyz: wrong :space"
                     {:expected expected-space :actual (:space pt) :point pt})))
  (:xyz pt))

;; ---------------------------------------------------------------------------
;; Conversions — the ONLY sanctioned way to change a point's :space
;; ---------------------------------------------------------------------------

(defn head-local->world
  "Convert a `:head-local` tagged point to `:world` by adding
  `head-world-offset` (the head bone's own world-space rest position, a
  bare `[x y z]`, e.g. `character.body/bone-world-positions`'s entry for
  the `\"head\"` bone).

  v0 limitation: TRANSLATION ONLY (no rotation) — every generator this repo
  has today (`character.base-mesh/generate-head`/`generate-eyes`/
  `generate-eyebrows`, `character.hair/generate-hair`) builds head-local
  geometry axis-aligned with the head bone's own local frame at bind pose,
  so a translate-only conversion is exact for them; a head bone with a
  non-identity bind ROTATION would need a full transform (rotate then
  translate), not just an offset add — this fn does not attempt that."
  [head-world-offset pt]
  (let [[x y z] (xyz :head-local pt)
        [ox oy oz] head-world-offset]
    (point :world [(+ x ox) (+ y oy) (+ z oz)])))

(defn world->head-local
  "Inverse of `head-local->world` (same translation-only v0 limitation)."
  [head-world-offset pt]
  (let [[x y z] (xyz :world pt)
        [ox oy oz] head-world-offset]
    (point :head-local [(- x ox) (- y oy) (- z oz)])))

;; ---------------------------------------------------------------------------
;; Part-level tagging (v0 granularity — see ns docstring)
;; ---------------------------------------------------------------------------

(defn tag-part
  "Tag every vertex `:position` in `MeshPart` map `part` (`{:vertices
  [{:position [x y z] ...} ...] ...}`) as a `space`-tagged point, and stamp
  `part` itself with `:space` (redundant with every vertex's own tag, but
  lets a caller branch on `(:space part)` without touching every vertex)."
  [space part]
  (-> part
      (assoc :space space)
      (update :vertices (fn [vs] (mapv (fn [v] (update v :position #(point space %))) vs)))))

(defn untag-part
  "Exact inverse of `tag-part`: strip every vertex `:position` back to a
  bare `[x y z]` vector AND drop the part-level `:space` key `tag-part`
  added, asserting (via `xyz`) that every vertex is ACTUALLY tagged
  `expected-space` first — a part that claims a space it doesn't have
  throws instead of silently untagging the wrong data. Use this at the
  boundary back into space-agnostic legacy math (skin-weights, GLB export)
  once every part in a batch is confirmed to share one space."
  [expected-space part]
  (-> part
      (dissoc :space)
      (update :vertices (fn [vs] (mapv (fn [v] (update v :position #(xyz expected-space %))) vs)))))

(defn retag-part
  "Convert every vertex `:position` in `part` from `from-space` to
  `to-space` via `convert-fn` (a tagged-point -> tagged-point fn, e.g.
  `(partial head-local->world head-world-pos)`), returning `part` with
  `:space to-space`. `convert-fn` itself is expected to assert `from-space`
  (every fn in this namespace does, via `xyz`)."
  [to-space convert-fn part]
  (-> part
      (assoc :space to-space)
      (update :vertices (fn [vs] (mapv (fn [v] (update v :position convert-fn)) vs)))))
