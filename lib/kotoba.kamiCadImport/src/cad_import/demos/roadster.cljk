(ns cad-import.demos.roadster
  "Miata-class roadster expressed as parametric SCAD primitives — the
   reference vehicle for ADR 2605051430. All shapes are etzhayyim-authored
   parametric (license MIT) so there's no third-party CAD licence
   question. Geometry is illustrative — wheelbase / track / panel
   proportions are roughly NA-Miata, but the dimensions are tuneable
   parameters at the top of `roadster-na`.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Ported 1:1 from the
   original `src/demos/roadster.rs`."
  (:require [kotoba.lang.text :as str]
            [cad-import.ingest.scad :as scad]))

(defn roadster-na []
  (let [wheelbase 2.27
        track-f 1.41
        track-r 1.43
        chassis-h 0.20
        belt-y 0.55
        roof-y 1.10

        scad-uri "scad://gftd/roadster-na/v0.1.0"
        scad-sha (apply str (repeat 64 "1"))
        prov {:uri scad-uri :sha256 scad-sha :license "MIT"}
        prov-part (fn [path] {:uri (str "scad://gftd/roadster-na/" path ".scad") :sha256 scad-sha :license "MIT"})
        supplier-gftd (fn [] {:name "gftd" :cpe "" :mpn ""})

        entity (fn [primitive transform annotation] {:primitive primitive :transform transform :annotation annotation})
        default-t (scad/default-transform)

        e1 (entity (scad/cube [track-f chassis-h (+ wheelbase 0.6)])
                    (scad/translate default-t 0.0 0.30 0.0)
                    {:part-id "chassis" :display-name "Chassis main + floor pan (HSS)"
                     :kind :chassis :material :steel-hss :mass-kg 180.0 :parent nil
                     :break-group nil :supplier (supplier-gftd) :revision "0.1.0"
                     :source (prov-part "chassis")})
        e2 (entity (scad/cube [track-f 0.05 0.08])
                    (scad/translate default-t 0.0 roof-y 0.20)
                    {:part-id "windshield_header" :display-name "Windshield header beam"
                     :kind :chassis :material :steel-hss :mass-kg 8.0 :parent "chassis"
                     :break-group nil :supplier (supplier-gftd) :revision "0.1.0"
                     :source (prov-part "windshield_header")})
        e3 (entity (scad/cube [(- track-f 0.1) 0.04 0.95])
                    (scad/translate default-t 0.0 (+ belt-y 0.18) (- (* wheelbase 0.5) 0.2))
                    {:part-id "hood" :display-name "Hood (aluminium sheet)"
                     :kind :body :material :aluminium-sheet :mass-kg 9.0 :parent "chassis"
                     :break-group nil :supplier (supplier-gftd) :revision "0.1.0"
                     :source (prov-part "hood")})
        e4 (entity (scad/cube [(- track-f 0.1) 0.05 0.85])
                    (scad/translate default-t 0.0 (+ belt-y 0.20) (- (* wheelbase 0.5)))
                    {:part-id "trunk" :display-name "Trunk lid"
                     :kind :body :material :steel-mild :mass-kg 12.0 :parent "chassis"
                     :break-group nil :supplier (supplier-gftd) :revision "0.1.0"
                     :source (prov-part "trunk")})

        door-entities
        (for [[id x nm src-path] [["door_l" (+ (- (* track-f 0.5)) 0.05) "Door (driver)" "door_l"]
                                    ["door_r" (- (* track-f 0.5) 0.05) "Door (passenger)" "door_r"]]]
          (entity (scad/cube [0.05 0.55 0.95])
                   (scad/translate default-t x (- belt-y 0.10) 0.0)
                   {:part-id id :display-name nm :kind :body :material :steel-mild
                    :mass-kg 15.0 :parent "chassis" :break-group nil
                    :supplier (supplier-gftd) :revision "0.1.0" :source (prov-part src-path)}))

        fender-entities
        (for [[id x nm] [["fender_fl" (- (* track-f 0.5)) "Front fender L"]
                          ["fender_fr" (* track-f 0.5) "Front fender R"]
                          ["fender_rl" (- (* track-r 0.5)) "Rear fender L"]
                          ["fender_rr" (* track-r 0.5) "Rear fender R"]]
              :let [z (if (str/includes? id "_f") (* wheelbase 0.5) (- (* wheelbase 0.5)))]]
          (entity (scad/cube [0.06 0.30 0.45])
                   (scad/translate default-t x (- belt-y 0.05) z)
                   {:part-id id :display-name nm :kind :body :material :steel-mild
                    :mass-kg 5.5 :parent "chassis" :break-group nil
                    :supplier (supplier-gftd) :revision "0.1.0" :source (prov-part id)}))

        e5 (entity (scad/cube [(- track-f 0.1) 0.55 0.05])
                    (scad/translate default-t 0.0 (+ belt-y 0.30) 0.45)
                    {:part-id "windshield" :display-name "Windshield (laminated)"
                     :kind :window :material :glass :mass-kg 8.5 :parent "chassis"
                     :break-group nil :supplier {:name "AGC" :cpe "" :mpn "AGC-RDST-NA"}
                     :revision "0.1.0" :source (prov-part "windshield")})
        e6 (entity (scad/cube [0.55 0.55 0.65])
                    (scad/translate default-t 0.0 0.55 0.95)
                    {:part-id "engine" :display-name "1.6L NA inline-4 block"
                     :kind :powertrain :material :aluminium-cast :mass-kg 102.0 :parent "chassis"
                     :break-group nil :supplier {:name "Mazda" :cpe "" :mpn "B6ZE-RS"}
                     :revision "0.1.0" :source (prov-part "engine_block")})
        e7 (entity (scad/cube [0.30 0.30 0.85])
                    (scad/translate default-t 0.0 0.45 0.20)
                    {:part-id "transmission" :display-name "5-speed manual gearbox"
                     :kind :powertrain :material :aluminium-cast :mass-kg 38.0 :parent "chassis"
                     :break-group nil :supplier {:name "Mazda" :cpe "" :mpn "M5-NA"}
                     :revision "0.1.0" :source (prov-part "transmission")})
        e8 (entity (scad/cube [0.40 0.25 0.40])
                    (scad/translate default-t 0.0 0.40 (+ (- (* wheelbase 0.5)) 0.15))
                    {:part-id "diff" :display-name "Open differential (rear)"
                     :kind :powertrain :material :aluminium-cast :mass-kg 26.0 :parent "chassis"
                     :break-group nil :supplier (supplier-gftd) :revision "0.1.0"
                     :source (prov-part "diff_rear")})
        frac-1-sqrt-2 (/ 1.0 (Math/sqrt 2.0))
        e9 (entity (scad/cylinder 1.40 0.04 0.04)
                    (-> default-t
                        (scad/translate 0.0 0.30 -0.40)
                        (scad/rotate-xyzw frac-1-sqrt-2 0.0 0.0 frac-1-sqrt-2))
                    {:part-id "driveshaft" :display-name "Propeller shaft"
                     :kind :powertrain :material :steel-hss :mass-kg 8.0 :parent "chassis"
                     :break-group nil :supplier (supplier-gftd) :revision "0.1.0"
                     :source (prov-part "driveshaft")})
        e10 (entity (scad/cube [0.35 0.20 0.50])
                     (scad/translate default-t 0.40 0.42 1.30)
                     {:part-id "battery" :display-name "12V battery"
                      :kind :electrical :material :li-ion :mass-kg 11.0 :parent "chassis"
                      :break-group nil :supplier {:name "Panasonic" :cpe "" :mpn "44B19L"}
                      :revision "0.1.0" :source (prov-part "battery")})
        e11 (entity (scad/cube [0.55 0.30 0.35])
                     (scad/translate default-t 0.0 0.40 1.50)
                     {:part-id "radiator" :display-name "Coolant radiator"
                      :kind :fluid :material :aluminium-sheet :mass-kg 6.5 :parent "chassis"
                      :break-group nil :supplier {:name "Denso" :cpe "" :mpn "DRA-1989-NA"}
                      :revision "0.1.0" :source (prov-part "radiator")})
        e12 (entity (scad/cube [0.55 0.20 0.45])
                     (scad/translate default-t 0.0 0.30 (- (* wheelbase 0.5)))
                     {:part-id "fuel_tank" :display-name "Fuel tank"
                      :kind :fluid :material :plastic :mass-kg 45.0 :parent "chassis"
                      :break-group nil :supplier (supplier-gftd) :revision "0.1.0"
                      :source (prov-part "fuel_tank")})

        strut-entities
        (for [[id x z nm] [["strut_fl" (+ (- (* track-f 0.5)) 0.05) (* wheelbase 0.5) "Strut FL"]
                            ["strut_fr" (- (* track-f 0.5) 0.05) (* wheelbase 0.5) "Strut FR"]
                            ["strut_rl" (+ (- (* track-r 0.5)) 0.05) (- (* wheelbase 0.5)) "Strut RL"]
                            ["strut_rr" (- (* track-r 0.5) 0.05) (- (* wheelbase 0.5)) "Strut RR"]]]
          (entity (scad/cylinder 0.40 0.04 0.04)
                   (scad/translate default-t x 0.40 z)
                   {:part-id id :display-name nm :kind :suspension :material :steel-hss
                    :mass-kg 7.5 :parent "chassis" :break-group nil
                    :supplier (supplier-gftd) :revision "0.1.0" :source (prov-part "strut")}))

        brake-entities
        (for [[id x z] [["brake_fl" (- (* track-f 0.5)) (* wheelbase 0.5)]
                         ["brake_fr" (* track-f 0.5) (* wheelbase 0.5)]
                         ["brake_rl" (- (* track-r 0.5)) (- (* wheelbase 0.5))]
                         ["brake_rr" (* track-r 0.5) (- (* wheelbase 0.5))]]]
          (entity (scad/cylinder 0.025 0.135 0.135)
                   (-> default-t
                       (scad/translate x 0.30 z)
                       (scad/rotate-xyzw 0.0 0.0 frac-1-sqrt-2 frac-1-sqrt-2))
                   {:part-id id :display-name (str "Brake disc " (last (str/split id #"_")))
                    :kind :brake :material :steel-mild :mass-kg 8.0 :parent "chassis"
                    :break-group nil :supplier {:name "Akebono" :cpe "" :mpn "ABK-NA-235"}
                    :revision "0.1.0" :source (prov-part "brake_disc")}))

        wheel-entities
        (for [[id x z] [["wheel_fl" (- (* track-f 0.5)) (* wheelbase 0.5)]
                         ["wheel_fr" (* track-f 0.5) (* wheelbase 0.5)]
                         ["wheel_rl" (- (* track-r 0.5)) (- (* wheelbase 0.5))]
                         ["wheel_rr" (* track-r 0.5) (- (* wheelbase 0.5))]]]
          (entity (scad/cylinder 0.18 0.30 0.30)
                   (-> default-t
                       (scad/translate x 0.30 z)
                       (scad/rotate-xyzw 0.0 0.0 frac-1-sqrt-2 frac-1-sqrt-2))
                   {:part-id id :display-name (str "Wheel + tire " id)
                    :kind :wheel :material :rubber :mass-kg 15.0 :parent "chassis"
                    :break-group nil :supplier {:name "Bridgestone" :cpe "" :mpn "ER300-185-60-R14"}
                    :revision "0.1.0" :source (prov-part "wheel")}))

        seat-entities
        (for [[id x nm] [["seat_l" -0.30 "Seat (driver)"] ["seat_r" 0.30 "Seat (passenger)"]]]
          (entity (scad/cube [0.50 0.95 0.55])
                   (scad/translate default-t x 0.65 -0.10)
                   {:part-id id :display-name nm :kind :interior :material :plastic
                    :mass-kg 18.0 :parent "chassis" :break-group nil
                    :supplier (supplier-gftd) :revision "0.1.0" :source (prov-part "seat")}))

        e-dash (entity (scad/cube [(- track-f 0.1) 0.18 0.30])
                        (scad/translate default-t 0.0 (+ belt-y 0.05) 0.50)
                        {:part-id "dashboard" :display-name "Dashboard"
                         :kind :interior :material :plastic :mass-kg 9.0 :parent "chassis"
                         :break-group nil :supplier (supplier-gftd) :revision "0.1.0"
                         :source (prov-part "dashboard")})

        entities (-> [e1 e2 e3 e4]
                      (into door-entities) (into fender-entities)
                      (conj e5 e6 e7 e8 e9 e10 e11 e12)
                      (into strut-entities) (into brake-entities) (into wheel-entities)
                      (into seat-entities) (conj e-dash))

        hp (fn [id from to pos kind] {:id id :from-part from :to-part to :position pos :kind kind})

        hps0 [(hp "hp_header" "chassis" "windshield_header" [0.0 roof-y 0.20] :weld)
              (hp "hp_hood" "chassis" "hood" [0.0 (+ belt-y 0.20) 1.55] :hinge)
              (hp "hp_trunk" "chassis" "trunk" [0.0 (+ belt-y 0.22) -0.95] :hinge)
              (hp "hp_door_l" "chassis" "door_l" [(+ (- (* track-f 0.5)) 0.05) 0.50 0.30] :hinge)
              (hp "hp_door_r" "chassis" "door_r" [(- (* track-f 0.5) 0.05) 0.50 0.30] :hinge)]

        hps-fenders (mapv (fn [fid] (hp (str "hp_" fid) "chassis" fid [0.0 (- belt-y 0.05) 0.0] :bolt))
                           ["fender_fl" "fender_fr" "fender_rl" "fender_rr"])

        hps1 [(hp "hp_windshield" "windshield_header" "windshield" [0.0 (- roof-y 0.05) 0.40] :adhesive)
              (hp "hp_engine_l" "chassis" "engine" [-0.20 0.45 0.95] :bolt)
              (hp "hp_engine_r" "chassis" "engine" [0.20 0.45 0.95] :bolt)
              (hp "hp_trans" "engine" "transmission" [0.0 0.45 0.55] :bolt)
              (hp "hp_driveshaft_f" "transmission" "driveshaft" [0.0 0.30 0.20] :bolt)
              (hp "hp_driveshaft_r" "driveshaft" "diff" [0.0 0.30 -0.95] :bolt)
              (hp "hp_radiator" "chassis" "radiator" [0.0 0.40 1.50] :bolt)
              (hp "hp_battery" "chassis" "battery" [0.40 0.42 1.30] :bolt)
              (hp "hp_fuel_tank" "chassis" "fuel_tank" [0.0 0.35 (- (* wheelbase 0.5))] :bolt)]

        wheel->strut {"wheel_fl" "strut_fl" "wheel_fr" "strut_fr" "wheel_rl" "strut_rl" "wheel_rr" "strut_rr"}
        wheel->brake {"wheel_fl" "brake_fl" "wheel_fr" "brake_fr" "wheel_rl" "brake_rl" "wheel_rr" "brake_rr"}
        hps-wheels (vec (mapcat
                          (fn [w]
                            (let [strut (wheel->strut w) brake (wheel->brake w)]
                              [(hp (str "hp_strut_" w) strut w [0.0 0.30 0.0] :press)
                               (hp (str "hp_strut_" strut "_chassis") "chassis" strut [0.0 0.55 0.0] :bolt)
                               (hp (str "hp_brake_" w) brake w [0.0 0.30 0.0] :bolt)]))
                          ["wheel_fl" "wheel_fr" "wheel_rl" "wheel_rr"]))

        hps2 [(hp "hp_seat_l" "chassis" "seat_l" [-0.30 0.30 -0.10] :bolt)
              (hp "hp_seat_r" "chassis" "seat_r" [0.30 0.30 -0.10] :bolt)
              (hp "hp_dashboard" "chassis" "dashboard" [0.0 belt-y 0.55] :bolt)]

        hps (-> hps0 (into hps-fenders) (into hps1) (into hps-wheels) (into hps2))

        [status result] (scad/from-annotated "scad-roadster-na" "etzhayyim SCAD Roadster NA" "0.1.0"
                                              prov entities hps)]
    (if (= status :error)
      (throw (ex-info "assembly validates" {:error result}))
      result)))
