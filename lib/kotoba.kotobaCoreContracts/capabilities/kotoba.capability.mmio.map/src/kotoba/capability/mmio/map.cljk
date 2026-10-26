(ns kotoba.capability.mmio.map
  "Importable contract for mmio/map.")

(def manifest
  {:schema "kotoba.capability.repository.v1", :capability/version 1, :capability/hash-contract-cid "bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi", :capability/definition-cid "bafyreigeh26tuyndf55r2d3garz4m3dndcgumlalu6x2mnhvhtuctu3l5i", :capability/dependencies #{}, :capability/imports #{:mmio-map}, :authority "kotoba-lang/kotoba-core-contracts", :capability/default-policy :autonomous, :capability/artifact {:format :wasm-component, :digest-required? true, :signature-required? true}, :capability/radicle-rid "rad:z3Pfx2pcf59cizdozsEEY1m6a2si3", :capability/repository "kotoba-lang/capability-mmio-map", :capability/id "mmio/map", :capability/effects #{:memory-access :device-control}, :capability/provider-status :contract-only})

(def supported-widths #{1 2 4})

(defn access-valid?
  "MMIO access must use an admitted width, be naturally aligned, and fit
  entirely inside the mapped region."
  [length offset width]
  (and (contains? supported-widths width)
       (<= 0 offset)
       (<= width length)
       (<= offset (- length width))
       (zero? (bit-and offset (dec width)))))
