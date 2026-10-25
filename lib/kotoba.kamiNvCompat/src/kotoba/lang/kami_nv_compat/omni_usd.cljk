(ns kotoba.lang.kami-nv-compat.omni-usd
  "Drop-in pxr.Usd / UsdGeom / omni.usd API-compat facade. Portable .cljc
  port of src/omni-usd.ts. Wave 35.

  Mirrors the documented public OpenUSD Python surface (Stage / Prim /
  Attribute + UsdGeom.Mesh / UsdGeom.Xformable) for the USDA geometry
  subset. Backed by the clean-room kami-usd reader (USDA parse +
  geometry flatten).

  A Stage is {:roots [UsdPrimNode...] :index {path -> UsdPrimNode}}.
  Prims and Attributes ARE the UsdPrimNode / UsdAttribute maps
  kami-usd.usda/parse-usda already produces — no wrapper classes are
  needed (unlike the TS source's Prim/Attribute classes), since those
  maps already expose :path/:name/:type-name/:specifier/:attributes/
  :children/:value directly. This namespace's real value-add over
  kami-usd.usda is stage indexing + traversal + the USD -> kami-rt /
  kami-rtx scene bridge. The prim-get-*/attribute-get-* functions below
  are thin (mostly redundant with plain keyword access) and exist only
  for API-surface parity with the TS source's Prim.Get*()/
  Attribute.Get*() methods.

  Clean-room: this re-implements the public USD API *shape* (Google v.
  Oracle, 593 U.S. ___ (2021)). No USD / OpenUSD / tinyusdz source,
  headers, or SDK binaries are used. The canonical engine has a
  distinct name -- kami-usd.

  Trademark: USD / OpenUSD are projects of Pixar / the Alliance for
  OpenUSD; \"Omniverse\" is a trademark of NVIDIA Corporation. Names
  here are API-compat identifiers only.

  ADR-2605261800 SD1/D6, R1.4 omni-usd surface."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.index :as kami-rt]
            [kotoba.lang.kami-nv-compat.kami-rt.pathtrace :as pt]
            [kotoba.lang.kami-nv-compat.kami-usd.usda :as usda]
            [kotoba.lang.kami-nv-compat.kami-usd.geom :as geom]))

;; ── pxr.Usd.Stage ─────────────────────────────────────────────────────────

(defn- index-tree
  [acc node]
  (reduce index-tree (assoc acc (:path node) node) (:children node)))

(defn stage-open
  "Usd.Stage.Open() mirror. Accepts USDA text (a path-loading overload is a
  future kami-usd milestone; this build is text-in)."
  [usda-text]
  (let [roots (usda/parse-usda usda-text)]
    {:roots roots :index (reduce index-tree {} roots)}))

(defn stage-create-in-memory
  "Usd.Stage.CreateInMemory() mirror — an empty stage."
  []
  {:roots [] :index {}})

(defn get-prim-at-path
  [stage path]
  (get (:index stage) path))

(defn get-pseudo-root
  [stage]
  (:roots stage))

(defn traverse
  "Usd.Stage.Traverse() mirror — depth-first over every prim (pre-order,
  children left-to-right), as a lazy seq."
  [stage]
  (letfn [(walk [node] (cons node (mapcat walk (:children node))))]
    (mapcat walk (:roots stage))))

;; ── pxr.Usd.Prim / pxr.Usd.Attribute accessors ───────────────────────────

(defn prim-valid? [prim] (some? prim))
(defn prim-get-path [prim] (:path prim))
(defn prim-get-name [prim] (:name prim))
(defn prim-get-type-name [prim] (:type-name prim))
(defn prim-get-specifier [prim] (:specifier prim))
(defn prim-get-attribute [prim attr-name] (get (:attributes prim) attr-name))
(defn prim-has-attribute? [prim attr-name] (contains? (:attributes prim) attr-name))
(defn prim-get-attribute-names [prim] (vec (keys (:attributes prim))))
(defn prim-get-children [prim] (:children prim))

(defn attribute-valid? [attr] (some? attr))
(defn attribute-get [attr] (:value attr))
(defn attribute-get-type-name [attr] (or (:type-name attr) ""))
(defn attribute-get-name [attr] (or (:name attr) ""))

;; ── UsdGeom typed-schema helper ───────────────────────────────────────────

(defn usd-geom-mesh-get
  "UsdGeom.Mesh.Get(prim) mirror — mesh accessors for a prim whose type is
  \"Mesh\"."
  [prim]
  {:points-attr (prim-get-attribute prim "points")
   :face-vertex-indices-attr (prim-get-attribute prim "faceVertexIndices")
   :face-vertex-counts-attr (prim-get-attribute prim "faceVertexCounts")
   :display-color-attr (prim-get-attribute prim "primvars:displayColor")})

;; ── scene bridge (KAMI extension: USD -> kami-rt / kami-rtx) ─────────────

(defn stage->flat-scene
  "Flatten a stage to world-space triangles + materials."
  [stage]
  (geom/flatten-stage (:roots stage)))

(defn stage->scene
  "Build a kami-rt ray-trace Scene from a stage."
  [stage]
  (kami-rt/build-scene (:triangles (stage->flat-scene stage))))

(defn stage->path-scene
  "Build a kami-rtx path-trace PathScene from a stage."
  [stage]
  (let [flat (stage->flat-scene stage)]
    (pt/build-path-scene (:triangles flat) (:materials flat))))

(def kami-engine "kami-usd")
(def adr "ADR-2605261800")
