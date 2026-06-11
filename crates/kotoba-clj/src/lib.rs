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
//! - control: `if`, `when`, `cond`, `let`, `do`, `loop`/`recur` (bounded iteration)
//! - arithmetic: `+ - * / mod`
//! - comparison: `= < > <= >=`
//! - logic: `and or not` (short-circuit; return 0/1)
//! - strings: `"…"` literals, `(str-len s)`, `(byte-at s i)`
//! - byte builder: `(bytes-alloc cap)`, `(byte-append! buf b)`, `(bytes-len buf)`,
//!   `(bytes-finish buf)` — a mutable buffer in linear memory; `bytes-finish`
//!   yields a string handle (the foundation for in-guest CBOR encode/decode)
//! - raw memory: `(alloc n)`, `(load64 a)`, `(store64! a v)`, `(load32 a)`,
//!   `(store32! a v)` — the substrate the [`PRELUDE`] vector/map build on
//! - host calls: `(has-capability? resource ability)` → `auth.has-capability`;
//!   `(llm-infer model prompt)` → `llm.infer` (ok → output handle, err → `0`).
//!   These grow a real wasm import section wired to the `kotoba:kais` world.
//! - in-guest CBOR decode via [`CBOR_PRELUDE`] (`cbor-reader`, `cbor-uint`,
//!   `cbor-text`, `cbor-map-seek`, …) — decode a `run(ctx-cbor)` payload
//! - in-guest CBOR encode via [`CBOR_ENC_PRELUDE`] (`cbor-enc-uint!`,
//!   `cbor-enc-text!`, `cbor-enc-map-header!`, …) — return a structured result
//! - `(defgraph name :entry :n :nodes {…} :edges {…} [:state {…}])` — a
//!   langgraph-shaped control-flow graph; desugars to dispatch/next/runner (and,
//!   with `:state`, a reducer-merge) `defn`s. Static + `(if-edge pred? :then
//!   :else)` edges; `:state {:ch add-messages}` makes nodes return partial
//!   updates merged per channel (extend vs override). State = a Stage-B map.
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
//! 5. ✅ **emit the `kotoba-node` `run` export + run it on kotoba-runtime.**
//!    [`component::compile_kais_component_str`] targets the real `kotoba-node`
//!    world (`run: func(list<u8>) -> result<list<u8>, string>`).
//!    [`component::assert_loads`] confirms it compiles under the Component Model
//!    (the `ProgramStore` path), and — verified in `tests/kais_invoke.rs` — the
//!    runtime's own `WasmExecutor` (binding all `kotoba:kais` host imports)
//!    instantiates it and invokes `run(ctx)` end-to-end, lifting the result.
//!
//! Steps 1–3 and 5 are implemented: a Clojure program compiles to a Component
//! that **runs on kotoba-runtime's `WasmExecutor`**. The one boundary left is
//! step 4 — the wrapper passes raw `ctx-cbor` to the program undecoded, so a
//! program that *meaningfully reads* `ctx`/`args` needs the language to grow
//! loops + byte-building (CBOR decode). See `docs/ADR-clojure-wasm.md`.

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

/// A dynamic-container prelude written in the kotoba-clj subset **itself**:
/// growable `vector` and string-keyed `map`, built on the raw-memory builtins
/// (`alloc`/`load64`/`store64!`) and Stage-A `loop`/`recur`. This is the heap
/// substrate a langgraph-style `state` map and `messages` vector need.
///
/// Representation (raw i64 handles into linear memory; bump-only, no GC):
/// - **vector** `[len:i64@0, cap:i64@8, elem:i64×cap @16+8i]` — elements are
///   arbitrary i64 (numbers, string handles, or nested vector/map handles).
/// - **map** `[len:i64@0, cap:i64@8, (key:i64, val:i64)×cap @16+16i]` — keys are
///   string handles compared by content (`str-eq?`); linear scan.
///
/// Prepend it with [`compile_str_with_prelude`]. Names: `vec-make` `vec-count`
/// `vec-nth` `vec-conj!` `vec-extend!` (the `add_messages` reducer), `map-make`
/// `map-count` `map-get` `map-assoc!`, and `str-eq?`.
pub const PRELUDE: &str = r#"
;; ---- vector: [len, cap, e0, e1, …] ----------------------------------------
(defn vec-make [cap]
  (let [p (alloc (* 8 (+ 2 cap)))]
    (store64! p 0)
    (store64! (+ p 8) cap)
    p))
(defn vec-count [v] (load64 v))
(defn vec-nth [v i] (load64 (+ v (* 8 (+ 2 i)))))
(defn vec-conj! [v x]
  (let [n (load64 v)]
    (store64! (+ v (* 8 (+ 2 n))) x)
    (store64! v (+ n 1))
    v))
