(ns cad-import.part
  "Vehicle part graph data model.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Ported 1:1 from the
   original `src/part.rs`.

   `VehicleAssembly` is the single source of truth shared between the
   soft-body simulator (`kami-vehicle` / `vehicle.*`, restored as CLJC
   too — see kotoba-lang/kami-vehicle) and the SBOM emitter
   (`sbom.etzhayyim.com`). Every part carries provenance — without it the
   emitters refuse to produce output (ADR 2605051430).

   Data shapes (plain Clojure maps, mirroring the original Rust structs):

   ```clojure
   ;; ProvenanceSource
   {:uri \"scad://...\" :sha256 \"<64 hex chars>\" :license \"MIT\"}

   ;; Supplier
   {:name \"\" :cpe \"\" :mpn \"\"}          ; default-supplier

   ;; Hardpoint
   {:id \"hp1\" :from-part \"chassis\" :to-part \"hood\"
    :position [0.0 0.7 1.4] :kind :hinge}

   ;; VehiclePart
   {:id \"chassis\" :display-name \"Chassis\" :kind :chassis
    :material :steel-hss :aabb-min [x y z] :aabb-max [x y z]
    :mass-kg nil :parent nil :break-group nil
    :source {...ProvenanceSource...} :supplier {...Supplier...}
    :revision \"0.1.0\"}

   ;; VehicleAssembly
   {:vehicle-id \"v1\" :display-name \"...\" :revision \"0.1.0\"
    :source {...ProvenanceSource...} :parts [...] :hardpoints [...]}
   ```

   `validate` returns `[:ok nil]` or `[:error {:error <kind> ...}]`
   mirroring Rust's `Result<(), AssemblyError>` (`AssemblyError` variants
   become `:error` keys: `:missing-provenance`, `:unknown-hardpoint-part`,
   `:duplicate-part`, `:unknown-parent`)."
  (:require [cad-import.xform :as xf]))

;; ---- PartKind ----

(def part-kinds
  #{:chassis :body :window :powertrain :suspension :wheel :brake
    :interior :electrical :fluid :trim})

(defn default-break-group
  "Default break group used by the BeamNG-style detach API. Mirrors
   `kami-vehicle` / `vehicle.models.sedan` group conventions."
  [kind]
  (case kind
    :chassis 1
    :body 2
    :window 2
    :powertrain 4
    :suspension 5
    :wheel 5
    :brake 5
    :interior 3
    :electrical 4
    :fluid 4
    :trim 3))

;; ---- Material ----

(def materials
  #{:steel-hss :steel-mild :aluminium-cast :aluminium-sheet :glass
    :rubber :plastic :li-ion :composite :other})

(defn density-kg-m3 [material]
  (case material
    :steel-hss 7850.0
    :steel-mild 7850.0
    :aluminium-cast 2700.0
    :aluminium-sheet 2700.0
    :glass 2500.0
    :rubber 1100.0
    :plastic 1100.0
    :li-ion 2500.0
    :composite 1600.0
    :other 1000.0))

(defn beam-spring-n-m
  "Beam axial stiffness (N/m) used as the JBeam emitter default."
  [material]
  (case material
    :steel-hss 800000.0
    :steel-mild 500000.0
    :aluminium-cast 350000.0
    :aluminium-sheet 200000.0
    :glass 100000.0
    :rubber 80000.0
    :plastic 80000.0
    :li-ion 250000.0
    :composite 600000.0
    :other 200000.0))

(defn break-strain
  "Plastic-strain break threshold (dimensionless, fraction of rest length)."
  [material]
  (case material
    :steel-hss 0.20
    :steel-mild 0.18
    :aluminium-cast 0.10
    :aluminium-sheet 0.14
    :glass 0.02
    :rubber 0.50
    :plastic 0.08
    :li-ion 0.06
    :composite 0.06
    :other 0.10))

;; ---- HardpointKind ----

(def hardpoint-kinds #{:bolt :weld :hinge :latch :press :adhesive})

;; ---- Supplier ----

(def default-supplier {:name "" :cpe "" :mpn ""})

;; ---- construction helpers ----

(def default-revision "0.1.0")

(defn new-assembly
  "Construct a new, empty `VehicleAssembly`."
  [vehicle-id source]
  {:vehicle-id vehicle-id
   :display-name vehicle-id
   :revision default-revision
   :source source
   :parts []
   :hardpoints []})

(defn add-part [asm part] (update asm :parts conj part))
(defn add-hardpoint [asm hp] (update asm :hardpoints conj hp))

(defn part-by-id [asm id] (first (filter #(= (:id %) id) (:parts asm))))

;; ---- VehiclePart derived accessors ----

(defn aabb-min-v [part] (:aabb-min part))
(defn aabb-max-v [part] (:aabb-max part))

(defn aabb-centre [part]
  (xf/v3-scale (xf/v3-add (aabb-min-v part) (aabb-max-v part)) 0.5))

(defn aabb-volume-m3 [part]
  (let [[sx sy sz] (xf/v3-sub (aabb-max-v part) (aabb-min-v part))]
    (* (max sx 0.0) (max sy 0.0) (max sz 0.0))))

(defn effective-mass-kg
  "Effective mass — explicit override if set, else volume x density."
  [part]
  (or (:mass-kg part)
      (* (aabb-volume-m3 part) (density-kg-m3 (:material part)))))

(defn effective-break-group [part]
  (or (:break-group part) (default-break-group (:kind part))))

(defn aabb-corners
  "8 AABB corners, used by the JBeam emitter as the part's mass-node
   scaffolding."
  [part]
  (xf/aabb-corners (aabb-min-v part) (aabb-max-v part)))

;; ---- VehicleAssembly derived accessors ----

(defn total-mass-kg
  "Aggregate mass — sum of `effective-mass-kg` over every part."
  [asm]
  (reduce + 0.0 (map effective-mass-kg (:parts asm))))

(defn parts-by-break-group
  "BeamNG-style \"break group -> parts\" rollup, same shape as
   `kami-vehicle` / `vehicle.models.sedan` break_group conventions.
   Returns a sorted seq of `[group [part ...]]` pairs."
  [asm]
  (->> (:parts asm)
       (group-by effective-break-group)
       (into (sorted-map))
       (seq)))

(defn validate
  "Validate the assembly. Refuses to emit JBeam / SBOM if this fails.
   Returns `[:ok nil]` or `[:error {:error <kind> ...}]`."
  [asm]
  (let [parts (:parts asm)]
    (or
     ;; duplicate ids
     (let [seen (atom #{})]
       (some (fn [p]
               (if (contains? @seen (:id p))
                 [:error {:error :duplicate-part :id (:id p)}]
                 (do (swap! seen conj (:id p)) nil)))
             parts))
     ;; provenance
     (some (fn [p]
             (when (or (empty? (get-in p [:source :sha256]))
                       (empty? (get-in p [:source :uri])))
               [:error {:error :missing-provenance :id (:id p)}]))
           parts)
     ;; parent fk
     (some (fn [p]
             (when-let [parent (:parent p)]
               (when-not (some #(= (:id %) parent) parts)
                 [:error {:error :unknown-parent :child (:id p) :parent parent}])))
           parts)
     ;; hardpoint fk
     (some (fn [hp]
             (cond
               (not (some #(= (:id %) (:from-part hp)) parts))
               [:error {:error :unknown-hardpoint-part :part (:from-part hp)}]
               (not (some #(= (:id %) (:to-part hp)) parts))
               [:error {:error :unknown-hardpoint-part :part (:to-part hp)}]))
           (:hardpoints asm))
     [:ok nil])))
