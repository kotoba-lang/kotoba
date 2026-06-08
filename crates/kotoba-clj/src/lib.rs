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
//! 3. ⬜ **`list<u8>` in/out Component export** via `wit-component` (the
//!    Canonical-ABI list machinery kotoba:kais reuses).
//! 4. ⬜ **CBOR-decode `InvokeContext`** in-guest.
//! 5. ⬜ **emit the `kotoba-node` `run` export**; load via `WasmExecutor`.
//!
//! Today (steps 1–2) the crate emits a **core wasm module** run on a plain
//! `wasmtime::Engine` ([`run`]); it is not yet a Component bound to the
//! `kotoba:kais` world. See `docs/ADR-clojure-wasm.md` for the full plan.

pub mod ast;
pub mod codegen;
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
