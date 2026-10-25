(ns pdk.liberty
  "Compat facade over `kotoba-lang/org-synopsys-liberty` — the Liberty (.lib)
  timing library model + parser was split out of `pdk` on 2026-07-07
  (ADR-2607072500) into its own standards-substrate repo since it's an
  independent industry-standard format (Synopsys Liberty, synopsys.com/liberty),
  not pdk-specific logic. The actual implementation (`parse-liberty`,
  `find-cell`, `cell-count`, `total-area`) lives in `liberty.core` over there;
  this namespace just re-exports it so `pdk` remains a fully-composed PDK
  front-end (technology + stdcell + memory + liberty + lef)."
  (:require [liberty.core :as liberty]))

(def parse-liberty liberty/parse-liberty)
(def find-cell liberty/find-cell)
(def cell-count liberty/cell-count)
(def total-area liberty/total-area)
