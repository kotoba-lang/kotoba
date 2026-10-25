(ns cad-import.ingest.gltf
  "glTF 2.0 -> VehicleAssembly ingest.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Ported 1:1 from the
   original `src/ingest/gltf.rs`.

   The original Rust adapter parsed a raw glTF JSON *string* via
   `serde_json`. This port has no JSON dependency (zero-dependency
   requirement, ADR-2607010930) and instead consumes an
   already-parsed glTF document as a plain Clojure map with **string**
   keys, spelled exactly as the glTF 2.0 spec + the etzhayyim `extras`
   annotation convention below — i.e. the direct result of
   `(clojure.data.json/read-str json-text)` (default string keys, no
   `:key-fn`). Callers with a raw JSON string parse it with whatever
   JSON library they already depend on and pass the resulting map to
   `from-gltf-map`.

   Pure-Clojure subset reader. We only consume what the part graph
   needs:

   1. Scene -> root nodes
   2. Node hierarchy + per-node TRS (translation / rotation / scale or
      matrix) — accumulated to a world transform per node
   3. Mesh primitive POSITION accessor `min` / `max` (glTF spec mandates
      these on the POSITION accessor) — used to derive the per-part AABB
      without ever loading vertex data
   4. `extras` block on each node + on the asset — picks up the etzhayyim
      annotation that says \"this node *is* a VehiclePart, and here is
      its kind / material / supplier / source\"

   Annotation contract (glTF `extras`), unchanged from the original:

   ```jsonc
   // Node-level — each annotated node becomes a VehiclePart
   \"extras\": {
     \"gftd_part\": {
       \"id\": \"chassis\", \"display_name\": \"Chassis main rail\",
       \"kind\": \"chassis\", \"material\": \"steel-hss\",
       \"mass_kg\": 220.0, \"parent\": \"...\", \"break_group\": 1,
       \"supplier\": { \"name\": \"...\", \"cpe\": \"...\", \"mpn\": \"...\" },
       \"source\": { \"uri\": \"...\", \"sha256\": \"...\", \"license\": \"MIT\" },
       \"revision\": \"1.0.0\"
     }
   }

   // Scene-level — list of inter-part hardpoints
   \"scenes[0].extras.gftd_hardpoints\": [
     { \"id\": \"hp_hood\", \"from\": \"chassis\", \"to\": \"hood\",
       \"position\": [0,0.7,1.4], \"kind\": \"hinge\" }
   ]

   // Asset-level — vehicle-wide source + license + revision
   \"asset.extras.gftd_vehicle\": {
     \"id\": \"miata-na-1989\", \"display_name\": \"...\", \"revision\": \"1.0.0\",
     \"source\": { \"uri\": \"...\", \"sha256\": \"...\", \"license\": \"MIT\" }
   }
   ```

   Nodes without `gftd_part` are skipped — they're typically render-only
   decoration. The caller can opt every mesh node in by passing
   `{:auto-part-kind [kind material]}` in `opts` to fall back to a
   default `PartKind` and material when annotations are missing."
  (:require [cad-import.part :as part]
            [cad-import.xform :as xf]))

(defn default-ingest-options [] {:auto-part-kind nil :scene-index nil})

;; ── parse helpers ───────────────────────────────────────────────────

(defn- kind-from-str [s]
  (case s
    "chassis" [:ok :chassis]
    "body" [:ok :body]
    "window" [:ok :window]
    "powertrain" [:ok :powertrain]
    "suspension" [:ok :suspension]
    "wheel" [:ok :wheel]
    "brake" [:ok :brake]
    "interior" [:ok :interior]
    "electrical" [:ok :electrical]
    "fluid" [:ok :fluid]
    "trim" [:ok :trim]
    [:error {:error :unknown-kind :detail s}]))

(defn- material-from-str [s]
  (case s
    "steel-hss" [:ok :steel-hss]
    "steel-mild" [:ok :steel-mild]
    "aluminium-cast" [:ok :aluminium-cast]
    "aluminium-sheet" [:ok :aluminium-sheet]
    "glass" [:ok :glass]
    "rubber" [:ok :rubber]
    "plastic" [:ok :plastic]
    "lithium-ion" [:ok :li-ion]
    "composite" [:ok :composite]
    "other" [:ok :other]
    [:error {:error :unknown-material :detail s}]))

(defn- hardpoint-kind-from-str [s]
  (case s
    "bolt" [:ok :bolt]
    "weld" [:ok :weld]
    "hinge" [:ok :hinge]
    "latch" [:ok :latch]
    "press" [:ok :press]
    "adhesive" [:ok :adhesive]
    [:error {:error :unknown-hardpoint-kind :detail s}]))

