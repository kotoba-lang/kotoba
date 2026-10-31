(ns kami.gen.procedural
  "Deterministic EDN-parameter composed character pipeline — Approach 1 of 4
  in the `kami-gen-*` head-to-head comparison (ADR-2607051100,
  com-junkawasaki/root). No ML inference, no per-asset GPU cost: every
  tunable is a plain value in an EDN map, and the whole pipeline is pure
  data + pure functions over `kotoba-lang/character` (parametric body/head),
  `kotoba-lang/mesher` (Marching Cubes SDF -> mesh, used for the new
  'kigurumi' hood/beak costume attachment), and `kotoba-lang/vrm`
  (VrmDocument assembly + GLB export). This is the direct 3D extension of
  `kotoba-lang/kami-isekai-assets`'s `kami.isekai.chargen/compose-character`
  (2D sprite-primitive composition) — same 'view source + fork, no PNG/GLB/
  WAV asset *files* checked in, the EDN parameter map is the source of
  truth' philosophy, extended from 2D sprite primitives to 3D parametric
  meshes.

  Entry point: `compose-costumed-character`.

  ## What `kotoba-lang/character`'s real API does *not* have

  The ADR's `{:proportions {:head-scale 1.6 :limb-scale 0.6}}` sketch
  describes the desired chibi RATIO, but `character.params/
  default-character-def` has no `:proportions` field and
  `character/generate-character` takes no proportion knob at all — this is
  a real gap between the ADR sketch and the upstream library's actual
  surface, not something this repo silently papers over. What DOES exist:
  `character.body`'s `:body {:height ...}` param already scales torso AND
  limb length together (`character.body/torso-profile`, `leg-mesh`,
  `arm-mesh`, `generate-humanoid-skeleton`'s `height` arg) — so `:limb-scale`
  maps directly onto that real `:height` field. There is no head-size knob
  at all (`character.base-mesh/generate-head` is a fixed-size sphere, not
  parametrized by the character def), so `:head-scale` is applied here as
  an explicit post-hoc uniform vertex scale of every generated part that
  ISN'T `\"body\"`/`\"clothing\"` (head/eyes/eyebrows/hair), around a
  configurable pivot. Both knobs are plain overridable values in
  `default-proportions`, not hidden constants.

  A second real gap existed here (documented, then FIXED — see below rather
  than left as a standing limitation): `character/generate-character` does
  not attach any of its rigid parts (head/eyes/eyebrows/hair/clothing) to
  skeleton-bone NODES at all — only the `\"body\"` MeshPart gets real
  `JOINTS_0`/`WEIGHTS_0` skin data (`character.body/skin-body`). Every
  other part is a static mesh sharing one world-space coordinate frame with
  the skeleton's BIND pose. Exporting that faithfully (rigid siblings, no
  skin) meant posing the exported VRM away from bind pose moved the skinned
  body/body-suit but left head/hair/hood/beak/clothing visually frozen in
  place — verified as a real, visible bug (parsed the exported glTF JSON by
  hand and confirmed the second mesh node had no `skin` reference at all,
  then confirmed the practical symptom under `kami-engine`'s `:dance/avatar`
  pose pipeline, ADR-0043), not merely a theoretical gap.

  This pipeline's `:vrm` export now closes that gap itself rather than
  inheriting it: every rigid part gets a real single-bone `JOINTS_0`/
  `WEIGHTS_0` binding (`material->joint-bone-name` + `bind-part-to-joint`,
  below) before being written into the same `skins[0]` the body mesh uses
  — head-family parts (`head` shell/`eye-white`/`iris`/`pupil`/`eyebrow`/
  `hair`, plus the kigurumi `hood`/`beak`) bind fully to the `head` joint,
  and `clothing` binds fully to `chest` (a torso-level garment; `chest`
  rather than `hips`, since it should sway with the upper torso/shoulders,
  not just follow hip motion — see `character.body/generate-humanoid-
  skeleton`'s `hips(0) -> spine(1) -> chest(2) -> upperChest(3) ->
  neck(4) -> head(5)` chain). A single-bone weight of `[1,0,0,0]` is a
  legitimate, spec-valid skin binding (nothing in glTF/VRM requires
  influence spread across 4 joints); this is intentionally NOT the
  `character.body/skin-weights` inverse-distance auto-skinning `\"body\"`
  uses, since these parts are rigid by construction (a hood/beak/eyeball
  should not deform, only follow one bone rigidly). Both the rigid and the
  skinned body mesh NODES reference the one shared `skins[0]` (see
  `assemble-vrm`), so a `:dance/avatar` pose now moves the whole figure
  together."
  (:require [character :as character]
            [character.params :as char-params]
            [character.body :as char-body]
            [character.material :as char-material]
            [character.math :as m]
            [character.bin :as bin]
            [mesher :as mesher]
            [vrm.vrm-types :as vt]
            [vrm.gltf-types :as gt]
            [vrm.export :as vrm-export]))

;; ---------------------------------------------------------------------------
;; Portable scalar math (`#?(:clj ... :cljs ...)`, same convention every
;; sibling repo in this org uses so this namespace stays a portable `.cljc`).
;; ---------------------------------------------------------------------------

(defn- sin* [x] #?(:clj (Math/sin (double x)) :cljs (js/Math.sin x)))
(defn- cos* [x] #?(:clj (Math/cos (double x)) :cljs (js/Math.cos x)))
(defn- tan* [x] #?(:clj (Math/tan (double x)) :cljs (js/Math.tan x)))

;; ---------------------------------------------------------------------------
;; Every tunable, as plain overridable EDN — no magic numbers live only
;; inside a generator function; each one is a key here that
;; `compose-costumed-character`'s `:proportions`/`:kigurumi` opts merge over.
;; ---------------------------------------------------------------------------

(def default-proportions
  "Chibi proportion knobs (see namespace docstring for why these map onto
  `character`'s real `:height` field / a post-hoc vertex scale rather than
  a native 'chibi' primitive)."
  {:head-scale 1.6
   :limb-scale 0.6
   :head-scale-pivot [0.0 0.0 0.0]})

(def default-kigurumi
  "Every parameter the 'kigurumi' costume attachment (hood + beak SDF via
  `mesher`, body-suit shell) uses. `:hood-center` is in the SAME shared
  character-local coordinate frame `character/generate-character`'s head
  mesh already occupies (see namespace docstring) — not a skeleton-bone-
  relative offset, since nothing in that frame is bone-relative to begin
  with."
  {:hood-radius 0.145
   :hood-center [0.0 0.02 0.0]
   :hood-droop 0.05
   :beak-length 0.09
   :beak-half-angle 0.35
   :beak-tilt -0.35
   :beak-offset-z 0.10
   :body-suit-padding 0.012
   :body-suit-color [0.08 0.08 0.09]
   :mesh-resolution 24
   :mesh-bounds 0.26
   :palette {:hood-color [0.08 0.08 0.09]
             :beak-color [0.88 0.47 0.06]}})

(defn- merge-kigurumi
  [defaults overrides]
  (-> (merge defaults overrides)
      (assoc :palette (merge (:palette defaults) (:palette overrides)))))

;; ---------------------------------------------------------------------------
;; Seed -> deterministic small color jitter (mirrors
;; `kami.isekai.palette/jitter-color`'s role in the 2D sibling
;; `kami-isekai-assets`'s `compose-character` — `:seed` actually changes the
;; output, not just the asset id, via `character.math/hash-f32`'s
;; deterministic hash, reused rather than re-invented).
;; ---------------------------------------------------------------------------

(defn- jitter-channel [v seed salt]
  (let [j (- (* 2.0 (m/hash-f32 seed salt)) 1.0)]
    (max 0.0 (min 1.0 (+ v (* j 0.04))))))

(defn- jitter-color [[r g b] seed salt-base]
  [(jitter-channel r seed salt-base)
   (jitter-channel g seed (+ salt-base 1))
   (jitter-channel b seed (+ salt-base 2))])

;; ---------------------------------------------------------------------------
;; Mesh-part helpers shared by both the chibi head-scale pass and the
;; body-suit inflation pass — plain vertex transforms over the
;; `{:vertices [{:position :normal :uv ...}] :indices [...]}` MeshPart
;; shape `character.body` already returns.
;; ---------------------------------------------------------------------------

(defn- scale-part-about
  "Uniform-scale every vertex `:position` in `part` about `pivot` by
  `scale`. Normals are left untouched — a uniform scale never changes a
  normal's direction, only non-uniform scale would need the usual
  inverse-transpose correction."
  [part pivot scale]
  (update part :vertices
          (fn [vs] (mapv (fn [v] (update v :position
                                          (fn [p] (m/vec3+ pivot (m/vec3-scale (m/vec3- p pivot) scale)))))
                         vs))))

(defn- inflate-part
  "Offset every vertex `:position` outward along its own `:normal` by
  `padding` — the 'body-suit shell offset from the base body silhouette'
  the ADR calls for, implemented as the simplest of its two suggested
  techniques (per-vertex normal offset) since `character.body` exposes no
  second parametric 'oversized body' pass. `:joint-indices`/`:joint-weights`
  (already computed by `character.body/skin-body` against the base body)
  are carried through unchanged — a small, documented approximation (the
  padding here is small relative to bone spacing, so re-binding would not
  meaningfully change which bones a shell vertex nearest-binds to), same
  honesty convention `character.body`'s own auto-skinning docstring uses."
  [part padding]
  (update part :vertices
          (fn [vs] (mapv (fn [{:keys [normal] :as v}]
                           (update v :position #(m/vec3+ % (m/vec3-scale normal padding))))
                         vs))))

(defn- merge-by-material
  "Groups mesh parts (`{:material kw :vertices [...] :indices [...]}`) by
  `:material`, concatenating vertices and offsetting indices — same
  technique `character.export/group-parts-by-material` uses to fold many
  named MeshParts sharing one material into a single glTF primitive."
  [parts]
  (->> (reduce (fn [groups {:keys [material vertices indices]}]
                 (let [existing (get groups material {:vertices [] :indices []})
                       offset (count (:vertices existing))]
                   (assoc groups material
                          {:vertices (into (:vertices existing) vertices)
                           :indices (into (:indices existing) (map #(+ % offset) indices))})))
               {} parts)
       (mapv (fn [[material {:keys [vertices indices]}]]
               {:material material :vertices vertices :indices indices}))))

;; ---------------------------------------------------------------------------
;; Body: `character/generate-character` with chibi proportions applied.
;; ---------------------------------------------------------------------------

(defn- build-body
  "`char-def` with `[:body :height]` driven by `:limb-scale` (the real knob
  that shrinks torso+limb length together, see namespace docstring), then
  every generated part that is not `\"body\"`/`\"clothing\"`
  (head/eyes/eyebrows/hair) uniform-scaled by `:head-scale` about
  `:head-scale-pivot`. Returns `{:parts :skeleton :blendshape-targets
  :char-def}` (the last so callers/materials downstream can read the final
  skin/hair/clothing colors actually used)."
  [{:keys [head-scale limb-scale head-scale-pivot]} char-def]
  (let [char-def (assoc-in char-def [:body :height] limb-scale)
        {:keys [parts skeleton blendshape-targets]} (character/generate-character char-def)
        rigid-non-scaling? #{"body" "clothing"}
        parts' (mapv (fn [p] (if (rigid-non-scaling? (:name p))
                                p
                                (scale-part-about p head-scale-pivot head-scale)))
                     parts)]
    {:parts parts' :skeleton skeleton :blendshape-targets blendshape-targets :char-def char-def}))

;; ---------------------------------------------------------------------------
;; Costume: kigurumi hood + beak (SDF via `mesher`) + body-suit shell.
;; ---------------------------------------------------------------------------

(defn- sdf-sphere [p center radius]
  (- (m/vec3-length (m/vec3- p center)) radius))

(defn- sdf-cone
  "Approximate finite-cone signed field, apex-anchored, opening along unit
  `axis` for `height` before its flat end cap. This is NOT an exact
  metric SDF (the lateral/cap/back half-space terms are combined with a
  plain `max`, not a true Euclidean distance blend) — but `mesher/
  sdf-to-mesh` only ever needs a correctly-signed, locally-smooth field:
  it derives vertex normals from a NUMERIC central difference of `sample`
  itself (see `mesher.cljc`'s `process-cell`), not an analytic gradient of
  a true SDF, so an approximate field with the right zero-crossing shape
  is sufficient and produces correct-looking normals."
  [p apex axis half-angle height]
  (let [local (m/vec3- p apex)
        along (m/vec3-dot local axis)
        perp (m/vec3- local (m/vec3-scale axis along))
        perp-dist (m/vec3-length perp)
        h (max height 1e-6)
        t (max 0.0 (min 1.0 (/ along h)))
        radius-at (* h (tan* half-angle) t)
        lateral (- perp-dist radius-at)
        cap (- along h)
        back (- along)]
    (max lateral cap back)))

(defn- hood-sample-fn
  "`(fn [x y z] -> [dist [r g b a]])`, matching `mesher/sdf-to-colored-mesh`'s
  `sample` contract exactly: a sphere (the hood) union a tilted finite cone
  (the beak), penguin-palette colored by which of the two primitives is
  locally closer. `:hood-droop` sags the sphere's own center downward for
  points behind (`-z` of) `:hood-center`, an anisotropic coordinate warp
  approximating a hood drooping over the shoulders at the back — documented
  approximation, not a physically simulated cloth drape."
  [{:keys [hood-radius hood-center hood-droop
           beak-length beak-half-angle beak-tilt beak-offset-z
           palette]}]
  (let [[hcx hcy hcz] hood-center
        {:keys [hood-color beak-color]} palette
        beak-apex [hcx hcy (+ hcz beak-offset-z)]
        beak-axis (m/vec3-normalize [0.0 (sin* beak-tilt) (cos* beak-tilt)])]
    (fn [x y z]
      (let [p [x y z]
            backness (max 0.0 (min 1.0 (/ (- hcz z) (* hood-radius 1.5))))
            center' [hcx (- hcy (* hood-droop backness)) hcz]
            sphere-d (sdf-sphere p center' hood-radius)
            cone-d (sdf-cone p beak-apex beak-axis beak-half-angle beak-length)
            d (min sphere-d cone-d)
            color (if (< cone-d sphere-d) beak-color hood-color)]
        [d (conj (vec color) 1.0)]))))

(defn- unflatten-mesh
  "`mesher`'s stride-8 interleaved `pos3+norm3+uv2` flat mesh ->
  `character.body`'s `{:vertices [{:position :normal :uv} ...] :indices
  [...]}` MeshPart vertex shape, so the rest of this pipeline (accessor
  building, `merge-by-material`) can treat every mesh part uniformly
  regardless of whether it came from `character` or `mesher`."
  [{:keys [vertices indices vertex-count]}]
  {:vertices (mapv (fn [i]
                      (let [b (* i 8)]
                        {:position [(nth vertices b) (nth vertices (+ b 1)) (nth vertices (+ b 2))]
                         :normal [(nth vertices (+ b 3)) (nth vertices (+ b 4)) (nth vertices (+ b 5))]
                         :uv [(nth vertices (+ b 6)) (nth vertices (+ b 7))]}))
                    (range vertex-count))
   :indices (vec indices)})

(defn- classify-hood-color
  "Which of the two known palette colors a `split-mesh-by-color` group's
  average color is nearest to (squared-distance nearest-neighbor over 2
  candidates) — `mesher`'s marching-cubes linearly interpolates color
  along cell edges (see `process-cell`'s `vc`), so the sphere/cone seam
  produces a handful of blended intermediate groups, not just 2 pure ones;
  this assigns each back to whichever named material (`:hood`/`:beak`) it
  is closer to so `merge-by-material` can fold them back into exactly 2
  primitives."
  [color palette]
  (let [{:keys [hood-color beak-color]} palette
        sq-dist (fn [a b] (reduce + (map (fn [x y] (let [d (- x y)] (* d d))) a b)))]
    (if (<= (sq-dist color hood-color) (sq-dist color beak-color)) :hood :beak)))

(defn- gen-hood-parts
  "The kigurumi hood: sphere (hood) union cone (beak) SDF, marching-cubes
  meshed via `mesher/sdf-to-colored-mesh`, split back into exactly a
  `:hood` and a `:beak` MeshPart (see `classify-hood-color`)."
  [kigurumi]
  (let [sample (hood-sample-fn kigurumi)
        [mesh colors] (mesher/sdf-to-colored-mesh sample (:mesh-resolution kigurumi) (:mesh-bounds kigurumi))
        groups (mesher/split-mesh-by-color mesh colors)
        classified (mapv (fn [[sub-mesh avg-color]]
                            (assoc (unflatten-mesh sub-mesh)
                                   :material (classify-hood-color avg-color (:palette kigurumi))))
                          groups)]
    (merge-by-material classified)))

(defn- find-part [parts name]
  (some #(when (= (:name %) name) %) parts))

;; ---------------------------------------------------------------------------
;; Rigid-part skin binding (bugfix, see namespace docstring's "second real
;; gap" section): every non-body MeshPart used to be left with no
;; `:joint-indices`/`:joint-weights` at all, so `add-mesh-primitive` emitted
;; it as a static, unskinned glTF primitive parented directly under the
;; scene root — correct at bind pose, visibly wrong (frozen head/hood/hair/
;; clothing) as soon as the skeleton is posed. Every rigid part legitimately
;; needs only ONE bone's full influence (nothing here deforms), so this is a
;; single-bone bind, not `character.body/skin-weights`'s multi-bone inverse-
;; distance auto-skinning (that fn is for genuinely deforming meshes like
;; the torso/limbs, not a rigid hood or eyeball).
;; ---------------------------------------------------------------------------

(defn- bind-part-to-joint
  "Every vertex of `part` bound fully (glTF `WEIGHTS_0 = [1,0,0,0]`) to the
  single skeleton joint `joint-idx` (`JOINTS_0 = [joint-idx,0,0,0]`) — a
  rigid part (hood, eyeball, hair shell, ...) doesn't deform, so it only
  ever needs one bone's influence to become fully posable."
  [part joint-idx]
  (update part :vertices
          (fn [vs] (mapv (fn [v] (assoc v
                                        :joint-indices [joint-idx 0 0 0]
                                        :joint-weights [1.0 0.0 0.0 0.0]))
                         vs))))

(def ^:private material->joint-bone-name
  "Which single `character.body/generate-humanoid-skeleton` bone NAME each
  rigid (non-\"body\") material's `merge-by-material` group binds fully to.
  Head-family parts (the head shell itself, both eye materials, eyebrows,
  hair, and the kigurumi hood+beak) all rigidly follow `\"head\"`.
  `:clothing` is the one exception: a torso-level garment should sway with
  the upper body, not swing on head turns, so it follows `\"chest\"` —
  picked over `\"hips\"` (too low; would not follow shoulder/torso lean at
  all) and over `\"head\"` (would make a shirt spin with head rotation) in
  the skeleton's `hips -> spine -> chest -> upperChest -> neck -> head`
  chain (`generate-humanoid-skeleton`'s bone list, indices 0-5)."
  {:skin "head" :eye-white "head" :iris "head" :pupil "head"
   :eyebrow "head" :hair "head" :hood "head" :beak "head"
   :clothing "chest"})

(defn- bind-rigid-parts
  "`merge-by-material`'d rigid parts -> the same parts with real skin
  weights attached, via `material->joint-bone-name` + `bind-part-to-joint`.
  `bone-idx` is a `{bone-name-string joint-index}` lookup built from the
  live skeleton (`bones->nodes`'s own bone list), not a hardcoded index, so
  this stays correct if the skeleton's bone ORDER ever changes. Throws on
  an unmapped material rather than silently leaving a part unskinned again
  — same 'no silent wrong-but-valid output' convention `compose-costumed-
  character` already uses for unknown race/costume ids."
  [rigid-merged bone-idx]
  (mapv (fn [{:keys [material] :as part}]
          (let [bone-name (or (get material->joint-bone-name material)
                               (throw (ex-info "kami.gen.procedural: no joint binding mapped for rigid material"
                                                {:material material})))
                joint-idx (or (get bone-idx bone-name)
                              (throw (ex-info "kami.gen.procedural: joint bone not found in skeleton"
                                               {:bone-name bone-name})))]
            (bind-part-to-joint part joint-idx)))
        rigid-merged))

(defn- build-body-suit
  "The body-suit shell: `body-part` (already skinned by
  `character.body/skin-body` inside `character/generate-character`) offset
  outward along its own vertex normals by `:body-suit-padding` (see
  `inflate-part`)."
  [body-part kigurumi]
  (-> body-part
      (inflate-part (:body-suit-padding kigurumi))
      (assoc :name "body-suit" :material :body-suit)))

;; ---------------------------------------------------------------------------
;; VRM assembly: build a real VrmDocument's glTF (nodes/skin/accessors/
;; materials) by hand from the character mesh + skeleton, then hand it to
;; `vrm.export/export-glb` for the actual GLB byte serialization. This does
;; NOT go through `vrm.parse` -> `vrm.part/decompose` -> `vrm.compose`
;; (that pipeline merges parts cut from PRE-EXISTING VRM files; there is no
;; existing VRM file here to decompose — the mesh is generated fresh) --
;; only the export half of "compose/export" applies, per the ADR text
;; ("run through kotoba-lang/vrm's compose/export ... to produce a genuine
;; .vrm"): we compose our own VrmDocument directly, then reuse `vrm.export`
;; verbatim for the GLB byte-level serialization.
;; ---------------------------------------------------------------------------

(defn- pad4 [buf] (loop [b buf] (if (zero? (mod (count b) 4)) b (recur (conj b 0)))))

(defn- vec-min3 [vs] (reduce (fn [[ax ay az] [x y z]] [(min ax x) (min ay y) (min az z)]) (first vs) (rest vs)))
(defn- vec-max3 [vs] (reduce (fn [[ax ay az] [x y z]] [(max ax x) (max ay y) (max az z)]) (first vs) (rest vs)))

(defn- add-accessor
  "Appends `values` (a flat seq of numbers, `write-fn` a `character.bin`
  writer like `write-f32-le`) to `state`'s shared binary buffer (4-byte
  padded, matching `character.export`'s own GLB-buffer convention), and
  records the matching bufferView + accessor. Returns `[state' accessor-idx]`."
  [state {:keys [values component-type type byte-target write-fn min-vals max-vals]
          elem-count :count}]
  (let [{:keys [bin buffer-views accessors]} state
        byte-offset (count bin)
        bin' (pad4 (reduce write-fn bin values))
        byte-length (- (count bin') byte-offset)
        bv-idx (count buffer-views)
        bv (cond-> {:buffer 0 :byteOffset byte-offset :byteLength byte-length}
             byte-target (assoc :target byte-target))
        acc-idx (count accessors)
        acc (cond-> {:bufferView bv-idx :componentType component-type :count elem-count :type type :byteOffset 0}
              min-vals (assoc :min min-vals)
              max-vals (assoc :max max-vals))]
    [(-> state (assoc :bin bin') (update :buffer-views conj bv) (update :accessors conj acc)) acc-idx]))

(defn- add-mesh-primitive
  "One `{:material kw :vertices [...] :indices [...]}` part -> one glTF
  primitive (attributes + indices accessor). Whether to emit `JOINTS_0`/
  `WEIGHTS_0` is detected from whether vertices actually carry
  `:joint-indices` — `\"body\"`/`\"body-suit\"` get theirs from
  `character.body/skin-body`'s multi-bone auto-skinning, every other
  (\"rigid\") part gets a single-bone binding from this namespace's own
  `bind-rigid-parts` (see namespace docstring's bugfix section) — so in
  practice every part is skinned now, but this fn stays agnostic and would
  still correctly emit an unskinned primitive if a caller ever passed one."
  [state {:keys [vertices indices]} material-index]
  (let [positions (mapv :position vertices)
        normals (mapv :normal vertices)
        uvs (mapv :uv vertices)
        n (count vertices)
        [state pos-acc] (add-accessor state {:values (apply concat positions)
                                              :component-type gt/component-type-float :type "VEC3" :count n
                                              :byte-target gt/buffer-target-array-buffer :write-fn bin/write-f32-le
                                              :min-vals (vec-min3 positions) :max-vals (vec-max3 positions)})
        [state norm-acc] (add-accessor state {:values (apply concat normals)
                                               :component-type gt/component-type-float :type "VEC3" :count n
                                               :byte-target gt/buffer-target-array-buffer :write-fn bin/write-f32-le})
        [state uv-acc] (add-accessor state {:values (apply concat uvs)
                                             :component-type gt/component-type-float :type "VEC2" :count n
                                             :byte-target gt/buffer-target-array-buffer :write-fn bin/write-f32-le})
        skinned? (every? :joint-indices vertices)
        [state attrs]
        (if skinned?
          (let [joints (mapv :joint-indices vertices)
                weights (mapv :joint-weights vertices)
                [state j-acc] (add-accessor state {:values (apply concat joints)
                                                    :component-type gt/component-type-unsigned-short :type "VEC4" :count n
                                                    :byte-target gt/buffer-target-array-buffer :write-fn bin/write-u16-le})
                [state w-acc] (add-accessor state {:values (apply concat weights)
                                                    :component-type gt/component-type-float :type "VEC4" :count n
                                                    :byte-target gt/buffer-target-array-buffer :write-fn bin/write-f32-le})]
            [state {:POSITION pos-acc :NORMAL norm-acc :TEXCOORD_0 uv-acc :JOINTS_0 j-acc :WEIGHTS_0 w-acc}])
          [state {:POSITION pos-acc :NORMAL norm-acc :TEXCOORD_0 uv-acc}])
        [state idx-acc] (add-accessor state {:values indices
                                              :component-type gt/component-type-unsigned-int :type "SCALAR" :count (count indices)
                                              :byte-target gt/buffer-target-element-array-buffer :write-fn bin/write-u32-le})]
    [state {:attributes attrs :indices idx-acc :material material-index} skinned?]))

(defn- bone->node [{:keys [name local-position local-rotation]}]
  {:name name :translation local-position :rotation local-rotation})

(defn- bones->nodes
  [bones]
  (reduce (fn [nodes [i {:keys [parent]}]]
            (if parent (update-in nodes [parent :children] (fnil conj []) i) nodes))
          (mapv bone->node bones)
          (map-indexed vector bones)))

(defn- inverse-bind-mat4
  "Translation-only inverse bind matrix (`generate-humanoid-skeleton`'s
  bones are all `identity-rot`, see `character.body`), matching
  `character.body/bone-world-positions`'s own rest-pose convention."
  [[wx wy wz]]
  (-> m/mat4-identity (assoc 12 (- wx)) (assoc 13 (- wy)) (assoc 14 (- wz))))

(defn- build-skin
  [state bones skeleton-root-idx]
  (let [n (count bones)
        bwp (char-body/bone-world-positions bones)
        ibm-values (vec (apply concat (mapv inverse-bind-mat4 bwp)))
        [state ibm-acc] (add-accessor state {:values ibm-values
                                              :component-type gt/component-type-float :type "MAT4" :count n
                                              :write-fn bin/write-f32-le})]
    [state {:joints (vec (range n)) :inverseBindMatrices ibm-acc :skeleton skeleton-root-idx}]))

(defn- build-humanoid
  [bones]
  (vt/vrm-humanoid
   (keep (fn [[i {:keys [name]}]]
           (when-let [kw (vt/str->human-bone-name name)] (vt/vrm-human-bone kw i)))
         (map-indexed vector bones))))

(defn- costume-materials [kigurumi]
  (let [{:keys [hood-color beak-color]} (:palette kigurumi)]
    {:hood {:name "kigurumi-hood" :base-color (conj (vec hood-color) 1.0) :metallic 0.0 :roughness 0.85}
     :beak {:name "kigurumi-beak" :base-color (conj (vec beak-color) 1.0) :metallic 0.0 :roughness 0.4}
     :body-suit {:name "kigurumi-suit" :base-color (conj (vec (:body-suit-color kigurumi)) 1.0)
                 :metallic 0.0 :roughness 0.8}}))

(def ^:private standard-material-kws
  #{:skin :eye-white :iris :pupil :lip :eyebrow :hair :clothing :eyelash})

(defn- pbr->gltf-material [pbr]
  {:name (:name pbr)
   :pbrMetallicRoughness {:baseColorFactor (:base-color pbr)
                           :metallicFactor (:metallic pbr)
                           :roughnessFactor (:roughness pbr)}
   :doubleSided true})

(defn- build-materials
  "`used-kws` (in first-use order) -> `{:index {kw idx} :json [gltf-material
  ...]}`. Standard part kinds (`:skin`/`:hair`/... ) go through
  `character.material/for-part` unchanged (the same function
  `character.export/export-glb` itself uses); the 3 new kigurumi kinds
  (`:hood`/`:beak`/`:body-suit`) use `costume-materials`."
  [char-def kigurumi used-kws]
  (let [{:keys [skin eyes mouth hair clothing]} char-def
        costume (costume-materials kigurumi)
        pbr-for (fn [kw] (if (standard-material-kws kw)
                            (char-material/for-part kw skin eyes mouth hair clothing)
                            (get costume kw)))
        ordered (vec (distinct used-kws))]
    {:index (into {} (map-indexed (fn [i kw] [kw i]) ordered))
     :json (mapv (comp pbr->gltf-material pbr-for) ordered)}))

(defn- assemble-vrm
  [{:keys [char-def skeleton parts body-suit-part hood-parts kigurumi seed base costume]}]
  (let [bones (:bones skeleton)
        skel-nodes (bones->nodes bones)
        n-bones (count bones)
        bone-idx (into {} (map-indexed (fn [i {:keys [name]}] [name i]) bones))
        body-part (find-part parts "body")
        rigid-parts (into (remove #(= (:name %) "body") parts) hood-parts)
        rigid-merged (-> (merge-by-material rigid-parts)
                          (bind-rigid-parts bone-idx))
        used-kws (into (mapv :material rigid-merged) [:skin :body-suit])
        {:keys [index json]} (build-materials char-def kigurumi used-kws)
        state0 {:bin [] :buffer-views [] :accessors []}
        [state rigid-prims]
        (reduce (fn [[state prims] part]
                  (let [[state prim _skinned?] (add-mesh-primitive state part (get index (:material part)))]
                    [state (conj prims prim)]))
                [state0 []] rigid-merged)
        [state body-prim _] (add-mesh-primitive state body-part (get index :skin))
        [state suit-prim _] (add-mesh-primitive state body-suit-part (get index :body-suit))
        [state skin] (build-skin state bones 0)
        rigid-node-idx n-bones
        skinned-node-idx (inc n-bones)
        rigid-mesh-idx 0
        skinned-mesh-idx 1
        all-nodes (conj skel-nodes
                        ;; Both mesh nodes reference the SAME `skins[0]` (the
                        ;; fix, see namespace docstring): rigid vertices now
                        ;; carry real single-bone JOINTS_0/WEIGHTS_0 too
                        ;; (`bind-rigid-parts`, above), so this is no longer
                        ;; a static mesh parented under the scene root.
                        {:name "kami-gen-procedural-rigid" :mesh rigid-mesh-idx :skin 0}
                        {:name "kami-gen-procedural-body" :mesh skinned-mesh-idx :skin 0})
        humanoid (build-humanoid bones)
        meta (vt/vrm-meta
              {:name (str "kami-gen-procedural/" (subs (str base) 1) "/" (clojure.core/name costume) "/" seed)
               :version "1.0"
               :authors ["kami-gen-procedural"]
               :avatar-permission "everyone"
               :commercial-usage "personalNonProfit"})
        gltf (gt/gltf-document
              {:asset (gt/asset {:generator "kami-gen-procedural"})
               :scene 0
               :scenes [{:nodes [0 rigid-node-idx skinned-node-idx]}]
               :nodes all-nodes
               :meshes [{:primitives rigid-prims} {:primitives [body-prim suit-prim]}]
               :accessors (:accessors state)
               :bufferViews (:buffer-views state)
               :buffers [{:byteLength (count (:bin state))}]
               :materials json
               :skins [skin]})]
    (vt/vrm-document
     {:gltf gltf :bin (:bin state) :version :v1-0 :meta meta :humanoid humanoid})))

;; ---------------------------------------------------------------------------
;; render/profile fallback (kami-isekai-assets `:render/profile` shape).
;; ---------------------------------------------------------------------------

(defn- build-render-profile [proportions kigurumi]
  {:color (get-in kigurumi [:palette :hood-color])
   :w (* 0.8 (:limb-scale proportions))
   :h (* 1.7 (:limb-scale proportions) (max 1.0 (/ (:head-scale proportions) 1.6)))
   :geo :capsule
   :emissive 0.0})

;; ---------------------------------------------------------------------------
;; Public API
;; ---------------------------------------------------------------------------

(defn compose-costumed-character
  "`{:base :race/human :costume :penguin-kigurumi :seed n
     :proportions {...overrides of default-proportions...}
     :kigurumi {...overrides of default-kigurumi, incl. nested :palette...}
     :char-def {...deep-merged onto character.params/default-character-def...}}
    -> {:body {:parts :skeleton :blendshape-targets}
        :costume {:hood [...MeshParts...] :body-suit MeshPart :params kigurumi}
        :vrm {:document VrmDocument :glb-bytes [byte-int ...]}
        :render/profile {...}}`.

  Only `:race/human` x `:penguin-kigurumi` is implemented (`character.params`
  has no race concept at all — see namespace docstring; a non-human `:base`
  or a costume other than `:penguin-kigurumi` throws rather than silently
  falling back, same 'no silent wrong-but-valid output' convention
  `kami.isekai.chargen/compose-character` uses for unknown race/class ids)."
  [{:keys [base costume seed proportions kigurumi char-def]
    :or {base :race/human costume :penguin-kigurumi seed 42}}]
  (when-not (= base :race/human)
    (throw (ex-info "kami.gen.procedural: only :race/human is implemented (character.params has no race concept)"
                     {:base base})))
  (when-not (= costume :penguin-kigurumi)
    (throw (ex-info "kami.gen.procedural: only :costume :penguin-kigurumi is implemented"
                     {:costume costume})))
  (let [proportions (merge default-proportions proportions)
        kigurumi (merge-kigurumi default-kigurumi kigurumi)
        kigurumi (update-in kigurumi [:palette :hood-color] jitter-color seed 11)
        kigurumi (update-in kigurumi [:palette :beak-color] jitter-color seed 101)
        base-def (merge-with (fn [a b] (if (map? a) (merge a b) b))
                              (char-params/default-character-def) char-def)
        {:keys [parts skeleton blendshape-targets char-def]} (build-body proportions base-def)
        body-part (find-part parts "body")
        body-suit-part (build-body-suit body-part kigurumi)
        hood-parts (gen-hood-parts kigurumi)
        vrm-doc (assemble-vrm {:char-def char-def :skeleton skeleton :parts parts
                                :body-suit-part body-suit-part :hood-parts hood-parts
                                :kigurumi kigurumi :seed seed :base base :costume costume})
        vrm-bytes (vrm-export/export-glb vrm-doc)]
    {:body {:parts parts :skeleton skeleton :blendshape-targets blendshape-targets}
     :costume {:hood hood-parts :body-suit body-suit-part :params kigurumi}
     :vrm {:document vrm-doc :glb-bytes vrm-bytes}
     :render/profile (build-render-profile proportions kigurumi)}))

;; ---------------------------------------------------------------------------
;; network-isekai Asset Hub publishing (public/assets/index.edn schema).
;; ---------------------------------------------------------------------------

(defn- bytes->hex [bs]
  (apply str (map (fn [b] #?(:clj (format "%02x" (bit-and (int b) 0xFF))
                              :cljs (.padStart (.toString (bit-and b 0xFF) 16) 2 "0")))
                   bs)))

(defn content-cid
  "sha256-based CID surrogate, same `\"bafy-sha256-<hex>\"` string shape as
  `cloud-murakumo`'s `executor.clj` `content-cid` (there operating on a
  file/string; here on the exported GLB byte vector directly) — so all 4
  `kami-gen-*` sibling repos publish payload CIDs in one consistent shape."
  [byte-seq]
  #?(:clj (let [ba (byte-array (map unchecked-byte byte-seq))
                digest (.digest (java.security.MessageDigest/getInstance "SHA-256") ba)]
            (str "bafy-sha256-" (bytes->hex digest)))
     :cljs (throw (ex-info "content-cid: SHA-256 not yet implemented for cljs" {}))))

(defn publish-to-asset-hub
  "Shapes `compose-costumed-character`'s `:vrm` output into a
  `network-isekai` Asset Hub entry (`public/assets/index.edn`'s
  `:asset/*` schema — `:asset/kind :model3d`, CID-addressed payload,
  `:asset/preview {:webgpu true}`), ready to append to that catalog and
  use from `dance.html`'s `:dance/avatar {:vrm ...}`. Does not itself
  write anything to `network-isekai`'s checkout — returns the plain EDN
  entry map for the caller to append/commit."
  ([result] (publish-to-asset-hub result {}))
  ([{:keys [vrm]} {:keys [id title tags author license uri deps]}]
   (let [glb-bytes (:glb-bytes vrm)
         cid (content-cid glb-bytes)]
     {:asset/id (or id (str "kami-gen-procedural-" cid))
      :asset/kind :model3d
      :asset/format :vrm
      :asset/title (or title "Procedural penguin-kigurumi chibi character")
      :asset/author (or author "gftdcojp / kami-gen-procedural")
      :asset/license (or license :cc0)
      :asset/tags (or tags ["3d" "vrm" "kigurumi" "chibi" "procedural"])
      :asset/payload {:cid {:hash cid} :bytes (count glb-bytes)
                       :uri (or uri (str "/assets/kami-gen-procedural/" cid ".vrm"))}
      :asset/preview {:webgpu true}
      :asset/deps (or deps ["kotoba-lang/kami-gen-procedural" "kotoba-lang/character"
                            "kotoba-lang/mesher" "kotoba-lang/vrm"])
      :asset/source :upload})))
