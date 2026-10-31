(ns cae.sbse-block-mesh
  "Body-fitted multi-block Hex mesh for the NASA SBSE ideal test section."
  (:require [cae.sbse-geometry :as sbse]
            [kotoba.lang.text :as str]))

(defn- join-lines [xs] (str/join "\n" xs))
(defn- face [ids] (str "        (" (str/join " " ids) ")"))

(defn block-mesh-dict
  [{:keys [nx ny nz x-min-m x-max-m half-width-m top-m wall-normal-grading]
    :or {nx 24 ny 24 nz 12 x-min-m -0.9144 x-max-m 1.8288
         half-width-m 0.4572 top-m 0.9144 wall-normal-grading 20.0}}]
  (when-not (and (pos-int? nx) (pos-int? ny) (pos-int? nz)
                 (< x-min-m x-max-m) (pos? half-width-m) (pos? top-m)
                 (> wall-normal-grading 1.0))
    (throw (ex-info "valid positive SBSE block mesh controls are required" {})))
  (let [gx (inc nx) gz (inc nz)
        id (fn [level i j] (+ (* level gx gz) (* i gz) j))
        x-at (fn [i] (+ x-min-m (* i (/ (- x-max-m x-min-m) nx))))
        z-at (fn [j] (+ (- half-width-m) (* j (/ (* 2.0 half-width-m) nz))))
        vertices (for [level (range 2) i (range gx) j (range gz)
                       :let [x (x-at i) z (z-at j)
                             y (if (zero? level) (sbse/height-m x z) top-m)]]
                   (format "    (%.12f %.12f %.12f) // %d" x y z (id level i j)))
        blocks (for [i (range nx) j (range nz)
                     :let [b00 (id 0 i j) b10 (id 0 (inc i) j)
                           b11 (id 0 (inc i) (inc j)) b01 (id 0 i (inc j))
                           t00 (id 1 i j) t10 (id 1 (inc i) j)
                           t11 (id 1 (inc i) (inc j)) t01 (id 1 i (inc j))]]
                 (format "    hex (%d %d %d %d %d %d %d %d) (1 1 %d) simpleGrading (1 1 %.8f)"
                         b00 b01 b11 b10 t00 t01 t11 t10 ny wall-normal-grading))
        floor (for [i (range nx) j (range nz)]
                (face [(id 0 i j) (id 0 i (inc j)) (id 0 (inc i) (inc j)) (id 0 (inc i) j)]))
        ceiling (for [i (range nx) j (range nz)]
                  (face [(id 1 i j) (id 1 (inc i) j) (id 1 (inc i) (inc j)) (id 1 i (inc j))]))
        inlet (for [j (range nz)]
                (face [(id 0 0 j) (id 1 0 j) (id 1 0 (inc j)) (id 0 0 (inc j))]))
        outlet (for [j (range nz)]
                 (face [(id 0 nx j) (id 0 nx (inc j)) (id 1 nx (inc j)) (id 1 nx j)]))
        side-a (for [i (range nx)]
                 (face [(id 0 i 0) (id 0 (inc i) 0) (id 1 (inc i) 0) (id 1 i 0)]))
        side-b (for [i (range nx)]
                 (face [(id 0 i nz) (id 1 i nz) (id 1 (inc i) nz) (id 0 (inc i) nz)]))
        patch (fn [name type faces]
                (str "    " name "\n    {\n        type " type ";\n        faces\n        (\n"
                     (join-lines faces) "\n        );\n    }"))]
    {:format :sbse-block-mesh-v1 :nx nx :ny ny :nz nz
     :cells (* nx ny nz) :blocks (* nx nz) :vertices (* 2 gx gz)
     :dict (str "FoamFile\n{\n    format ascii;\n    class dictionary;\n    object blockMeshDict;\n}\n"
                "scale 1;\nvertices\n(\n" (join-lines vertices) "\n);\nblocks\n(\n"
                (join-lines blocks) "\n);\nedges ();\nboundary\n(\n"
                (str/join "\n" [(patch "inlet" "patch" inlet)
                                  (patch "outlet" "patch" outlet)
                                  (patch "floorBump" "wall" floor)
                                  (patch "ceiling" "wall" ceiling)
                                  (patch "sideA" "wall" side-a)
                                  (patch "sideB" "wall" side-b)])
                "\n);\nmergePatchPairs ();\n")}))

