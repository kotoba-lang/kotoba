(ns pdk.lef
  "Compat facade over `kotoba-lang/org-si2-lef` — the LEF (Library Exchange
  Format) physical-abstract library model + parser was split out of `pdk`
  on 2026-07-07 (ADR-2607072500) into its own standards-substrate repo since
  it's an independent industry-standard format (Si2, si2.org), not
  pdk-specific logic. The actual implementation (`parse-lef`, `find-macro`)
  lives in `lef.core` over there; this namespace just re-exports it so `pdk`
  remains a fully-composed PDK front-end (technology + stdcell + memory +
  liberty + lef)."
  (:require [lef.core :as lef]))

(def parse-lef lef/parse-lef)
(def find-macro lef/find-macro)