;; add_messages reducer: extend dst with every element of src (returns dst)
(defn vec-extend! [dst src]
  (loop [i 0]
    (if (>= i (vec-count src))
      dst
      (do (vec-conj! dst (vec-nth src i))
          (recur (+ i 1))))))

;; ---- string equality by content -------------------------------------------
(defn str-eq? [a b]
  (if (= (str-len a) (str-len b))
    (loop [i 0]
      (if (>= i (str-len a))
        1
        (if (= (byte-at a i) (byte-at b i))
          (recur (+ i 1))
          0)))
    0))

;; ---- map: [len, cap, k0, v0, k1, v1, …] (string keys, linear scan) ---------
(defn map-make [cap]
  (let [p (alloc (* 8 (+ 2 (* 2 cap))))]
    (store64! p 0)
    (store64! (+ p 8) cap)
    p))
(defn map-count [m] (load64 m))
;; positional accessors (for iterating all entries, e.g. reducer merge)
(defn map-key-at [m i] (load64 (+ m (+ 16 (* 16 i)))))
(defn map-val-at [m i] (load64 (+ m (+ 24 (* 16 i)))))
;; index of key k, or -1
(defn map-find [m k]
  (let [n (load64 m)]
    (loop [i 0]
      (if (>= i n)
        -1
        (if (str-eq? (load64 (+ m (+ 16 (* 16 i)))) k)
          i
          (recur (+ i 1)))))))
(defn map-get [m k]
  (let [idx (map-find m k)]
    (if (< idx 0)
      0
      (load64 (+ m (+ 24 (* 16 idx)))))))
(defn map-assoc! [m k v]
  (let [idx (map-find m k)]
    (if (< idx 0)
      (let [n (load64 m)
            base (+ m (+ 16 (* 16 n)))]
        (store64! base k)
        (store64! (+ base 8) v)
        (store64! m (+ n 1))
        m)
      (do (store64! (+ m (+ 24 (* 16 idx))) v) m))))
"#;

/// An **in-guest CBOR decoder** (subset) written in the kotoba-clj language,
/// closing the ADR's step-4 gap: a `kotoba-node` `run(ctx-cbor)` can now decode
/// its `InvokeContext`/args instead of receiving them raw. Built on Stage-A
/// `loop`/`recur` + `byte-at` and Stage-B `str-eq?` — no bitwise ops needed: a
/// CBOR head byte splits as major `(/ b 32)`, info `(mod b 32)`, and multi-byte
/// lengths assemble with `(* 256)`.
///
/// Supported: major types 0 (uint), 1 (negint, skip-only), 2 (bytes), 3 (text),
/// 4 (array), 5 (map); length encodings inline / 1 / 2 / 4 bytes. **Not** yet:
/// 8-byte lengths (info 27), indefinite-length (info 31), tags, floats.
///
/// A *reader* is a heap cell `[ctx-handle@0, pos@8]`; `pos` is a byte index.
/// Key entry points: `cbor-reader` `cbor-uint` `cbor-text` (→ a string handle
/// slicing the ctx) `cbor-skip` `cbor-map-seek` (position at a text key's value).
/// Depends on [`PRELUDE`] (`str-eq?`).
pub const CBOR_PRELUDE: &str = r#"
(defn cbor-reader [ctx]
  (let [r (alloc 16)]
    (store64! r ctx)
    (store64! (+ r 8) 0)
    r))
(defn cbor-ctx [r] (load64 r))
(defn cbor-pos [r] (load64 (+ r 8)))
(defn cbor-set-pos! [r p] (store64! (+ r 8) p))
(defn cbor-peek [r] (byte-at (cbor-ctx r) (cbor-pos r)))
(defn cbor-next-byte [r]
  (let [p (cbor-pos r) b (byte-at (cbor-ctx r) p)]
    (cbor-set-pos! r (+ p 1))
    b))
(defn cbor-major [r] (/ (cbor-peek r) 32))
;; read head + extension bytes → the encoded argument (uint value / length)
(defn cbor-read-arg [r]
  (let [info (mod (cbor-next-byte r) 32)]
    (cond
      (< info 24) info
      (= info 24) (cbor-next-byte r)
      (= info 25) (let [h (cbor-next-byte r) l (cbor-next-byte r)] (+ (* h 256) l))
      (= info 26) (let [b0 (cbor-next-byte r) b1 (cbor-next-byte r)
                        b2 (cbor-next-byte r) b3 (cbor-next-byte r)]
                    (+ (+ (+ (* b0 16777216) (* b1 65536)) (* b2 256)) b3))
      :else -1)))
(defn cbor-uint [r] (cbor-read-arg r))
;; ctx buffer slicing into a string handle ((ptr<<32)|len, via arithmetic)
(defn cbor--hptr [h] (/ h 4294967296))
(defn cbor--mkhandle [ptr len] (+ (* ptr 4294967296) len))
;; read a text/bytes value → string handle into the ctx; advances past it
(defn cbor-text [r]
  (let [len (cbor-read-arg r)
        abs (+ (cbor--hptr (cbor-ctx r)) (cbor-pos r))]
    (cbor-set-pos! r (+ (cbor-pos r) len))
    (cbor--mkhandle abs len)))
