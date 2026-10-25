(ns mangaka-scene.pose
  "Character pose + facial expression.

  Restored from `kami-mangaka-scene/src/pose.rs` (kotoba-lang/kami-engine,
  deleted in PR #82) as zero-dependency portable CLJC, per ADR-2607010930.

  VRM standard humanoid bone names + ARKit-style blendshape weights, exactly
  as the Rust `PoseSpec` / `BoneRotation` / `IkTarget` / `Expression` types
  defined them. `Quat` is represented as `[x y z w]`.

  The IK solver and VRM-bound bone application (`MangakaScene::pose`'s use
  of a live `VrmDocument` skeleton) are native-only and are NOT ported here
  — see `mangaka-scene.scene` docstring for the portable/native split.")

(defn transform-default
  "Forward-declared shape to avoid a circular require with `mangaka-scene.scene`;
  callers typically pass `(mangaka-scene.scene/default-transform)` here."
  []
  {:translation [0.0 0.0 0.0]
   :rotation [0.0 0.0 0.0 1.0]
   :scale [1.0 1.0 1.0]})

(defn bone-rotation
  "`{:bone \"leftUpperArm\" :rotation [x y z w]}` — VRM humanoid bone name +
  quaternion rotation."
  [bone rotation]
  {:bone bone :rotation rotation})

(defn ik-target
  [end-bone target weight]
  {:end-bone end-bone :target target :weight weight})

(def expressions
  "Variant names verbatim from the Rust `Expression` enum."
  #{:neutral :happy :angry :sad :surprised :determined :pained :smirk})

(defn pose-spec
  "Mirrors `PoseSpec`. `root-xform` defaults to `transform-default`."
  ([] (pose-spec {}))
  ([{:keys [root-xform bones ik-targets label]
     :or {root-xform (transform-default) bones [] ik-targets []}}]
   {:root-xform root-xform
    :bones bones
    :ik-targets ik-targets
    :label label}))

(defn rest-pose
  "Mirrors `PoseSpec::rest()`."
  []
  {:root-xform (transform-default)
   :bones []
   :ik-targets []
   :label "rest"})
