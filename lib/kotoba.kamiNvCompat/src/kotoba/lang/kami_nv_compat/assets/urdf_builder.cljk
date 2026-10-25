(ns kotoba.lang.kami-nv-compat.assets.urdf-builder
  "URDF builder helpers — JVM port of src/assets/urdf-builder.ts. Programmatic
  construction of minimal URDFs from joint specs (serial + branched chains) +
  lightweight count/name parsing via regex (no XML-parser dep). Used by the
  Franka Panda + ANYmal C wrappers when a vendored mesh-bearing URDF isn't
  available. Generates valid URDFs (serial link chains, revolute/prismatic/
  continuous/fixed joints with axes + limits, placeholder unit-mass inertias).
  Wave 5 of the kami-nv-compat TS->CLJC port (ADR-2607020130)."
  (:require [kotoba.lang.text :as str]))

(defn- num-str
  "Format a number for XML output, matching JS Number->string (trailing '.0'
  stripped: 100.0 -> \"100\", 1.0 -> \"1\", 0.1 -> \"0.1\")."
  [n]
  (let [s (str n)]
    (if (str/ends-with? s ".0") (subs s 0 (- (count s) 2)) s)))

(def ^:private unit-inertia
  (str "<inertial>"
       "<mass value=\"1.0\"/>"
       "<inertia ixx=\"0.1\" ixy=\"0\" ixz=\"0\" iyy=\"0.1\" iyz=\"0\" izz=\"0.1\"/>"
       "</inertial>"))

(defn- origin-xml [xyz rpy]
  (str "<origin xyz=\"" (num-str (nth xyz 0)) " " (num-str (nth xyz 1)) " " (num-str (nth xyz 2))
       "\" rpy=\"" (num-str (nth rpy 0)) " " (num-str (nth rpy 1)) " " (num-str (nth rpy 2)) "\"/>"))

(defn- link-xml [name]
  (str "<link name=\"" name "\">" unit-inertia "</link>"))

(defn- joint-xml
  [joint parent-link child-link]
  (let [type       (:type joint)
        axis       (or (:axis joint) [0 0 1])
        origin-xyz (or (:origin-xyz joint) [0 0 0.1])
        origin-rpy (or (:origin-rpy joint) [0 0 0])
        base       [(str "<joint name=\"" (:name joint) "\" type=\"" type "\">")
                    (origin-xml origin-xyz origin-rpy)
                    (str "<parent link=\"" parent-link "\"/>")
                    (str "<child link=\"" child-link "\"/>")
                    (str "<axis xyz=\"" (num-str (nth axis 0)) " " (num-str (nth axis 1)) " " (num-str (nth axis 2)) "\"/>")]
        parts      (if (or (= type "revolute") (= type "prismatic"))
                     (let [lower    (or (:lower joint) -3.14159)
                           upper    (or (:upper joint) 3.14159)
                           velocity (or (:velocity joint) 1.0)
                           effort   (or (:effort joint) 100.0)]
                       (conj base (str "<limit lower=\"" (num-str lower) "\" upper=\"" (num-str upper)
                                       "\" velocity=\"" (num-str velocity) "\" effort=\"" (num-str effort) "\"/>")))
                     base)]
    (str/join "" (conj parts "</joint>"))))

;; ── Public builders ───────────────────────────────────────────────────────

(defn build-serial-chain-urdf
  "Build a serial-chain URDF from a list of joint specs. Each joint connects
  link_i -> link_(i+1); link names follow `<robot-name>_link<i>` (i = 0..n)."
  [robot-name joints]
  (str "<?xml version=\"1.0\"?>"
       "<robot name=\"" robot-name "\">"
       (link-xml (str robot-name "_link0"))
       (str/join "" (map-indexed (fn [i joint]
                                   (let [parent (str robot-name "_link" i)
                                         child  (str robot-name "_link" (inc i))]
                                     (str (joint-xml joint parent child) (link-xml child))))
                                 joints))
       "</robot>"))

(defn build-branched-urdf
  "Build a URDF with a common base link and multiple serial branches (e.g. a
  quadruped: base + 4 legs). `branches` is a list of per-branch joint-spec
  lists, each a serial chain rooted at `base-link`. `branch-link-prefixes`
  (optional) names each branch's links."
  ([robot-name base-link branches]
   (build-branched-urdf robot-name base-link branches nil))
  ([robot-name base-link branches branch-link-prefixes]
   (str "<?xml version=\"1.0\"?>"
        "<robot name=\"" robot-name "\">"
        (link-xml base-link)
        (str/join "" (map-indexed (fn [b branch]
                                    (let [prefix      (if (and branch-link-prefixes (< b (count branch-link-prefixes)))
                                                        (nth branch-link-prefixes b)
                                                        (str "branch" b "_link"))
                                          first-child (str prefix "0")]
                                      (str (joint-xml (nth branch 0) base-link first-child)
                                           (link-xml first-child)
                                           (str/join "" (for [i (range 1 (count branch))]
                                                          (let [parent (str prefix (dec i))
                                                                child  (str prefix i)]
                                                            (str (joint-xml (nth branch i) parent child)
                                                                 (link-xml child))))))))
                                  branches))
        "</robot>")))

;; ── Parsing utilities (regex; avoids a full XML-parser dep) ───────────────

(defn count-joints
  "Count non-fixed joints in URDF text via regex."
  [urdf-text]
  (count (for [m (re-seq #"<joint\s+name=\"[^\"]+\"\s+type=\"([^\"]+)\"" urdf-text)
               :let [type (nth m 1)]
               :when (not= type "fixed")]
           m)))

(defn joint-names
  "Return joint names in URDF order (excludes type='fixed')."
  [urdf-text]
  (vec (for [m (re-seq #"<joint\s+name=\"([^\"]+)\"\s+type=\"([^\"]+)\"" urdf-text)
             :let [name (nth m 1) type (nth m 2)]
             :when (not= type "fixed")]
         name)))
