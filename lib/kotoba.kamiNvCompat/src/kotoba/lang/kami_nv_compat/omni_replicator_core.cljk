(ns kotoba.lang.kami-nv-compat.omni-replicator-core
  "Drop-in `omni.replicator.core` API-compat facade — portable .cljc port of
  src/omni-replicator-core.ts. Synthetic-data generation + domain
  randomization: mirrors the documented Replicator surface
  (`rep.distribution.*`, `rep.create/modify/randomize.*`,
  `rep.WriterRegistry`, `rep.new_layer()` / `rep.trigger.on_frame()` /
  `rep.orchestrator.run()`), so Isaac Sim Replicator scripts port to KAMI via
  require-path-only changes.

  Nearly all of this facade is TS re-export bookkeeping with no CLJC
  equivalent need — every sampler / distribution / create / modify /
  randomize / writer / render-bridge / orchestrator function is already
  ported 1:1 in the utsushimi.* namespaces; callers require those directly
  (matching the kami-rt.index / omni-kit-app barrel precedent). Renamed vs.
  the TS surface (collision with core forms — see utsushimi.randomize /
  utsushimi.writers docstrings): `resolve` -> `resolve-op`, `IWriter` ->
  `IUtsushimiWriter`, `finalize` -> `finalize-writer`.

  The one piece of real new logic is Layer: a Replicator authoring layer
  (captured primitives, randomizers, writers, frame count) mirroring the
  `with rep.new_layer():` context — TS has no `with`, so the layer is an
  explicit mutable object; here, an atom-backed reify with the same fluent-
  builder shape as kami-drive.coc/causation-builder. TS's variadic
  `...prims: PrimSpec[]` becomes a single seq arg per mutator — idiomatic
  Clojure, e.g. `(add-primitives! layer [p1 p2])` not `(add-primitives!
  layer p1 p2)`.

  Backed by the clean-room utsushimi engine (bit-reproducible DR sampler +
  kami-rt projection for real ground-truth boxes). No Replicator source or
  binaries; from-spec reproduction of the public API + on-disk schema
  (Google v. Oracle, 593 U.S. ___ (2021)). Canonical engine: utsushimi.

  Trademark: NVIDIA® / Omniverse® / Replicator are trademarks of NVIDIA
  Corporation; API-compat identifiers only.

  ADR-2605261800 §D1/D6, R1.3 omni-replicator-core surface. Wave 38 of
  ADR-2607020130.")

;; ── new_layer / trigger / orchestrator (Replicator script-graph shape) ──────

(defprotocol ILayer
  "A Replicator authoring layer: captured primitives, triggers, and writers.
  Mirrors the `with rep.new_layer():` context."
  (on-frame!         [this num-frames] "Sets the frame count; mirrors `with rep.trigger.on_frame(n):`.")
  (add-primitives!   [this prims]      "Appends a seq of PrimSpecs.")
  (add-randomizers!  [this ops]        "Appends a seq of RandomizeOps.")
  (add-writers!      [this writers]    "Appends a seq of Writers.")
  (layer-primitives  [this])
  (layer-randomizers [this])
  (layer-writers     [this])
  (layer-num-frames  [this]))

(defn new-layer
  "Build a new, empty ILayer (num-frames defaults to 1)."
  []
  (let [state (atom {:primitives [] :randomizers [] :writers [] :num-frames 1})]
    (reify ILayer
      (on-frame!        [this n]       (swap! state assoc :num-frames n) this)
      (add-primitives!  [this prims]   (swap! state update :primitives into prims) this)
      (add-randomizers! [this ops]     (swap! state update :randomizers into ops) this)
      (add-writers!     [this writers] (swap! state update :writers into writers) this)
      (layer-primitives  [_] (:primitives @state))
      (layer-randomizers [_] (:randomizers @state))
      (layer-writers     [_] (:writers @state))
      (layer-num-frames  [_] (:num-frames @state)))))

(def kami-engine "utsushimi")
(def adr "ADR-2605261800")
