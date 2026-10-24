(ns terrain.chunk
  "TerrainChunk: mesh generation from heightmap + splatmap.

  Restored from kotoba-lang/kami-engine's kami-terrain/src/chunk.rs (deleted in
  PR #82 \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root). Generates a triangle mesh
  with per-vertex normals and material weights; LOD support via stride (skip
  vertices for coarser mesh). A terrain vertex is a plain map
  {:position [x y z] :normal [nx ny nz] :uv [u v] :splat [g r s sn]}."
  (:require [terrain.heightmap :as heightmap]
            [terrain.splatmap :as splatmap]))

(defn generate-chunk-mesh
  "Generate a triangle mesh for a terrain chunk.

  `stride`: vertex skip for LOD (1 = full, 2 = half, 4 = quarter).
  `scale`: world-space distance between adjacent vertices at LOD 0.
  Returns {:vertices [...] :indices [...] :origin [x 0 z] :lod n}."
  [hm splat origin-x origin-z stride scale lod]
  (let [{:keys [width depth data]} hm
        step (max stride 1)
        cols (quot (- width 1) step)
        rows (quot (- depth 1) step)
        vertices (vec (for [row (range (inc rows))
                             col (range (inc cols))]
                         (let [hx (min (* col step) (dec width))
                               hz (min (* row step) (dec depth))
                               idx (+ (* hz width) hx)
                               h (nth data idx)
                               n (heightmap/normal hm hx hz)
                               sw (:weights (nth (:data splat) idx))
                               wx (+ origin-x (* (double col) step scale))
                               wz (+ origin-z (* (double row) step scale))]
                           {:position [wx h wz]
                            :normal n
                            :uv [(/ (double col) cols) (/ (double row) rows)]
                            :splat sw})))
        row-verts (inc cols)
        indices (vec (mapcat
                      (fn [row]
                        (mapcat
                         (fn [col]
                           (let [tl (+ (* row row-verts) col)
                                 tr (inc tl)
                                 bl (+ (* (inc row) row-verts) col)
                                 br (inc bl)]
                             ;; Triangle 1: tl, bl, tr ; Triangle 2: tr, bl, br
                             [tl bl tr tr bl br]))
                         (range cols)))
                      (range rows)))]
    {:vertices vertices
     :indices indices
     :origin [origin-x 0.0 origin-z]
     :lod lod}))
