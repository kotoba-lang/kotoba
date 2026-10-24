(ns kotoba.raytrace.vec3
  "Minimal Vec3 math — the portable subset of Rust `glam::Vec3` that kami-rt's
   BVH/AABB/triangle code (bvh.rs) needs. kami-rt depended on the external
   `glam` crate for this; kotoba.raytrace has no such crate on the classpath
   (and doesn't need one for two operators + a handful of vector ops), so
   this is a small from-scratch shim, not a port of any specific Rust file.

   A Vec3 is a plain 3-vector `[x y z]` so it round-trips through EDN and
   indexes the same way the Rust source indexes `self.min[a]` in a loop."
  (:require [kotoba.raytrace.mathx :as mathx]))

(defn v3 [x y z] [x y z])

(defn x [v] (v 0))
(defn y [v] (v 1))
(defn z [v] (v 2))

(defn splat [s] (v3 s s s))

(defn add [a b] (mapv + a b))
(defn sub [a b] (mapv - a b))
(defn mul [a b] (mapv * a b))
(defn div [a b] (mapv / a b))
(defn scale [v s] (mapv #(* % s) v))
(defn recip [v] (mapv #(/ 1.0 %) v))

(defn dot [a b] (reduce + (map * a b)))

(defn cross [a b]
  (v3 (- (* (y a) (z b)) (* (z a) (y b)))
      (- (* (z a) (x b)) (* (x a) (z b)))
      (- (* (x a) (y b)) (* (y a) (x b)))))

(defn vmin [a b] (mapv min a b))
(defn vmax [a b] (mapv max a b))

(defn clamp01 [v] (mapv #(mathx/clamp % 0.0 1.0) v))