(defn- kind-label [k]
  (case k :chassis "chassis" :body "body" :window "window" :powertrain "powertrain"
    :suspension "suspension" :wheel "wheel" :brake "brake" :interior "interior"
    :electrical "electrical" :fluid "fluid" :trim "trim"))

(defn- material-label [m]
  (case m :steel-hss "steel-hss" :steel-mild "steel-mild" :aluminium-cast "aluminium-cast"
    :aluminium-sheet "aluminium-sheet" :glass "glass" :rubber "rubber" :plastic "plastic"
    :li-ion "lithium-ion" :composite "composite" :other "other"))

(defn- node-local-transform [node]
  (if-let [m (get node "matrix")]
    ;; column-major 16-float glTF matrix -> {:linear 3x3 :translation v3}
    (let [m (vec m)]
      {:linear [[(nth m 0) (nth m 4) (nth m 8)]
                [(nth m 1) (nth m 5) (nth m 9)]
                [(nth m 2) (nth m 6) (nth m 10)]]
       :translation [(nth m 12) (nth m 13) (nth m 14)]})
    (let [t (get node "translation" [0.0 0.0 0.0])
          r (get node "rotation" [0.0 0.0 0.0 1.0])
          s (get node "scale" [1.0 1.0 1.0])]
      (xf/trs->affine s r t))))

