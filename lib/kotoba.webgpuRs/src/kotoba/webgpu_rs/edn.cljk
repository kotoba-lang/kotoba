(ns kotoba.webgpu-rs.edn
  "Small EDN-value coercion helpers mirroring the tolerant-default reading
  rules `kami-webgpu-rs` (kami-engine, retired per ADR-2607010000) used
  from its `kami-scene` dependency's `num`/`vec3` helpers: missing keys and
  wrong-shaped values fall back to sane defaults instead of panicking/
  throwing. Not a full port of `kami-scene` (a separate crate, out of
  scope for this repo) — just the narrow subset `kami-webgpu-rs` actually
  called, reimplemented directly against Clojure's native EDN data (a
  parsed `.cljc` EDN map already has keyword keys, so the Rust `mget`/
  `kw_key` string-matching machinery has no Clojure counterpart worth
  keeping — plain `get`/keyword lookup replaces it 1:1).

  No network, no I/O.")

(defn numf
  "Read `v` as a double, coercing ints; `0.0` when absent or non-numeric.
  Mirrors kami-scene's `num(Option<&EdnValue>) -> f32`. Named `numf`, not
  `num`, to avoid shadowing `clojure.core/num`."
  [v]
  (if (number? v) (double v) 0.0))

(defn num-or
  "Like [[numf]] but with an explicit default instead of the implicit 0.0."
  [v default]
  (if (number? v) (double v) (double default)))

(defn vec2
  "Read `v` as a 2-vector `[x y]`; missing components default to `1.0`
  (kami-webgpu-rs's own local `vec2` helper, distinct from kami-scene's
  `vec3`, which pads with `0.0` — instance `:size` has no sane zero)."
  [v]
  (let [s (if (vector? v) v [])]
    [(num-or (get s 0) 1.0) (num-or (get s 1) 1.0)]))

(defn vec3
  "Read `v` as a 3-vector `[x y z]`; missing components default to `0.0`,
  and a non-vector yields `[0 0 0]`. Mirrors kami-scene's `vec3`."
  [v]
  (let [s (if (vector? v) v [])]
    [(numf (get s 0)) (numf (get s 1)) (numf (get s 2))]))

(defn opt-vec3
  "[[vec3]], but `nil` (not `[0 0 0]`) when `v` isn't a vector at all —
  mirrors kami-webgpu-rs's `opt_vec3`, used where 'absent' and 'present at
  the origin' must be distinguishable (e.g. `Globals :eye`/`:target`)."
  [v]
  (when (vector? v) (vec3 v)))

(defn bool-or
  "`v` if it's actually a boolean, else `default` — mirrors
  `EdnValue::as_bool().unwrap_or(default)` (a non-bool value, not just a
  missing key, falls back to the default)."
  [v default]
  (if (boolean? v) v default))

(defn ident
  "Local (namespace-dropped) name of a keyword or string value, if `v` is
  one of those; `nil` otherwise. Mirrors kami-webgpu-rs's `ident`."
  [v]
  (cond
    (keyword? v) (name v)
    (string? v) v
    :else nil))
