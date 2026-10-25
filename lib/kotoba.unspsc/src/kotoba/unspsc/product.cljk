(ns kotoba.unspsc.product
  "Portable UNSPSC-keyed product digital twin: SBOM + CAD features + physics + 3D IR.

  Purpose
  -------
  Give trade items a **shared, pure EDN contract** so cloud-itonami (procurement /
  open-business / PLM lanes) and network-isekai (CAD mode, render-IR viewport)
  can consume the same product description without re-deriving geometry or BOM.

  What this is
  ------------
  - **Product-level** data keyed by 8-digit UNSPSC commodity (+ 2-digit segment).
  - **SBOM**: coarse component tree (CycloneDX-shaped maps; not a full SPDX dump).
  - **CAD**: sketch-less feature tree matching network-isekai `isekai.ui.cad`
    (`:feat/kind` extrude|revolve|boss + pose/size) — kami-cad BREP is the documented
    high-fidelity swap behind the same document.
  - **Physics**: mass, bbox, density, material class (CAD/CAE friendly units: mm, kg).
  - **3D**: render-IR instances (box/cylinder proxies) for WebGPU / isekai viewport.

  What this is NOT
  ----------------
  - Not the etzhayyim 18k commodity table (classification SSoT stays there).
  - Not a full STEP/glTF binary store (binaries stay annex/B2; here is the **descriptor**).
  - Not kami-engine ECS — only data + pure projectors."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────── units / helpers ─────────────────────────

(defn unspsc-segment
  "8-digit (or longer) commodity → 2-digit segment string, or nil."
  [code]
  (when-let [d (some-> code str (str/replace #"[^0-9]" "") not-empty)]
    (when (>= (count d) 2) (subs d 0 2))))

(defn- vol-mm3
  "Axis-aligned volume proxy (mm³) from feature dims."
  [{:keys [w h r] :as _f}]
  (if r
    (* Math/PI r r (or h 1.0))
    (* (or w 1.0) (or w 1.0) (or h 1.0))))

;; ───────────────────────── constructors ─────────────────────────

(defn component
  "One SBOM line. Required: :id :name. Optional: :unspsc :qty :unit :mass-kg
  :material :role (:assembly|:part|:material|:packaging|:software)."
  [{:keys [id name unspsc qty unit mass-kg material role supplier]
    :or {qty 1.0 unit :each role :part}}]
  (cond-> {:component/id (str id)
           :component/name (str name)
           :component/qty (double qty)
           :component/unit unit
           :component/role role}
    unspsc (assoc :component/unspsc (str unspsc))
    mass-kg (assoc :component/mass-kg (double mass-kg))
    material (assoc :component/material material)
    supplier (assoc :component/supplier (str supplier))))

(defn cad-feature
  "One CAD feature (isekai.ui.cad-compatible keys, namespaced for pure maps).
  kind ∈ #{:extrude :revolve :boss}."
  [{:keys [id kind order name x y z w h r]
    :or {x 0 y 0 z 0 order 0}}]
  (cond-> {:feat/id (str id)
           :feat/kind kind
           :feat/order (long order)
           :feat/name (str (or name id))
           :feat/x (double x)
           :feat/y (double y)
           :feat/z (double z)}
    w (assoc :feat/w (double w))
    h (assoc :feat/h (double h))
    r (assoc :feat/r (double r))))

(defn make-physics
  "Physical envelope. Lengths mm, mass kg, density g/cm³."
  [{:keys [mass-kg bbox-mm density-g-cm3 center-of-mass-mm material-class]
    :or {bbox-mm [0.0 0.0 0.0] density-g-cm3 1.0 material-class :mixed}}]
  (let [[bx by bz] bbox-mm]
    {:physics/mass-kg (double (or mass-kg 0.0))
     :physics/bbox-mm [(double bx) (double by) (double bz)]
     :physics/density-g-cm3 (double density-g-cm3)
     :physics/material-class material-class
     :physics/center-of-mass-mm (or center-of-mass-mm
                                    [(/ (double bx) 2.0)
                                     (/ (double by) 2.0)
                                     (/ (double bz) 2.0)])}))

(defn product
  "UNSPSC product digital twin.

  Required: :id :name :unspsc
  Optional: :rev :brand :components :features :physics :gltf-ref :notes :sector
            :aliases (seed/GTIN product ids that should resolve as this twin)"
  [{:keys [id name unspsc rev brand components features physics gltf-ref notes sector aliases]
    :or {rev "A" components [] features [] aliases []}}]
  (let [seg (unspsc-segment unspsc)
        comps (mapv #(if (map? %) (if (:component/id %) % (component %)) %) components)
        feats (mapv #(if (map? %) (if (:feat/id %) % (cad-feature %)) %) features)
        phys (cond
               (nil? physics) (make-physics {})
               (:physics/mass-kg physics) physics
               :else (make-physics physics))]
    (cond-> {:product/id (str id)
             :product/name (str name)
             :product/unspsc (str unspsc)
             :product/unspsc-segment seg
             :product/rev (str rev)
             :product/sbom comps
             :product/cad-features (vec (sort-by :feat/order feats))
             :product/physics phys
             :product/open-business-id (when seg (str "cloud-itonami-unspsc-" seg))
             :product/aliases (mapv str aliases)}
      brand (assoc :product/brand (str brand))
      sector (assoc :product/sector sector)
      gltf-ref (assoc :product/gltf-ref gltf-ref)
      notes (assoc :product/notes notes))))

;; ───────────────────────── SBOM projectors ─────────────────────────

(defn sbom-lines
  "Flat SBOM lines from a product twin."
  [prod]
  (vec (:product/sbom prod)))

(defn sbom-by-role
  "Group SBOM by :component/role."
  [prod]
  (->> (sbom-lines prod)
       (group-by :component/role)
       (into (sorted-map))))

(defn sbom-cyclonedx-lite
  "CycloneDX-shaped map (not a full 1.5 serialize — enough for isekai/doctor).
  Components carry bom-ref, type, name, optional purl-ish unspsc property."
  [prod]
  {:bomFormat "CycloneDX"
   :specVersion "1.5"
   :version 1
   :metadata {:component {:type "device"
                          :name (:product/name prod)
                          :version (:product/rev prod)
                          :bom-ref (:product/id prod)
                          :properties [{:name "unspsc:commodity"
                                        :value (:product/unspsc prod)}
                                       {:name "unspsc:segment"
                                        :value (str (:product/unspsc-segment prod))}]}}
   :components
   (mapv (fn [c]
           (cond-> {:type (case (:component/role c)
                            :software "library"
                            :material "material"
                            :packaging "container"
                            "device")
                    :name (:component/name c)
                    :bom-ref (:component/id c)
                    :properties (cond-> [{:name "qty" :value (str (:component/qty c))}]
                                  (:component/unspsc c)
                                  (conj {:name "unspsc:commodity"
                                         :value (:component/unspsc c)})
                                  (:component/mass-kg c)
                                  (conj {:name "mass-kg"
                                         :value (str (:component/mass-kg c))}))}
             (:component/supplier c)
             (assoc :supplier {:name (:component/supplier c)})))
         (sbom-lines prod))})

(defn sbom-feature-summary
  "isekai.ui.cad/sbom-compatible summary over CAD features (kind/qty/vol)."
  [prod]
  (->> (:product/cad-features prod)
       (group-by :feat/kind)
       (map (fn [[kind fs]]
              {:kind kind
               :qty  (count fs)
               :vol  (reduce + 0.0
                             (map (fn [f]
                                    (vol-mm3 {:w (:feat/w f)
                                              :h (:feat/h f)
                                              :r (:feat/r f)}))
                                  fs))}))
       (sort-by :kind)
       vec))

;; ───────────────────────── CAD / 3D projectors ─────────────────────────

(defn cad-features-isekai
  "Feature maps ready for DataScript / isekai.ui.cad (negative temp eids)."
  [prod]
  (mapv (fn [f i]
          (cond-> {:db/id (- (inc i))
                   :feat/kind (:feat/kind f)
                   :feat/order (:feat/order f)
                   :feat/name (:feat/name f)
                   :feat/x (:feat/x f)
                   :feat/y (:feat/y f)
                   :feat/z (:feat/z f)}
            (:feat/w f) (assoc :feat/w (:feat/w f))
            (:feat/h f) (assoc :feat/h (:feat/h f))
            (:feat/r f) (assoc :feat/r (:feat/r f))))
        (:product/cad-features prod)
        (range)))

(defn- feat->inst [f selected-id]
  (let [sel? (and selected-id (= (:feat/id f) selected-id))
        c (if sel? [0.88 0.66 0.23] [0.62 0.66 0.72])
        base {:pos [(:feat/x f) (:feat/z f) (:feat/y f)]
              :color c :metallic 0.35 :roughness 0.4
              :meta {:feat-id (:feat/id f)
                     :name (:feat/name f)
                     :unspsc-segment (:product/unspsc-segment f)}}]
    (case (:feat/kind f)
      :revolve (assoc base :geo :cylinder
                      :size [(or (:feat/r f) 20.0) (or (:feat/h f) 40.0)])
      (assoc base :geo :box
             :size [(or (:feat/w f) 60.0) (or (:feat/h f) 40.0)]))))

(defn render-ir
  "Render-IR for WebGPU / isekai viewport (same shape as isekai.ui.cad/part->ir)."
  ([prod] (render-ir prod nil))
  ([prod selected-feat-id]
   (let [feats (:product/cad-features prod)
         insts (mapv #(feat->inst % selected-feat-id) feats)
         [sx sz] (reduce (fn [[ax az] {:keys [pos]}]
                           [(+ ax (nth pos 0)) (+ az (nth pos 2))])
                         [0.0 0.0] insts)
         n (max 1 (count insts))
         cx (/ sx n) cz (/ sz n)
         bbox (:physics/bbox-mm (:product/physics prod) [100 100 100])
         far (max 6000.0 (* 20.0 (apply max bbox)))]
     {:globals {:sky {:horizon [0.93 0.92 0.86]
                      :sun-dir [-0.4 -0.85 -0.35]
                      :sun [1 0.96 0.85]}
                :eye [(+ cx 130) 150 (+ cz 200)]
                :target [cx 20 cz]
                :fov 48
                :far far}
      :instances insts
      :product {:id (:product/id prod)
                :unspsc (:product/unspsc prod)
                :segment (:product/unspsc-segment prod)
                :gltf-ref (:product/gltf-ref prod)}})))

(defn gltf-descriptor
  "Logical glTF/GLB descriptor (no binary). Consumers resolve :uri via annex/CDN."
  [prod]
  {:asset {:version "2.0" :generator "kotoba.unspsc.product"}
   :extensionsUsed ["KOTOBA_unspsc_product"]
   :extensions
   {:KOTOBA_unspsc_product
    {:productId (:product/id prod)
     :unspsc (:product/unspsc prod)
     :segment (:product/unspsc-segment prod)
     :physics (:product/physics prod)
     :sbomRef (str (:product/id prod) "#sbom")}}
   :nodes (mapv (fn [f]
                  {:name (:feat/name f)
                   :translation [(:feat/x f) (:feat/y f) (:feat/z f)]
                   :extras {:feat/kind (:feat/kind f)
                            :feat/w (:feat/w f)
                            :feat/h (:feat/h f)
                            :feat/r (:feat/r f)}})
                (:product/cad-features prod))
   :uri (:product/gltf-ref prod)})

;; ───────────────────────── cloud-itonami projectors ─────────────────────────

(defn twin-brand-owner-id
  "Kabuto-valid party id for a twin's representative brand-owner
  (`org.corp.<cc>.…` — required by product-party/valid-party-id?)."
  [prod]
  (let [seg (or (:product/unspsc-segment prod) "00")]
    (str "org.corp.jp.unspsc-twin-" seg)))

(defn ->product-party-entity
  "Map twin → product-party / uchiwake-shaped product entity.
  When `with-brand-owner?` (default true), sets `:product/brand-owner` so
  bulk `import-entities` creates a brand-owner edge without interactive gate."
  ([prod] (->product-party-entity prod true))
  ([prod with-brand-owner?]
   (cond-> {:product/id (:product/id prod)
            :product/name (:product/name prod)
            :product/unspsc (:product/unspsc prod)
            :product/sourcing :representative}
     (:product/brand prod) (assoc :product/brand (:product/brand prod))
     (:product/sector prod) (assoc :product/sector (:product/sector prod))
     with-brand-owner?
     (assoc :product/brand-owner (twin-brand-owner-id prod)))))

(defn ->plm-bom-props
  "Map twin → cloud-itonami.smartphone/bom-artifact style props map."
  [prod]
  {:model (:product/id prod)
   :rev (:product/rev prod)
   :unspsc (:product/unspsc prod)
   :segment (:product/unspsc-segment prod)
   :physics (:product/physics prod)
   :components
   (mapv (fn [c]
           {:item (:component/id c)
            :name (:component/name c)
            :qty (:component/qty c)
            :unspsc (:component/unspsc c)
            :ref (:component/id c)})
         (sbom-lines prod))})

(defn open-business-hints
  "Routing hints aligned with cloud-itonami.product-party/open-business-hints shape."
  [prod]
  (let [seg (:product/unspsc-segment prod)]
    {:product (:product/id prod)
     :unspsc (:product/unspsc prod)
     :unspsc-segment seg
     :blueprint-hints
     (cond-> {:unspsc-blueprint (:product/open-business-id prod)
              :has-cad? (boolean (seq (:product/cad-features prod)))
              :has-sbom? (boolean (seq (:product/sbom prod)))
              :has-physics? (boolean (:product/physics prod))}
       seg (assoc :unspsc-segment seg))}))

;; ───────────────────────── catalog (representative twins) ─────────────────────────

(def catalog
  "Representative UNSPSC product twins for open-business + isekai demos.
   Sourcing is :representative — not manufacturer confidential design data."
  [(product
    {:id "prod.smartphone-flagship"
     :name "Flagship smartphone"
     :unspsc "43191501"
     :brand "demo-brand"
     :sector :electronics
     :gltf-ref "asset://unspsc/43/smartphone-flagship.glb"
     :physics {:mass-kg 0.22 :bbox-mm [75 160 8] :density-g-cm3 2.4
               :material-class :electronics}
     :components
     [(component {:id "part.soc" :name "Application SoC" :unspsc "32101604"
                  :qty 1 :mass-kg 0.004 :material :silicon :role :part})
      (component {:id "part.display-oled" :name "OLED display" :unspsc "32121509"
                  :qty 1 :mass-kg 0.03 :material :glass :role :part})
      (component {:id "part.battery" :name "Li-ion pack" :unspsc "26111710"
                  :qty 1 :mass-kg 0.05 :material :li-ion :role :part})
      (component {:id "part.frame" :name "Aluminum frame" :unspsc "30171500"
                  :qty 1 :mass-kg 0.04 :material :aluminum :role :assembly})
      (component {:id "sw.modem-fw" :name "Baseband firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 75 :h 8})
      (cad-feature {:id "screen" :kind :boss :order 1 :name "screen"
                    :x 0 :y 0 :z 4 :w 70 :h 2})
      (cad-feature {:id "camera-bump" :kind :revolve :order 2 :name "camera"
                    :x -20 :y 50 :z 8 :r 8 :h 4})]})

   (product
    {:id "prod.ai-gpu-module"
     :name "AI GPU module"
     :unspsc "43201401"
     :brand "demo-silicon"
     :sector :electronics
     :gltf-ref "asset://unspsc/43/ai-gpu-module.glb"
     :physics {:mass-kg 1.4 :bbox-mm [270 110 40] :density-g-cm3 3.1
               :material-class :electronics}
     :components
     [(component {:id "part.gpu-die" :name "GPU die" :unspsc "32101604"
                  :qty 1 :mass-kg 0.02 :material :silicon :role :part
                  :supplier "org.corp.tw.tsmc"})
      (component {:id "part.hbm" :name "HBM stack" :unspsc "32101602"
                  :qty 4 :mass-kg 0.01 :material :silicon :role :part})
      (component {:id "part.pcb" :name "Module PCB" :unspsc "32101500"
                  :qty 1 :mass-kg 0.2 :material :fr4 :role :assembly})
      (component {:id "part.cooler" :name "Vapor chamber" :unspsc "40101800"
                  :qty 1 :mass-kg 0.35 :material :copper :role :part})]
     :features
     [(cad-feature {:id "pcb" :kind :extrude :order 0 :name "pcb"
                    :x 0 :y 0 :z 0 :w 270 :h 3})
      (cad-feature {:id "die" :kind :boss :order 1 :name "die"
                    :x 0 :y 0 :z 3 :w 40 :h 4})
      (cad-feature {:id "cooler" :kind :revolve :order 2 :name "cooler"
                    :x 0 :y 0 :z 8 :r 50 :h 25})]})

   (product
    {:id "prod.engine-blade-set"
     :name "Turbine engine blade set"
     :unspsc "25101504"
     :sector :aerospace
     :gltf-ref "asset://unspsc/25/engine-blade-set.glb"
     :physics {:mass-kg 12.5 :bbox-mm [400 400 600] :density-g-cm3 8.2
               :material-class :superalloy}
     :components
     [(component {:id "part.blade" :name "HPT blade" :unspsc "25101504"
                  :qty 36 :mass-kg 0.28 :material :ni-superalloy :role :part
                  :supplier "sup-aero-blades"})
      (component {:id "part.disk" :name "Turbine disk" :unspsc "25101500"
                  :qty 1 :mass-kg 4.5 :material :ni-superalloy :role :assembly})
      (component {:id "part.coating" :name "TBC coating" :unspsc "31200000"
                  :qty 1 :mass-kg 0.1 :material :ceramic :role :material})]
     :features
     [(cad-feature {:id "disk" :kind :revolve :order 0 :name "disk"
                    :x 0 :y 0 :z 0 :r 180 :h 40})
      (cad-feature {:id "blade-ring" :kind :extrude :order 1 :name "blade-span"
                    :x 0 :y 0 :z 40 :w 360 :h 200})]})

   (product
    {:id "prod.ev-battery-pack"
     :name "EV battery pack"
     :unspsc "26111701"
     :sector :energy-storage
     :gltf-ref "asset://unspsc/26/ev-battery-pack.glb"
     :physics {:mass-kg 450.0 :bbox-mm [2100 1500 150] :density-g-cm3 1.8
               :material-class :energy-storage}
     :components
     [(component {:id "part.module" :name "Cell module" :unspsc "26111710"
                  :qty 16 :mass-kg 22.0 :material :li-ion :role :part})
      (component {:id "part.bms" :name "BMS controller" :unspsc "32151700"
                  :qty 1 :mass-kg 1.2 :material :electronics :role :part})
      (component {:id "part.tray" :name "Aluminum tray" :unspsc "30171500"
                  :qty 1 :mass-kg 40.0 :material :aluminum :role :assembly})]
     :features
     [(cad-feature {:id "tray" :kind :extrude :order 0 :name "tray"
                    :x 0 :y 0 :z 0 :w 2100 :h 40})
      (cad-feature {:id "modules" :kind :boss :order 1 :name "modules"
                    :x 0 :y 0 :z 40 :w 1900 :h 90})]})

   (product
    {:id "prod.service-tool-kit"
     :name "Industrial service tool kit"
     :unspsc "27111700"
     :sector :tools
     :gltf-ref "asset://unspsc/27/service-tool-kit.glb"
     :physics {:mass-kg 3.2 :bbox-mm [400 250 80] :density-g-cm3 2.0
               :material-class :steel}
     :components
     [(component {:id "part.wrench" :name "Combination wrench" :unspsc "27111700"
                  :qty 8 :mass-kg 0.15 :material :steel :role :part})
      (component {:id "part.socket" :name "Socket set 1/2in" :unspsc "27111700"
                  :qty 12 :mass-kg 0.08 :material :steel :role :part})
      (component {:id "part.torque" :name "Torque wrench" :unspsc "27111700"
                  :qty 1 :mass-kg 0.9 :material :steel :role :part})
      (component {:id "part.case" :name "Tool case" :unspsc "24120000"
                  :qty 1 :mass-kg 1.0 :material :polymer :role :packaging})
      (component {:id "sw.tool-inv" :name "Tool inventory firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "case" :kind :extrude :order 0 :name "case"
                    :x 0 :y 0 :z 0 :w 400 :h 80})
      (cad-feature {:id "handle" :kind :revolve :order 1 :name "handle"
                    :x 0 :y 120 :z 80 :r 12 :h 30})
      (cad-feature {:id "latch" :kind :boss :order 2 :name "latch"
                    :x 180 :y 0 :z 40 :w 30 :h 15})]})

   ;; Curated open-business blueprint segments 10 / 39 / 73 (complete the five)
   (product
    {:id "prod.hive-sensor-array"
     :name "Apiary hive sensor array"
     :unspsc "10151500"
     :sector :agriculture
     :gltf-ref "asset://unspsc/10/hive-sensor-array.glb"
     :physics {:mass-kg 1.8 :bbox-mm [200 200 80] :density-g-cm3 1.2
               :material-class :electronics}
     :components
     [(component {:id "part.th-sensor" :name "Temp/humidity sensor" :unspsc "41111900"
                  :qty 4 :mass-kg 0.02 :material :electronics :role :part})
      (component {:id "part.radio" :name "LoRa radio" :unspsc "43191500"
                  :qty 1 :mass-kg 0.05 :material :electronics :role :part})
      (component {:id "part.housing" :name "Weather housing" :unspsc "24112400"
                  :qty 1 :mass-kg 0.4 :material :polymer :role :assembly})]
     :features
     [(cad-feature {:id "base" :kind :extrude :order 0 :name "base"
                    :x 0 :y 0 :z 0 :w 200 :h 20})
      (cad-feature {:id "mast" :kind :revolve :order 1 :name "mast"
                    :x 0 :y 0 :z 20 :r 15 :h 50})]})

   (product
    {:id "prod.led-panel-driver"
     :name "LED panel driver module"
     :unspsc "39111500"
     :sector :electrical
     :gltf-ref "asset://unspsc/39/led-panel-driver.glb"
     :physics {:mass-kg 0.65 :bbox-mm [180 90 40] :density-g-cm3 2.1
               :material-class :electronics}
     :components
     [(component {:id "part.psu" :name "Constant-current PSU" :unspsc "39121000"
                  :qty 1 :mass-kg 0.25 :material :electronics :role :part})
      (component {:id "part.pcb-drv" :name "Driver PCB" :unspsc "32101500"
                  :qty 1 :mass-kg 0.08 :material :fr4 :role :assembly})
      (component {:id "part.heatsink" :name "Aluminum heatsink" :unspsc "40101800"
                  :qty 1 :mass-kg 0.2 :material :aluminum :role :part})]
     :features
     [(cad-feature {:id "enclosure" :kind :extrude :order 0 :name "enclosure"
                    :x 0 :y 0 :z 0 :w 180 :h 40})
      (cad-feature {:id "heatsink" :kind :boss :order 1 :name "heatsink"
                    :x 0 :y 0 :z 40 :w 160 :h 25})]})

   (product
    {:id "prod.line-cert-kit"
     :name "Manufacturing line certification kit"
     :unspsc "73101500"
     :sector :industrial-services
     :gltf-ref "asset://unspsc/73/line-cert-kit.glb"
     :physics {:mass-kg 4.5 :bbox-mm [500 300 120] :density-g-cm3 1.5
               :material-class :mixed}
     :components
     [(component {:id "part.gauge" :name "Calibrated gauge block" :unspsc "41111600"
                  :qty 6 :mass-kg 0.3 :material :steel :role :part})
      (component {:id "part.logger" :name "Process logger" :unspsc "43211500"
                  :qty 1 :mass-kg 0.5 :material :electronics :role :part})
      (component {:id "part.case-cert" :name "Hard case" :unspsc "24120000"
                  :qty 1 :mass-kg 1.2 :material :polymer :role :packaging})
      (component {:id "sw.cert-fw" :name "Cert workflow firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "case" :kind :extrude :order 0 :name "case"
                    :x 0 :y 0 :z 0 :w 500 :h 120})
      (cad-feature {:id "logger" :kind :boss :order 1 :name "logger"
                    :x -80 :y 0 :z 120 :w 100 :h 30})]})

   ;; High-traffic :spec segments present in uchiwake seed / fixture graphs
   ;; (food 50, pharma 51, apparel 53) — SBOM/CAD twins so graph twin-segment
   ;; coverage can reach 1.0 without promoting registry maturity tiers.
   (product
    {:id "prod.beverage-can-330"
     :name "Carbonated soft drink 330ml can"
     :unspsc "50202301"
     :brand "demo-cola"
     :sector :food-beverage
     :aliases ["gtin.05449000000996"]
     :gltf-ref "asset://unspsc/50/beverage-can-330.glb"
     :physics {:mass-kg 0.35 :bbox-mm [66 66 115] :density-g-cm3 1.0
               :material-class :aluminum}
     :components
     [(component {:id "part.can-body" :name "Aluminum can body" :unspsc "24121500"
                  :qty 1 :mass-kg 0.013 :material :aluminum :role :packaging})
      (component {:id "part.syrup" :name "Beverage concentrate" :unspsc "50192400"
                  :qty 1 :mass-kg 0.04 :material :agricultural :role :material})
      (component {:id "part.end" :name "Stay-on tab end" :unspsc "24121500"
                  :qty 1 :mass-kg 0.003 :material :aluminum :role :part})]
     :features
     [(cad-feature {:id "body" :kind :revolve :order 0 :name "can-body"
                    :x 0 :y 0 :z 0 :r 33 :h 115})
      (cad-feature {:id "tab" :kind :boss :order 1 :name "tab"
                    :x 0 :y 0 :z 115 :w 20 :h 3})]})

   (product
    {:id "prod.paracetamol-500-twin"
     :name "Paracetamol 500mg tablet pack"
     :unspsc "51142003"
     :sector :pharma
     :aliases ["prod.paracetamol-500"]
     :gltf-ref "asset://unspsc/51/paracetamol-500.glb"
     :physics {:mass-kg 0.02 :bbox-mm [90 50 15] :density-g-cm3 0.8
               :material-class :pharma}
     :components
     [(component {:id "part.api" :name "Paracetamol API" :unspsc "51142000"
                  :qty 20 :mass-kg 0.0005 :material :chemical :role :material})
      (component {:id "part.blister" :name "Blister pack" :unspsc "24120000"
                  :qty 1 :mass-kg 0.008 :material :polymer :role :packaging})
      (component {:id "part.carton" :name "Carton" :unspsc "24121500"
                  :qty 1 :mass-kg 0.01 :material :paper :role :packaging})]
     :features
     [(cad-feature {:id "carton" :kind :extrude :order 0 :name "carton"
                    :x 0 :y 0 :z 0 :w 90 :h 15})
      (cad-feature {:id "blister" :kind :boss :order 1 :name "blister"
                    :x 0 :y 0 :z 8 :w 80 :h 5})]})

   (product
    {:id "prod.cotton-tee-basic"
     :name "Basic cotton T-shirt"
     :unspsc "53101500"
     :sector :apparel
     :gltf-ref "asset://unspsc/53/cotton-tee-basic.glb"
     :physics {:mass-kg 0.18 :bbox-mm [300 200 20] :density-g-cm3 0.3
               :material-class :textile}
     :components
     [(component {:id "part.fabric" :name "Cotton jersey" :unspsc "11151700"
                  :qty 1 :mass-kg 0.15 :material :cotton :role :material})
      (component {:id "part.thread" :name "Sewing thread" :unspsc "11151500"
                  :qty 1 :mass-kg 0.005 :material :cotton :role :material})
      (component {:id "part.label" :name "Care label" :unspsc "14111800"
                  :qty 1 :mass-kg 0.001 :material :paper :role :part})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body-panel"
                    :x 0 :y 0 :z 0 :w 300 :h 8})
      (cad-feature {:id "sleeve" :kind :boss :order 1 :name "sleeve"
                    :x 160 :y 0 :z 0 :w 80 :h 6})]})

   ;; Commodity-exact twins for seed products that previously only matched by segment
   (product
    {:id "prod.cotton-tshirt"
     :name "Cotton T-shirt (seed commodity)"
     :unspsc "53102516"
     :sector :apparel
     :gltf-ref "asset://unspsc/53/cotton-tshirt.glb"
     :physics {:mass-kg 0.19 :bbox-mm [310 210 20] :density-g-cm3 0.3
               :material-class :textile}
     :components
     [(component {:id "part.fabric-tee" :name "Cotton jersey body" :unspsc "11151700"
                  :qty 1 :mass-kg 0.16 :material :cotton :role :material})
      (component {:id "part.neck" :name "Rib neck band" :unspsc "11151700"
                  :qty 1 :mass-kg 0.01 :material :cotton :role :part})
      (component {:id "part.thread-tee" :name "Sewing thread" :unspsc "11151500"
                  :qty 1 :mass-kg 0.005 :material :cotton :role :material})
      (component {:id "part.polybag" :name "Poly bag" :unspsc "24121500"
                  :qty 1 :mass-kg 0.005 :material :polymer :role :packaging})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 310 :h 8})
      (cad-feature {:id "collar" :kind :revolve :order 1 :name "collar"
                    :x 0 :y 90 :z 8 :r 40 :h 6})
      (cad-feature {:id "sleeve" :kind :boss :order 2 :name "sleeve"
                    :x 160 :y 0 :z 0 :w 80 :h 6})]})

   (product
    {:id "prod.5g-radio"
     :name "5G radio unit"
     :unspsc "43222609"
     :sector :telecom
     :gltf-ref "asset://unspsc/43/5g-radio.glb"
     :physics {:mass-kg 8.5 :bbox-mm [400 300 150] :density-g-cm3 1.8
               :material-class :electronics}
     :components
     [(component {:id "part.rf" :name "RF front-end" :unspsc "32101500"
                  :qty 1 :mass-kg 1.2 :material :electronics :role :part})
      (component {:id "part.antenna" :name "Antenna array" :unspsc "43191500"
                  :qty 1 :mass-kg 2.0 :material :electronics :role :assembly})
      (component {:id "part.psu-radio" :name "Power module" :unspsc "39121000"
                  :qty 1 :mass-kg 1.5 :material :electronics :role :part})]
     :features
     [(cad-feature {:id "chassis" :kind :extrude :order 0 :name "chassis"
                    :x 0 :y 0 :z 0 :w 400 :h 150})
      (cad-feature {:id "antenna" :kind :boss :order 1 :name "antenna"
                    :x 0 :y 0 :z 150 :w 380 :h 40})]})

   (product
    {:id "prod.ev-vehicle"
     :name "Battery-electric passenger vehicle"
     :unspsc "25101503"
     :sector :automotive
     :gltf-ref "asset://unspsc/25/ev-vehicle.glb"
     :physics {:mass-kg 1800.0 :bbox-mm [4500 1800 1500] :density-g-cm3 0.15
               :material-class :mixed}
     :components
     [(component {:id "part.pack" :name "Traction pack" :unspsc "26111701"
                  :qty 1 :mass-kg 450 :material :li-ion :role :assembly})
      (component {:id "part.motor" :name "Drive motor" :unspsc "26101500"
                  :qty 1 :mass-kg 80 :material :steel :role :part})
      (component {:id "part.body-in-white" :name "BIW shell" :unspsc "25171500"
                  :qty 1 :mass-kg 350 :material :aluminum :role :assembly})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 4500 :h 1500})
      (cad-feature {:id "wheel" :kind :revolve :order 1 :name "wheel"
                    :x -1500 :y -700 :z 0 :r 350 :h 200})]})

   (product
    {:id "prod.aircraft-narrowbody"
     :name "Narrowbody commercial aircraft"
     :unspsc "25111500"
     :sector :aerospace
     :gltf-ref "asset://unspsc/25/aircraft-narrowbody.glb"
     :physics {:mass-kg 42000.0 :bbox-mm [38000 35000 12000] :density-g-cm3 0.05
               :material-class :superalloy}
     :components
     [(component {:id "part.fuselage" :name "Fuselage sections" :unspsc "25111500"
                  :qty 1 :mass-kg 12000 :material :aluminum :role :assembly})
      (component {:id "part.wing" :name "Wing box" :unspsc "25111500"
                  :qty 2 :mass-kg 4000 :material :composite :role :assembly})
      (component {:id "part.engine" :name "Turbofan" :unspsc "25101504"
                  :qty 2 :mass-kg 2500 :material :ni-superalloy :role :part})]
     :features
     [(cad-feature {:id "fuselage" :kind :revolve :order 0 :name "fuselage"
                    :x 0 :y 0 :z 0 :r 2000 :h 38000})
      (cad-feature {:id "wing" :kind :extrude :order 1 :name "wing"
                    :x 0 :y 0 :z 5000 :w 35000 :h 800})]})

   (product
    {:id "prod.chocolate-spread-jar"
     :name "Chocolate hazelnut spread jar"
     :unspsc "50161900"
     :sector :food-beverage
     :aliases ["gtin.03017620422003" "gtin.07613035044289"]
     :gltf-ref "asset://unspsc/50/chocolate-spread-jar.glb"
     :physics {:mass-kg 0.85 :bbox-mm [90 90 120] :density-g-cm3 1.1
               :material-class :glass}
     :components
     [(component {:id "part.jar" :name "Glass jar" :unspsc "24121500"
                  :qty 1 :mass-kg 0.25 :material :glass :role :packaging})
      (component {:id "part.spread" :name "Spread fill" :unspsc "50192400"
                  :qty 1 :mass-kg 0.55 :material :agricultural :role :material})
      (component {:id "part.lid" :name "Metal lid" :unspsc "24121500"
                  :qty 1 :mass-kg 0.03 :material :steel :role :part})]
     :features
     [(cad-feature {:id "jar" :kind :revolve :order 0 :name "jar"
                    :x 0 :y 0 :z 0 :r 45 :h 110})
      (cad-feature {:id "lid" :kind :boss :order 1 :name "lid"
                    :x 0 :y 0 :z 110 :w 90 :h 10})]})

   ;; ── densify curated :blueprint segments (lift blueprint product share) ──
   (product
    {:id "prod.rugged-tablet"
     :name "Rugged field tablet"
     :unspsc "43211503"
     :brand "demo-field"
     :sector :electronics
     :gltf-ref "asset://unspsc/43/rugged-tablet.glb"
     :physics {:mass-kg 0.95 :bbox-mm [280 190 25] :density-g-cm3 1.6
               :material-class :electronics}
     :components
     [(component {:id "part.soc-tab" :name "Mobile SoC" :unspsc "32101604"
                  :qty 1 :mass-kg 0.006 :material :silicon :role :part})
      (component {:id "part.lcd" :name "Sunlight LCD" :unspsc "32121509"
                  :qty 1 :mass-kg 0.12 :material :glass :role :part})
      (component {:id "part.batt-tab" :name "Swap battery" :unspsc "26111710"
                  :qty 1 :mass-kg 0.18 :material :li-ion :role :part})
      (component {:id "part.shell" :name "IP67 shell" :unspsc "30171500"
                  :qty 1 :mass-kg 0.35 :material :polymer :role :assembly})
      (component {:id "sw.field-os" :name "Field OS image" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 280 :h 25})
      (cad-feature {:id "screen" :kind :boss :order 1 :name "screen"
                    :x 0 :y 0 :z 12 :w 250 :h 4})
      (cad-feature {:id "grip" :kind :revolve :order 2 :name "grip"
                    :x 140 :y 0 :z 0 :r 12 :h 190})]})

   (product
    {:id "prod.cnc-tool-holder"
     :name "CNC collet tool holder set"
     :unspsc "27112700"
     :sector :tools
     :gltf-ref "asset://unspsc/27/cnc-tool-holder.glb"
     :physics {:mass-kg 2.4 :bbox-mm [200 200 180] :density-g-cm3 7.5
               :material-class :steel}
     :components
     [(component {:id "part.holder" :name "BT40 holder" :unspsc "27112700"
                  :qty 6 :mass-kg 0.28 :material :steel :role :part})
      (component {:id "part.collet" :name "ER32 collet" :unspsc "27112700"
                  :qty 12 :mass-kg 0.04 :material :steel :role :part})
      (component {:id "part.rack" :name "Tool rack" :unspsc "24112400"
                  :qty 1 :mass-kg 0.6 :material :polymer :role :assembly})
      (component {:id "part.tag" :name "RFID tool tag" :unspsc "43211700"
                  :qty 6 :mass-kg 0.005 :material :electronics :role :part})]
     :features
     [(cad-feature {:id "rack" :kind :extrude :order 0 :name "rack"
                    :x 0 :y 0 :z 0 :w 200 :h 40})
      (cad-feature {:id "holder" :kind :revolve :order 1 :name "holder"
                    :x 0 :y 0 :z 40 :r 30 :h 120})
      (cad-feature {:id "collet" :kind :boss :order 2 :name "collet"
                    :x 0 :y 0 :z 160 :w 40 :h 20})]})

   (product
    {:id "prod.smart-meter-module"
     :name "3-phase smart meter module"
     :unspsc "39121007"
     :sector :electrical
     :gltf-ref "asset://unspsc/39/smart-meter-module.glb"
     :physics {:mass-kg 1.1 :bbox-mm [120 90 70] :density-g-cm3 1.9
               :material-class :electronics}
     :components
     [(component {:id "part.meter-ic" :name "Metrology SoC" :unspsc "32101604"
                  :qty 1 :mass-kg 0.003 :material :silicon :role :part})
      (component {:id "part.ct" :name "Current transformer" :unspsc "39121000"
                  :qty 3 :mass-kg 0.08 :material :steel :role :part})
      (component {:id "part.case-m" :name "DIN rail case" :unspsc "24112400"
                  :qty 1 :mass-kg 0.25 :material :polymer :role :assembly})
      (component {:id "sw.ami" :name "AMI firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "case" :kind :extrude :order 0 :name "case"
                    :x 0 :y 0 :z 0 :w 120 :h 70})
      (cad-feature {:id "terminal" :kind :boss :order 1 :name "terminal"
                    :x 0 :y -40 :z 20 :w 100 :h 15})
      (cad-feature {:id "display" :kind :boss :order 2 :name "display"
                    :x 0 :y 20 :z 70 :w 60 :h 3})]})

   (product
    {:id "prod.soil-probe-kit"
     :name "Agricultural soil probe kit"
     :unspsc "10151505"
     :sector :agriculture
     :gltf-ref "asset://unspsc/10/soil-probe-kit.glb"
     :physics {:mass-kg 0.85 :bbox-mm [50 50 600] :density-g-cm3 2.2
               :material-class :mixed}
     :components
     [(component {:id "part.probe" :name "Stainless probe" :unspsc "41111900"
                  :qty 1 :mass-kg 0.35 :material :steel :role :part})
      (component {:id "part.npk" :name "NPK sensor head" :unspsc "41111900"
                  :qty 1 :mass-kg 0.08 :material :electronics :role :part})
      (component {:id "part.logger-soil" :name "Field logger" :unspsc "43211500"
                  :qty 1 :mass-kg 0.2 :material :electronics :role :part})
      (component {:id "part.sheath" :name "Carry sheath" :unspsc "24120000"
                  :qty 1 :mass-kg 0.12 :material :polymer :role :packaging})]
     :features
     [(cad-feature {:id "shaft" :kind :revolve :order 0 :name "shaft"
                    :x 0 :y 0 :z 0 :r 8 :h 550})
      (cad-feature {:id "head" :kind :boss :order 1 :name "sensor-head"
                    :x 0 :y 0 :z 550 :w 40 :h 40})
      (cad-feature {:id "handle" :kind :extrude :order 2 :name "handle"
                    :x 0 :y 0 :z 590 :w 50 :h 20})]})

   (product
    {:id "prod.spc-audit-console"
     :name "SPC line audit console"
     :unspsc "73101505"
     :sector :industrial-services
     :gltf-ref "asset://unspsc/73/spc-audit-console.glb"
     :physics {:mass-kg 2.8 :bbox-mm [320 220 40] :density-g-cm3 1.4
               :material-class :electronics}
     :components
     [(component {:id "part.panel" :name "Operator panel" :unspsc "43211500"
                  :qty 1 :mass-kg 0.9 :material :electronics :role :assembly})
      (component {:id "part.probe-io" :name "Probe I/O hub" :unspsc "41111600"
                  :qty 1 :mass-kg 0.35 :material :electronics :role :part})
      (component {:id "part.stand" :name "Articulated stand" :unspsc "30171500"
                  :qty 1 :mass-kg 1.1 :material :aluminum :role :assembly})
      (component {:id "sw.spc" :name "SPC workflow app" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "panel" :kind :extrude :order 0 :name "panel"
                    :x 0 :y 0 :z 0 :w 320 :h 20})
      (cad-feature {:id "stand" :kind :revolve :order 1 :name "stand"
                    :x 0 :y -80 :z -200 :r 20 :h 200})
      (cad-feature {:id "hub" :kind :boss :order 2 :name "io-hub"
                    :x 120 :y 0 :z 20 :w 60 :h 25})]})

   ;; ── wave-2 goods segments (registry breadth, stay :spec) ──
   (product
    {:id "prod.steel-i-beam"
     :name "Structural steel I-beam 6m"
     :unspsc "30103600"
     :sector :construction
     :gltf-ref "asset://unspsc/30/steel-i-beam.glb"
     :physics {:mass-kg 280.0 :bbox-mm [6000 200 300] :density-g-cm3 7.85
               :material-class :steel}
     :components
     [(component {:id "part.web" :name "Web plate" :unspsc "30103600"
                  :qty 1 :mass-kg 120 :material :steel :role :part})
      (component {:id "part.flange" :name "Flange plates" :unspsc "30103600"
                  :qty 2 :mass-kg 70 :material :steel :role :part})
      (component {:id "part.coat" :name "Zinc coat" :unspsc "31200000"
                  :qty 1 :mass-kg 5 :material :zinc :role :material})
      (component {:id "part.tag-beam" :name "Mill cert tag" :unspsc "14111800"
                  :qty 1 :mass-kg 0.02 :material :steel :role :part})]
     :features
     [(cad-feature {:id "web" :kind :extrude :order 0 :name "web"
                    :x 0 :y 0 :z 0 :w 6000 :h 10})
      (cad-feature {:id "flange-top" :kind :boss :order 1 :name "flange-top"
                    :x 0 :y 0 :z 150 :w 6000 :h 20})
      (cad-feature {:id "flange-bot" :kind :boss :order 2 :name "flange-bot"
                    :x 0 :y 0 :z -150 :w 6000 :h 20})]})

   (product
    {:id "prod.mlcc-reel"
     :name "MLCC capacitor reel 10k"
     :unspsc "32121505"
     :sector :electronics
     :gltf-ref "asset://unspsc/32/mlcc-reel.glb"
     :physics {:mass-kg 0.45 :bbox-mm [180 180 20] :density-g-cm3 1.2
               :material-class :electronics}
     :components
     [(component {:id "part.mlcc" :name "0402 MLCC units" :unspsc "32121505"
                  :qty 10000 :mass-kg 0.00002 :material :ceramic :role :part})
      (component {:id "part.tape" :name "Carrier tape" :unspsc "31200000"
                  :qty 1 :mass-kg 0.15 :material :polymer :role :packaging})
      (component {:id "part.reel" :name "Plastic reel" :unspsc "24121500"
                  :qty 1 :mass-kg 0.12 :material :polymer :role :packaging})
      (component {:id "part.msl" :name "MSL barrier bag" :unspsc "24120000"
                  :qty 1 :mass-kg 0.03 :material :polymer :role :packaging})]
     :features
     [(cad-feature {:id "reel" :kind :revolve :order 0 :name "reel"
                    :x 0 :y 0 :z 0 :r 90 :h 15})
      (cad-feature {:id "hub" :kind :boss :order 1 :name "hub"
                    :x 0 :y 0 :z 0 :w 40 :h 20})
      (cad-feature {:id "tape" :kind :extrude :order 2 :name "tape-wind"
                    :x 0 :y 0 :z 8 :w 160 :h 4})]})

   (product
    {:id "prod.digital-caliper"
     :name "Digital caliper 150mm"
     :unspsc "41111600"
     :sector :metrology
     :gltf-ref "asset://unspsc/41/digital-caliper.glb"
     :physics {:mass-kg 0.18 :bbox-mm [230 80 15] :density-g-cm3 2.8
               :material-class :steel}
     :components
     [(component {:id "part.beam" :name "Scale beam" :unspsc "41111600"
                  :qty 1 :mass-kg 0.08 :material :steel :role :part})
      (component {:id "part.jaws" :name "Measuring jaws" :unspsc "41111600"
                  :qty 1 :mass-kg 0.04 :material :steel :role :part})
      (component {:id "part.encoder" :name "Capacitive encoder" :unspsc "32101604"
                  :qty 1 :mass-kg 0.01 :material :electronics :role :part})
      (component {:id "part.case-cal" :name "Plastic case" :unspsc "24120000"
                  :qty 1 :mass-kg 0.04 :material :polymer :role :packaging})
      (component {:id "sw.cal" :name "Cal firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "beam" :kind :extrude :order 0 :name "beam"
                    :x 0 :y 0 :z 0 :w 230 :h 8})
      (cad-feature {:id "jaw" :kind :boss :order 1 :name "jaw"
                    :x -100 :y 0 :z 8 :w 40 :h 40})
      (cad-feature {:id "display" :kind :boss :order 2 :name "display"
                    :x 40 :y 0 :z 10 :w 40 :h 3})]})

   (product
    {:id "prod.pulse-oximeter"
     :name "Fingertip pulse oximeter"
     :unspsc "42181700"
     :sector :medical
     :gltf-ref "asset://unspsc/42/pulse-oximeter.glb"
     :physics {:mass-kg 0.05 :bbox-mm [60 35 30] :density-g-cm3 1.1
               :material-class :electronics}
     :components
     [(component {:id "part.spo2" :name "SpO2 sensor" :unspsc "42181700"
                  :qty 1 :mass-kg 0.008 :material :electronics :role :part})
      (component {:id "part.mcu" :name "MCU board" :unspsc "32101500"
                  :qty 1 :mass-kg 0.01 :material :fr4 :role :assembly})
      (component {:id "part.clip" :name "Finger clip" :unspsc "42181700"
                  :qty 1 :mass-kg 0.015 :material :polymer :role :part})
      (component {:id "part.cell" :name "Coin cell" :unspsc "26111710"
                  :qty 1 :mass-kg 0.003 :material :li-ion :role :part})
      (component {:id "sw.spo2" :name "SpO2 firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "clip" :kind :extrude :order 0 :name "clip"
                    :x 0 :y 0 :z 0 :w 60 :h 30})
      (cad-feature {:id "sensor" :kind :boss :order 1 :name "sensor"
                    :x 0 :y 0 :z 15 :w 20 :h 8})
      (cad-feature {:id "oled" :kind :boss :order 2 :name "oled"
                    :x 0 :y 10 :z 30 :w 25 :h 2})]})

   (product
    {:id "prod.laptop-dock"
     :name "USB-C laptop docking station"
     :unspsc "44101800"
     :sector :office
     :gltf-ref "asset://unspsc/44/laptop-dock.glb"
     :physics {:mass-kg 0.55 :bbox-mm [160 80 30] :density-g-cm3 1.5
               :material-class :electronics}
     :components
     [(component {:id "part.hub-ic" :name "USB hub SoC" :unspsc "32101604"
                  :qty 1 :mass-kg 0.002 :material :silicon :role :part})
      (component {:id "part.pd" :name "PD controller" :unspsc "32101500"
                  :qty 1 :mass-kg 0.005 :material :electronics :role :part})
      (component {:id "part.pcb-dock" :name "Dock PCB" :unspsc "32101500"
                  :qty 1 :mass-kg 0.08 :material :fr4 :role :assembly})
      (component {:id "part.shell-dock" :name "Aluminum shell" :unspsc "30171500"
                  :qty 1 :mass-kg 0.25 :material :aluminum :role :assembly})
      (component {:id "sw.pd" :name "PD firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 160 :h 30})
      (cad-feature {:id "ports" :kind :boss :order 1 :name "ports"
                    :x 70 :y 0 :z 10 :w 20 :h 15})
      (cad-feature {:id "stand" :kind :revolve :order 2 :name "feet"
                    :x 0 :y -30 :z 0 :r 8 :h 5})]})

   (product
    {:id "prod.office-chair"
     :name "Ergonomic office chair"
     :unspsc "56101500"
     :sector :furniture
     :gltf-ref "asset://unspsc/56/office-chair.glb"
     :physics {:mass-kg 18.0 :bbox-mm [700 700 1200] :density-g-cm3 0.25
               :material-class :mixed}
     :components
     [(component {:id "part.seat" :name "Seat cushion" :unspsc "56101500"
                  :qty 1 :mass-kg 3.5 :material :foam :role :part})
      (component {:id "part.back" :name "Mesh back" :unspsc "56101500"
                  :qty 1 :mass-kg 2.0 :material :polymer :role :part})
      (component {:id "part.base" :name "5-star base" :unspsc "56101500"
                  :qty 1 :mass-kg 4.5 :material :aluminum :role :assembly})
      (component {:id "part.gas" :name "Gas lift" :unspsc "31161700"
                  :qty 1 :mass-kg 1.2 :material :steel :role :part})
      (component {:id "part.casters" :name "Casters" :unspsc "31161700"
                  :qty 5 :mass-kg 0.15 :material :polymer :role :part})]
     :features
     [(cad-feature {:id "seat" :kind :extrude :order 0 :name "seat"
                    :x 0 :y 0 :z 450 :w 500 :h 80})
      (cad-feature {:id "back" :kind :boss :order 1 :name "back"
                    :x 0 :y -200 :z 700 :w 480 :h 500})
      (cad-feature {:id "base" :kind :revolve :order 2 :name "base"
                    :x 0 :y 0 :z 0 :r 350 :h 50})]})

   ;; ── densify-3 curated :blueprint (target density ≥3) ──
   (product
    {:id "prod.edge-compute-node"
     :name "Edge compute node 1U"
     :unspsc "43211508"
     :brand "demo-edge"
     :sector :electronics
     :gltf-ref "asset://unspsc/43/edge-compute-node.glb"
     :physics {:mass-kg 8.5 :bbox-mm [450 400 45] :density-g-cm3 1.8
               :material-class :electronics}
     :components
     [(component {:id "part.cpu-edge" :name "Edge CPU" :unspsc "32101604"
                  :qty 1 :mass-kg 0.05 :material :silicon :role :part})
      (component {:id "part.ssd" :name "NVMe SSD" :unspsc "43201800"
                  :qty 2 :mass-kg 0.08 :material :electronics :role :part})
      (component {:id "part.mobo" :name "Carrier board" :unspsc "32101500"
                  :qty 1 :mass-kg 0.4 :material :fr4 :role :assembly})
      (component {:id "part.chassis-1u" :name "1U chassis" :unspsc "30171500"
                  :qty 1 :mass-kg 3.5 :material :steel :role :assembly})
      (component {:id "sw.edge-os" :name "Edge OS image" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "chassis" :kind :extrude :order 0 :name "chassis"
                    :x 0 :y 0 :z 0 :w 450 :h 45})
      (cad-feature {:id "psu" :kind :boss :order 1 :name "psu"
                    :x 180 :y 0 :z 10 :w 80 :h 40})
      (cad-feature {:id "fan" :kind :revolve :order 2 :name "fan"
                    :x -180 :y 0 :z 20 :r 20 :h 20})]})

   (product
    {:id "prod.hydraulic-shop-press"
     :name "Hydraulic shop press 20t"
     :unspsc "27112705"
     :sector :tools
     :gltf-ref "asset://unspsc/27/hydraulic-shop-press.glb"
     :physics {:mass-kg 95.0 :bbox-mm [600 500 1600] :density-g-cm3 7.0
               :material-class :steel}
     :components
     [(component {:id "part.ram" :name "Hydraulic ram" :unspsc "27112700"
                  :qty 1 :mass-kg 25 :material :steel :role :part})
      (component {:id "part.frame-press" :name "H-frame" :unspsc "30103600"
                  :qty 1 :mass-kg 50 :material :steel :role :assembly})
      (component {:id "part.pump" :name "Hand pump" :unspsc "27112700"
                  :qty 1 :mass-kg 8 :material :steel :role :part})
      (component {:id "part.hose" :name "HP hose" :unspsc "40151500"
                  :qty 1 :mass-kg 1.2 :material :polymer :role :part})]
     :features
     [(cad-feature {:id "frame" :kind :extrude :order 0 :name "frame"
                    :x 0 :y 0 :z 0 :w 600 :h 1600})
      (cad-feature {:id "ram" :kind :revolve :order 1 :name "ram"
                    :x 0 :y 0 :z 800 :r 40 :h 400})
      (cad-feature {:id "base" :kind :boss :order 2 :name "base"
                    :x 0 :y 0 :z 0 :w 500 :h 80})]})

   (product
    {:id "prod.din-contactor"
     :name "DIN rail contactor 3-phase"
     :unspsc "39121522"
     :sector :electrical
     :gltf-ref "asset://unspsc/39/din-contactor.glb"
     :physics {:mass-kg 0.42 :bbox-mm [90 60 75] :density-g-cm3 2.0
               :material-class :electronics}
     :components
     [(component {:id "part.coil" :name "Control coil" :unspsc "39121500"
                  :qty 1 :mass-kg 0.08 :material :copper :role :part})
      (component {:id "part.contacts" :name "Power contacts" :unspsc "39121500"
                  :qty 3 :mass-kg 0.03 :material :silver :role :part})
      (component {:id "part.housing-c" :name "DIN housing" :unspsc "24112400"
                  :qty 1 :mass-kg 0.15 :material :polymer :role :assembly})
      (component {:id "part.arc" :name "Arc chute" :unspsc "39121500"
                  :qty 1 :mass-kg 0.05 :material :ceramic :role :part})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 90 :h 75})
      (cad-feature {:id "din" :kind :boss :order 1 :name "din-clip"
                    :x 0 :y -30 :z 10 :w 80 :h 15})
      (cad-feature {:id "terminals" :kind :boss :order 2 :name "terminals"
                    :x 0 :y 25 :z 60 :w 70 :h 12})]})

   (product
    {:id "prod.seedling-tray-sensor"
     :name "Seedling tray moisture array"
     :unspsc "10151508"
     :sector :agriculture
     :gltf-ref "asset://unspsc/10/seedling-tray-sensor.glb"
     :physics {:mass-kg 0.65 :bbox-mm [540 280 50] :density-g-cm3 0.9
               :material-class :electronics}
     :components
     [(component {:id "part.tray" :name "Nursery tray" :unspsc "24112400"
                  :qty 1 :mass-kg 0.25 :material :polymer :role :packaging})
      (component {:id "part.m-sensor" :name "Moisture probes" :unspsc "41111900"
                  :qty 12 :mass-kg 0.01 :material :electronics :role :part})
      (component {:id "part.bus" :name "Sensor bus hub" :unspsc "43211500"
                  :qty 1 :mass-kg 0.08 :material :electronics :role :assembly})
      (component {:id "sw.grow" :name "Grow monitor FW" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "tray" :kind :extrude :order 0 :name "tray"
                    :x 0 :y 0 :z 0 :w 540 :h 40})
      (cad-feature {:id "hub" :kind :boss :order 1 :name "hub"
                    :x 250 :y 0 :z 40 :w 60 :h 20})
      (cad-feature {:id "probe" :kind :revolve :order 2 :name "probe"
                    :x -200 :y 0 :z 20 :r 3 :h 30})]})

   (product
    {:id "prod.laser-alignment-kit"
     :name "Laser shaft alignment kit"
     :unspsc "73101508"
     :sector :industrial-services
     :gltf-ref "asset://unspsc/73/laser-alignment-kit.glb"
     :physics {:mass-kg 3.8 :bbox-mm [400 300 150] :density-g-cm3 1.6
               :material-class :mixed}
     :components
     [(component {:id "part.laser" :name "Laser emitter" :unspsc "41111600"
                  :qty 2 :mass-kg 0.4 :material :electronics :role :part})
      (component {:id "part.detector" :name "Detector head" :unspsc "41111600"
                  :qty 2 :mass-kg 0.35 :material :electronics :role :part})
      (component {:id "part.bracket" :name "Shaft brackets" :unspsc "31161700"
                  :qty 4 :mass-kg 0.2 :material :aluminum :role :part})
      (component {:id "part.case-la" :name "Hard case" :unspsc "24120000"
                  :qty 1 :mass-kg 1.0 :material :polymer :role :packaging})
      (component {:id "sw.align" :name "Alignment app" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "case" :kind :extrude :order 0 :name "case"
                    :x 0 :y 0 :z 0 :w 400 :h 150})
      (cad-feature {:id "emitter" :kind :boss :order 1 :name "emitter"
                    :x -80 :y 0 :z 150 :w 50 :h 40})
      (cad-feature {:id "bracket" :kind :revolve :order 2 :name "bracket"
                    :x 80 :y 0 :z 150 :r 25 :h 30})]})

   ;; ── wave-3 goods segments (registry breadth, stay :spec) ──
   (product
    {:id "prod.solvent-drum-200l"
     :name "Industrial solvent drum 200L"
     :unspsc "12191500"
     :sector :chemicals
     :gltf-ref "asset://unspsc/12/solvent-drum-200l.glb"
     :physics {:mass-kg 220.0 :bbox-mm [600 600 900] :density-g-cm3 0.85
               :material-class :steel}
     :components
     [(component {:id "part.drum" :name "Steel drum" :unspsc "24121500"
                  :qty 1 :mass-kg 18 :material :steel :role :packaging})
      (component {:id "part.solvent" :name "Solvent fill" :unspsc "12191500"
                  :qty 1 :mass-kg 170 :material :chemical :role :material})
      (component {:id "part.bung" :name "Bung plugs" :unspsc "24121500"
                  :qty 2 :mass-kg 0.1 :material :steel :role :part})
      (component {:id "part.label-haz" :name "GHS label" :unspsc "14111800"
                  :qty 1 :mass-kg 0.01 :material :paper :role :part})]
     :features
     [(cad-feature {:id "drum" :kind :revolve :order 0 :name "drum"
                    :x 0 :y 0 :z 0 :r 300 :h 880})
      (cad-feature {:id "rim" :kind :boss :order 1 :name "rim"
                    :x 0 :y 0 :z 880 :w 600 :h 20})
      (cad-feature {:id "bung" :kind :boss :order 2 :name "bung"
                    :x 100 :y 0 :z 900 :w 50 :h 30})]})

   (product
    {:id "prod.diesel-jerrycan"
     :name "Diesel jerrycan 20L"
     :unspsc "15101500"
     :sector :fuels
     :gltf-ref "asset://unspsc/15/diesel-jerrycan.glb"
     :physics {:mass-kg 18.5 :bbox-mm [350 200 450] :density-g-cm3 0.85
               :material-class :steel}
     :components
     [(component {:id "part.can" :name "Steel can body" :unspsc "24121500"
                  :qty 1 :mass-kg 2.5 :material :steel :role :packaging})
      (component {:id "part.diesel" :name "Diesel fill" :unspsc "15101500"
                  :qty 1 :mass-kg 15.5 :material :fuel :role :material})
      (component {:id "part.spout" :name "Flex spout" :unspsc "40151500"
                  :qty 1 :mass-kg 0.2 :material :polymer :role :part})
      (component {:id "part.cap" :name "Cap seal" :unspsc "24121500"
                  :qty 1 :mass-kg 0.05 :material :polymer :role :part})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 350 :h 450})
      (cad-feature {:id "handle" :kind :revolve :order 1 :name "handle"
                    :x 0 :y 80 :z 420 :r 15 :h 80})
      (cad-feature {:id "spout" :kind :boss :order 2 :name "spout"
                    :x 120 :y 0 :z 450 :w 40 :h 50})]})

   (product
    {:id "prod.mini-excavator-bucket"
     :name "Mini excavator digging bucket"
     :unspsc "22101500"
     :sector :construction
     :gltf-ref "asset://unspsc/22/mini-excavator-bucket.glb"
     :physics {:mass-kg 85.0 :bbox-mm [600 500 450] :density-g-cm3 7.5
               :material-class :steel}
     :components
     [(component {:id "part.shell-b" :name "Bucket shell" :unspsc "22101500"
                  :qty 1 :mass-kg 55 :material :steel :role :assembly})
      (component {:id "part.teeth" :name "Bucket teeth" :unspsc "22101500"
                  :qty 5 :mass-kg 2.5 :material :steel :role :part})
      (component {:id "part.pins" :name "Hinge pins" :unspsc "31161700"
                  :qty 2 :mass-kg 1.5 :material :steel :role :part})
      (component {:id "part.bush" :name "Bushings" :unspsc "31161700"
                  :qty 4 :mass-kg 0.3 :material :bronze :role :part})]
     :features
     [(cad-feature {:id "shell" :kind :extrude :order 0 :name "shell"
                    :x 0 :y 0 :z 0 :w 600 :h 400})
      (cad-feature {:id "tooth" :kind :boss :order 1 :name "teeth"
                    :x 0 :y 200 :z 0 :w 500 :h 80})
      (cad-feature {:id "ear" :kind :revolve :order 2 :name "hinge-ear"
                    :x 0 :y -200 :z 300 :r 40 :h 50})]})

   (product
    {:id "prod.pallet-jack"
     :name "Manual pallet jack 2.5t"
     :unspsc "24101600"
     :sector :material-handling
     :gltf-ref "asset://unspsc/24/pallet-jack.glb"
     :physics {:mass-kg 75.0 :bbox-mm [1600 550 1200] :density-g-cm3 3.0
               :material-class :steel}
     :components
     [(component {:id "part.forks" :name "Forks" :unspsc "24101600"
                  :qty 2 :mass-kg 18 :material :steel :role :part})
      (component {:id "part.hyd" :name "Hydraulic unit" :unspsc "27112700"
                  :qty 1 :mass-kg 12 :material :steel :role :assembly})
      (component {:id "part.wheels" :name "Load wheels" :unspsc "31161700"
                  :qty 4 :mass-kg 2.0 :material :polymer :role :part})
      (component {:id "part.handle-pj" :name "Steering handle" :unspsc "24101600"
                  :qty 1 :mass-kg 5 :material :steel :role :part})]
     :features
     [(cad-feature {:id "fork" :kind :extrude :order 0 :name "forks"
                    :x 0 :y 0 :z 50 :w 1600 :h 50})
      (cad-feature {:id "mast" :kind :boss :order 1 :name "mast"
                    :x -700 :y 0 :z 100 :w 200 :h 800})
      (cad-feature {:id "wheel" :kind :revolve :order 2 :name "wheel"
                    :x 600 :y -200 :z 0 :r 80 :h 50})]})

   (product
    {:id "prod.bearing-6205"
     :name "Deep groove ball bearing 6205"
     :unspsc "31171500"
     :sector :manufacturing-components
     :gltf-ref "asset://unspsc/31/bearing-6205.glb"
     :physics {:mass-kg 0.13 :bbox-mm [52 52 15] :density-g-cm3 7.8
               :material-class :steel}
     :components
     [(component {:id "part.inner" :name "Inner race" :unspsc "31171500"
                  :qty 1 :mass-kg 0.04 :material :steel :role :part})
      (component {:id "part.outer" :name "Outer race" :unspsc "31171500"
                  :qty 1 :mass-kg 0.05 :material :steel :role :part})
      (component {:id "part.balls" :name "Steel balls" :unspsc "31171500"
                  :qty 9 :mass-kg 0.003 :material :steel :role :part})
      (component {:id "part.cage" :name "Cage" :unspsc "31171500"
                  :qty 1 :mass-kg 0.01 :material :steel :role :part})
      (component {:id "part.seal" :name "Rubber seal" :unspsc "31171500"
                  :qty 2 :mass-kg 0.002 :material :polymer :role :part})]
     :features
     [(cad-feature {:id "outer" :kind :revolve :order 0 :name "outer"
                    :x 0 :y 0 :z 0 :r 26 :h 15})
      (cad-feature {:id "inner" :kind :revolve :order 1 :name "inner"
                    :x 0 :y 0 :z 0 :r 12 :h 15})
      (cad-feature {:id "ball" :kind :boss :order 2 :name "ball-ring"
                    :x 18 :y 0 :z 7 :w 8 :h 8})]})

   (product
    {:id "prod.hvac-duct-section"
     :name "Galvanized HVAC duct section"
     :unspsc "40101500"
     :sector :hvac
     :gltf-ref "asset://unspsc/40/hvac-duct-section.glb"
     :physics {:mass-kg 12.0 :bbox-mm [1200 400 400] :density-g-cm3 0.4
               :material-class :steel}
     :components
     [(component {:id "part.sheet" :name "Galv sheet" :unspsc "30103600"
                  :qty 1 :mass-kg 9 :material :steel :role :material})
      (component {:id "part.flange-d" :name "Duct flanges" :unspsc "40101500"
                  :qty 2 :mass-kg 1.2 :material :steel :role :part})
      (component {:id "part.gasket" :name "Neoprene gasket" :unspsc "31200000"
                  :qty 2 :mass-kg 0.15 :material :rubber :role :material})
      (component {:id "part.screws" :name "Self-tap screws" :unspsc "31161500"
                  :qty 24 :mass-kg 0.01 :material :steel :role :part})]
     :features
     [(cad-feature {:id "duct" :kind :extrude :order 0 :name "duct"
                    :x 0 :y 0 :z 0 :w 1200 :h 400})
      (cad-feature {:id "flange-a" :kind :boss :order 1 :name "flange-a"
                    :x -600 :y 0 :z 0 :w 20 :h 420})
      (cad-feature {:id "flange-b" :kind :boss :order 2 :name "flange-b"
                    :x 600 :y 0 :z 0 :w 20 :h 420})]})

   ;; ── densify-4 curated :blueprint (target density ≥4) ──
   (product
    {:id "prod.lora-gateway"
     :name "Outdoor LoRaWAN gateway"
     :unspsc "43222612"
     :brand "demo-iot"
     :sector :electronics
     :gltf-ref "asset://unspsc/43/lora-gateway.glb"
     :physics {:mass-kg 1.8 :bbox-mm [220 180 90] :density-g-cm3 1.4
               :material-class :electronics}
     :components
     [(component {:id "part.lora-ic" :name "LoRa baseband" :unspsc "32101604"
                  :qty 1 :mass-kg 0.005 :material :silicon :role :part})
      (component {:id "part.ant-lora" :name "Omni antenna" :unspsc "43191500"
                  :qty 1 :mass-kg 0.15 :material :electronics :role :part})
      (component {:id "part.poe" :name "PoE injector board" :unspsc "32101500"
                  :qty 1 :mass-kg 0.08 :material :fr4 :role :assembly})
      (component {:id "part.ip67" :name "IP67 enclosure" :unspsc "24112400"
                  :qty 1 :mass-kg 0.6 :material :polymer :role :assembly})
      (component {:id "sw.lora" :name "Gateway firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "box" :kind :extrude :order 0 :name "enclosure"
                    :x 0 :y 0 :z 0 :w 220 :h 90})
      (cad-feature {:id "ant" :kind :revolve :order 1 :name "antenna"
                    :x 0 :y 0 :z 90 :r 8 :h 200})
      (cad-feature {:id "bracket" :kind :boss :order 2 :name "mount"
                    :x 0 :y -90 :z 40 :w 80 :h 20})]})

   (product
    {:id "prod.impact-driver-kit"
     :name "Cordless impact driver kit"
     :unspsc "27112712"
     :sector :tools
     :gltf-ref "asset://unspsc/27/impact-driver-kit.glb"
     :physics {:mass-kg 2.1 :bbox-mm [280 220 100] :density-g-cm3 1.8
               :material-class :mixed}
     :components
     [(component {:id "part.driver" :name "Impact driver" :unspsc "27112700"
                  :qty 1 :mass-kg 1.1 :material :steel :role :assembly})
      (component {:id "part.batt-id" :name "18V battery" :unspsc "26111710"
                  :qty 2 :mass-kg 0.35 :material :li-ion :role :part})
      (component {:id "part.charger" :name "Charger" :unspsc "39121000"
                  :qty 1 :mass-kg 0.25 :material :electronics :role :part})
      (component {:id "part.case-id" :name "Kit case" :unspsc "24120000"
                  :qty 1 :mass-kg 0.4 :material :polymer :role :packaging})
      (component {:id "sw.batt-m" :name "BMS firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "case" :kind :extrude :order 0 :name "case"
                    :x 0 :y 0 :z 0 :w 280 :h 100})
      (cad-feature {:id "driver" :kind :boss :order 1 :name "driver"
                    :x -40 :y 0 :z 100 :w 180 :h 50})
      (cad-feature {:id "batt" :kind :revolve :order 2 :name "battery"
                    :x 80 :y 0 :z 50 :r 30 :h 60})]})

   (product
    {:id "prod.led-highbay"
     :name "LED high-bay luminaire 150W"
     :unspsc "39111512"
     :sector :electrical
     :gltf-ref "asset://unspsc/39/led-highbay.glb"
     :physics {:mass-kg 3.2 :bbox-mm [350 350 120] :density-g-cm3 1.5
               :material-class :aluminum}
     :components
     [(component {:id "part.leds" :name "LED modules" :unspsc "39111500"
                  :qty 4 :mass-kg 0.15 :material :electronics :role :part})
      (component {:id "part.driver-hb" :name "LED driver" :unspsc "39121000"
                  :qty 1 :mass-kg 0.4 :material :electronics :role :part})
      (component {:id "part.heatsink-hb" :name "Heatsink body" :unspsc "40101800"
                  :qty 1 :mass-kg 1.8 :material :aluminum :role :assembly})
      (component {:id "part.lens" :name "Optics lens" :unspsc "39111500"
                  :qty 1 :mass-kg 0.2 :material :polymer :role :part})
      (component {:id "sw.dim" :name "DALI firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :revolve :order 0 :name "body"
                    :x 0 :y 0 :z 0 :r 160 :h 80})
      (cad-feature {:id "lens" :kind :boss :order 1 :name "lens"
                    :x 0 :y 0 :z 80 :w 300 :h 15})
      (cad-feature {:id "hook" :kind :revolve :order 2 :name "hang-hook"
                    :x 0 :y 0 :z -20 :r 15 :h 40})]})

   (product
    {:id "prod.pollinator-nest-box"
     :name "Solitary bee nest box kit"
     :unspsc "10151512"
     :sector :agriculture
     :gltf-ref "asset://unspsc/10/pollinator-nest-box.glb"
     :physics {:mass-kg 1.4 :bbox-mm [300 200 200] :density-g-cm3 0.5
               :material-class :wood}
     :components
     [(component {:id "part.box-wood" :name "Cedar box" :unspsc "11120000"
                  :qty 1 :mass-kg 0.9 :material :wood :role :assembly})
      (component {:id "part.tubes" :name "Nest tubes" :unspsc "11120000"
                  :qty 40 :mass-kg 0.005 :material :paper :role :part})
      (component {:id "part.roof" :name "Metal roof" :unspsc "30103600"
                  :qty 1 :mass-kg 0.2 :material :steel :role :part})
      (component {:id "part.mount-p" :name "Mount bracket" :unspsc "31161700"
                  :qty 1 :mass-kg 0.1 :material :steel :role :part})]
     :features
     [(cad-feature {:id "box" :kind :extrude :order 0 :name "box"
                    :x 0 :y 0 :z 0 :w 300 :h 200})
      (cad-feature {:id "roof" :kind :boss :order 1 :name "roof"
                    :x 0 :y 0 :z 200 :w 320 :h 20})
      (cad-feature {:id "tubes" :kind :revolve :order 2 :name "tube-bundle"
                    :x 0 :y 50 :z 50 :r 60 :h 150})]})

   (product
    {:id "prod.vibration-analyzer"
     :name "Portable vibration analyzer"
     :unspsc "73101512"
     :sector :industrial-services
     :gltf-ref "asset://unspsc/73/vibration-analyzer.glb"
     :physics {:mass-kg 1.6 :bbox-mm [250 160 50] :density-g-cm3 1.3
               :material-class :electronics}
     :components
     [(component {:id "part.accel" :name "Accelerometer probe" :unspsc "41111900"
                  :qty 2 :mass-kg 0.08 :material :electronics :role :part})
      (component {:id "part.daq" :name "DAQ unit" :unspsc "43211500"
                  :qty 1 :mass-kg 0.7 :material :electronics :role :assembly})
      (component {:id "part.cable-v" :name "Sensor cables" :unspsc "26121600"
                  :qty 2 :mass-kg 0.1 :material :copper :role :part})
      (component {:id "part.case-v" :name "Soft case" :unspsc "24120000"
                  :qty 1 :mass-kg 0.25 :material :polymer :role :packaging})
      (component {:id "sw.vib" :name "FFT analysis app" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "unit" :kind :extrude :order 0 :name "unit"
                    :x 0 :y 0 :z 0 :w 250 :h 50})
      (cad-feature {:id "probe" :kind :revolve :order 1 :name "probe"
                    :x 120 :y 0 :z 50 :r 12 :h 80})
      (cad-feature {:id "screen" :kind :boss :order 2 :name "screen"
                    :x 0 :y 0 :z 50 :w 120 :h 3})]})

   ;; ── wave-4 goods segments (registry breadth, stay :spec) ──
   (product
    {:id "prod.cotton-bale"
     :name "Raw cotton bale"
     :unspsc "11151500"
     :sector :materials
     :gltf-ref "asset://unspsc/11/cotton-bale.glb"
     :physics {:mass-kg 220.0 :bbox-mm [1400 700 700] :density-g-cm3 0.3
               :material-class :textile}
     :components
     [(component {:id "part.lint" :name "Cotton lint" :unspsc "11151500"
                  :qty 1 :mass-kg 210 :material :cotton :role :material})
      (component {:id "part.wrap" :name "Bale wrap" :unspsc "24121500"
                  :qty 1 :mass-kg 2 :material :polymer :role :packaging})
      (component {:id "part.wires" :name "Bale wires" :unspsc "31161700"
                  :qty 6 :mass-kg 0.5 :material :steel :role :part})
      (component {:id "part.tag-c" :name "Grade tag" :unspsc "14111800"
                  :qty 1 :mass-kg 0.01 :material :paper :role :part})]
     :features
     [(cad-feature {:id "bale" :kind :extrude :order 0 :name "bale"
                    :x 0 :y 0 :z 0 :w 1400 :h 700})
      (cad-feature {:id "wire" :kind :boss :order 1 :name "wires"
                    :x 0 :y 0 :z 350 :w 1400 :h 10})
      (cad-feature {:id "tag" :kind :boss :order 2 :name "tag"
                    :x 600 :y 0 :z 700 :w 80 :h 5})]})

   (product
    {:id "prod.copy-paper-ream"
     :name "A4 copy paper ream 500 sheets"
     :unspsc "14111500"
     :sector :paper
     :gltf-ref "asset://unspsc/14/copy-paper-ream.glb"
     :physics {:mass-kg 2.5 :bbox-mm [300 210 50] :density-g-cm3 0.8
               :material-class :paper}
     :components
     [(component {:id "part.sheets" :name "A4 sheets" :unspsc "14111500"
                  :qty 500 :mass-kg 0.005 :material :paper :role :material})
      (component {:id "part.wrap-p" :name "Ream wrap" :unspsc "24121500"
                  :qty 1 :mass-kg 0.05 :material :paper :role :packaging})
      (component {:id "part.carton-p" :name "Carton sleeve" :unspsc "24121500"
                  :qty 1 :mass-kg 0.1 :material :paper :role :packaging})
      (component {:id "part.label-p" :name "Grade label" :unspsc "14111800"
                  :qty 1 :mass-kg 0.005 :material :paper :role :part})]
     :features
     [(cad-feature {:id "ream" :kind :extrude :order 0 :name "ream"
                    :x 0 :y 0 :z 0 :w 300 :h 50})
      (cad-feature {:id "wrap" :kind :boss :order 1 :name "wrap"
                    :x 0 :y 0 :z 25 :w 300 :h 2})
      (cad-feature {:id "label" :kind :boss :order 2 :name "label"
                    :x 100 :y 0 :z 52 :w 80 :h 1})]})

   (product
    {:id "prod.tractor-pto-shaft"
     :name "Tractor PTO drive shaft"
     :unspsc "21101500"
     :sector :farming
     :gltf-ref "asset://unspsc/21/tractor-pto-shaft.glb"
     :physics {:mass-kg 18.0 :bbox-mm [1200 150 150] :density-g-cm3 7.5
               :material-class :steel}
     :components
     [(component {:id "part.tube" :name "Telescopic tubes" :unspsc "21101500"
                  :qty 2 :mass-kg 6 :material :steel :role :part})
      (component {:id "part.ujoint" :name "U-joints" :unspsc "31161700"
                  :qty 2 :mass-kg 1.5 :material :steel :role :part})
      (component {:id "part.yoke" :name "End yokes" :unspsc "21101500"
                  :qty 2 :mass-kg 2 :material :steel :role :part})
      (component {:id "part.guard" :name "Safety guard" :unspsc "24112400"
                  :qty 1 :mass-kg 1.2 :material :polymer :role :part})]
     :features
     [(cad-feature {:id "shaft" :kind :revolve :order 0 :name "shaft"
                    :x 0 :y 0 :z 0 :r 40 :h 1200})
      (cad-feature {:id "yoke" :kind :boss :order 1 :name "yoke"
                    :x 0 :y 0 :z 0 :w 120 :h 80})
      (cad-feature {:id "guard" :kind :revolve :order 2 :name "guard"
                    :x 0 :y 0 :z 200 :r 70 :h 800})]})

   (product
    {:id "prod.cnc-lathe-chuck"
     :name "CNC lathe 3-jaw chuck 200mm"
     :unspsc "23151500"
     :sector :industrial-machinery
     :gltf-ref "asset://unspsc/23/cnc-lathe-chuck.glb"
     :physics {:mass-kg 22.0 :bbox-mm [220 220 120] :density-g-cm3 7.5
               :material-class :steel}
     :components
     [(component {:id "part.body-ch" :name "Chuck body" :unspsc "23151500"
                  :qty 1 :mass-kg 14 :material :steel :role :assembly})
      (component {:id "part.jaws-ch" :name "Soft jaws" :unspsc "23151500"
                  :qty 3 :mass-kg 1.2 :material :steel :role :part})
      (component {:id "part.scroll" :name "Scroll plate" :unspsc "23151500"
                  :qty 1 :mass-kg 3 :material :steel :role :part})
      (component {:id "part.bolts" :name "Mount bolts" :unspsc "31161500"
                  :qty 6 :mass-kg 0.05 :material :steel :role :part})]
     :features
     [(cad-feature {:id "body" :kind :revolve :order 0 :name "body"
                    :x 0 :y 0 :z 0 :r 100 :h 100})
      (cad-feature {:id "jaw" :kind :boss :order 1 :name "jaw"
                    :x 60 :y 0 :z 50 :w 40 :h 40})
      (cad-feature {:id "bore" :kind :revolve :order 2 :name "bore"
                    :x 0 :y 0 :z 0 :r 30 :h 120})]})

   (product
    {:id "prod.access-control-reader"
     :name "RFID access control reader"
     :unspsc "46171600"
     :sector :security
     :gltf-ref "asset://unspsc/46/access-control-reader.glb"
     :physics {:mass-kg 0.35 :bbox-mm [120 80 25] :density-g-cm3 1.2
               :material-class :electronics}
     :components
     [(component {:id "part.rfid" :name "RFID module" :unspsc "32101604"
                  :qty 1 :mass-kg 0.02 :material :electronics :role :part})
      (component {:id "part.mcu-ac" :name "Reader MCU" :unspsc "32101500"
                  :qty 1 :mass-kg 0.03 :material :fr4 :role :assembly})
      (component {:id "part.shell-ac" :name "Weather shell" :unspsc "24112400"
                  :qty 1 :mass-kg 0.15 :material :polymer :role :assembly})
      (component {:id "part.relay" :name "Door relay" :unspsc "39121500"
                  :qty 1 :mass-kg 0.04 :material :electronics :role :part})
      (component {:id "sw.acs" :name "ACS firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 120 :h 25})
      (cad-feature {:id "pad" :kind :boss :order 1 :name "pad"
                    :x 0 :y 0 :z 25 :w 80 :h 3})
      (cad-feature {:id "led" :kind :boss :order 2 :name "status-led"
                    :x 40 :y 20 :z 28 :w 10 :h 2})]})

   (product
    {:id "prod.robot-vacuum"
     :name "Robot vacuum cleaner"
     :unspsc "52141500"
     :sector :appliances
     :gltf-ref "asset://unspsc/52/robot-vacuum.glb"
     :physics {:mass-kg 3.5 :bbox-mm [350 350 100] :density-g-cm3 0.9
               :material-class :electronics}
     :components
     [(component {:id "part.motor-v" :name "Brushless motor" :unspsc "26101500"
                  :qty 1 :mass-kg 0.4 :material :steel :role :part})
      (component {:id "part.batt-v" :name "Li-ion pack" :unspsc "26111710"
                  :qty 1 :mass-kg 0.6 :material :li-ion :role :part})
      (component {:id "part.lidar" :name "LiDAR module" :unspsc "41111900"
                  :qty 1 :mass-kg 0.15 :material :electronics :role :part})
      (component {:id "part.shell-v" :name "ABS shell" :unspsc "24112400"
                  :qty 1 :mass-kg 0.8 :material :polymer :role :assembly})
      (component {:id "sw.nav" :name "Nav firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :revolve :order 0 :name "body"
                    :x 0 :y 0 :z 0 :r 170 :h 90})
      (cad-feature {:id "lidar" :kind :boss :order 1 :name "lidar"
                    :x 0 :y 0 :z 90 :w 60 :h 20})
      (cad-feature {:id "wheel" :kind :revolve :order 2 :name "drive-wheel"
                    :x 100 :y 0 :z 20 :r 30 :h 20})]})

   (product
    {:id "prod.stem-robot-kit"
     :name "STEM education robot kit"
     :unspsc "60141000"
     :sector :education
     :gltf-ref "asset://unspsc/60/stem-robot-kit.glb"
     :physics {:mass-kg 1.2 :bbox-mm [300 200 80] :density-g-cm3 0.8
               :material-class :mixed}
     :components
     [(component {:id "part.board" :name "Controller board" :unspsc "32101500"
                  :qty 1 :mass-kg 0.05 :material :fr4 :role :assembly})
      (component {:id "part.servos" :name "Micro servos" :unspsc "26101500"
                  :qty 4 :mass-kg 0.04 :material :electronics :role :part})
      (component {:id "part.chassis-r" :name "Chassis kit" :unspsc "24112400"
                  :qty 1 :mass-kg 0.3 :material :polymer :role :assembly})
      (component {:id "part.manual" :name "Lesson guide" :unspsc "55101500"
                  :qty 1 :mass-kg 0.1 :material :paper :role :part})
      (component {:id "sw.stem" :name "Block coding IDE" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "case" :kind :extrude :order 0 :name "kit-case"
                    :x 0 :y 0 :z 0 :w 300 :h 80})
      (cad-feature {:id "chassis" :kind :boss :order 1 :name "chassis"
                    :x 0 :y 0 :z 80 :w 150 :h 40})
      (cad-feature {:id "wheel-r" :kind :revolve :order 2 :name "wheel"
                    :x 60 :y 0 :z 40 :r 25 :h 15})]})

   ;; ── densify-5 curated :blueprint (target density ≥5) ──
   (product
    {:id "prod.wifi6-ap"
     :name "Wi-Fi 6 enterprise AP"
     :unspsc "43222615"
     :brand "demo-net"
     :sector :electronics
     :gltf-ref "asset://unspsc/43/wifi6-ap.glb"
     :physics {:mass-kg 0.85 :bbox-mm [200 200 45] :density-g-cm3 1.2
               :material-class :electronics}
     :components
     [(component {:id "part.soc-ap" :name "Wi-Fi SoC" :unspsc "32101604"
                  :qty 1 :mass-kg 0.008 :material :silicon :role :part})
      (component {:id "part.ant-ap" :name "Internal antennas" :unspsc "43191500"
                  :qty 4 :mass-kg 0.02 :material :electronics :role :part})
      (component {:id "part.poe-ap" :name "PoE PD board" :unspsc "32101500"
                  :qty 1 :mass-kg 0.05 :material :fr4 :role :assembly})
      (component {:id "part.shell-ap" :name "Ceiling shell" :unspsc "24112400"
                  :qty 1 :mass-kg 0.35 :material :polymer :role :assembly})
      (component {:id "sw.ap" :name "AP firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "shell" :kind :revolve :order 0 :name "shell"
                    :x 0 :y 0 :z 0 :r 100 :h 40})
      (cad-feature {:id "mount" :kind :boss :order 1 :name "mount"
                    :x 0 :y 0 :z 0 :w 80 :h 10})
      (cad-feature {:id "led" :kind :boss :order 2 :name "status"
                    :x 0 :y 40 :z 40 :w 15 :h 2})]})

   (product
    {:id "prod.torque-wrench-digital"
     :name "Digital torque wrench 1/2in"
     :unspsc "27112718"
     :sector :tools
     :gltf-ref "asset://unspsc/27/torque-wrench-digital.glb"
     :physics {:mass-kg 1.4 :bbox-mm [450 50 40] :density-g-cm3 4.0
               :material-class :steel}
     :components
     [(component {:id "part.beam-tw" :name "Wrench beam" :unspsc "27112700"
                  :qty 1 :mass-kg 0.7 :material :steel :role :part})
      (component {:id "part.head-tw" :name "Ratchet head" :unspsc "27112700"
                  :qty 1 :mass-kg 0.25 :material :steel :role :part})
      (component {:id "part.strain" :name "Strain gauge" :unspsc "41111900"
                  :qty 1 :mass-kg 0.01 :material :electronics :role :part})
      (component {:id "part.disp-tw" :name "LCD module" :unspsc "32121509"
                  :qty 1 :mass-kg 0.03 :material :electronics :role :part})
      (component {:id "sw.torque" :name "Torque firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "beam" :kind :extrude :order 0 :name "beam"
                    :x 0 :y 0 :z 0 :w 450 :h 20})
      (cad-feature {:id "head" :kind :revolve :order 1 :name "head"
                    :x -200 :y 0 :z 0 :r 25 :h 40})
      (cad-feature {:id "display" :kind :boss :order 2 :name "display"
                    :x 50 :y 0 :z 20 :w 40 :h 8})]})

   (product
    {:id "prod.breaker-panel-3ph"
     :name "3-phase breaker panel 100A"
     :unspsc "39121600"
     :sector :electrical
     :gltf-ref "asset://unspsc/39/breaker-panel-3ph.glb"
     :physics {:mass-kg 12.0 :bbox-mm [400 250 120] :density-g-cm3 2.5
               :material-class :steel}
     :components
     [(component {:id "part.breakers" :name "MCB breakers" :unspsc "39121600"
                  :qty 12 :mass-kg 0.2 :material :electronics :role :part})
      (component {:id "part.busbar" :name "Copper busbar" :unspsc "39121600"
                  :qty 3 :mass-kg 0.8 :material :copper :role :part})
      (component {:id "part.encl" :name "Steel enclosure" :unspsc "24112400"
                  :qty 1 :mass-kg 6 :material :steel :role :assembly})
      (component {:id "part.din-rail" :name "DIN rails" :unspsc "30171500"
                  :qty 2 :mass-kg 0.3 :material :steel :role :part})
      (component {:id "sw.panel" :name "Panel monitor FW" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "encl" :kind :extrude :order 0 :name "enclosure"
                    :x 0 :y 0 :z 0 :w 400 :h 120})
      (cad-feature {:id "door" :kind :boss :order 1 :name "door"
                    :x 0 :y 0 :z 120 :w 380 :h 5})
      (cad-feature {:id "breaker" :kind :boss :order 2 :name "breaker-row"
                    :x 0 :y 0 :z 60 :w 300 :h 40})]})

   (product
    {:id "prod.apiary-scale"
     :name "Hive under-scale IoT"
     :unspsc "10151515"
     :sector :agriculture
     :gltf-ref "asset://unspsc/10/apiary-scale.glb"
     :physics {:mass-kg 4.5 :bbox-mm [500 400 80] :density-g-cm3 1.5
               :material-class :mixed}
     :components
     [(component {:id "part.loadcell" :name "Load cells" :unspsc "41111900"
                  :qty 4 :mass-kg 0.15 :material :steel :role :part})
      (component {:id "part.frame-sc" :name "Scale frame" :unspsc "30103600"
                  :qty 1 :mass-kg 2.5 :material :steel :role :assembly})
      (component {:id "part.radio-sc" :name "LoRa node" :unspsc "43191500"
                  :qty 1 :mass-kg 0.05 :material :electronics :role :part})
      (component {:id "part.plat" :name "Hive platform" :unspsc "11120000"
                  :qty 1 :mass-kg 1.0 :material :wood :role :part})
      (component {:id "sw.hive" :name "Hive telemetry FW" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "frame" :kind :extrude :order 0 :name "frame"
                    :x 0 :y 0 :z 0 :w 500 :h 40})
      (cad-feature {:id "platform" :kind :boss :order 1 :name "platform"
                    :x 0 :y 0 :z 40 :w 480 :h 20})
      (cad-feature {:id "cell" :kind :revolve :order 2 :name "load-cell"
                    :x 200 :y 150 :z 20 :r 20 :h 30})]})

   (product
    {:id "prod.thermal-imager"
     :name "Handheld thermal imager"
     :unspsc "73101515"
     :sector :industrial-services
     :gltf-ref "asset://unspsc/73/thermal-imager.glb"
     :physics {:mass-kg 0.55 :bbox-mm [220 90 80] :density-g-cm3 1.4
               :material-class :electronics}
     :components
     [(component {:id "part.sensor-ir" :name "IR microbolometer" :unspsc "41111900"
                  :qty 1 :mass-kg 0.03 :material :electronics :role :part})
      (component {:id "part.lens-ir" :name "IR lens" :unspsc "41111900"
                  :qty 1 :mass-kg 0.04 :material :germanium :role :part})
      (component {:id "part.disp-ir" :name "LCD viewfinder" :unspsc "32121509"
                  :qty 1 :mass-kg 0.06 :material :electronics :role :part})
      (component {:id "part.body-ir" :name "Grip housing" :unspsc "24112400"
                  :qty 1 :mass-kg 0.25 :material :polymer :role :assembly})
      (component {:id "sw.therm" :name "Thermography FW" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 220 :h 80})
      (cad-feature {:id "lens" :kind :revolve :order 1 :name "lens"
                    :x -90 :y 0 :z 40 :r 20 :h 30})
      (cad-feature {:id "screen" :kind :boss :order 2 :name "screen"
                    :x 40 :y 0 :z 80 :w 70 :h 5})]})

   ;; ── wave-5 goods: complete remaining goods segments <70 ──
   (product
    {:id "prod.silicone-sheet"
     :name "Silicone rubber sheet roll"
     :unspsc "13111000"
     :sector :elastomers
     :gltf-ref "asset://unspsc/13/silicone-sheet.glb"
     :physics {:mass-kg 25.0 :bbox-mm [1000 200 200] :density-g-cm3 1.2
               :material-class :rubber}
     :components
     [(component {:id "part.silicone" :name "Silicone compound" :unspsc "13111000"
                  :qty 1 :mass-kg 22 :material :rubber :role :material})
      (component {:id "part.core" :name "Cardboard core" :unspsc "14111500"
                  :qty 1 :mass-kg 0.5 :material :paper :role :packaging})
      (component {:id "part.wrap-s" :name "PE wrap" :unspsc "24121500"
                  :qty 1 :mass-kg 0.2 :material :polymer :role :packaging})
      (component {:id "part.tag-s" :name "Spec tag" :unspsc "14111800"
                  :qty 1 :mass-kg 0.01 :material :paper :role :part})]
     :features
     [(cad-feature {:id "roll" :kind :revolve :order 0 :name "roll"
                    :x 0 :y 0 :z 0 :r 100 :h 1000})
      (cad-feature {:id "core" :kind :revolve :order 1 :name "core"
                    :x 0 :y 0 :z 0 :r 30 :h 1000})
      (cad-feature {:id "wrap" :kind :boss :order 2 :name "wrap"
                    :x 0 :y 0 :z 500 :w 200 :h 5})]})

   (product
    {:id "prod.drill-bit-set"
     :name "Rock drill bit set"
     :unspsc "20111600"
     :sector :mining
     :gltf-ref "asset://unspsc/20/drill-bit-set.glb"
     :physics {:mass-kg 8.5 :bbox-mm [400 250 100] :density-g-cm3 7.5
               :material-class :steel}
     :components
     [(component {:id "part.bits" :name "Tungsten bits" :unspsc "20111600"
                  :qty 6 :mass-kg 0.8 :material :carbide :role :part})
      (component {:id "part.holders-d" :name "Bit holders" :unspsc "20111600"
                  :qty 2 :mass-kg 1.2 :material :steel :role :part})
      (component {:id "part.case-d" :name "Steel case" :unspsc "24120000"
                  :qty 1 :mass-kg 2.0 :material :steel :role :packaging})
      (component {:id "part.oil" :name "Thread compound" :unspsc "15121500"
                  :qty 1 :mass-kg 0.2 :material :chemical :role :material})]
     :features
     [(cad-feature {:id "case" :kind :extrude :order 0 :name "case"
                    :x 0 :y 0 :z 0 :w 400 :h 100})
      (cad-feature {:id "bit" :kind :revolve :order 1 :name "bit"
                    :x -100 :y 0 :z 100 :r 15 :h 200})
      (cad-feature {:id "holder" :kind :boss :order 2 :name "holder"
                    :x 100 :y 0 :z 50 :w 60 :h 40})]})

   (product
    {:id "prod.mirrorless-camera"
     :name "Mirrorless camera body"
     :unspsc "45121500"
     :sector :photo-av
     :gltf-ref "asset://unspsc/45/mirrorless-camera.glb"
     :physics {:mass-kg 0.45 :bbox-mm [130 95 70] :density-g-cm3 1.8
               :material-class :electronics}
     :components
     [(component {:id "part.sensor-c" :name "CMOS sensor" :unspsc "32101604"
                  :qty 1 :mass-kg 0.01 :material :silicon :role :part})
      (component {:id "part.shutter" :name "Shutter unit" :unspsc "45121500"
                  :qty 1 :mass-kg 0.05 :material :steel :role :part})
      (component {:id "part.body-c" :name "Magnesium body" :unspsc "30171500"
                  :qty 1 :mass-kg 0.2 :material :aluminum :role :assembly})
      (component {:id "part.batt-c" :name "Camera battery" :unspsc "26111710"
                  :qty 1 :mass-kg 0.08 :material :li-ion :role :part})
      (component {:id "sw.cam" :name "Camera firmware" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 130 :h 70})
      (cad-feature {:id "mount" :kind :revolve :order 1 :name "lens-mount"
                    :x -50 :y 0 :z 35 :r 30 :h 15})
      (cad-feature {:id "lcd" :kind :boss :order 2 :name "rear-lcd"
                    :x 30 :y 0 :z 70 :w 70 :h 3})]})

   (product
    {:id "prod.floor-scrubber"
     :name "Walk-behind floor scrubber"
     :unspsc "47121800"
     :sector :cleaning
     :gltf-ref "asset://unspsc/47/floor-scrubber.glb"
     :physics {:mass-kg 85.0 :bbox-mm [1200 600 1100] :density-g-cm3 1.2
               :material-class :mixed}
     :components
     [(component {:id "part.brush" :name "Scrub brushes" :unspsc "47121800"
                  :qty 2 :mass-kg 3 :material :polymer :role :part})
      (component {:id "part.tank" :name "Solution tank" :unspsc "24121500"
                  :qty 1 :mass-kg 8 :material :polymer :role :assembly})
      (component {:id "part.motor-f" :name "Drive motor" :unspsc "26101500"
                  :qty 1 :mass-kg 12 :material :steel :role :part})
      (component {:id "part.batt-f" :name "Traction battery" :unspsc "26111710"
                  :qty 1 :mass-kg 25 :material :li-ion :role :part})
      (component {:id "sw.scrub" :name "Scrubber controller" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 200 :w 800 :h 600})
      (cad-feature {:id "brush" :kind :revolve :order 1 :name "brush"
                    :x 0 :y 0 :z 0 :r 200 :h 80})
      (cad-feature {:id "handle" :kind :boss :order 2 :name "handle"
                    :x -400 :y 0 :z 800 :w 100 :h 300})]})

   (product
    {:id "prod.commercial-oven"
     :name "Commercial convection oven"
     :unspsc "48101500"
     :sector :foodservice
     :gltf-ref "asset://unspsc/48/commercial-oven.glb"
     :physics {:mass-kg 95.0 :bbox-mm [900 800 700] :density-g-cm3 1.5
               :material-class :steel}
     :components
     [(component {:id "part.chamber" :name "Oven chamber" :unspsc "48101500"
                  :qty 1 :mass-kg 40 :material :steel :role :assembly})
      (component {:id "part.heater" :name "Heating elements" :unspsc "39121000"
                  :qty 3 :mass-kg 2 :material :steel :role :part})
      (component {:id "part.fan-o" :name "Convection fan" :unspsc "40101600"
                  :qty 1 :mass-kg 3 :material :steel :role :part})
      (component {:id "part.ctrl" :name "Control board" :unspsc "32101500"
                  :qty 1 :mass-kg 0.5 :material :electronics :role :assembly})
      (component {:id "sw.oven" :name "Oven controller FW" :unspsc "43230000"
                  :qty 1 :role :software})]
     :features
     [(cad-feature {:id "body" :kind :extrude :order 0 :name "body"
                    :x 0 :y 0 :z 0 :w 900 :h 700})
      (cad-feature {:id "door" :kind :boss :order 1 :name "door"
                    :x 0 :y 400 :z 50 :w 800 :h 600})
      (cad-feature {:id "knob" :kind :revolve :order 2 :name "control"
                    :x 350 :y 350 :z 700 :r 20 :h 30})]})

   (product
    {:id "prod.textbook-set"
     :name "Printed textbook set (class pack)"
     :unspsc "55101500"
     :sector :published
     :gltf-ref "asset://unspsc/55/textbook-set.glb"
     :physics {:mass-kg 12.0 :bbox-mm [400 300 250] :density-g-cm3 0.7
               :material-class :paper}
     :components
     [(component {:id "part.books" :name "Textbooks" :unspsc "55101500"
                  :qty 30 :mass-kg 0.35 :material :paper :role :part})
      (component {:id "part.carton-t" :name "Shipping carton" :unspsc "24121500"
                  :qty 1 :mass-kg 0.8 :material :paper :role :packaging})
      (component {:id "part.wrap-t" :name "Shrink wrap" :unspsc "24121500"
                  :qty 1 :mass-kg 0.1 :material :polymer :role :packaging})
      (component {:id "part.label-t" :name "ISBN labels" :unspsc "14111800"
                  :qty 30 :mass-kg 0.001 :material :paper :role :part})]
     :features
     [(cad-feature {:id "carton" :kind :extrude :order 0 :name "carton"
                    :x 0 :y 0 :z 0 :w 400 :h 250})
      (cad-feature {:id "book" :kind :boss :order 1 :name "book-stack"
                    :x 0 :y 0 :z 50 :w 300 :h 150})
      (cad-feature {:id "label" :kind :boss :order 2 :name "label"
                    :x 150 :y 0 :z 250 :w 100 :h 2})]})])

(def curated-blueprint-segments
  "Open-business curated UNSPSC segments that should each have ≥1 twin."
  ["10" "27" "39" "43" "73"])

(def seed-traffic-segments
  "High-traffic :spec segments from uchiwake seed/fixture that should have twins
  for graph twin-segment coverage (not registry maturity promotion)."
  ["25" "26" "50" "51" "53"])

(def wave2-goods-segments
  "Second-wave goods segments for registry twin breadth (stay :spec until
  blueprint repos exist). Structures / electronic components / lab / medical /
  office / furniture."
  ["30" "32" "41" "42" "44" "56"])

(def wave3-goods-segments
  "Third-wave goods segments: chemicals / fuels / construction machinery /
  material handling / manufacturing components / HVAC distribution."
  ["12" "15" "22" "24" "31" "40"])

(def wave4-goods-segments
  "Fourth-wave goods segments: textile materials / paper / farming machinery /
  industrial machinery / security / domestic appliances / education kits."
  ["11" "14" "21" "23" "46" "52" "60"])

(def wave5-goods-segments
  "Fifth-wave goods: complete remaining goods segments <70
  (elastomers / mining / photo-AV / cleaning / foodservice / published)."
  ["13" "20" "45" "47" "48" "55"])

;; Soft depth targets for scorecard (catalog densification goals).
(def ^:private target-mean-sbom-lines 3.5)
(def ^:private target-mean-cad-features 2.4)
(def ^:private target-curated-density 5.0)

(defn coverage-entities
  "Uchiwake-shaped entity vector for bulk import: every twin as a product
  with a representative brand-owner. Lifts brand-owner coverage and
  open-business blueprint routes when imported into product-party."
  []
  (mapv #(->product-party-entity % true) catalog))

(defn by-id
  ([] (into {} (map (juxt :product/id identity) catalog)))
  ([id] (get (by-id) (str id))))

(defn by-segment
  [seg]
  (let [s (unspsc-segment seg)]
    (filterv #(= s (:product/unspsc-segment %)) catalog)))

(defn by-unspsc
  "Products whose commodity equals `code`, or (when `code` is a 2-digit segment)
  all twins in that segment."
  [code]
  (let [digits (some-> code str (str/replace #"[^0-9]" "") not-empty)]
    (cond
      (nil? digits) []
      (= 2 (count digits))
      (by-segment digits)
      :else
      (filterv #(= digits (:product/unspsc %)) catalog))))

(defn- by-alias
  "Find twin that lists `id` in `:product/aliases`."
  [id]
  (when (seq id)
    (first (filter (fn [t] (some #{id} (:product/aliases t))) catalog))))

(defn resolve-twin
  "Best-effort twin for a product map, id string, or commodity code.

  Match order:
  1. exact `:product/id`
  2. `:product/aliases` (seed/GTIN ids mapped onto catalog twins) → conf 1.0
  3. exact 8-digit commodity (`:product/unspsc`) → conf 0.8
  4. 2-digit segment (first twin in catalog for that segment) → conf 0.5

  Returns `{:twin … :match :id|:alias|:commodity|:segment :confidence …}`
  or nil when nothing matches."
  [product-or-id]
  (let [m (cond (map? product-or-id) product-or-id
                (string? product-or-id) {:product/id product-or-id}
                :else nil)
        id (some-> m :product/id str)
        code (or (some-> m :product/unspsc str not-empty)
                 (some-> m :unspsc str not-empty)
                 (when (and (string? product-or-id)
                            (re-matches #"\d{2,}" product-or-id))
                   product-or-id))
        seg (or (unspsc-segment code)
                (some-> m :product/unspsc-segment str))]
    (or (when-let [t (and id (by-id id))]
          {:twin t :match :id :confidence 1.0})
        (when-let [t (and id (by-alias id))]
          {:twin t :match :alias :confidence 1.0})
        (when-let [t (and code (>= (count (str/replace (str code) #"[^0-9]" "")) 8)
                          (first (by-unspsc code)))]
          {:twin t :match :commodity :confidence 0.8})
        (when-let [t (and seg (first (by-segment seg)))]
          {:twin t :match :segment :confidence 0.5}))))

(defn- clamp01 [x]
  (max 0.0 (min 1.0 (double x))))

(defn maturity-scorecard
  "Aggregate operator maturity dims into a 0–100 score.

  Inputs may be a graph-routing-coverage map and optional brand-owner coverage
  (0–1). Dimensions are equally weighted soft gates already used by doctor.
  Optional twin-depth dims (mean SBOM/CAD vs targets) lift when catalog densifies."
  ([uob] (maturity-scorecard uob nil))
  ([uob brand-owner-coverage]
   (let [mean-sbom (double (:product-twin-mean-sbom-lines uob 0))
         mean-cad (double (:product-twin-mean-cad-features uob 0))
         depth-sbom (when (pos? mean-sbom)
                      (clamp01 (/ mean-sbom target-mean-sbom-lines)))
         depth-cad (when (pos? mean-cad)
                     (clamp01 (/ mean-cad target-mean-cad-features)))
         wave2 (double (:wave2-goods-coverage uob 0))
         wave3 (double (:wave3-goods-coverage uob 0))
         wave4 (double (:wave4-goods-coverage uob 0))
         wave5 (double (:wave5-goods-coverage uob 0))
         dens (double (:curated-blueprint-density uob 0))
         ;; Density soft gate: 1.0 at ≥ target-curated-density twins/segment.
         dens-score (when (pos? dens) (clamp01 (/ dens target-curated-density)))
         dims (cond-> {:product-twin (double (:product-twin-coverage uob 0))
                       :high-confidence (double (:product-twin-high-confidence-coverage uob 0))
                       :mean-confidence (double (:product-twin-mean-confidence uob 0))
                       :twin-segment (double (:twin-segment-coverage uob 0))
                       :operator-ready (double (:operator-ready-coverage uob 0))
                       :registry-known (double (:registry-known-coverage uob 0))
                       :wave2-goods wave2
                       :wave3-goods wave3
                       :wave4-goods wave4
                       :wave5-goods wave5}
                dens-score (assoc :curated-density dens-score)
                (number? brand-owner-coverage)
                (assoc :brand-owner (double brand-owner-coverage))
                depth-sbom (assoc :twin-depth-sbom depth-sbom)
                depth-cad (assoc :twin-depth-cad depth-cad))
         n (count dims)
         score (if (pos? n)
                 (* 100.0 (/ (reduce + 0.0 (vals dims)) n))
                 0.0)
         grade (cond (>= score 95) :A
                     (>= score 85) :B
                     (>= score 70) :C
                     (>= score 50) :D
                     :else :F)]
     {:score score
      :grade grade
      :dims dims
      :product-twin-by-match (:product-twin-by-match uob)
      :mean-confidence (:product-twin-mean-confidence uob)
      :mean-sbom-lines mean-sbom
      :mean-cad-features mean-cad})))

(defn catalog-summary
  "Operator-facing maturity of the twin catalog.

  `:curated-blueprint-coverage` is the fraction of open-business curated
  segments (10/27/39/43/73) that have at least one twin with SBOM+CAD+physics.
  Wave-2 goods + mean SBOM/CAD depth track registry breadth densification."
  []
  (let [segs (mapv :product/unspsc-segment catalog)
        seg-set (set segs)
        curated curated-blueprint-segments
        curated-hits (filterv seg-set curated)
        wave2 wave2-goods-segments
        wave2-hits (filterv seg-set wave2)
        wave3 wave3-goods-segments
        wave3-hits (filterv seg-set wave3)
        wave4 wave4-goods-segments
        wave4-hits (filterv seg-set wave4)
        wave5 wave5-goods-segments
        wave5-hits (filterv seg-set wave5)
        complete? (fn [p]
                    (and (seq (:product/sbom p))
                         (seq (:product/cad-features p))
                         (:product/physics p)))
        sbom-ns (map #(count (:product/sbom %)) catalog)
        cad-ns (map #(count (:product/cad-features %)) catalog)
        n (count catalog)
        mean-sbom (if (pos? n) (double (/ (reduce + 0 sbom-ns) n)) 0.0)
        mean-cad (if (pos? n) (double (/ (reduce + 0 cad-ns) n)) 0.0)
        curated-twin-n (count (filter #(contains? (set curated)
                                                  (:product/unspsc-segment %))
                                      catalog))]
    {:products n
     :segments (vec (sort seg-set))
     :segment-count (count seg-set)
     :with-sbom (count (filter #(seq (:product/sbom %)) catalog))
     :with-cad (count (filter #(seq (:product/cad-features %)) catalog))
     :with-physics (count (filter :product/physics catalog))
     :with-gltf-ref (count (filter :product/gltf-ref catalog))
     :with-full-twin (count (filter complete? catalog))
     :mean-sbom-lines mean-sbom
     :mean-cad-features mean-cad
     :curated-blueprint-segments curated
     :curated-blueprint-hits curated-hits
     :curated-blueprint-missing (filterv (complement seg-set) curated)
     :curated-blueprint-coverage
     (if (seq curated)
       (double (/ (count curated-hits) (count curated)))
       0.0)
     :curated-blueprint-twin-count curated-twin-n
     :curated-blueprint-density
     (if (seq curated)
       (double (/ curated-twin-n (count curated)))
       0.0)
     :seed-traffic-segments seed-traffic-segments
     :seed-traffic-hits (filterv seg-set seed-traffic-segments)
     :seed-traffic-missing (filterv (complement seg-set) seed-traffic-segments)
     :seed-traffic-coverage
     (if (seq seed-traffic-segments)
       (double (/ (count (filter seg-set seed-traffic-segments))
                  (count seed-traffic-segments)))
       0.0)
     :wave2-goods-segments wave2
     :wave2-goods-hits wave2-hits
     :wave2-goods-missing (filterv (complement seg-set) wave2)
     :wave2-goods-coverage
     (if (seq wave2)
       (double (/ (count wave2-hits) (count wave2)))
       0.0)
     :wave3-goods-segments wave3
     :wave3-goods-hits wave3-hits
     :wave3-goods-missing (filterv (complement seg-set) wave3)
     :wave3-goods-coverage
     (if (seq wave3)
       (double (/ (count wave3-hits) (count wave3)))
       0.0)
     :wave4-goods-segments wave4
     :wave4-goods-hits wave4-hits
     :wave4-goods-missing (filterv (complement seg-set) wave4)
     :wave4-goods-coverage
     (if (seq wave4)
       (double (/ (count wave4-hits) (count wave4)))
       0.0)
     :wave5-goods-segments wave5
     :wave5-goods-hits wave5-hits
     :wave5-goods-missing (filterv (complement seg-set) wave5)
     :wave5-goods-coverage
     (if (seq wave5)
       (double (/ (count wave5-hits) (count wave5)))
       0.0)
     :commodities (into (sorted-set) (map :product/unspsc catalog))
     :ids (mapv :product/id catalog)}))

(defn segment-twin-stats
  "Stats for one open-business segment entry (product twin maturity)."
  [seg]
  (let [twins (by-segment seg)
        n (count twins)]
    {:product-twins n
     :twin-ids (mapv :product/id twins)
     :has-sbom-twins? (and (pos? n) (every? #(seq (:product/sbom %)) twins))
     :has-cad-twins? (and (pos? n) (every? #(seq (:product/cad-features %)) twins))
     :has-physics-twins? (and (pos? n) (every? :product/physics twins))
     :total-sbom-lines (reduce + 0 (map #(count (:product/sbom %)) twins))
     :total-cad-features (reduce + 0 (map #(count (:product/cad-features %)) twins))}))
