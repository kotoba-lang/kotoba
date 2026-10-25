(ns kami_articulated.urdf
  "Restored from the legacy kami-engine/kami-articulated Rust crate
  (kotoba-lang/kami-engine, deleted in PR #82 \"Remove Rust workspace from
  kami-engine\") as zero-dep portable CLJC, per ADR-2607010930 (clj-wgsl
  migration, com-junkawasaki/root).

  Purpose (from the original crate docstring / src/urdf.rs): a minimum URDF
  (Unified Robot Description Format) parser for Cartpole-class and small
  manipulator topologies. Supports prismatic + revolute + fixed + continuous
  joints, link mass + inertia, joint axis + limits + dynamics
  damping/friction. Drops (as the original did): visual/collision meshes,
  `<mimic>`, `<transmission>`, Gazebo extensions — none of those are read by
  `parse-urdf` below, matching `parse_urdf` in the original.

  This is pure, load-time XML -> data parsing: no IO, no GPU, no physics
  solver. The original depended on the `roxmltree` crate for XML
  tokenizing (WASM-friendly, chosen per the crate's Cargo.toml \"Pure Rust +
  roxmltree (WASM-friendly)\" note) and on `glam::Vec3` for 3-vectors; since
  both are out of scope for a zero-dep CLJC port, this namespace ships a
  small hand-rolled recursive-descent XML reader (`parse-xml`, scoped to the
  element/attribute subset URDF actually uses — no text nodes, no CDATA, no
  entity decoding beyond none-needed-here) and represents `glam::Vec3` as a
  plain `[x y z]` double vector.

  Explicitly OUT OF SCOPE for this restoration (native/vendor-facade,
  handled elsewhere): the downstream `kami-genesis` articulated
  rigid-body-dynamics solver (PxArticulationReducedCoordinate-shaped, per
  the original's `NV_COMPAT_TARGET = \"isaacsim.core.prims.Articulation\"`)
  that consumes the `ArticulatedSystem` this namespace produces. Only the
  URDF -> data parsing step is ported here.")

#?(:clj (require '[kotoba.lang.text :as str])
   :cljs (require '[kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Minimal recursive-descent XML reader — element/attribute subset only.
;; Produces `{:tag <string> :attrs {<string> <string>} :children [<node>...]}`
;; trees. Mirrors just enough of `roxmltree::Document`/`Node` for `parse-urdf`
;; below (`tag_name().name()`, `.attribute(k)`, `.children()`).
;; ---------------------------------------------------------------------------

(defn- ws-char? [c]
  (or (= c \space) (= c \tab) (= c \newline) (= c \return)))

(defn- skip-ws
  [s i]
  (let [n (count s)]
    (loop [i i]
      (if (and (< i n) (ws-char? (nth s i)))
        (recur (inc i))
        i))))

(defn- strip-comments
  "Remove all `<!-- ... -->` regions (URDF fixtures embed prose comments)."
  [s]
  (loop [s s]
    (let [start (str/index-of s "<!--")]
      (if-not start
        s
        (let [end (str/index-of s "-->" start)]
          (if-not end
            s
            (recur (str (subs s 0 start) (subs s (+ end 3))))))))))

(defn- strip-decl
  "Remove a leading `<?xml ... ?>` declaration, if present."
  [s]
  (let [s (str/trim s)]
    (if (str/starts-with? s "<?xml")
      (if-let [end (str/index-of s "?>")]
        (str/trim (subs s (+ end 2)))
        s)
      s)))

(declare parse-element)

(defn- parse-attrs
  "Parse `name=\"value\"` pairs starting at index `i`. Returns `[attrs next-i]`
  where `next-i` points at the `>` or `/` that ends the opening tag."
  [s i]
  (loop [i (skip-ws s i) attrs {}]
    (let [c (nth s i)]
      (if (or (= c \>) (= c \/))
        [attrs i]
        (let [name-end (loop [j i]
                          (if (or (= (nth s j) \=) (ws-char? (nth s j)))
                            j
                            (recur (inc j))))
              aname (subs s i name-end)
              eq-i (loop [j name-end] (if (= (nth s j) \=) j (recur (inc j))))
              q-i (skip-ws s (inc eq-i))
              quote-char (nth s q-i)
              val-start (inc q-i)
              val-end (loop [j val-start] (if (= (nth s j) quote-char) j (recur (inc j))))
              aval (subs s val-start val-end)
              next-i (skip-ws s (inc val-end))]
          (recur next-i (assoc attrs aname aval)))))))

(defn- parse-children
  "Parse child elements until the matching `</tag>` close tag, starting at
  index `i` (just after the opening tag's `>`)."
  [s i tag attrs]
  (loop [i i children []]
    (let [i (skip-ws s i)]
      (if (and (= (nth s i) \<) (= (nth s (inc i)) \/))
        (let [gt (str/index-of s ">" i)]
          [{:tag tag :attrs attrs :children children} (inc gt)])
        (let [[child ni] (parse-element s i)]
          (recur ni (conj children child)))))))

(defn- parse-element
  "Parse one element (open+children+close, or self-closing) starting at the
  `<` at index `i`. Returns `[node next-i]`."
  [s i]
  (let [i (inc i)
        name-end (loop [j i]
                    (if (or (ws-char? (nth s j)) (= (nth s j) \>) (= (nth s j) \/))
                      j
                      (recur (inc j))))
        tag (subs s i name-end)
        [attrs i2] (parse-attrs s name-end)]
    (cond
      (= (nth s i2) \/) [{:tag tag :attrs attrs :children []} (+ i2 2)]
      (= (nth s i2) \>) (parse-children s (inc i2) tag attrs)
      :else (throw (ex-info (str "malformed xml near position " i2) {:pos i2})))))

(defn parse-xml
  "Parse `xml-str` into a `{:tag :attrs :children}` element tree (root
  element only — declaration and comments are stripped first)."
  [xml-str]
  (let [s (-> xml-str strip-comments strip-decl str/trim)
        start (str/index-of s "<")]
    (when-not start
      (throw (ex-info "no root element found" {})))
    (first (parse-element s start))))

(defn- node-attr [node k] (get (:attrs node) k))

(defn- children-named [node tag] (filterv #(= (:tag %) tag) (:children node)))

(defn- child-named [node tag] (first (children-named node tag)))

;; ---------------------------------------------------------------------------
;; Errors — the original's `thiserror` `ParseError` enum, as tagged maps
;; raised via `ex-info`. `:error/type` is one of `error-types` below;
;; `ex-message` carries wording matching the Rust `#[error(...)]` messages.
;; ---------------------------------------------------------------------------

(def error-types
  "Valid `:error/type` values raised by this namespace (mirrors the original
  `ParseError` enum variants: Xml / MissingElement / MissingAttr /
  InvalidNumber / UnsupportedJointType / UnknownLink)."
  #{:xml :missing-element :missing-attr :invalid-number
    :unsupported-joint-type :unknown-link})

(defn- parse-error [type message data]
  (ex-info message (merge {:error/type type} data)))

;; ---------------------------------------------------------------------------
;; Number/vector parsing helpers.
;; ---------------------------------------------------------------------------

(defn- parse-double*
  "String -> double, or nil if unparsable (portable clj/cljs)."
  [s]
  #?(:clj (try (Double/parseDouble s) (catch Exception _ nil))
     :cljs (let [n (js/parseFloat s)] (when-not (js/isNaN n) n))))

(defn- parse-attr-f32
  "Read+parse a required numeric attribute, throwing `:missing-attr` /
  `:invalid-number` on failure (mirrors `parse_attr_f32` used with `?`)."
  [node attr-name ctx]
  (let [raw (node-attr node attr-name)]
    (when-not raw
      (throw (parse-error :missing-attr
                           (str "missing required attribute `" attr-name "` on element `" ctx "`")
                           {:elem ctx :attr attr-name})))
    (let [v (parse-double* raw)]
      (when-not v
        (throw (parse-error :invalid-number (str "invalid number `" raw "` in " ctx) {:value raw :ctx ctx})))
      v)))

(defn- try-attr-f32
  "Like `parse-attr-f32` but returns `default` on any failure (mirrors
  `parse_attr_f32(...).unwrap_or(default)` call sites in the original)."
  [node attr-name ctx default]
  (try
    (parse-attr-f32 node attr-name ctx)
    (catch #?(:clj Exception :cljs :default) _ default)))

(defn- parse-vec3
  "`\"x y z\"` -> `[x y z]` doubles. Throws `:invalid-number` if not exactly
  3 whitespace-separated numbers (mirrors `parse_vec3`)."
  [s]
  (let [parts (str/split (str/trim s) #"\s+")
        nums (mapv parse-double* parts)]
    (if (and (= 3 (count parts)) (every? some? nums))
      nums
      (throw (parse-error :invalid-number (str "invalid number `" s "` in vec3") {:value s :ctx "vec3"})))))

;; ---------------------------------------------------------------------------
;; Domain data — `Pose` / `Inertia` / `Link` / `Joint` / `ArticulatedSystem`
;; are plain maps (the original's Rust structs). `JointKind` is a keyword
;; drawn from `joint-kind-values`.
;; ---------------------------------------------------------------------------

(def default-pose
  "The zero `Pose` (mirrors `Pose::default()`: xyz/rpy both `Vec3::ZERO`)."
  {:xyz [0.0 0.0 0.0] :rpy [0.0 0.0 0.0]})

(defn- parse-pose [node]
  (let [xyz-s (node-attr node "xyz")
        rpy-s (node-attr node "rpy")]
    {:xyz (if xyz-s (parse-vec3 xyz-s) [0.0 0.0 0.0])
     :rpy (if rpy-s (parse-vec3 rpy-s) [0.0 0.0 0.0])}))

(def default-inertia
  "The zero `Inertia` (mirrors `Inertia::default()`)."
  {:mass 0.0 :ixx 0.0 :iyy 0.0 :izz 0.0 :ixy 0.0 :ixz 0.0 :iyz 0.0 :com default-pose})

(def joint-kind-values
  "Valid `:kind` values (mirrors the original `JointKind` enum)."
  #{:fixed :prismatic :revolute :continuous})

(defn- parse-link
  "Build a `Link` map (`{:name :inertia}`) from a `<link>` node. Throws
  `:missing-attr` if `name` is absent (mirrors `parse_link`)."
  [node]
  (let [nm (node-attr node "name")]
    (when-not nm
      (throw (parse-error :missing-attr "missing required attribute `name` on element `link`"
                           {:elem "link" :attr "name"})))
    (let [in-node (child-named node "inertial")]
      (if-not in-node
        {:name nm :inertia default-inertia}
        (let [origin (child-named in-node "origin")
              com (if origin (parse-pose origin) default-pose)
              mass-node (child-named in-node "mass")
              mass (if mass-node (parse-attr-f32 mass-node "value" "mass") 0.0)
              inertia-node (child-named in-node "inertia")
              inertia (if-not inertia-node
                        (assoc default-inertia :mass mass :com com)
                        {:mass mass
                         :ixx (parse-attr-f32 inertia-node "ixx" "inertia")
                         :iyy (parse-attr-f32 inertia-node "iyy" "inertia")
                         :izz (parse-attr-f32 inertia-node "izz" "inertia")
                         :ixy (try-attr-f32 inertia-node "ixy" "inertia" 0.0)
                         :ixz (try-attr-f32 inertia-node "ixz" "inertia" 0.0)
                         :iyz (try-attr-f32 inertia-node "iyz" "inertia" 0.0)
                         :com com})]
          {:name nm :inertia inertia})))))

(defn- joint-kind-of
  "String -> `JointKind` keyword, or throw `:unsupported-joint-type` for
  anything other than fixed/prismatic/revolute/continuous."
  [s]
  (case s
    "fixed" :fixed
    "prismatic" :prismatic
    "revolute" :revolute
    "continuous" :continuous
    (throw (parse-error :unsupported-joint-type
                         (str "unsupported joint type `" s "` (expected prismatic | revolute | fixed | continuous)")
                         {:value s}))))

(defn- parse-joint
  "Build a `Joint` map from a `<joint>` node (mirrors `parse_joint`)."
  [node]
  (let [nm (node-attr node "name")
        _ (when-not nm
            (throw (parse-error :missing-attr "missing required attribute `name` on element `joint`"
                                 {:elem "joint" :attr "name"})))
        kind-str (node-attr node "type")
        _ (when-not kind-str
            (throw (parse-error :missing-attr "missing required attribute `type` on element `joint`"
                                 {:elem "joint" :attr "type"})))
        kind (joint-kind-of kind-str)
        parent-node (child-named node "parent")
        parent (when parent-node (node-attr parent-node "link"))
        _ (when-not parent
            (throw (parse-error :missing-element "missing required element: joint/parent" {:elem "joint/parent"})))
        child-node (child-named node "child")
        child (when child-node (node-attr child-node "link"))
        _ (when-not child
            (throw (parse-error :missing-element "missing required element: joint/child" {:elem "joint/child"})))
        origin-node (child-named node "origin")
        origin (if origin-node (parse-pose origin-node) default-pose)
        axis-node (child-named node "axis")
        axis-s (when axis-node (node-attr axis-node "xyz"))
        axis (if axis-s (parse-vec3 axis-s) [1.0 0.0 0.0])
        limit-node (child-named node "limit")
        [lower upper effort velocity]
        (if limit-node
          [(try-attr-f32 limit-node "lower" "limit" ##-Inf)
           (try-attr-f32 limit-node "upper" "limit" ##Inf)
           (try-attr-f32 limit-node "effort" "limit" 0.0)
           (try-attr-f32 limit-node "velocity" "limit" 0.0)]
          [##-Inf ##Inf 0.0 0.0])
        dynamics-node (child-named node "dynamics")
        [damping friction]
        (if dynamics-node
          [(try-attr-f32 dynamics-node "damping" "dynamics" 0.0)
           (try-attr-f32 dynamics-node "friction" "dynamics" 0.0)]
          [0.0 0.0])]
    {:name nm :kind kind :parent parent :child child :origin origin :axis axis
     :lower lower :upper upper :effort effort :velocity velocity
     :damping damping :friction friction}))

(defn link-index
  "Index of the link named `nm` in `sys`, else nil (mirrors
  `ArticulatedSystem::link_index`)."
  [sys nm]
  (first (keep-indexed (fn [i l] (when (= (:name l) nm) i)) (:links sys))))

(defn joint-index
  "Index of the joint named `nm` in `sys`, else nil (mirrors
  `ArticulatedSystem::joint_index`)."
  [sys nm]
  (first (keep-indexed (fn [i j] (when (= (:name j) nm) i)) (:joints sys))))

(defn parse-urdf
  "Parse a URDF XML string into an `ArticulatedSystem` map
  (`{:name :links :joints}`). Throws `ex-info` (see `error-types`) on
  malformed input, unsupported joint types, or joint parent/child references
  to unknown links (mirrors `parse_urdf`)."
  [xml-str]
  (let [root (try
               (parse-xml xml-str)
               (catch #?(:clj Exception :cljs :default) e
                 (throw (parse-error :xml (str "xml parse: " (ex-message e)) {}))))
        nm (or (node-attr root "name") "robot")
        links (mapv parse-link (children-named root "link"))
        joints (mapv parse-joint (children-named root "joint"))
        known (set (map :name links))]
    (doseq [j joints]
      (when (and (not= (:parent j) "world") (not (contains? known (:parent j))))
        (throw (parse-error :unknown-link
                             (str "unknown link `" (:parent j) "` referenced by joint `" (:name j) "`")
                             {:link (:parent j) :joint (:name j)})))
      (when-not (contains? known (:child j))
        (throw (parse-error :unknown-link
                             (str "unknown link `" (:child j) "` referenced by joint `" (:name j) "`")
                             {:link (:child j) :joint (:name j)}))))
    {:name nm :links links :joints joints}))