(defn- mesh-local-aabb [doc mesh-idx]
  (let [meshes (get doc "meshes" [])]
    (if (>= mesh-idx (count meshes))
      [:error {:error :bad-mesh-index :detail mesh-idx}]
      (let [mesh (nth meshes mesh-idx)
            mesh-name (get mesh "name" "")
            accessors (get doc "accessors" [])]
        (loop [prims (get mesh "primitives" [])
               lo xf/v3-inf hi xf/v3-neg-inf]
          (if (empty? prims)
            (if (== (first lo) ##Inf)
              [:error {:error :missing-accessor-bounds :mesh mesh-name}]
              [:ok [lo hi]])
            (let [prim (first prims)
                  acc-idx (get-in prim ["attributes" "POSITION"])]
              (if (nil? acc-idx)
                (recur (rest prims) lo hi)
                (if (>= acc-idx (count accessors))
                  [:error {:error :bad-accessor :detail acc-idx}]
                  (let [acc (nth accessors acc-idx)
                        mn (get acc "min") mx (get acc "max")]
                    (if (or (nil? mn) (nil? mx) (< (count mn) 3) (< (count mx) 3))
                      [:error {:error :missing-accessor-bounds :mesh mesh-name}]
                      (recur (rest prims)
                             (xf/v3-min lo [(nth mn 0) (nth mn 1) (nth mn 2)])
                             (xf/v3-max hi [(nth mx 0) (nth mx 1) (nth mx 2)])))))))))))))

;; ── walk ────────────────────────────────────────────────────────────

(declare walk-children)

(defn- gftd-part->annotation
  [gp]
  {:id (get gp "id")
   :display-name (get gp "display_name")
   :kind (get gp "kind")
   :material (get gp "material")
   :mass-kg (when-let [m (get gp "mass_kg")] (double m))
   :parent (get gp "parent")
   :break-group (get gp "break_group")
   :supplier (when-let [s (get gp "supplier")]
               {:name (get s "name" "") :cpe (get s "cpe" "") :mpn (get s "mpn" "")})
   :source (when-let [s (get gp "source")]
             {:uri (get s "uri") :sha256 (get s "sha256") :license (get s "license")})
   :revision (get gp "revision")})

(defn- walk-node [ctx node-idx parent-world parent-part-id]
  (let [nodes (:doc-nodes ctx)]
    (if (>= node-idx (count nodes))
      [:error {:error :bad-node-index :detail node-idx}]
      (let [node (nth nodes node-idx)
            world (xf/compose-affine parent-world (node-local-transform node))
            gp (get-in node ["extras" "gftd_part"])
            auto (:auto-part-kind (:options ctx))
            mesh-idx (get node "mesh")]
        (let [part-info
              (cond
                gp
                (if (nil? mesh-idx)
                  [:error {:error :part-without-mesh :node-idx node-idx :name (get node "name" "")}]
                  [:ok [(gftd-part->annotation gp) mesh-idx]])

                (and auto mesh-idx)
                (let [[auto-kind auto-mat] auto
                      auto-id (get node "name" (str "node_" node-idx))]
                  [:ok [{:id auto-id :display-name (get node "name") :kind (kind-label auto-kind)
                         :material (material-label auto-mat) :mass-kg nil :parent nil
                         :break-group nil :supplier nil :source nil :revision nil}
                        mesh-idx]])

                :else [:ok nil])]
          (if (= (first part-info) :error)
            part-info
            (let [info (second part-info)]
              (if (nil? info)
                (walk-children ctx (get node "children" []) world parent-part-id)
                (let [[ann mesh-idx] info]
                  (let [[status aabb-or-err] (mesh-local-aabb (:doc ctx) mesh-idx)]
                    (if (= status :error)
                      [:error aabb-or-err]
                      (let [[lo hi] aabb-or-err
                            local-corners (xf/aabb-corners lo hi)
                            [wlo whi] (xf/world-aabb-of-local-corners world local-corners)
                            [kstat kind] (kind-from-str (:kind ann))]
                        (if (= kstat :error)
                          [:error kind]
                          (let [[mstat material] (material-from-str (:material ann))]
                            (if (= mstat :error)
                              [:error material]
                              (let [id (:id ann)
                                    part-map {:id id
                                               :display-name (or (:display-name ann) id)
                                               :kind kind
                                               :material material
                                               :aabb-min wlo
                                               :aabb-max whi
                                               :mass-kg (:mass-kg ann)
                                               :parent (or (:parent ann) parent-part-id)
                                               :break-group (:break-group ann)
                                               :source (or (:source ann) (:asm-source ctx))
                                               :supplier (or (:supplier ann) part/default-supplier)
                                               :revision (or (:revision ann) (:asm-revision ctx))}]
                                (swap! (:parts-atom ctx) conj part-map)
                                (walk-children ctx (get node "children" []) world id)))))))))))))))))

(defn- walk-children [ctx children world parent-part-id]
  (loop [cs children]
    (if (empty? cs)
      [:ok nil]
      (let [result (walk-node ctx (first cs) world parent-part-id)]
        (if (= (first result) :error)
          result
          (recur (rest cs)))))))

;; ── public API ──────────────────────────────────────────────────────

(defn from-gltf-map
  "Parse an already-parsed glTF 2.0 document (a Clojure map with
   string keys, see namespace docstring) and produce a validated
   `VehicleAssembly`. Returns `[:ok assembly]` or `[:error error-map]`."
  ([doc] (from-gltf-map doc (default-ingest-options)))
  ([doc opts]
   (let [vehicle-extras (get-in doc ["asset" "extras" "gftd_vehicle"])]
     (if (nil? vehicle-extras)
       [:error {:error :missing-vehicle-annotation}]
       (let [vsource {:uri (get-in vehicle-extras ["source" "uri"])
                       :sha256 (get-in vehicle-extras ["source" "sha256"])
                       :license (get-in vehicle-extras ["source" "license"])}
             scene-idx (or (:scene-index opts) (get doc "scene") 0)
             scenes (get doc "scenes" [])]
         (if (>= scene-idx (count scenes))
           [:error {:error :bad-scene :detail scene-idx}]
           (let [scene (nth scenes scene-idx)
                 asm-revision (get vehicle-extras "revision" "0.1.0")
                 parts-atom (atom [])
                 ctx {:doc doc :doc-nodes (get doc "nodes" [])
                      :options opts :asm-source vsource :asm-revision asm-revision
                      :parts-atom parts-atom}
                 world0 (xf/affine-identity)]
             (let [walk-result (walk-children ctx (get scene "nodes" []) world0 nil)]
               (if (= (first walk-result) :error)
                 walk-result
                 (let [asm0 (part/new-assembly (get vehicle-extras "id") vsource)
                       asm (-> asm0
                               (assoc :display-name (get vehicle-extras "display_name" (get vehicle-extras "id")))
                               (assoc :revision asm-revision)
                               (assoc :parts @parts-atom))
                       hp-entries (get-in scene ["extras" "gftd_hardpoints"] [])
                       hp-results (mapv (fn [hp]
                                           (let [[status kind] (hardpoint-kind-from-str (get hp "kind"))]
                                             (if (= status :error)
                                               [:error kind]
                                               [:ok {:id (get hp "id") :from-part (get hp "from")
                                                     :to-part (get hp "to") :position (vec (get hp "position"))
                                                     :kind kind}])))
                                         hp-entries)
                       hp-error (first (filter #(= (first %) :error) hp-results))]
                   (if hp-error
                     [:error (second hp-error)]
                     (let [asm (reduce (fn [a [_ hp]] (part/add-hardpoint a hp)) asm hp-results)
                           [vstat verr] (part/validate asm)]
                       (if (= vstat :error)
                         [:error verr]
                         [:ok asm])))))))))))))
