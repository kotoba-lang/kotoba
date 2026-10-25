(ns kotoba.sarutahiko-factory
  "猿田彦 (sarutahiko) Class-8 cargo truck assembly plant — pure data/domain
  contract, ported from the Rust `kami-app-sarutahiko-factory` crate
  (`orgs/kotoba-lang/kami-engine`) per ADR-2607010000
  (kotoba-runtime-sdk-cljc-migration).

  The plant designs the 猿田彦 truck end-to-end in kami-engine + kotoba EAVT
  (ADR-2606013100 / ADR-2605252500) and reuses the giemon-factory 4D-BIM
  construction-sequence-playback pattern (ADR-2606010030, shared with the
  sibling `kami-app-tatekata` crate).

  This library owns the *domain data model*: factory layout (buildings /
  zones / machines / MEP / site), the 4D construction order, the robot
  roster, the production line (stations), the 積込ロボット (finished-truck
  loading robot) logistics config, and engineering-clash records — plus
  pure derivation/validation functions over that data. It does **not** own
  wgpu rendering, `wasm_bindgen` entry points, or the kami-genesis
  rigid-body/articulation contact solver that the original Rust crate used
  to animate arm6 work-cells and AGV/loader physics — those remain
  unported host-adapter concerns (see the README's 'Unported' section).

  No network, no I/O in the domain namespaces
  (`kotoba.sarutahiko-factory.factory` / `.construction-order` / `.robots`
  / `.prod-order` / `.loader` / `.clashes`): callers read/parse EDN data
  and pass it in, same convention as `kotoba-lang/giemon`. The one
  exception is `kotoba.sarutahiko-factory.fixtures`, a JVM-only resource
  loader for this repo's synthetic test fixtures (real upstream scene data
  is unavailable in this checkout — see README).

  Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM (domain
  namespaces only; `fixtures` is `:clj`-only I/O).")

(def plant
  "Static plant identity metadata (not derived from any fixture — just the
  crate's own self-description)."
  {:plant/id "sarutahiko-factory"
   :plant/product "猿田彦 (sarutahiko) Class-8 cargo truck"
   :plant/site "sarutahiko-factory.etzhayyim.com"
   :plant/pattern :giemon-factory-4d-bim
   :plant/adr-refs ["ADR-2606013100" "ADR-2605252500" "ADR-2606010030"
                     "ADR-2607010000"]})
