(ns byoubu-gpu.shader
  "Tier 2: a `:byoubu/scene` compiled to WGSL, as data.

  The shader is built with `kami.wgsl` — the workspace's WGSL-as-data SSoT —
  not written as a string, for the same reason `liquid-glass.style` builds CSS
  from declaration maps: the program is a value, so a test can assert on the
  structure that produced it and a malformed shader is a malformed value
  rather than a runtime compile error in somebody's browser.

  This namespace is `.cljc` and has no browser dependency: it turns a scene
  spec into a WGSL source string, and can be tested on the JVM and on nbb
  without a GPU. `byoubu-gpu.core` is the thin browser half that hands the
  string to `kami.webgpu`.

  Structure constants are baked at generation time. `:ridge-count` is known
  from the spec, so the ridge loop is unrolled here rather than becoming a
  WGSL `for` over a uniform — a backdrop is not switched per frame, and a
  specialized shader is both simpler and exactly what \"the scene spec is the
  source\" means. Colours stay in the uniform so a theme can move them without
  a recompile."
  (:require [kami.wgsl :as w]))

;; ---------------------------------------------------------------------------
;; uniform layout
;;
;; Every field is a vec4 so std140 alignment is trivial and the packing code
;; in byoubu-gpu.uniforms is a flat float list with no padding rules to get
;; subtly wrong. 12 vec4 = 192 bytes.

(def uniform-fields
  "Ordered [field doc] pairs. `byoubu-gpu.uniforms/pack` walks the same vector,
  so the CPU-side layout cannot drift from the GPU-side struct."
  [[:sky-zenith  "palette :sky-zenith, rgb"]
   [:sky-mid     "palette :sky-mid"]
   [:sky-horizon "palette :sky-horizon"]
   [:haze        "palette :haze"]
   [:ridge-far   "palette :ridge-far"]
   [:ridge-near  "palette :ridge-near"]
   [:dune-lit    "palette :dune-lit"]
   [:dune-shadow "palette :dune-shadow"]
   [:star        "palette :star"]
   [:p0          "x horizon(0..1)  y vignette  z haze-density  w star-density"]
   [:p1          "x ridge-cycles   y dune-amp  z seed          w dune-cycles"]
   [:p2          "x time(s)        y aspect    z width         w height"]])

(def uniform-bytes (* 16 (count uniform-fields)))

(defn- struct-decl []
  (w/struct* :BU (for [[f _] uniform-fields] [f [:vec4 :f32]])))

;; ---------------------------------------------------------------------------
;; noise — the same value-noise/FBM shape terrain.noise uses on the CPU
;;
;; It is NOT bit-identical to terrain.noise: that one is a 32-bit integer hash
;; matched to the original Rust, and reproducing i32 wrapping semantics in
;; WGSL would be a second implementation to keep in sync for no visible gain.
;; What matches is the *construction* — hash-based value noise (deliberately
;; not gradient/Perlin, to stay clear of US10232272B2, same reasoning as
;; terrain.noise), cosine interpolation, and octaves at lacunarity 2 /
;; persistence 0.45. The poster and the live scene therefore read as the same
;; landscape without pretending to be the same pixels.

(defn- noise-funcs []
  [(w/func :hash21 {:params [[:p [:vec2 :f32]]] :ret :f32}
           [:let :h [:dot :p [:vec2 43.2371 91.7219]]]
           [:return [:fract [:* [:sin :h] 43758.5453]]])

   (w/func :cosint {:params [[:a :f32] [:b :f32] [:t :f32]] :ret :f32}
           ;; cosine interpolation, matching terrain.noise's smoothing
           [:let :f [:* 0.5 [:- 1.0 [:cos [:* :t 3.14159265]]]]]
           [:return [:mix :a :b :f]])

   (w/func :vnoise {:params [[:p [:vec2 :f32]]] :ret :f32}
           [:let :i [:floor :p]]
           [:let :f [:- :p :i]]
           [:let :a [:hash21 :i]]
           [:let :b [:hash21 [:+ :i [:vec2 1.0 0.0]]]]
           [:let :c [:hash21 [:+ :i [:vec2 0.0 1.0]]]]
           [:let :d [:hash21 [:+ :i [:vec2 1.0 1.0]]]]
           [:let :x0 [:cosint :a :b :f.x]]
           [:let :x1 [:cosint :c :d :f.x]]
           [:return [:cosint :x0 :x1 :f.y]])

   (w/func :fbm3 {:params [[:p [:vec2 :f32]]] :ret :f32}
           [:var :v 0.0]
           [:var :amp 1.0]
           [:var :freq 1.0]
           [:var :norm 0.0]
           [:for [:var :k [:i 0]] [:< :k [:i 3]] [:++ :k]
            [:set :v [:+ :v [:* :amp [:vnoise [:* :p :freq]]]]]
            [:set :norm [:+ :norm :amp]]
            [:set :amp [:* :amp 0.45]]
            [:set :freq [:* :freq 2.0]]]
           [:return [:/ :v :norm]])])

