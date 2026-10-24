(ns kami-app-giemon-factory.clashes
  "Engineering clashes (`Clashes`/`Clash` in `scene.rs`), generated in the
  original crate by an external `engineering.py` into `clashes.json` and
  deserialized via serde. That JSON is not present anywhere in this monorepo
  checkout, so `Clashes::load` is not ported — callers supply the parsed
  clashes map.

  A clashes map: `{:clashes/of \"giemon-factory-r0\" :clashes/clashes
  [clash ...]}`. Each clash: `{:id .. :kind .. :systems [..] :x .. :y ..
  :z ..}` — 1:1 with the Rust `Clash` fields (`kind` is \"hard\" (utility ∩
  structure) or \"coordination\" (services < clearance)).

  `valid?`/`hard`/`coordination` are inlined from the Rust crate's own
  `#[cfg(test)]` `clashes_load` test, which asserted every clash has a known
  kind and finite `x`/`z` coordinates.")

(def kinds #{"hard" "coordination"})

(defn- finite? [n]
  #?(:clj (and (number? n) (not (Double/isNaN (double n))) (not (Double/isInfinite (double n))))
     :cljs (and (number? n) (js/isFinite n))))

(defn hard
  "Only the \"hard\" (utility ∩ structure) clashes."
  [clashes]
  (filterv #(= (:kind %) "hard") (:clashes/clashes clashes)))

(defn coordination
  "Only the \"coordination\" (services < clearance) clashes."
  [clashes]
  (filterv #(= (:kind %) "coordination") (:clashes/clashes clashes)))

(defn valid?
  "True if every clash has a known `:kind` and finite `:x`/`:y`/`:z`
  coordinates (ported from the Rust `clashes_load` test)."
  [clashes]
  (every? (fn [c]
            (and (contains? kinds (:kind c))
                 (finite? (:x c)) (finite? (:y c)) (finite? (:z c))))
          (:clashes/clashes clashes)))
