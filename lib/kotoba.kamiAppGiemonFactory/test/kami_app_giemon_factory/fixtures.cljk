(ns kami-app-giemon-factory.fixtures
  "Small hand-authored synthetic fixtures for `kami-app-giemon-factory`'s
  tests.

  The original Rust crate's `scene.rs` loaded its data via `include_str!`
  from `70-tools/e7m-sim/scenes/giemon-factory-r0/{factory.scene,
  construction.order, clashes, robots}.json`. That dataset is not present
  anywhere in this monorepo checkout — confirmed absent by a tree search of
  the source commit (`a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa`) before this
  port began, not something this port failed to locate. Fabricating a
  plausible-looking \"real\" dataset would misrepresent the actual giemon
  factory plant, so this namespace instead ships a small synthetic factory
  (a four-wall/four-column building shell with one machine, one conveyor, one
  arm6 cell and one AGV), a 3-step construction order, a 2-robot roster, and
  2 engineering clashes — enough to exercise every ported function against
  the same *kinds* of properties the original Rust `#[cfg(test)]` suite
  checked, against synthetic data, not the real plant.")

(defn factory []
  {:factory/name "giemon-factory-r0-synthetic"
   :factory/bbox-m [0.0 0.0 40.0 20.0]
   :factory/site-bbox-m [-12.0 -12.0 52.0 32.0]
   :factory/walls [{:id "wall_n" :aabb [0.0 19.5 40.0 20.0] :height 6.0}
                   {:id "wall_s" :aabb [0.0 0.0 40.0 0.5] :height 6.0}
                   {:id "wall_e" :aabb [39.5 0.0 40.0 20.0] :height 6.0}
                   {:id "wall_w" :aabb [0.0 0.0 0.5 20.0] :height 6.0}]
   :factory/columns [{:id "col_1" :x 5.0 :y 5.0 :w 0.6 :height 6.0}
                     {:id "col_2" :x 35.0 :y 5.0 :w 0.6 :height 6.0}
                     {:id "col_3" :x 5.0 :y 15.0 :w 0.6 :height 6.0}
                     {:id "col_4" :x 35.0 :y 15.0 :w 0.6 :height 6.0}]
   :factory/beams [{:id "beam_1" :x 5.0 :span-y [0.0 20.0] :section 0.4 :z 6.0}]
   :factory/zones [{:id "zone_prod" :label "production" :rect [2.0 2.0 20.0 18.0] :tint [0.2 0.5 0.3]}]
   :factory/machines [{:id "mach_cnc_1" :kind "cnc-mill" :aabb [8.0 8.0 12.0 12.0] :height 2.4}]
   :factory/conveyors [{:id "conv_1" :path [[12.0 10.0] [30.0 10.0]] :width 0.8}]
   :factory/cells [{:id "cell_1" :urdf "giemon_arm6.urdf" :pos [10.0 10.0 0.0] :yaw 0.0}]
   :factory/agvs [{:id "agv_1" :pos [20.0 4.0 0.6] :yaw 0.0 :size [2.0 1.2 0.8] :mass 220.0}]
   :factory/service-nodes [{:id "svc_elec" :kind "受電" :aabb [-2.0 8.0 -0.5 10.0] :height 2.0}]
   :factory/utilities [{:id "util_water" :kind "water-supply" :path [[-2.0 9.0] [8.0 9.0]] :z 0.2 :width 0.15}]
   :factory/fixtures [{:id "lighting" :kind "luminaire" :size 0.5 :points [[10.0 5.0 5.5] [30.0 15.0 5.5]]}]
   :factory/site-pavements [{:id "site_drive" :kind "asphalt drive" :rect [-10.0 -10.0 50.0 -2.0]}]
   :factory/site-greens [{:id "site_green_1" :kind "green" :rect [-10.0 22.0 50.0 30.0]}]
   :factory/site-structures [{:id "site_fence" :kind "fence" :aabb [-12.0 -12.0 52.0 32.0] :height 1.8}]
   :factory/site-posts [{:id "site_poles" :kind "外灯ポール" :x -8.0 :y -8.0 :height 5.0}]})

(defn construction-order []
  {:order/of "giemon-factory-r0-synthetic"
   :order/steps
   [{:step/seq 1 :step/id "step-1" :step/name "site-prep" :step/trade "civil"
     :step/robot "robot:excavator" :step/zone "site" :step/duration-d 3.0
     :step/reveals ["ground" "site_fence"]}
    {:step/seq 2 :step/id "step-2" :step/name "foundation-steel" :step/trade "structural"
     :step/robot "robot:bolter" :step/zone "building" :step/duration-d 8.0
     :step/reveals ["floor" "col_1" "col_2" "col_3" "col_4" "wall_n" "wall_s" "wall_e" "wall_w"]}
    {:step/seq 3 :step/id "step-3" :step/name "machines-robots" :step/trade "install"
     :step/robot "robot:printer" :step/zone "production" :step/duration-d 4.0
     :step/reveals ["mach_cnc_1" "conv_1" "cell_1" "agv_1"]}]})

(defn robots []
  {:robots/robots
   [{:id "robot:printer" :name "Printer" :kind "gantry" :reach-m 6.0 :base [0.0 0.0]
     :cycle-min 12.0 :mobile false :process "deposition" :maturity "production"}
    {:id "robot:bolter" :name "Bolter" :kind "crane" :reach-m 20.0 :base [5.0 5.0]
     :cycle-min 30.0 :mobile true :process "thermal-weld" :maturity "production"}
    {:id "robot:excavator" :name "Excavator" :kind "tracked" :reach-m 8.0 :base [-5.0 -5.0]
     :cycle-min 45.0 :mobile true :process "none" :maturity "production"}]})

(defn clashes []
  {:clashes/of "giemon-factory-r0-synthetic"
   :clashes/clashes
   [{:id "clash-1" :kind "hard" :systems ["util_water" "col_1"] :x 4.0 :y 8.5 :z 0.2}
    {:id "clash-2" :kind "coordination" :systems ["util_water" "conv_1"] :x 12.0 :y 9.5 :z 0.2}]})
