(ns uvm.sv-class
  "Types UVM's component/object runtime model against
  `org-ieee-systemverilog`'s SystemVerilog class model. In real UVM
  (Accellera UVM), uvm_object and uvm_component are not inert
  bookkeeping shapes -- they are SystemVerilog classes: uvm_object is
  the UVM root class and uvm_component extends it (single inheritance,
  IEEE 1800 clause 8), adding the parent/children hierarchy and the
  standard phase-method hooks (build_phase/connect_phase/run_phase --
  a subset of `uvm.phase/phases`) every concrete component overrides.
  This namespace supplies those two base classes as `systemverilog.class`
  maps and resolves a `uvm.component` runtime instance's flattened
  field/method list against a class-registry seeded with those two
  bases plus any user-defined subclasses (e.g. a concrete driver's own
  SystemVerilog class) -- so UVM's runtime component tree is typed
  against SystemVerilog's static class semantics, not just carrying
  inert :type keywords."
  (:require [systemverilog.class :as sv-class]))

(defn uvm-object-class
  "The uvm_object base class every UVM object/component ultimately
  extends (`uvm_object` in Accellera UVM): identity plus the handful
  of reflection/utility methods every derived class inherits, with no
  `:extends` -- it is the root of the UVM class hierarchy."
  []
  (sv-class/make-class
   "uvm_object"
   [{:name "name" :type "string"}]
   [{:name "get_name" :args []}
    {:name "get_type_name" :args []}
    {:name "create" :args []}
    {:name "compare" :args ["rhs"]}]))

(defn uvm-component-class
  "uvm_component extends uvm_object (`:extends` is \"uvm_object\"), adding
  the parent/children hierarchy that mirrors `uvm.component`'s runtime
  tree shape, plus the standard phase-method hooks (build_phase/
  connect_phase/run_phase) every concrete component overrides via
  `uvm.phase/run-phases`."
  []
  (sv-class/make-class
   "uvm_component"
   "uvm_object"
   [{:name "parent" :type "uvm_component"}
    {:name "children" :type "uvm_component[]"}]
   [{:name "build_phase" :args ["phase"]}
    {:name "connect_phase" :args ["phase"]}
    {:name "run_phase" :args ["phase"]}]))

(defn base-class-registry
  "A class-registry (map of class-name -> class map, the shape
  `systemverilog.class/resolve-members` expects) seeded with the two
  UVM base classes. Callers layer their own user-defined subclasses
  on top (e.g. `(assoc (base-class-registry) \"my_driver\" my-driver-class)`)
  before resolving component instances against it."
  []
  (let [obj (uvm-object-class)
        comp (uvm-component-class)]
    {(:name obj) obj (:name comp) comp}))

(defn component->class-instance
  "Resolve `component` (a `uvm.component`-shaped map, `{:name :parent
  :type :children ...}`) against its SystemVerilog type in
  `class-registry`. `component`'s optional `:class` key names its
  concrete SystemVerilog class (e.g. \"my_driver\"); when absent it
  defaults to \"uvm_component\" itself. The named class's fields/
  methods are flattened via `systemverilog.class/resolve-members`,
  walking single inheritance all the way up to uvm_object. Returns
  `{:component component :resolved-class {:fields [...] :methods
  [...]}}` -- this is the real composition point: UVM's runtime
  component tree, typed against SystemVerilog's static class model,
  not a parallel/duplicated type system."
  [component class-registry]
  (let [class-name (or (:class component) "uvm_component")]
    {:component component
     :resolved-class (sv-class/resolve-members class-registry class-name)}))
