(ns kotoba.gltf.retarget
  "Chain-based pose retargeting (ADR-0048 §3, com-junkawasaki/root,
  `90-docs/adr/0048-global-format-standards-kotoba-clj-wasm-no-rust.md`).

  VRM 1.0's `humanBones` mapping requires an exact, fixed set of NAMED
  bones — a poor fit for non-humanoid silhouettes (this org's own
  `kami-gen-*` penguin-kigurumi test case: a body plan with no 1:1
  correspondence to VRM's 15 required human bones). Plain glTF skinning
  (`skins`/`joints`/`inverseBindMatrices`) has no humanoid assumption at
  all, so a retargeting scheme built on top of it only needs a bone
  CORRESPONDENCE, not identical bone names/counts.

  Design reference (NOT a dependency, no Unreal code used): Unreal's IK
  Rig / IK Retargeter maps bone *chains* (a named, ordered run of bones —
  \"spine chain\", \"left arm chain\") between a source and target
  skeleton, rather than matching individual bones by name. That
  chain-to-chain correspondence is exactly what generalizes to
  non-standard/non-biped skeletons where VRM's named-bone contract can't:
  a 3-bone spine and a 5-bone spine are still both \"the spine chain\"
  even though no bone-for-bone name mapping exists between them.

  ## What this v0 actually does

  For each named chain present in BOTH the source and target chain maps,
  every SOURCE bone is assigned a chain-relative parameter `t` in `[0,1]`
  (0 = chain root, 1 = chain tip, evenly spaced by INDEX — bone `i` of
  `n` gets `t = i/(n-1)`, or `t = 0` for a single-bone chain). Every
  TARGET bone gets its own parameter `u` the same way over its own
  (possibly different) bone count. Each target bone's pose is then
  produced by resampling the source chain's piecewise-linear pose curve
  at `u`: linearly interpolating `:translation` and normalized-lerp
  (`nlerp`) interpolating `:rotation` between the two source samples
  bracketing `u`.

  ## Known limitations (v0, documented per this org's \"no overclaiming\"
  convention — do not read this as production-quality retargeting)

  - **Proportional by INDEX, not by bone LENGTH/arc-length.** A source
    chain whose bones have very uneven lengths (e.g. a long thigh + a
    short shin) still spaces its `t` values evenly by index — a target
    bone at `u=0.5` lands at the source's index-midpoint, not at its
    anatomical/geometric midpoint. A length-aware version would
    accumulate real bone lengths (or rest-pose translations) into `t`
    instead of `i/(n-1)`.
  - **`nlerp`, not `slerp`, for rotation.** Normalized-lerp is a cheap,
    well-known approximation of spherical interpolation, good for small
    angular gaps between adjacent chain samples, but it does not preserve
    constant angular velocity and degrades for widely-differing
    orientations. A production retargeter should slerp.
  - **No IK / end-effector preservation.** This resamples a POSE CURVE
    per chain; it does not solve inverse kinematics to keep a hand/foot
    at a specific world-space target the way Unreal's IK Retargeter does
    (that also needs the target skeleton's own rest-pose/bind-pose bone
    lengths, which this module does not take as input at all). Calling
    this \"retargeting\" is a deliberate nod to the reference design's
    name, not a claim of feature parity with it.
  - **No global root motion handling, no space awareness.** Poses here
    are opaque `{:translation :rotation}` maps in whatever space the
    caller's chains already share — this module does NOT itself apply
    `kotoba-lang/character`'s tagged-point convention (ADR-0048 §1); a
    caller mixing head-local and world-space chains would need to
    normalize spaces (via `character.space` or equivalent) BEFORE calling
    this namespace, the same discipline ADR-0048 §1 exists to enforce
    elsewhere.
  - **Chain correspondence is author-supplied, not discovered.** A
    chain-name mismatch between source/target chain maps is silently
    skipped (see `retarget-pose`) — there is no bone-name inference or
    automatic chain detection."
  )

;; ---------------------------------------------------------------------------
;; Pose primitives
;; ---------------------------------------------------------------------------

(def identity-pose
  "The default pose for any field a caller's per-bone pose map omits."
  {:translation [0.0 0.0 0.0] :rotation [0.0 0.0 0.0 1.0]})

(defn- pose-of
  "Look up `bone`'s pose in `pose-map`, defaulting only MISSING FIELDS
  (`:translation`/`:rotation`) to identity — a bone entirely absent from
  `pose-map` throws (this org's \"no silent fallback\" convention: a typo'd
  or forgotten bone name should not silently retarget as if it were
  identity, which would be indistinguishable from a real authored
  identity pose)."
  [pose-map bone]
  (if-let [p (get pose-map bone)]
    (merge identity-pose p)
    (throw (ex-info "kotoba.gltf.retarget: pose has no entry for chain bone"
                     {:bone bone :known-bones (set (keys pose-map))}))))

(defn- lerp [a b t] (+ a (* (- b a) t)))

(defn- vec3-lerp [[ax ay az] [bx by bz] t]
  [(lerp ax bx t) (lerp ay by t) (lerp az bz t)])

