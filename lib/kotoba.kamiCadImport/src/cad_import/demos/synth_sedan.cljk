(ns cad-import.demos.synth-sedan
  "9-part synthetic sedan — the original Phase 1 reference assembly,
   kept around as a tiny smoke-test that exercises every CDX field
   including supplier MPNs and the bidirectional dependency edges.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Ported 1:1 from the
   original `src/demos/synth_sedan.rs`."
  (:require [cad-import.part :as part]))

(defn synth-sedan []
  (let [scad-sha (apply str (repeat 64 "0"))
        prov (fn [uri] {:uri uri :sha256 scad-sha :license "MIT"})
        supplier-gftd (fn [] {:name "gftd" :cpe "" :mpn ""})

        a0 (-> (part/new-assembly "synth-sedan-na" (prov "scad://synth-sedan/v1.0.0"))
               (assoc :display-name "etzhayyim Synth Sedan NA")
               (assoc :revision "1.0.0"))

        a (-> a0
              (part/add-part {:id "chassis" :display-name "Chassis main rail + floor pan"
                               :kind :chassis :material :steel-hss
                               :aabb-min [-0.85 0.20 -2.20] :aabb-max [0.85 0.55 2.20]
                               :mass-kg 220.0 :parent nil :break-group nil
                               :source (prov "scad://synth-sedan/chassis.scad")
                               :supplier (supplier-gftd) :revision "1.0.0"})
              (part/add-part {:id "hood" :display-name "Hood (aluminium sheet)"
                               :kind :body :material :aluminium-sheet
                               :aabb-min [-0.80 0.70 1.20] :aabb-max [0.80 0.78 2.10]
                               :mass-kg 11.0 :parent "chassis" :break-group nil
                               :source (prov "scad://synth-sedan/hood.scad")
                               :supplier (supplier-gftd) :revision "1.0.0"})
              (part/add-part {:id "trunk" :display-name "Trunk lid"
                               :kind :body :material :steel-mild
                               :aabb-min [-0.80 0.85 -2.10] :aabb-max [0.80 0.93 -1.20]
                               :mass-kg 14.0 :parent "chassis" :break-group nil
                               :source (prov "scad://synth-sedan/trunk.scad")
                               :supplier (supplier-gftd) :revision "1.0.0"})
              (part/add-part {:id "windshield" :display-name "Windshield (laminated glass)"
                               :kind :window :material :glass
                               :aabb-min [-0.78 0.95 0.80] :aabb-max [0.78 1.45 1.20]
                               :mass-kg 15.0 :parent "chassis" :break-group nil
                               :source (prov "scad://synth-sedan/windshield.scad")
                               :supplier {:name "AGC" :cpe "" :mpn "AGC-WSH-1989-NA"} :revision "1.0.0"})
              (part/add-part {:id "engine" :display-name "1.6L NA engine block"
                               :kind :powertrain :material :aluminium-cast
                               :aabb-min [-0.30 0.45 1.30] :aabb-max [0.30 0.85 1.95]
                               :mass-kg 115.0 :parent "chassis" :break-group nil
                               :source (prov "scad://synth-sedan/engine.scad")
                               :supplier {:name "Mazda" :cpe "" :mpn "B6ZE-RS"} :revision "1.0.0"}))

        wheel-defs [["wheel_fl" -0.78 1.30] ["wheel_fr" 0.78 1.30]
                    ["wheel_rl" -0.78 -1.30] ["wheel_rr" 0.78 -1.30]]
        a (reduce (fn [a [i [id x z]]]
                    (part/add-part a {:id id :display-name (str "Wheel #" (inc i))
                                       :kind :wheel :material :rubber
                                       :aabb-min [(- x 0.12) 0.0 (- z 0.32)]
                                       :aabb-max [(+ x 0.12) 0.64 (+ z 0.32)]
                                       :mass-kg 18.0 :parent "chassis" :break-group nil
                                       :source (prov "scad://synth-sedan/wheel.scad")
                                       :supplier {:name "Bridgestone" :cpe "" :mpn "ER300-185-60-R14"}
                                       :revision "1.0.0"}))
                  a (map-indexed vector wheel-defs))

        a (-> a
              (part/add-hardpoint {:id "hp_hood" :from-part "chassis" :to-part "hood"
                                    :position [0.0 0.70 1.80] :kind :hinge})
              (part/add-hardpoint {:id "hp_trunk" :from-part "chassis" :to-part "trunk"
                                    :position [0.0 0.85 -1.50] :kind :hinge})
              (part/add-hardpoint {:id "hp_windshield" :from-part "chassis" :to-part "windshield"
                                    :position [0.0 0.95 1.00] :kind :adhesive})
              (part/add-hardpoint {:id "hp_engine_mount_l" :from-part "chassis" :to-part "engine"
                                    :position [-0.30 0.45 1.50] :kind :bolt})
              (part/add-hardpoint {:id "hp_engine_mount_r" :from-part "chassis" :to-part "engine"
                                    :position [0.30 0.45 1.50] :kind :bolt}))

        a (reduce (fn [a w]
                    (part/add-hardpoint a {:id (str "hp_" w) :from-part "chassis" :to-part w
                                            :position [0.0 0.30 0.0] :kind :bolt}))
                  a ["wheel_fl" "wheel_fr" "wheel_rl" "wheel_rr"])]
    a))
