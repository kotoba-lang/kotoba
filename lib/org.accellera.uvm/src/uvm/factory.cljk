(ns uvm.factory
  "Minimal uvm_factory-style type-override registry. Real UVM code
  never calls `new` on a component/object type directly — it goes
  through `uvm_factory::create_component_by_name` /
  `create_object_by_name` so tests can register a
  `set_type_override_by_name` and get an alternate implementation
  without touching the code under test. This models that same
  override-then-fall-back-to-default resolution, without the
  string/type-handle machinery or instance-specific overrides.")

(defn create-factory
  "Build an atom-backed factory registry. `default-ctors` (optional) is
  a map of type-name -> constructor-fn used whenever no override has
  been registered for that type-name — the factory's out-of-the-box
  behavior before any `set-type-override!`."
  ([] (create-factory {}))
  ([default-ctors]
   (atom {:defaults default-ctors :overrides {}})))

(defn set-type-override!
  "Register `override-ctor-fn` as the constructor `create` should use
  for `original-type-name` from now on, mirroring
  `uvm_factory::set_type_override_by_name`. Returns `factory`."
  [factory original-type-name override-ctor-fn]
  (swap! factory assoc-in [:overrides original-type-name] override-ctor-fn)
  factory)

(defn clear-override!
  "Remove any override registered for `type-name`, reverting `create`
  to that type-name's default constructor. Returns `factory`."
  [factory type-name]
  (swap! factory update :overrides dissoc type-name)
  factory)

(defn overridden?
  "True if `type-name` currently has an override registered on
  `factory` (as opposed to falling back to its default constructor)."
  [factory type-name]
  (contains? (:overrides @factory) type-name))

(defn create
  "Resolve `type-name` to a constructor — an override registered via
  `set-type-override!` takes precedence, otherwise `factory`'s default
  constructor for that type-name is used — and invoke it with `args`.
  Throws `ex-info` if `type-name` has neither an override nor a
  default, mirroring uvm_factory's fatal \"Cannot create\" error for
  an unregistered type-name."
  [factory type-name & args]
  (let [{:keys [defaults overrides]} @factory
        ctor (or (get overrides type-name) (get defaults type-name))]
    (if ctor
      (apply ctor args)
      (throw (ex-info (str "uvm.factory: no constructor registered for type-name "
                            (pr-str type-name))
                       {:type-name type-name})))))
