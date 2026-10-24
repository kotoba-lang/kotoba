(ns kotoba.engine-clj.component
  "WIT Component Model world binding for compiled kami-clj core modules —
  ported as a data schema.

  Mirrors `kami-engine-clj`'s Rust `src/component.rs` (26 lines; deleted,
  uncommitted, recovered from `kami-engine` git history, clj-wgsl migration
  ADR-2607010930). The Rust file did two things: (1) `wrap_as_component` — a
  documented pass-through TODO (\"full wit-component adapter encoding is a
  Phase-3 item, ADR-0035\"); it returns the core-module bytes unchanged
  because `kami-script-runtime`'s wasmtime host loads core modules directly.
  (2) `kami_game_wit` — `include_str!`s the WIT world source text from the
  sibling `wit/kami-game/world.wit` file for callers that want the raw IDL.

  Neither is compiler logic. (1) ports 1:1 below as a genuine pass-through
  (there being nothing to wrap yet, in either language). (2) — embedding a
  WIT *text* file — isn't portable AST/codegen logic to begin with; instead
  this namespace derives the equivalent information *as data* from
  `kotoba.engine-clj.ast`'s host-import tables (which already encode every
  `(module, field, param-kinds, return-kind)` triple the WIT world declares),
  so a future host-adapter can regenerate real `.wit` text — or bind
  directly — without re-deriving the interface list by hand. The literal
  `wit/kami-game/world.wit` file itself was not part of the recovered
  `kami-engine-clj` crate contents (it lives in a sibling directory of the
  Rust workspace) and is out of scope for this port — see README \"Unported
  items\"."
  (:require [kotoba.engine-clj.ast :as ast]))

(def kami-game-world
  "The `kami:engine/kami-game` WIT world described as data: one entry per
  WASM import interface (`kami:engine/scene@1.0.0`, `.../physics@1.0.0`,
  `.../input@1.0.0`, `.../render@1.0.0`, `.../audio@1.0.0`,
  `.../steam@1.0.0`, `.../time@1.0.0`, `.../random@1.0.0`), each holding the
  functions that interface exports, derived from
  `kotoba.engine-clj.ast/host-import->module-field` (the single source of
  truth for the import surface, shared with codegen)."
  (->> ast/host-import->module-field
       (group-by (fn [[_hi [module _field]]] module))
       (into {}
             (map (fn [[module entries]]
                    [module
                     (mapv (fn [[hi [_module field]]]
                             {:function     field
                              :host-import  hi
                              :param-kinds  (get ast/host-import->param-kinds hi)
                              :return-kind  (get ast/host-import->return-kind hi)})
                           entries)])))))

(defn wrap-as-component
  "Wrap a compiled core-module Module IR (`kotoba.engine-clj.codegen/compile`
  output) as a WIT component targeting `kami:engine/kami-game`.

  Pass-through today — mirrors the Rust original's documented Phase-3 TODO
  (ADR-0035): full wit-component adapter encoding (interface tables,
  canonical-ABI lifting/lowering) is unimplemented in BOTH the recovered
  Rust source and this port. A `kami-script-runtime`-style wasmtime/wasmi
  host can load the core module directly, so component wrapping is optional
  for the current phase."
  [module-ir]
  module-ir)
