# kami-engine-guest

> **Standalone SSoT (ADR-2607102200 addendum 10).**  
> Path: `orgs/kotoba-lang/kami-engine-guest` — **not** nested under `kami-engine/`.

`kotoba.engine-clj` — a Clojure/EDN-subset → WASM-targeted-instruction-IR
compiler for KAMI game scripting.

This is a **`.cljc` domain port** of `kami-engine-guest`, a Rust crate that
used to live at `kami-engine-guest/` in the `kotoba-lang/kami-engine` repo. The
crate was removed from that repo's working tree without a commit recording
the deletion; its full source was recovered read-only from `kami-engine`'s
git history (`git show HEAD:kami-engine-guest/<path>`, `kami-engine` left
untouched) as part of the clj-wgsl migration (ADR-2607010930). This repo is
the new, independent home for the ported Clojure implementation.

## What `kami-engine-guest` was

A Clojure-subset compiler that reads a `.clj`/EDN game-script source file and
targets the `kami:engine@1.0.0` WIT world: `spawn-entity`, `set-position!`,
`key-down?`, `draw-mesh!`, `play-sound`, `delta-ms`, and friends, plus
`defsystem` (tick-handler sugar), `defentity` (self-spawning constructor
sugar), and `defatom` (a mutable i64 state cell that persists across ticks).
All guest values are `i64`; f32 values are carried as their IEEE-754
bit-pattern zero-extended into the i64. See `src/kotoba/engine_clj.cljk`'s
namespace docstring for the full language-subset writeup and a worked
example, and `src/kotoba/engine_clj/ast.cljk` for the complete builtin/
host-import surface.

## Namespaces