;; ---------------------------------------------------------------------------
;; scene geometry — mirrors byoubu.render.poster so the tiers agree

(defn horizon
  "Horizon as a 0..1 fraction of frame height, from the camera pitch. Same
  derivation as `byoubu.plate/horizon-pct` and `poster/horizon-y` — the three
  tiers put the skyline in one place."
  [backdrop]
  (let [pitch (or (get-in backdrop [:byoubu/scene :camera :pitch-deg]) 0.0)]
    (/ (max 40.0 (min 80.0 (- 62.0 (* 2.6 pitch)))) 100.0)))

(defn- ridge-fn
  "One ridge's height in uv space, as its own WGSL function: FBM across x,
  amplitude and base from the ridge's depth. `depth` is baked; the wavelength
  and amplitude arrive in the uniform so a scene can be retuned live."
  [depth ridge-count]
  (let [t     (/ (double depth) (max 1.0 (double (dec ridge-count))))
        ;; perspective compresses further ridges horizontally, as in the poster
        squash (- 1.0 (* 0.45 (/ (double depth) (max 1.0 (double ridge-count)))))]
    (w/func (keyword (str "ridge" depth)) {:params [[:x :f32]] :ret :f32}
            [:let :cycles [:* :u.p1.x squash]]
            [:let :n [:fbm3 [:vec2 [:+ [:* :x :cycles] (* 3.7 (inc depth))]
                             [:+ [:* 0.5 :u.p1.z] (* 11.0 depth)]]]]
            [:let :rise [:* [:* 0.075 :u.p1.y] (+ 0.30 (* 1.30 t))]]
            [:let :base [:+ :u.p0.x (* 0.020 t)]]
            [:return [:- :base [:* :rise [:- [:* 2.0 :n] 1.0]]]])))

(defn- ridge-color
  "Fill colour for ridge `depth`, mixed far→near and lifted toward haze by the
  scene's own haze density — atmospheric perspective, as in the poster."
  [depth ridge-count]
  (let [t    (/ (double depth) (max 1.0 (double (dec ridge-count))))
        lift (- 1.0 t)]
    [:mix [:mix :u.ridge-far.xyz :u.ridge-near.xyz t]
     :u.haze.xyz [:* [:* :u.p0.z 0.55] lift]]))

