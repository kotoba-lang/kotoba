(ns kami.pipelines
  "Render pipelines as data (SSoT, ADR-2607102200 addendum 7).

   Open-world pipeline fields as EDN — the same way the web side describes its
   frame in kami.webgpu/default-graph. Repository-local gates keep committed
   fixtures in sync. Native adapters can consume this table from their own repos.

   Fields per pipeline: :shader, :cull (:back/:front/:none), :depth-write (bool),
   :depth-compare (:less/:less-equal/…), :blend (:none/:alpha)."
  (:require [kotoba.lang.text :as str]))

(def pipelines
  "The open-world render pipelines as pure data."
  {:terrain    {:shader "scene_terrain"    :cull :back :depth-write true  :depth-compare :less       :blend :none}
   :sky        {:shader "scene_sky"        :cull :none :depth-write false :depth-compare :less-equal :blend :none}
   :vegetation {:shader "scene_vegetation" :cull :none :depth-write true  :depth-compare :less       :blend :alpha}
   :character  {:shader "scene_character"  :cull :back :depth-write true  :depth-compare :less       :blend :none}
   :water      {:shader "scene_water"      :cull :none :depth-write false :depth-compare :less       :blend :alpha}
   :voxel      {:shader "scene_voxel"      :cull :back :depth-write true  :depth-compare :less       :blend :none}
   :particle   {:shader "scene_particle"  :cull :none :depth-write false :depth-compare :less       :blend :alpha}
   :atlas      {:shader "scene_atlas"     :cull :none :depth-write false :depth-compare :less       :blend :alpha}})

(def native-pipelines
  "Compatibility alias (webgpu fixture scripts historically required this name)."
  pipelines)

(def valid-culls #{:back :front :none})
(def valid-depth-compares #{:less :less-equal :greater :greater-equal :equal :always})
(def valid-blends #{:none :alpha})

(defn pipeline?
  [m]
  (and (map? m)
       (string? (:shader m))
       (contains? valid-culls (:cull m))
       (boolean? (:depth-write m))
       (contains? valid-depth-compares (:depth-compare m))
       (contains? valid-blends (:blend m))))

(defn valid?
  "True when every pipeline spec is structurally valid."
  [m]
  (and (map? m)
       (every? keyword? (keys m))
       (every? pipeline? (vals m))))

(defn spec
  "Return one pipeline spec by id."
  [id]
  (get pipelines id))

;; ── parse hand-written Rust into the same shape (drift gate for legacy native) ──
(defn- kw-cull [s] (case s "Back" :back "Front" :front :none))
(defn- kw-cmp  [s] (case s "Less" :less "LessEqual" :less-equal "Greater" :greater
                           "GreaterEqual" :greater-equal "Equal" :equal "Always" :always
                           (keyword (str/lower s))))

(defn parse-rust
  "Extract each native pipeline's varying fields from scene_pipelines.rs, keyed by shader.
   Slices the source into per-pipeline blocks at each shader include_str!, then takes each
   block's first cull/depth fields."
  [src]
  (let [blocks (rest (str/split src #"include_str!\(\"shaders/"))]
    (into {}
      (for [b blocks
            :let [sh (second (re-find #"^(scene_\w+)\.wgsl" b))]
            :when sh]
        [(keyword (str/replace sh "scene_" ""))
         {:shader sh
          :cull (if-let [m (re-find #"cull_mode:\s*Some\(wgpu::Face::(\w+)\)" b)] (kw-cull (second m)) :none)
          :depth-write (= "true" (second (re-find #"depth_write_enabled:\s*(true|false)" b)))
          :depth-compare (kw-cmp (second (re-find #"depth_compare:\s*wgpu::CompareFunction::(\w+)" b)))
          :blend (if (= "None" (second (re-find #"blend:\s*(None|Some)" b))) :none :alpha)}]))))