;; skip exactly one value (recursive for array/map)
(defn cbor-skip [r]
  (let [major (cbor-major r)]
    (cond
      (= major 0) (do (cbor-read-arg r) 0)
      (= major 1) (do (cbor-read-arg r) 0)
      (= major 2) (let [len (cbor-read-arg r)] (cbor-set-pos! r (+ (cbor-pos r) len)) 0)
      (= major 3) (let [len (cbor-read-arg r)] (cbor-set-pos! r (+ (cbor-pos r) len)) 0)
      (= major 4) (let [n (cbor-read-arg r)]
                    (loop [i 0] (if (>= i n) 0 (do (cbor-skip r) (recur (+ i 1))))))
      (= major 5) (let [n (cbor-read-arg r)]
                    (loop [i 0] (if (>= i (* 2 n)) 0 (do (cbor-skip r) (recur (+ i 1))))))
      :else 0)))
;; position the reader at the value for text key `key` in a CBOR map;
;; returns 1 (found; reader at value) or 0 (not found; map consumed).
(defn cbor-map-seek [r key]
  (let [n (cbor-read-arg r)]
    (loop [i 0]
      (if (>= i n)
        0
        (if (str-eq? (cbor-text r) key)
          1
          (do (cbor-skip r) (recur (+ i 1))))))))
"#;

/// An **in-guest CBOR encoder** (subset) — the symmetric counterpart to
/// [`CBOR_PRELUDE`], so a node/agent can return a *structured* `result` (map /
/// array / text / uint) instead of just a raw byte string. Builds bytes with
/// the Stage-A byte builder; a head byte is `(major*32 + info)` and multi-byte
/// lengths are emitted big-endian via `/`/`mod` (no bitwise ops). All builders
/// return the buffer so they thread through `do`/`recur`.
///
/// Entry points: `cbor-enc-uint!`, `cbor-enc-text!`, `cbor-enc-bytes!`,
/// `cbor-enc-map-header!`, `cbor-enc-array-header!` (write the header for `n`
/// pairs/items, then encode the members yourself). Pair with `bytes-finish` to
/// get the final `list<u8>` handle.
pub const CBOR_ENC_PRELUDE: &str = r#"
;; write a CBOR head: major type (0..7) + argument n (the value / length)
(defn cbor-enc-head! [buf major n]
  (let [m (* major 32)]
    (cond
      (< n 24)    (byte-append! buf (+ m n))
      (< n 256)   (do (byte-append! buf (+ m 24)) (byte-append! buf n))
      (< n 65536) (do (byte-append! buf (+ m 25))
                      (byte-append! buf (/ n 256))
                      (byte-append! buf (mod n 256)))
      :else       (do (byte-append! buf (+ m 26))
                      (byte-append! buf (mod (/ n 16777216) 256))
                      (byte-append! buf (mod (/ n 65536) 256))
                      (byte-append! buf (mod (/ n 256) 256))
                      (byte-append! buf (mod n 256))))))
(defn cbor-enc-uint! [buf n] (cbor-enc-head! buf 0 n))
(defn cbor-enc-map-header! [buf n] (cbor-enc-head! buf 5 n))
(defn cbor-enc-array-header! [buf n] (cbor-enc-head! buf 4 n))
;; copy the bytes of a string handle s into buf after a `major`-typed head
(defn cbor-enc--str! [buf major s]
  (cbor-enc-head! buf major (str-len s))
  (loop [i 0]
    (if (>= i (str-len s))
      buf
      (do (byte-append! buf (byte-at s i)) (recur (+ i 1))))))
(defn cbor-enc-text! [buf s] (cbor-enc--str! buf 3 s))
(defn cbor-enc-bytes! [buf s] (cbor-enc--str! buf 2 s))
"#;

/// Compile `src` with the container [`PRELUDE`], the CBOR decoder
/// [`CBOR_PRELUDE`], and the CBOR encoder [`CBOR_ENC_PRELUDE`] prepended, so the
/// program can use `vec-*` / `map-*` / `cbor-*` directly.
pub fn compile_str_with_prelude(src: &str) -> Result<Vec<u8>, CljError> {
    compile_str(&format!("{PRELUDE}\n{CBOR_PRELUDE}\n{CBOR_ENC_PRELUDE}\n{src}"))
}

/// The combined prelude text (containers + CBOR decode + CBOR encode), for
/// callers that compile via the component/kais path and need to prepend it to
/// their own `(defn run …)`.
pub fn prelude() -> String {
    format!("{PRELUDE}\n{CBOR_PRELUDE}\n{CBOR_ENC_PRELUDE}")
}