(defn- fragment [backdrop]
  (let [n (or (get-in backdrop [:byoubu/scene :terrain :ridge-count]) 3)]
    (apply
     w/func :fs {:stage :fragment :params [[:i :VO]] :ret [:loc 0 [:vec4 :f32]]}
     (concat
      [[:let :uv :i.uv]
       [:let :hz :u.p0.x]

       ;; --- sky: zenith → mid → horizon, the vertical structure every tier
       ;;     shares
       [:let :sky-t [:clamp [:/ :uv.y :hz] 0.0 1.0]]
       [:var :col [:mix [:mix :u.sky-zenith.xyz :u.sky-mid.xyz
                         [:clamp [:/ :sky-t 0.62] 0.0 1.0]]
                   :u.sky-horizon.xyz
                   [:smoothstep 0.62 1.0 :sky-t]]]

       ;; --- stars: hash lattice above the skyline, thinning toward it
       [:let :sp [:* :uv [:vec2 [:* 320.0 :u.p2.y] 320.0]]]
       [:let :sc [:hash21 [:+ [:floor :sp] [:* 7.0 :u.p1.z]]]]
       [:let :star-vis [:step [:- 1.0 [:* 0.02 :u.p0.w]] :sc]]
       [:let :above [:step :uv.y [:* :hz 0.98]]]
       ;; density falls off toward the horizon like the poster's squared draw
       [:let :depth-fade [:- 1.0 [:clamp [:/ :uv.y :hz] 0.0 1.0]]]
       [:set :col [:mix :col :u.star.xyz
                   [:* [:* [:* :star-vis :above] :depth-fade] 0.85]]]

       ;; --- horizon afterglow
       [:let :gd [:length [:* [:- :uv [:vec2 0.5 :hz]] [:vec2 [:* 0.9 :u.p2.y] 2.6]]]]
       [:let :glow [:* 0.85 [:- 1.0 [:smoothstep 0.0 1.0 :gd]]]]
       [:set :col [:mix :col :u.sky-horizon.xyz :glow]]

       ;; --- ground base below the skyline
       ;;
       ;; Filled with the FURTHEST ridge's colour, not :dune-shadow. A ridge
       ;; line oscillates around the horizon, so wherever it sits below hz the
       ;; base shows through — and a near-black base showed through as thin
       ;; dark slits along the skyline (seen on the GPU, 2026-08-03). Filling
       ;; with the far tone makes any such gap read as more distance.
       [:let :below [:step :hz :uv.y]]
       [:set :col [:mix :col
                   [:mix :u.ridge-far.xyz :u.haze.xyz [:* :u.p0.z 0.55]]
                   :below]]]

      ;; --- ridges, back to front (unrolled from :ridge-count)
      (for [d (range n)]
        ;; `[:ridgeN :uv.x]` is a call form — any head the DSL does not know is
        ;; emitted as a function call, so this stays a value rather than a
        ;; string with parentheses smuggled inside an identifier.
        [:set :col [:mix :col (ridge-color d n)
                    [:step [(keyword (str "ridge" d)) :uv.x] :uv.y]]])

      [;; --- near dune: fewer, broader forms, filled with the ground ramp
       [:let :fg-cycles [:* :u.p1.w 0.5]]
       [:let :fg-n [:fbm3 [:vec2 [:+ [:* :uv.x :fg-cycles] 91.0]
                           [:* 0.25 :u.p1.z]]]]
       [:let :fg-base [:+ :hz [:* [:- 1.0 :hz] 0.38]]]
       [:let :fg-y [:- :fg-base [:* [:* [:- 1.0 :hz] [:* 0.34 [:+ 0.4 :u.p1.y]]]
                                 [:- [:* 2.0 :fg-n] 1.0]]]]
       [:let :fg [:step :fg-y :uv.y]]
       [:let :fg-ramp [:clamp [:/ [:- :uv.y :fg-y] [:max 0.001 [:- 1.0 :fg-y]]] 0.0 1.0]]
       [:set :col [:mix :col [:mix :u.dune-lit.xyz :u.dune-shadow.xyz :fg-ramp] :fg]]

       ;; --- horizon haze, over the distances and under the near dune
       [:let :hb [:* [:- 1.0 [:smoothstep 0.0 0.11 [:abs [:- :uv.y [:+ :hz 0.02]]]]]
                  [:* 0.55 :u.p0.z]]]
       [:set :col [:mix :col :u.haze.xyz [:* :hb [:- 1.0 :fg]]]]

       ;; --- vignette, the grade's outermost darkening
       [:let :vd [:length [:* [:- :uv [:vec2 0.5 0.45]] [:vec2 [:* 1.1 :u.p2.y] 1.25]]]]
       [:set :col [:mix :col :u.dune-shadow.xyz
                   [:* :u.p0.y [:smoothstep 0.45 1.15 :vd]]]]

       [:return [:vec4 :col.x :col.y :col.z 1.0]]]))))

(defn wgsl
  "The complete WGSL source for a backdrop map.

  The vertex stage is a fullscreen triangle with uv.y = 0 at the TOP of the
  frame. That is stated explicitly and computed as `(1 - q.y) * 0.5` rather
  than inherited, because clip space is +Y up while every other tier here
  measures the horizon downward from the top — a silent disagreement there
  renders the sky underground."
  [backdrop]
  (apply w/shader
         (concat
          [(struct-decl)
           (w/binding* {:group 0 :binding 0 :space :uniform} :u :BU)
           (w/struct* :VO [[:clip [:vec4 :f32] {:builtin :position}]
                           [:uv [:vec2 :f32] {:location 0}]])
           (w/func :vs {:stage :vertex
                        :params [[:vid :u32 {:builtin :vertex-index}]]
                        :ret :VO}
                   "var p = array<vec2<f32>, 3>(vec2<f32>(-1.0, -3.0), vec2<f32>(-1.0, 1.0), vec2<f32>(3.0, 1.0))"
                   [:let :q "p[vid]"]
                   [:decl :o :VO]
                   [:set :o.clip [:vec4 :q.x :q.y 0.0 1.0]]
                   [:set :o.uv [:vec2 [:* [:+ :q.x 1.0] 0.5] [:* [:- 1.0 :q.y] 0.5]]]
                   [:return :o])]
          (noise-funcs)
          (let [n (or (get-in backdrop [:byoubu/scene :terrain :ridge-count]) 3)]
            (for [d (range n)] (ridge-fn d n)))
          [(fragment backdrop)])))
