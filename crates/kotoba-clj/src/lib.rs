//! # kotoba-clj — Clojure-subset → WebAssembly compiler
//!
//! `kotoba-clj` reads a Clojure/EDN-subset source program (via the SSoT EDN
//! reader, [`kotoba_edn`]) and **compiles it to real WebAssembly bytes**. The
//! Clojure source literally becomes a wasm module — this is a compiler, not an
//! embedded interpreter.
//!
//! ```
//! let src = r#"
//!   (defn fact [n]
//!     (if (< n 2) 1 (* n (fact (- n 1)))))
//! "#;
//! let wasm = kotoba_clj::compile_str(src).unwrap();
//! assert!(wasm.starts_with(b"\0asm"));
//! # #[cfg(feature = "run")]
//! assert_eq!(kotoba_clj::run::run(&wasm, "fact", &[5]).unwrap(), 120);
//! ```
//!
//! ## Supported subset
//!
//! Values on the stack are 64-bit. A number/boolean is the i64 itself (booleans
//! `1`/`0`, truthy ⇔ non-zero). A **string** is a packed `(offset << 32) | len`
//! handle into linear memory.
//!
//! - top-level: `(def name <const>)`, `(defn name [params…] body…)`, `(ns …)` (ignored)
//! - control: `if`, `when`, `let`, `do`
//! - arithmetic: `+ - * / mod`
//! - comparison: `= < > <= >=`
//! - logic: `and or not` (short-circuit; return 0/1)
//! - strings: `"…"` literals, `(str-len s)`, `(byte-at s i)`
//! - user function calls, including (mutual) recursion
//!
//! Each `defn` is exported under its own name. `def` initialisers are evaluated
//! at compile time and inlined. Every module also exports a linear `memory` and
//! a `cabi_realloc` bump allocator (the Canonical-ABI substrate).
//!
//! ## Roadmap to the kotoba:kais binding
//!
//! Making compiled Clojure load in `kotoba-runtime` means satisfying the
//! `kotoba-node` world's `run(ctx-cbor: list<u8>) -> result<list<u8>, string>`
//! export — which requires linear memory, an allocator, and byte/string values
//! *in the language*. So the dependency order is:
//!
//! 1. ✅ **memory + `cabi_realloc`** (this crate) — exported by every module.
//! 2. ✅ **string/bytes values** — `(ptr,len)` handles, `str-len`/`byte-at`.
//! 3. ✅ **`list<u8>` in/out Component export** via `wit-component`
//!    ([`component`]) — `(defn run [input] …)` → `run: func(list<u8>) ->
//!    list<u8>`, instantiated + invoked through `wasmtime::component`.
//! 4. ⬜ **CBOR-decode `InvokeContext`** in-guest — *blocked on the language
//!    growing loops + byte-building*; a separate, larger workstream.
//! 5. ◐ **emit the `kotoba-node` `run` export** — done as a *load-proof*:
//!    [`component::compile_kais_component_str`] targets the real `kotoba-node`
//!    world (`run: func(list<u8>) -> result<list<u8>, string>`) and
//!    [`component::assert_loads`] confirms it compiles under wasmtime's
//!    Component Model (the `ProgramStore` path). Live invoke through
//!    `WasmExecutor` (satisfying the world's 14 host imports) is the remaining
//!    stretch; meaningfully reading `ctx` is gated on step 4.
//!
//! Steps 1–3 are implemented and step 5 is proven at the load level. A program
//! compiles to a real Component today ([`component::compile_component_str`]);
//! the `kotoba-node` component loads in kotoba-runtime, but does not yet read
//! `ctx`. See `docs/ADR-clojure-wasm.md` for the full plan.

pub mod ast;
pub mod codegen;
#[cfg(feature = "component")]
pub mod component;
#[cfg(feature = "run")]
pub mod run;

use thiserror::Error;

/// Errors across the read → lower → codegen → run pipeline.
#[derive(Debug, Error)]
pub enum CljError {
    /// The EDN reader rejected the source text.
    #[error("read error: {0}")]
    Read(String),
    /// The source parsed as EDN but is not a valid program in the subset.
    #[error("lowering error: {0}")]
    Lower(String),
    /// The AST could not be compiled to wasm (e.g. unbound symbol, bad arity).
    #[error("codegen error: {0}")]
    Codegen(String),
    /// The emitted module failed to instantiate or trapped at run time.
    #[error("runtime error: {0}")]
    Run(String),
}

/// Compile Clojure-subset source text into WebAssembly bytes.
pub fn compile_str(src: &str) -> Result<Vec<u8>, CljError> {
    let program = ast::parse_program(src)?;
    codegen::compile(&program)
}
