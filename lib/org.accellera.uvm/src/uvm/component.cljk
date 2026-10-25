(ns uvm.component
  "UVM component-hierarchy model — mirrors the way real UVM testbenches
  (Accellera UVM, accellera.org) arrange uvm_driver / uvm_monitor /
  uvm_agent / uvm_scoreboard / uvm_env / uvm_test components into a
  single component tree rooted at the test. Components here are plain
  data maps; there is no base uvm_component class, virtual methods, or
  config_db — just the tree shape and the traversal functions real UVM
  code (and `uvm.phase/run-phases`) relies on.")

(def component-types
  "The component roles this model understands, mirroring the common
  UVM base classes (uvm_driver, uvm_monitor, uvm_agent, uvm_scoreboard,
  uvm_env, uvm_test)."
  #{:driver :monitor :agent :scoreboard :env :test})

(defn component
  "Build a component map `{:name :parent :type :children :callbacks}`.
  `type` should be one of `component-types`. `parent` is the name of
  the enclosing component (or nil for the root, typically the test).
  `children` is a vector of child component maps and `callbacks` is a
  phase-keyword -> fn map consumed by `uvm.phase/run-phases`."
  [{:keys [name parent type children callbacks]
    :or {children [] callbacks {}}}]
  {:name name :parent parent :type type :children children :callbacks callbacks})

(defn add-child
  "Return `comp` with `child` appended to its :children — the way a
  parent's build_phase instantiates and hooks up its sub-components."
  [comp child]
  (update comp :children conj child))

(defn walk
  "Depth-first, top-down (parent before children) walk of `comp`'s
  tree, returning a flat vector of every component visited, in visit
  order. The traversal primitive both `find-by-type` and
  `uvm.phase/run-phases` build on."
  [comp]
  (into [comp] (mapcat walk (:children comp))))

(defn find-by-type
  "Return a vector of every component in `comp`'s tree (root
  included) whose :type is `type`, in top-down visit order."
  [comp type]
  (filterv #(= type (:type %)) (walk comp)))

(defn leaf?
  "True if `comp` has no children — e.g. a driver or monitor at the
  bottom of the agent/env/test hierarchy."
  [comp]
  (empty? (:children comp)))

(defn count-by-type
  "Return a map of component-type -> count of components of that type
  across `comp`'s whole tree, a common sanity check on a built
  testbench topology (e.g. \"exactly one scoreboard\")."
  [comp]
  (reduce (fn [counts c] (update counts (:type c) (fnil inc 0)))
          {}
          (walk comp)))