- `kotoba.engine-clj` — top-level `compile-str` / `compile-file` /
  `compile-str-with-prelude` entry points, plus `game-prelude` (Vec3 /
  timer / growable vector / assoc-map helpers written in the language
  itself — ported verbatim as source text from the Rust `GAME_PRELUDE`
  constant, since it's game-script source, not compiler logic).
- `kotoba.engine-clj.ast` — EDN → typed AST lowering (`parse-program` /
  `parse-program-str`), the `Builtin` / `HostImport` tables, and every
  special-form desugaring (`if-let`, `dotimes`, `as->`, `cond->`, `clamp`,
  `doseq-entities`, …).
- `kotoba.engine-clj.codegen` — typed AST → **Module IR** (see "Where this
  port draws the line" below).
- `kotoba.engine-clj.component` — the `kami:engine/kami-game` WIT world
  described as data, derived from `ast`'s host-import tables.
- `kotoba.engine-clj.interp` — a reference stack-machine interpreter that
  executes `codegen`'s instruction IR, standing in for the Rust originals'
  `wasmtime`/`wasmi` runners so the test suite can prove the IR computes the
  right *values*, not just that codegen didn't throw.
- `kotoba.engine-clj.numerics` — f32-bits ⇄ i64 conversion and UTF-8 byte
  encoding, portable across `:clj`/`:cljs`.
- `kotoba.engine-clj.errors` — structured `ex-info` errors mirroring the
  Rust `CljError` enum (`{Read, Lower, Codegen, Run}`).

## Where this port draws the line: Module IR, not `.wasm` bytes

The Rust `codegen.rs` did two conceptually different things: (1) decide
*which* WASM instructions a given AST node compiles to — local/global
allocation, the block+loop+br lowering that makes `loop`/`recur` yield a
value, the i64↔f32 boxing/unboxing dance, host-call `ParamKind`/`ReturnKind`
lifting, the bump-allocator algorithm — and (2) call `wasm-encoder` to
serialize those `Instruction` values into actual `.wasm` binary bytes
(LEB128 varints, section framing). (1) is the compiler; `codegen.cljc` ports
ALL of it, faithfully, instruction op for instruction op. (2) is mechanical
— a fixed, generic table from instruction keyword to opcode bytes, with no
further semantic decisions of its own — and is out of scope for this
domain port. `compile` returns a **Module IR** instead: a data map
(`{:host-imports … :functions […{:name … :body […instr-tuple…]}…]
:atoms … :consts … :literals … :heap-start … :cabi-realloc … :export-
functions … :export-globals …}`). A future host-adapter package is expected
to do the mechanical byte-emission step. `kotoba.engine-clj.interp` proves
in the meantime that the IR computes the right values by actually running
it (see its docstring's "Honest scope" section for exactly what that proves
and doesn't).

## Building / testing

```bash
kbb -M:lint     # clj-kondo, --fail-level error (0 errors)
kbb -M:test      # cognitect test-runner — 39 tests / 188 assertions, 0 failures
```

## Known upstream gaps (inherited or introduced by this port)

- **`/f` (float division) cannot round-trip through source *text* here.**
  `ast/read-all-forms` is a JVM "convenience" reader substituting for the
  Rust original's `kotoba_edn::parse_all` — an external reader crate
  (`kotoba-edn`, living in a sibling `kotoba` repo) that was out of scope
  for this recovery (only the `kami-engine-guest` crate's own files were
  recovered — see "Unported items" below). The convenience reader is
  backed by `clojure.edn`/`clojure.core`'s own reader, which treats a
  leading `/` as the namespace separator and rejects the bare token `/f`
  (`Invalid token: /f`). This affects ONLY getting the `/f` symbol in from
  source text — the `Builtin`/`ast`/`codegen`/`interp` pipeline itself
  handles `/f` (`:fdiv`) correctly once a `/f` symbol exists as data (see
  `test/kotoba/engine_clj/exec_test.cljk`'s and `parity_test.cljc`'s
  `f32-division-agrees-and-is-correct`-style tests, which construct the
  form programmatically — `(symbol nil "/f")` — to prove this). A real
  `kotoba-edn`-equivalent reader (or a small custom tokenizer) would close
  this gap for actual game-script source files that use `/f`.
- **`codegen.rs`'s `cabi_realloc` dead computation, preserved verbatim.**
  The Rust source computed an aligned pointer, then immediately
  double-`Drop`ped it (steps 1–8 in the original), before recomputing it a
  second time correctly. `codegen.cljc`'s `cabi-realloc-instrs` mirrors
  this EXACTLY (wasteful but not incorrect — verified by hand and by
  `interp`) rather than "cleaning it up", so the ported IR matches the
  original compiler's actual output. See that function's docstring.
- **`:atom-set`'s `:value` is not traversed by the literal-collection or
  host-import-scan passes**, matching Rust's `_ => {}` fallthrough for
  `Expr::AtomSet` in `collect_str`/`scan_imports`. A string literal or
  host-call used directly (not nested in a builtin/call) as a `set-atom!`
  value would miss the literal pool / host-import scan in the *original*
  compiler too — this is an upstream gap, not one introduced by the port.
  See `codegen.cljc`'s `expr-children` docstring.
- **`compile-str` / `compile-file` / `compile-str-with-prelude` are
  `:clj`-only** (`#?(:clj (defn compile-str ...))` in
  `kotoba.engine-clj`), because they depend on `ast/read-all-forms`'s
  `java.io.PushbackReader`-based JVM reader. `ast/parse-program` (the
  already-read-forms entry point), and everything in `ast`/`codegen`/
  `component`/`numerics`, are portable `:clj`/`:cljs`. A `:cljs` source
  reader (or reuse of an existing portable EDN reader) would be needed to
  make the text-based entry points `:cljs`-capable too.

## Unported items (out of scope for this recovery)

- **`component.rs`'s `kami_game_wit` (`include_str!`ing the literal
  `wit/kami-game/world.wit` file)** — that WIT source file lives in a
  sibling directory of the original Rust workspace and was not part of the
  recovered `kami-engine-guest` crate contents. `kotoba.engine-clj.component`
  instead derives the equivalent interface information *as data*
  (`kami-game-world`) from `ast`'s host-import tables, so a future
  host-adapter can regenerate real `.wit` text (or bind directly) without
  re-deriving the interface list by hand.
- **Real `.wasm` byte emission** (`wasm-encoder`'s mechanical LEB128/section
  serialization) — see "Where this port draws the line" above.
- **The `wit-component` adapter encoding** (`component.rs`'s documented
  Phase-3 TODO, ADR-0035) — unimplemented in BOTH the recovered Rust source
  and this port.
- **`bin/kamiclj.rs`'s CLI front-end** (stdin/stdout/file plumbing, exit
  codes) — a thin OS-process shell around `compile-str`/
  `compile-str-with-prelude`; not compiler logic. A `-main` entry point can
  be added straightforwardly against the existing `kotoba.engine-clj` API
  if a CLI is needed.
- **`examples/compile_demo.rs`** — a demo script that wrote a `.wasm` file
  to a sibling `kami-web/` directory (outside this crate) and hand-rolled a
  LEB128 import-section scanner to print human-readable import names; not
  compiler logic, and the target directory doesn't exist in this repo.
- **Two-backend (wasmtime JIT vs. wasmi interpreter) execution parity** —
  see `kotoba.engine-clj.interp`'s and
  `test/kotoba/engine_clj/parity_test.cljk`'s "Honest scope" sections. This
  port has exactly one reference interpreter, so `parity_test.cljc` proves
  determinism (two independent runs of the same source agree) and
  correctness (against known-correct values), not cross-backend agreement.

## License

Apache License 2.0 — see `LICENSE`.
