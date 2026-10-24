(ns systemverilog.interface
  "SystemVerilog (IEEE 1800) `interface`/`modport` modeling.

  An interface bundles a signal list; a modport gives one named
  direction-restricted view of a subset of those signals for a given
  connecting module (IEEE 1800 clause 25).")

(defn make-interface
  "`signals` is a seq of `systemverilog.datatype/signal` maps.
  `modports` is `{modport-name {signal-name direction}}` where
  direction is `:input`/`:output`/`:inout`."
  [name signals modports]
  {:name name :signals (vec signals) :modports (or modports {})})

(defn signal-names
  [iface]
  (set (map :name (:signals iface))))

(defn dangling-refs
  "Every modport signal reference must name a signal that actually
  exists on the interface. Returns a seq of `[modport-name
  signal-name]` pairs for references that don't -- empty when the
  interface/modport model is well-formed."
  [iface]
  (let [known (signal-names iface)]
    (for [[modport dirs] (:modports iface)
          signal-name (keys dirs)
          :when (not (contains? known signal-name))]
      [modport signal-name])))

(defn valid?
  [iface]
  (empty? (dangling-refs iface)))
