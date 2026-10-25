(ns ibis.component
  "IBIS Component/Pin/Package model. A component has a name, a
  manufacturer, a default package RLC parasitic spec (applied to any pin
  that doesn't override it), and a pin list mapping pin-name ->
  {:signal-name :model-name :r-pin :l-pin :c-pin}.

  Simplified subset of the IBIS Open Forum's IBIS spec (ibis.org): single
  package default + per-pin overrides only, no differential pin mapping,
  no series/submodel pins.")

(defn package
  "A package parasitic spec: default R_pkg (ohms) / L_pkg (nH) / C_pkg
  (pF) applied to any pin that doesn't specify its own [R L C] override."
  [{:keys [r-pkg l-pkg c-pkg] :or {r-pkg 0.0 l-pkg 0.0 c-pkg 0.0}}]
  {:r-pkg r-pkg :l-pkg l-pkg :c-pkg c-pkg})

(defn pin
  "A single component pin: `signal-name` is the net it carries,
  `model-name` names the [Model] its buffer behavior comes from, and
  `r-pin`/`l-pin`/`c-pin` are optional per-pin package parasitic
  overrides (nil means: fall back to the component's default package)."
  [{:keys [signal-name model-name r-pin l-pin c-pin]}]
  {:signal-name signal-name :model-name model-name
   :r-pin r-pin :l-pin l-pin :c-pin c-pin})

(defn component
  "A component: `name`, `manufacturer`, a default `pkg` (see `package`),
  and `pins` — a map of pin-name -> pin (see `pin`)."
  ([name manufacturer pkg] (component name manufacturer pkg {}))
  ([name manufacturer pkg pins]
   {:name name :manufacturer manufacturer :package pkg :pins pins}))

(defn add-pin
  "Return `comp` with `pin-name` -> `pin-spec` (a map, see `pin`) added to
  its pin list."
  [comp pin-name pin-spec]
  (assoc-in comp [:pins pin-name] (pin pin-spec)))

(defn pin-parasitics
  "Resolve the effective `{:r :l :c}` package parasitics for `pin-name` on
  `comp`: its own per-pin overrides where given, else `comp`'s default
  package values."
  [comp pin-name]
  (let [{:keys [r-pin l-pin c-pin]} (get-in comp [:pins pin-name])
        {:keys [r-pkg l-pkg c-pkg]} (:package comp)]
    {:r (or r-pin r-pkg) :l (or l-pin l-pkg) :c (or c-pin c-pkg)}))