(defn layered-block-mesh-dict
  "Two wall-normal blocks: a thin surface-following low-Re layer and a smooth
  outer transition. This avoids the determinant collapse caused by applying
  extreme grading across the full tunnel height."
  [{:keys [nx ny nz x-min-m x-max-m half-width-m top-m wall-normal-grading
           boundary-layer-thickness-m boundary-layer-cells boundary-layer-grading]
    :or {x-min-m -0.9144 x-max-m 1.8288 half-width-m 0.4572 top-m 0.9144
         wall-normal-grading 10.0 boundary-layer-thickness-m 0.05
         boundary-layer-grading 500.0}}]
  (when-not (and (pos-int? nx) (pos-int? ny) (pos-int? nz)
                 (pos-int? boundary-layer-cells) (< boundary-layer-cells ny)
                 (< x-min-m x-max-m) (pos? half-width-m)
                 (< boundary-layer-thickness-m (- top-m 0.077724))
                 (> wall-normal-grading 1.0) (> boundary-layer-grading 1.0))
    (throw (ex-info "valid layered SBSE mesh controls are required" {})))
  (let [gx (inc nx) gz (inc nz) levels 3
        specs [{:cells boundary-layer-cells :grading boundary-layer-grading}
               {:cells (- ny boundary-layer-cells) :grading wall-normal-grading}]
        id (fn [level i j] (+ (* level gx gz) (* i gz) j))
        x-at (fn [i] (+ x-min-m (* i (/ (- x-max-m x-min-m) nx))))
        z-at (fn [j] (+ (- half-width-m) (* j (/ (* 2.0 half-width-m) nz))))
        vertices (for [level (range levels) i (range gx) j (range gz)
                       :let [x (x-at i) z (z-at j) floor-y (sbse/height-m x z)
                             y (case level 0 floor-y 1 (+ floor-y boundary-layer-thickness-m) top-m)]]
                   (format "    (%.12f %.12f %.12f) // %d" x y z (id level i j)))
        blocks (for [layer (range 2) i (range nx) j (range nz)
                     :let [{:keys [cells grading]} (nth specs layer)
                           b00 (id layer i j) b10 (id layer (inc i) j)
                           b11 (id layer (inc i) (inc j)) b01 (id layer i (inc j))
                           t00 (id (inc layer) i j) t10 (id (inc layer) (inc i) j)
                           t11 (id (inc layer) (inc i) (inc j)) t01 (id (inc layer) i (inc j))]]
                 (format "    hex (%d %d %d %d %d %d %d %d) (1 1 %d) simpleGrading (1 1 %.8f)"
                         b00 b01 b11 b10 t00 t01 t11 t10 cells grading))
        floor (for [i (range nx) j (range nz)]
                (face [(id 0 i j) (id 0 i (inc j)) (id 0 (inc i) (inc j)) (id 0 (inc i) j)]))
        ceiling (for [i (range nx) j (range nz)]
                  (face [(id 2 i j) (id 2 (inc i) j) (id 2 (inc i) (inc j)) (id 2 i (inc j))]))
        inlet (for [layer (range 2) j (range nz)]
                (face [(id layer 0 j) (id (inc layer) 0 j)
                       (id (inc layer) 0 (inc j)) (id layer 0 (inc j))]))
        outlet (for [layer (range 2) j (range nz)]
                 (face [(id layer nx j) (id layer nx (inc j))
                        (id (inc layer) nx (inc j)) (id (inc layer) nx j)]))
        side-a (for [layer (range 2) i (range nx)]
                 (face [(id layer i 0) (id layer (inc i) 0)
                        (id (inc layer) (inc i) 0) (id (inc layer) i 0)]))
        side-b (for [layer (range 2) i (range nx)]
                 (face [(id layer i nz) (id (inc layer) i nz)
                        (id (inc layer) (inc i) nz) (id layer (inc i) nz)]))
        patch (fn [name type faces]
                (str "    " name "\n    {\n        type " type ";\n        faces\n        (\n"
                     (join-lines faces) "\n        );\n    }"))]
    {:format :sbse-layered-block-mesh-v2 :nx nx :ny ny :nz nz :layers specs
     :cells (* nx ny nz) :blocks (* 2 nx nz) :vertices (* levels gx gz)
     :dict (str "FoamFile\n{\n    format ascii;\n    class dictionary;\n    object blockMeshDict;\n}\n"
                "scale 1;\nvertices\n(\n" (join-lines vertices) "\n);\nblocks\n(\n"
                (join-lines blocks) "\n);\nedges ();\nboundary\n(\n"
                (str/join "\n" [(patch "inlet" "patch" inlet) (patch "outlet" "patch" outlet)
                                  (patch "floorBump" "wall" floor) (patch "ceiling" "wall" ceiling)
                                  (patch "sideA" "wall" side-a) (patch "sideB" "wall" side-b)])
                "\n);\nmergePatchPairs ();\n")}))