(defn- sqrt* [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))

(defn- vec-len [v] (sqrt* (reduce + (map #(* % %) v))))

(defn quat-nlerp
  "Normalized-lerp quaternion interpolation (`[x y z w]`), taking the
  shortest path (negating `b` if `a . b < 0`). NOT spherical (`slerp`) —
  see ns docstring 'Known limitations'."
  [[ax ay az aw :as a] [bx by bz bw] t]
  (let [dot (+ (* ax bx) (* ay by) (* az bz) (* aw bw))
        [bx by bz bw] (if (neg? dot) [(- bx) (- by) (- bz) (- bw)] [bx by bz bw])
        x (lerp ax bx t) y (lerp ay by t) z (lerp az bz t) w (lerp aw bw t)
        len (vec-len [x y z w])]
    (if (zero? len) (vec a) [(/ x len) (/ y len) (/ z len) (/ w len)])))

(defn chain-param
  "Chain-relative parameter (`[0,1]`) for bone index `i` of `n` bones,
  evenly spaced by INDEX (see ns docstring limitation on length-awareness).
  A single-bone chain (`n<=1`) is `0.0` at every index."
  [i n]
  (if (<= n 1) 0.0 (/ (double i) (dec n))))

;; ---------------------------------------------------------------------------
;; Per-chain retargeting
;; ---------------------------------------------------------------------------

(defn- sample-chain-poses
  "`source-chain` (vector of bone names, root->tip) + `pose` (bone -> pose
  map) -> sorted vector of `[t pose]` pairs, one per source-chain bone (in
  chain order, so already ascending by `t`)."
  [source-chain pose]
  (let [n (count source-chain)]
    (vec (map-indexed (fn [i bone] [(chain-param i n) (pose-of pose bone)]) source-chain))))

(defn- interpolate-at
  "Resample the piecewise-linear pose curve `samples` (ascending `[t
  pose]` pairs) at parameter `u`, clamping to the first/last sample
  outside `[t-min, t-max]`."
  [samples u]
  (let [n (count samples)]
    (cond
      (zero? n) identity-pose
      (<= u (first (nth samples 0))) (second (nth samples 0))
      (>= u (first (nth samples (dec n)))) (second (nth samples (dec n)))
      :else
      (loop [i 0]
        (let [[t0 p0] (nth samples i)
              [t1 p1] (nth samples (inc i))]
          (if (<= u t1)
            (let [span (- t1 t0)
                  local-t (if (zero? span) 0.0 (/ (- u t0) span))]
              {:translation (vec3-lerp (:translation p0) (:translation p1) local-t)
               :rotation (quat-nlerp (:rotation p0) (:rotation p1) local-t)})
            (recur (inc i))))))))

(defn retarget-chain
  "Retarget one chain's pose. `source-chain`/`target-chain`: vectors of
  bone names root->tip (MAY DIFFER IN LENGTH — the entire point of a
  chain-based, not fixed-bone-name, mapping). `pose`: source-bone -> `{:translation
  [x y z] :rotation [x y z w]}` (either key optional, defaults to
  identity; a bone entirely missing from `pose` throws — see `pose-of`).

  Returns a map of target-bone -> retargeted pose, one entry per bone in
  `target-chain`. See ns docstring 'Known limitations' for what this v0
  algorithm does NOT do (bone-length weighting, slerp, IK)."
  [source-chain target-chain pose]
  (let [samples (sample-chain-poses source-chain pose)
        nt (count target-chain)]
    (into {}
          (map-indexed (fn [j bone] [bone (interpolate-at samples (chain-param j nt))])
                       target-chain))))

;; ---------------------------------------------------------------------------
;; Whole-pose retargeting across named chains
;; ---------------------------------------------------------------------------

(defn retarget-pose
  "Retarget a full pose across NAMED chains. `source-chains`/
  `target-chains`: maps of chain-name -> bone-name vector (root->tip),
  e.g. `{:spine-chain [:hips :spine :chest]
         :left-arm-chain [:leftShoulder :leftUpperArm :leftLowerArm :leftHand]
         ...}` — the exact shape ADR-0048 §3 specifies. `pose`: source-bone
  -> pose map (see `retarget-chain`).

  Only chain names present in BOTH `source-chains` and `target-chains` are
  retargeted; a chain-name present in only one side is silently skipped
  (a chain-name correspondence is an author-time mapping decision, not a
  structural fact this module can discover or validate on its own — use
  `retarget-chain` directly if a caller needs per-chain error handling on
  a chain-name mismatch).

  Returns a map of target-bone -> retargeted pose, merged across every
  matched chain (a target bone shared by two chains — e.g. a chain root
  reused as another chain's attachment bone — takes whichever chain
  happens to be reduced last; `source-chains` is a map so iteration order
  is unspecified. Avoid overlapping target-chain bone sets if that
  matters to a caller)."
  [source-chains target-chains pose]
  (reduce
   (fn [acc [chain-name source-chain]]
     (if-let [target-chain (get target-chains chain-name)]
       (merge acc (retarget-chain source-chain target-chain pose))
       acc))
   {} source-chains))
