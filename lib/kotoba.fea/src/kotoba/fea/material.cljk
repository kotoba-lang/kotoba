(ns kotoba.fea.material
  "Material model + built-in presets — cljc port of kami-cae's `material`
  module (kami-engine, retired per ADR-2607010000).

  A material is `{:name string :model model}`. A `LinearElastic` model is
  `{:type :linear-elastic :youngs-modulus :poissons-ratio :density
  :thermal-expansion :thermal-conductivity :specific-heat}` (SI units:
  Pa, -, kg/m^3, 1/K, W/(m*K), J/(kg*K)); `Hyperelastic`/`ElastoPlastic`
  are `{:type :hyperelastic}` / `{:type :elasto-plastic}` placeholders,
  matching kami-cae's unimplemented enum variants of the same names.

  kami-cae's `MaterialLibrary` struct (a `Vec<FeMaterial>` + methods) has
  no idiomatic-Clojure counterpart worth keeping — a materials collection
  here is just a plain vector of material maps, and `find-material`/
  `add-material` operate on it directly.

  The four built-in presets (Steel-Structural / Aluminum-6061 /
  Titanium-6Al4V / Concrete) are data, not code — extracted verbatim to
  `resources/kami/fea/materials.edn`. This namespace is 100% pure/portable
  (.cljc, no I/O); loading that EDN resource is a JVM classpath concern,
  split out to the sibling `kotoba.fea.material-loader` (plain `.clj`) so
  this namespace never needs a reader-conditional `require`.")

(def presets-resource
  "Classpath-relative path to the built-in presets EDN, for
  `kotoba.fea.material-loader/presets` (or any other host's resource
  loader) to read."
  "kami/fea/materials.edn")

(defn find-material
  "Look up a material by `name` within a `materials` collection. nil if
  not found."
  [materials name]
  (first (filter #(= (:name %) name) materials)))

(defn add-material
  "Append `mat` to `materials`, returning the updated collection."
  [materials mat]
  (conj (vec materials) mat))
