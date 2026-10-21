(ns kotoba.fmt.pprint-str
  "pprint-str -- addressed on its own.

  Split out of kotoba.lang.fmt on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.fmt.default-opts :refer [default-opts]]
            [kotoba.fmt.format-str :refer [format-str]])
)

(defn pprint-str
  "Pretty-print `x` (an EDN value: map/vector/set/seq/scalar) to a
  human-readable indented string. Same engine as `format-str` -- this exists
  so callers who want `(with-out-str (pprint x))` from `clojure.pprint` can
  call a string-returning function directly instead. Options: `:indent`
  (default 2), `:margin` (default 80)."
  ([x] (format-str x default-opts))
  ([x opts] (format-str x opts)))
