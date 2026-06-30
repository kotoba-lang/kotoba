//! Lowering from the EDN reader (`kotoba_edn::EdnValue`) into a typed AST for
//! the i64 Kotoba/EDN subset this compiler supports.
//!
//! Subset (everything is a 64-bit signed integer; booleans are 1/0):
//!   top-level   `(def name <const-expr>)`     compile-time integer constant
//!               `(defn name [a b …] body…)` / `(defn- …)` wasm function
//!               multi-arity `(defn name ([a] …) ([a b] …))`
//!               `(defonce name <const-expr>)` compile-time integer constant
//!               top-level `(do …)` wrapping definitions
//!               `(ns …)` namespace management decls, `(require …)` `(use …)` `(refer-clojure …)` `(import …)` `(gen-class …)` `(set! …)` record/type/protocol/multimethod decls, `(defmacro …)`, `(comment …)`, `(declare …)` ignored
//!   expressions integer literal, `true`/`false`, symbol
//!               `(if c t e?)`  `(if-not c t e?)` `(when c body…)`
//!               `(when-not c body…)` `(if-let [b v] t e)`
//!               `(when-let [b v] body…)` `(case e test result … default?)`
//!               `(let [b v …] body…)`  `(do e…)` `(comment …)`,
//!               vector/map literals
//!               `(-> x step…)` `(->> x step…)` `(cond-> x test step …)`
//!               `(cond->> x test step …)` `(some-> x step…)`
//!               `(some->> x step…)` `(as-> x name form …)`
//!               vector and map destructuring in `defn`, `let`, `loop`,
//!               `if-let`, `when-let`
//!               builtins: + - * / mod  = < > <= >=  and or not
//!               `(f args…)`  call a user `defn`

use std::collections::BTreeSet;

use kotoba_edn::{to_string as edn_to_string, EdnValue, Symbol};

use crate::CljError;

/// A whole compiled program: a set of integer constants and functions.
#[derive(Debug, Clone)]
pub struct Program {
    pub defs: Vec<Def>,
    pub functions: Vec<Function>,
}

/// `(def name <const>)` — a compile-time integer constant, inlined at use sites.
#[derive(Debug, Clone)]
pub struct Def {
    pub name: String,
    pub value: Expr,
}

/// `(defn name [params…] body…)` — becomes an exported wasm function when
/// `export_name` is set. Multi-arity definitions share `name` for source-level
/// calls and are resolved by arity during codegen.
#[derive(Debug, Clone)]
pub struct Function {
    pub name: String,
    pub export_name: Option<String>,
    pub params: Vec<String>,
    /// Optional source-level `{:effects #{...}}` declaration carried from the
    /// defn attr-map. Generated/lifted functions have no source declaration.
    pub declared_effects: Option<BTreeSet<String>>,
    /// Implicit `do`: the last expression is the return value.
    pub body: Vec<Expr>,
    /// `Some(slot)` for a lambda-lifted anonymous function: it is reachable via
    /// `call_indirect` and occupies `slot` in the module's funcref table. `None`
    /// for ordinary `defn`s (called directly by index).
    pub table_slot: Option<u32>,
}

/// Builtin operators recognised in call position.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Builtin {
    Add,
    Sub,
    Mul,
    Div,
    Mod, // Clojure floored mod (sign of divisor)
    Rem, // truncated remainder (sign of dividend)
    Inc,
    Dec,
    Abs,
    Min,
    Max,
    Eq,
    NotEq,
    Lt,
    Gt,
    Le,
    Ge,
    Zero,
    Some,
    Pos,
    Neg,
    Even,
    Odd,
    And,
    Or,
    Not,
    /// `(str-len s)` — byte length of a string value.
    StrLen,
    /// `(byte-at s i)` — unsigned byte at index `i` of a string value.
    ByteAt,
    /// `(bytes-alloc cap)` — allocate a mutable byte buffer with `cap` bytes of
    /// capacity; returns a *buffer handle* (a pointer to an 8-byte header
    /// `[cap:i32, len:i32]` followed by the data region). Distinct from a
    /// string handle: builder ops take a buffer handle, readers take a string.
    BytesAlloc,
    /// `(byte-append! buf b)` — append the low byte of `b` to the buffer, bump
    /// its length, and return the (unchanged) buffer handle so it threads
    /// through `loop`/`recur`. No capacity check in this phase (caller sizes).
    ByteAppend,
    /// `(bytes-len buf)` — current filled length of a byte buffer.
    BytesLen,
    /// `(bytes-finish buf)` — freeze a buffer into a readable **string handle**
    /// `((data_ptr << 32) | len)` so `str-len`/`byte-at` work on the result.
    BytesFinish,
    /// `(alloc n)` — raw `cabi_realloc` of `n` bytes; returns the pointer as an
    /// i64. The low-level substrate the dynamic-container prelude builds on.
    Alloc,
    /// `(load64 addr)` — read the i64 word at `addr`.
    Load64,
    /// `(store64! addr val)` — write `val` at `addr`; returns `val`.
    Store64,
    /// `(load32 addr)` — read the i32 word at `addr`, zero-extended to i64.
    Load32,
    /// `(store32! addr val)` — write the low 32 bits of `val` at `addr`; returns `val`.
    Store32,
    /// `(has-capability? resource ability)` — host call into the `kotoba:kais`
    /// `auth` interface (`has-capability: func(string, string) -> bool`).
    /// The two arguments are string handles; returns 1/0. This is the first
    /// host-import builtin: it makes the compiled guest grow a real wasm import
    /// section wired to the runtime's `auth` host functions.
    HasCapability,
    /// `(llm-infer model-cid prompt)` — host call into the `kotoba:kais` `llm`
    /// interface (`infer: func(string, list<u8>) -> result<list<u8>, string>`).
    /// Both arguments are string handles (the `list<u8>` lowers identically to a
    /// `string`: a `(ptr,len)` pair). Returns the **ok** output as a string
    /// handle, or `0` (the nil-ish sentinel) on the `err` variant — the i64
    /// value model has no exceptions, so a failed inference reads as empty.
    LlmInfer,
    /// `(kqe-assert! graph subject predicate object-cbor)` — host call into the
    /// `kotoba:kais` `kqe` interface (`assert-quad: func(quad) -> result<_,
    /// string>`). All four arguments are string handles — the WIT record's
    /// fields each flatten to a `(ptr,len)` pair, and `object-cbor` is the
    /// CBOR-encoded QuadObject (buildable with the CBOR encoder prelude).
    /// Returns `1` on ok, `0` on the err variant. **This is the Datom write
    /// surface**: each call buffers an assertion the host commits after `run`
    /// returns (`HostState::pending_asserts`, 10 gas).
    KqeAssert,
    /// `(kqe-retract! graph subject predicate object-cbor)` — `retract-quad`,
    /// the tombstone twin of [`Builtin::KqeAssert`]. Same shape; returns 1/0.
    KqeRetract,
    /// `(kqe-get-objects graph subject predicate)` — SPO point lookup
    /// (`get-objects: func(string,string,string) -> list<list<u8>>`, 5 gas).
    /// Returns a packed **list handle** `(ptr << 32) | count` over the lifted
    /// element array (8 bytes per element: `[ptr:i32, len:i32]`). Read it with
    /// the [`crate::KQE_PRELUDE`] accessors `kqe-count` / `kqe-obj-nth`.
    KqeGetObjects,
    /// `(kqe-query predicate-filter)` — snapshot query (`query: func(string) ->
    /// result<list<quad>, string>`, 100 gas; empty filter = all quads). Returns
    /// a packed list handle `(ptr << 32) | count` over the lifted quad array
    /// (32 bytes per quad: 4 × `[ptr,len]` for graph/subject/predicate/
    /// object-cbor), or `0` on err. Read with `kqe-count` /
    /// `kqe-quad-{graph,subject,predicate,object}`.
    KqeQuery,
    /// `(bit-and a b …)` — bitwise AND of all arguments (Clojure `bit-and`).
    /// Maps to WASM `i64.and` folded left over the arg list.
    BitAnd,
    /// `(bit-or a b …)` — bitwise OR of all arguments (Clojure `bit-or`).
    /// Maps to WASM `i64.or` folded left over the arg list.
    BitOr,
    /// `(bit-xor a b …)` — bitwise XOR of all arguments (Clojure `bit-xor`).
    /// Maps to WASM `i64.xor` folded left over the arg list.
    BitXor,
    /// `(bit-shift-left x n)` — left-shift `x` by `n` bits (Clojure `bit-shift-left`).
    /// Maps to WASM `i64.shl`. Exactly 2 args.
    BitShiftLeft,
    /// `(bit-shift-right x n)` — arithmetic right-shift `x` by `n` bits
    /// (Clojure `bit-shift-right`). Maps to WASM `i64.shr_s`. Exactly 2 args.
    BitShiftRight,
    /// `(double x)` — coerce `x` to an f64 value. An int is converted with
    /// `f64.convert_i64_s`; a float passes through. The result occupies the
    /// uniform i64 slot as the IEEE-754 bit pattern.
    Double,
    /// `(int x)` / `(long x)` — coerce `x` to an integer. A float is truncated
    /// toward zero (`i64.trunc_sat_f64_s`); an int passes through.
    Int,
    /// `(Math/round x)` — round `x` to the nearest integer (ties away from
    /// zero, Clojure semantics), returned as an integer value.
    MathRound,
    /// `(Math/floor x)` — largest integer ≤ `x`, returned as an f64 value
    /// (`f64.floor`, matching Clojure which yields a double).
    MathFloor,
    /// `(Math/ceil x)` — smallest integer ≥ `x`, returned as an f64 value
    /// (`f64.ceil`).
    MathCeil,
    /// `(Math/abs x)` — absolute value preserving the operand's float-ness
    /// (`f64.abs` for a float; integer abs otherwise).
    MathAbs,
    /// `(Math/sqrt x)` — square root as an f64 value (`f64.sqrt`).
    MathSqrt,
}

impl Builtin {
    /// If this builtin is a host-import call, the `(interface, function)` it
    /// lowers to in the `kotoba:kais` world. Used to emit the wasm import
    /// section and bind it through the Component Model.
    pub fn host_import(self) -> Option<HostImport> {
        match self {
            Builtin::HasCapability => Some(HostImport::HasCapability),
            Builtin::LlmInfer => Some(HostImport::LlmInfer),
            Builtin::KqeAssert => Some(HostImport::KqeAssertQuad),
            Builtin::KqeRetract => Some(HostImport::KqeRetractQuad),
            Builtin::KqeGetObjects => Some(HostImport::KqeGetObjects),
            Builtin::KqeQuery => Some(HostImport::KqeQuery),
            _ => None,
        }
    }
}

/// A `kotoba:kais` host interface function a builtin lowers to. Each variant
/// carries its WIT interface module name + field and its Canonical-ABI core
/// signature (see `codegen`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum HostImport {
    /// `kotoba:kais/auth@0.1.0` → `has-capability: func(string,string) -> bool`.
    /// Direct result (single i32, no return area).
    HasCapability,
    /// `kotoba:kais/llm@0.1.0` → `infer: func(string, list<u8>) ->
    /// result<list<u8>, string>`. Indirect result: lowers with a trailing
    /// return-area pointer the guest allocates.
    LlmInfer,
    /// `kotoba:kais/kqe@0.1.0` → `assert-quad: func(quad) -> result<_,
    /// string>`. The `quad` record flattens to 8 i32 params (4 × `(ptr,len)`);
    /// the result is indirect (12-byte return area: `[tag:u8 @0, err-ptr @4,
    /// err-len @8]`).
    KqeAssertQuad,
    /// `kotoba:kais/kqe@0.1.0` → `retract-quad` — same core shape as
    /// [`HostImport::KqeAssertQuad`].
    KqeRetractQuad,
    /// `kotoba:kais/kqe@0.1.0` → `get-objects: func(string,string,string) ->
    /// list<list<u8>>`. Indirect result (8-byte return area: `[ptr @0, len @4]`).
    KqeGetObjects,
    /// `kotoba:kais/kqe@0.1.0` → `query: func(string) -> result<list<quad>,
    /// string>`. Indirect result (12-byte return area, same variant layout as
    /// `llm.infer`).
    KqeQuery,
}

/// Whether a list head names an **inert form** — one whose body is data or is
/// dropped at compile time, and is therefore *never executed*:
/// `quote`/`var` (quoted data) and `comment` (discarded). The safe Kotoba analysis
/// walkers (subset / type / effect / capability / policy-synthesis) must not
/// descend into these, or they raise false positives — rejecting valid code,
/// mis-attributing effects, or demanding capabilities the cell never uses. This
/// is sound because `eval` is banned by the subset gate, so quoted data can
/// never be promoted back to executable code. Single-sourced here so every
/// walker stays in sync (`tests/safe_quote.rs` guards it).
pub fn is_inert_form(head_name: &str) -> bool {
    matches!(head_name, "quote" | "var" | "comment")
}

impl HostImport {
    /// Every variant, for exhaustive iteration — capability auditing
    /// ([`crate::embedded_capability_ifaces`]) derives the host-interface set
    /// from this rather than hardcoding it, so the audit cannot drift as the
    /// host world grows. Kept in sync with the enum by the
    /// `host_import_all_is_complete` test.
    pub const ALL: [HostImport; 6] = [
        HostImport::HasCapability,
        HostImport::LlmInfer,
        HostImport::KqeAssertQuad,
        HostImport::KqeRetractQuad,
        HostImport::KqeGetObjects,
        HostImport::KqeQuery,
    ];

    /// The wasm import `(module, field)` the Component encoder matches against
    /// the WIT world's interface import.
    pub fn module_field(self) -> (&'static str, &'static str) {
        match self {
            HostImport::HasCapability => ("kotoba:kais/auth@0.1.0", "has-capability"),
            HostImport::LlmInfer => ("kotoba:kais/llm@0.1.0", "infer"),
            HostImport::KqeAssertQuad => ("kotoba:kais/kqe@0.1.0", "assert-quad"),
            HostImport::KqeRetractQuad => ("kotoba:kais/kqe@0.1.0", "retract-quad"),
            HostImport::KqeGetObjects => ("kotoba:kais/kqe@0.1.0", "get-objects"),
            HostImport::KqeQuery => ("kotoba:kais/kqe@0.1.0", "query"),
        }
    }
}

#[cfg(test)]
mod host_import_meta_tests {
    use super::HostImport;

    /// A total match over `HostImport`. Adding a variant breaks compilation
    /// here, forcing whoever adds it to also extend [`HostImport::ALL`] (and,
    /// prompted by the failing assert below, the capability/effect mappings).
    fn tag(h: HostImport) -> u8 {
        match h {
            HostImport::HasCapability => 0,
            HostImport::LlmInfer => 1,
            HostImport::KqeAssertQuad => 2,
            HostImport::KqeRetractQuad => 3,
            HostImport::KqeGetObjects => 4,
            HostImport::KqeQuery => 5,
        }
    }

    #[test]
    fn host_import_all_is_complete() {
        let mut tags: Vec<u8> = HostImport::ALL.iter().copied().map(tag).collect();
        tags.sort_unstable();
        tags.dedup();
        assert_eq!(
            tags,
            (0..tag(HostImport::KqeQuery) + 1).collect::<Vec<u8>>(),
            "HostImport::ALL is missing a variant — capability auditing would not see it"
        );
    }

    #[test]
    fn every_host_import_has_a_well_formed_interface() {
        for imp in HostImport::ALL {
            let (module, field) = imp.module_field();
            assert!(module.starts_with("kotoba:kais/"), "bad module {module}");
            assert!(!field.is_empty());
        }
    }
}

impl Builtin {
    fn from_name(s: &str) -> Option<Builtin> {
        let s = s.strip_prefix("clojure.core/").unwrap_or(s);
        Some(match s {
            "+" => Builtin::Add,
            "-" => Builtin::Sub,
            "*" => Builtin::Mul,
            "/" | "quot" => Builtin::Div,
            "mod" => Builtin::Mod,
            "rem" => Builtin::Rem,
            "inc" => Builtin::Inc,
            "dec" => Builtin::Dec,
            "abs" => Builtin::Abs,
            "min" => Builtin::Min,
            "max" => Builtin::Max,
            "=" => Builtin::Eq,
            "!=" | "not=" => Builtin::NotEq,
            "<" => Builtin::Lt,
            ">" => Builtin::Gt,
            "<=" => Builtin::Le,
            ">=" => Builtin::Ge,
            "zero?" | "nil?" => Builtin::Zero,
            "some?" => Builtin::Some,
            "pos?" => Builtin::Pos,
            "neg?" => Builtin::Neg,
            "even?" => Builtin::Even,
            "odd?" => Builtin::Odd,
            "and" => Builtin::And,
            "or" => Builtin::Or,
            "not" => Builtin::Not,
            "str-len" => Builtin::StrLen,
            "byte-at" => Builtin::ByteAt,
            "bytes-alloc" => Builtin::BytesAlloc,
            "byte-append!" => Builtin::ByteAppend,
            "bytes-len" => Builtin::BytesLen,
            "bytes-finish" => Builtin::BytesFinish,
            "alloc" => Builtin::Alloc,
            "load64" => Builtin::Load64,
            "store64!" => Builtin::Store64,
            "load32" => Builtin::Load32,
            "store32!" => Builtin::Store32,
            "has-capability?" => Builtin::HasCapability,
            "llm-infer" => Builtin::LlmInfer,
            "kqe-assert!" => Builtin::KqeAssert,
            "kqe-retract!" => Builtin::KqeRetract,
            "kqe-get-objects" => Builtin::KqeGetObjects,
            "kqe-query" => Builtin::KqeQuery,
            "bit-and" => Builtin::BitAnd,
            "bit-or" => Builtin::BitOr,
            "bit-xor" => Builtin::BitXor,
            "bit-shift-left" => Builtin::BitShiftLeft,
            "bit-shift-right" => Builtin::BitShiftRight,
            "double" => Builtin::Double,
            "int" | "long" => Builtin::Int,
            "Math/round" | "java.lang.Math/round" => Builtin::MathRound,
            "Math/floor" | "java.lang.Math/floor" => Builtin::MathFloor,
            "Math/ceil" | "java.lang.Math/ceil" => Builtin::MathCeil,
            "Math/abs" | "java.lang.Math/abs" => Builtin::MathAbs,
            "Math/sqrt" | "java.lang.Math/sqrt" => Builtin::MathSqrt,
            _ => return None,
        })
    }
}

/// Expression AST.
#[derive(Debug, Clone)]
pub enum Expr {
    /// Integer literal (booleans lower to 1/0 here).
    Int(i64),
    /// Float literal. Carried as a native `f64`; codegen stores its IEEE-754
    /// bit pattern in the uniform i64 value slot (`i64.reinterpret_f64`) and
    /// reinterprets it back (`f64.reinterpret_i64`) at float-arithmetic
    /// boundaries. There is no runtime tag — float-ness is inferred
    /// *statically* (see `codegen::is_float_expr`).
    Float(f64),
    /// String literal — stored in a data segment; the value on the stack is a
    /// packed `(offset << 32) | len` i64 handle (see codegen).
    Str(Vec<u8>),
    /// A bare symbol — resolves to a param, a `let` binding, or a `def` constant.
    Var(String),
    If {
        cond: Box<Expr>,
        then: Box<Expr>,
        els: Box<Expr>,
    },
    /// Sequential `let` — each binding is in scope for the following ones.
    Let {
        bindings: Vec<(String, Expr)>,
        body: Vec<Expr>,
    },
    /// `do` block — last expression is the value.
    Do(Vec<Expr>),
    /// `(loop [b v …] body…)` — establishes a `recur` target. The bindings are
    /// the loop variables (sequential init, like `let`); `recur` rebinds them
    /// and jumps back to the top. Bounded iteration; no closures.
    Loop {
        bindings: Vec<(String, Expr)>,
        body: Vec<Expr>,
    },
    /// `(recur args…)` — rebind the nearest enclosing `loop` (or function, when
    /// a future phase allows it) and iterate. Must be in tail position; arity
    /// must match the target's binding count (checked in codegen).
    Recur(Vec<Expr>),
    Builtin {
        op: Builtin,
        args: Vec<Expr>,
    },
    /// Call a user-defined `defn`.
    Call {
        name: String,
        args: Vec<Expr>,
    },
    /// An anonymous function `(fn [params…] body…)` (also the target of the
    /// `#(…)` reader macro). This is a *transient* node: the lambda-lifting pass
    /// (`lift_program`) rewrites every `Fn` site into a [`Expr::MakeClosure`]
    /// plus a synthetic top-level [`Function`], so codegen never sees a raw `Fn`.
    Fn {
        params: Vec<String>,
        body: Vec<Expr>,
    },
    /// Heap-allocate a closure record `[table-slot:i64, cap0:i64, …]` and yield a
    /// pointer handle. Produced by lambda-lifting to stand in for an `(fn …)`.
    /// `table_slot` is the funcref-table index of the lifted function; `captures`
    /// are the free-variable values, evaluated in the enclosing scope.
    MakeClosure {
        table_slot: u32,
        captures: Vec<Expr>,
    },
    /// Inside a lifted function, read capture slot `n` from the closure record
    /// (local 0 holds the `self` closure pointer). Produced by lambda-lifting.
    ClosureRef(u32),
    /// Indirectly call a closure *value* (`(f args…)` where `f` is a local /
    /// captured binding, or `((fn …) args…)`). Lowers to `call_indirect`.
    CallValue {
        f: Box<Expr>,
        args: Vec<Expr>,
    },
}

/// Parse Kotoba/EDN-subset source text into a [`Program`].
pub fn parse_program(src: &str) -> Result<Program, CljError> {
    let forms = kotoba_edn::parse_all(src).map_err(|e| CljError::Read(e.to_string()))?;
    let mut defs = Vec::new();
    let mut functions = Vec::new();

    for form in &forms {
        parse_top_level_form(form, &mut defs, &mut functions)?;
    }

    let mut program = Program { defs, functions };
    lift_program(&mut program)?;
    Ok(program)
}

fn parse_top_level_form(
    form: &EdnValue,
    defs: &mut Vec<Def>,
    functions: &mut Vec<Function>,
) -> Result<(), CljError> {
    let items = match form {
        EdnValue::List(items) => items,
        // A bare top-level non-list (e.g. a stray literal) is meaningless.
        other => {
            return Err(CljError::Lower(format!(
                "top-level form must be a list, found: {other:?}"
            )));
        }
    };
    let head = list_head_symbol(items)?;
    match head.name.as_str() {
        "ns" | "require" | "require-macros" | "use" | "use-macros" | "refer-clojure" | "in-ns"
        | "alias" | "create-ns" | "remove-ns" | "import" | "gen-class" | "set!" | "defrecord"
        | "deftype" | "defprotocol" | "extend-type" | "extend-protocol" | "defmulti"
        | "defmethod" | "defmacro" | "defstruct" | "create-struct" | "comment" | "declare" => {
            /* source-compat declarations — accepted and ignored */
        }
        "do" => {
            for item in &items[1..] {
                parse_top_level_form(item, defs, functions)?;
            }
        }
        "def" | "defonce" => defs.push(lower_def(items)?),
        "defn" | "defn-" => functions.extend(lower_defn(items)?),
        "defgraph" => functions.extend(lower_defgraph(items)?),
        other => {
            return Err(CljError::Lower(format!(
                "unsupported top-level form `({other} …)` — expected def/defonce/defn/defn-/defmacro/ns/namespace-management/require/use/refer-clojure/import/gen-class/set!/record-type-protocol-multimethod/struct/defgraph/do/comment/declare"
            )));
        }
    }
    Ok(())
}

fn list_head_symbol(items: &[EdnValue]) -> Result<&Symbol, CljError> {
    match items.first() {
        Some(EdnValue::Symbol(s)) => Ok(s),
        _ => Err(CljError::Lower(
            "list must begin with a symbol in head position".into(),
        )),
    }
}

// ---- lambda lifting --------------------------------------------------------
//
// Anonymous functions are compiled by *lambda lifting*: every `(fn …)` becomes a
// synthetic top-level [`Function`] whose first parameter (`__self`) is a pointer
// to a heap closure record `[table-slot, cap0, cap1, …]`. Free variables (the
// enclosing locals the body references) are captured into that record at the
// `(fn …)` site (an [`Expr::MakeClosure`]); inside the lifted function each such
// reference is rewritten to an [`Expr::ClosureRef`] that loads from `__self`.
// Calls to a closure *value* (a local/captured binding, or an `(fn …)` in head
// position) become [`Expr::CallValue`], which codegen lowers to `call_indirect`.
//
// The same pass also rewrites *every* call whose head names a lexical binding
// (rather than a top-level `defn`) into a `CallValue` — this is what makes a
// higher-order parameter, e.g. `(defn ap [f x] (f x))`, work.

/// How a name in scope is accessed *in the function currently being lowered*:
/// either a real wasm local (`Var`) or a slot in the current closure record.
type LiftScope = Vec<(String, Expr)>;

fn scope_get<'a>(scope: &'a LiftScope, name: &str) -> Option<&'a Expr> {
    scope.iter().rev().find(|(n, _)| n == name).map(|(_, e)| e)
}

struct Lifter {
    /// Synthetic functions produced for each `(fn …)`, appended to the program.
    new_fns: Vec<Function>,
    /// Monotonic id for unique synthetic names.
    counter: u32,
    /// Next funcref-table slot to hand out.
    next_slot: u32,
}

impl Lifter {
    fn new() -> Self {
        Self {
            new_fns: Vec::new(),
            counter: 0,
            next_slot: 0,
        }
    }

    fn lift_body(&mut self, body: Vec<Expr>, scope: &LiftScope) -> Result<Vec<Expr>, CljError> {
        body.into_iter().map(|e| self.lift_expr(e, scope)).collect()
    }

    fn lift_expr(&mut self, e: Expr, scope: &LiftScope) -> Result<Expr, CljError> {
        Ok(match e {
            Expr::Int(_) | Expr::Float(_) | Expr::Str(_) | Expr::ClosureRef(_) => e,

            // A bare symbol that names a lexical binding is read through that
            // binding's current access path (`Var` for a local, `ClosureRef` for
            // a capture). Unknown names are top-level consts/defns — left as-is.
            Expr::Var(name) => match scope_get(scope, &name) {
                Some(access) => access.clone(),
                None => Expr::Var(name),
            },

            Expr::If { cond, then, els } => Expr::If {
                cond: Box::new(self.lift_expr(*cond, scope)?),
                then: Box::new(self.lift_expr(*then, scope)?),
                els: Box::new(self.lift_expr(*els, scope)?),
            },

            Expr::Let { bindings, body } => {
                let mut inner = scope.clone();
                let mut lowered = Vec::with_capacity(bindings.len());
                for (n, v) in bindings {
                    let v = self.lift_expr(v, &inner)?; // sequential: sees prior
                    inner.push((n.clone(), Expr::Var(n.clone())));
                    lowered.push((n, v));
                }
                Expr::Let {
                    bindings: lowered,
                    body: self.lift_body(body, &inner)?,
                }
            }

            Expr::Loop { bindings, body } => {
                let mut inner = scope.clone();
                let mut lowered = Vec::with_capacity(bindings.len());
                for (n, v) in bindings {
                    let v = self.lift_expr(v, &inner)?;
                    inner.push((n.clone(), Expr::Var(n.clone())));
                    lowered.push((n, v));
                }
                Expr::Loop {
                    bindings: lowered,
                    body: self.lift_body(body, &inner)?,
                }
            }

            Expr::Do(es) => Expr::Do(self.lift_body(es, scope)?),
            Expr::Recur(es) => Expr::Recur(self.lift_body(es, scope)?),
            Expr::Builtin { op, args } => Expr::Builtin {
                op,
                args: self.lift_body(args, scope)?,
            },

            // A call whose head names a lexical binding is an indirect closure
            // call; otherwise it is a direct call to a top-level `defn`.
            Expr::Call { name, args } => {
                let args = self.lift_body(args, scope)?;
                match scope_get(scope, &name) {
                    Some(access) => Expr::CallValue {
                        f: Box::new(access.clone()),
                        args,
                    },
                    None => Expr::Call { name, args },
                }
            }

            Expr::CallValue { f, args } => Expr::CallValue {
                f: Box::new(self.lift_expr(*f, scope)?),
                args: self.lift_body(args, scope)?,
            },

            Expr::Fn { params, body } => self.lift_fn(params, body, scope)?,

            // MakeClosure only appears post-lift; recurse defensively.
            Expr::MakeClosure {
                table_slot,
                captures,
            } => Expr::MakeClosure {
                table_slot,
                captures: self.lift_body(captures, scope)?,
            },
        })
    }

    /// Lift a single `(fn params body)` at `scope`, returning the `MakeClosure`.
    fn lift_fn(
        &mut self,
        params: Vec<String>,
        body: Vec<Expr>,
        scope: &LiftScope,
    ) -> Result<Expr, CljError> {
        // Free vars = lexical names the body references that live in `scope`.
        let free = free_vars(&params, &body, scope);
        let captures: Vec<Expr> = free
            .iter()
            .map(|n| {
                scope_get(scope, n)
                    .cloned()
                    .ok_or_else(|| CljError::Lower(format!("free var `{n}` vanished from scope")))
            })
            .collect::<Result<_, _>>()?;

        // Inside the lifted fn: captures map to closure slots; params to locals.
        let mut inner: LiftScope = Vec::new();
        for (i, n) in free.iter().enumerate() {
            inner.push((n.clone(), Expr::ClosureRef(i as u32)));
        }
        for p in &params {
            inner.push((p.clone(), Expr::Var(p.clone())));
        }
        let lifted_body = self.lift_body(body, &inner)?;

        let slot = self.next_slot;
        self.next_slot += 1;
        let fname = format!("\0kotoba_fn_{}", self.counter);
        self.counter += 1;

        let mut fn_params = Vec::with_capacity(params.len() + 1);
        fn_params.push("\0kotoba_self".to_string());
        fn_params.extend(params);

        self.new_fns.push(Function {
            name: fname,
            export_name: None,
            params: fn_params,
            declared_effects: None,
            body: lifted_body,
            table_slot: Some(slot),
        });

        Ok(Expr::MakeClosure {
            table_slot: slot,
            captures,
        })
    }
}

/// Ordered, de-duplicated free lexical variables of `(fn params body)`: the
/// names referenced in `body` that are present in `scope` (the enclosing
/// lexical environment) and not shadowed by `params` or an inner binder.
fn free_vars(params: &[String], body: &[Expr], scope: &LiftScope) -> Vec<String> {
    let mut bound: Vec<String> = params.to_vec();
    let mut acc: Vec<String> = Vec::new();
    let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
    for e in body {
        free_walk(e, &mut bound, scope, &mut acc, &mut seen);
    }
    acc
}

fn free_walk(
    e: &Expr,
    bound: &mut Vec<String>,
    scope: &LiftScope,
    acc: &mut Vec<String>,
    seen: &mut std::collections::HashSet<String>,
) {
    let refer = |name: &str,
                 bound: &Vec<String>,
                 acc: &mut Vec<String>,
                 seen: &mut std::collections::HashSet<String>| {
        if !bound.iter().any(|b| b == name)
            && scope_get(scope, name).is_some()
            && seen.insert(name.to_string())
        {
            acc.push(name.to_string());
        }
    };
    match e {
        Expr::Int(_) | Expr::Float(_) | Expr::Str(_) | Expr::ClosureRef(_) => {}
        Expr::Var(n) => refer(n, bound, acc, seen),
        Expr::If { cond, then, els } => {
            free_walk(cond, bound, scope, acc, seen);
            free_walk(then, bound, scope, acc, seen);
            free_walk(els, bound, scope, acc, seen);
        }
        Expr::Let { bindings, body } | Expr::Loop { bindings, body } => {
            let depth = bound.len();
            for (n, v) in bindings {
                free_walk(v, bound, scope, acc, seen); // value sees prior bindings
                bound.push(n.clone());
            }
            for b in body {
                free_walk(b, bound, scope, acc, seen);
            }
            bound.truncate(depth);
        }
        Expr::Do(es) | Expr::Recur(es) | Expr::Builtin { args: es, .. } => {
            es.iter()
                .for_each(|e| free_walk(e, bound, scope, acc, seen));
        }
        Expr::Call { name, args } => {
            refer(name, bound, acc, seen); // a call head may be a closure value
            args.iter()
                .for_each(|a| free_walk(a, bound, scope, acc, seen));
        }
        Expr::CallValue { f, args } => {
            free_walk(f, bound, scope, acc, seen);
            args.iter()
                .for_each(|a| free_walk(a, bound, scope, acc, seen));
        }
        // A nested `(fn …)` captures from us too, so descend with its params
        // added to `bound` (its own params are not our free vars).
        Expr::Fn { params, body } => {
            let depth = bound.len();
            bound.extend(params.iter().cloned());
            body.iter()
                .for_each(|e| free_walk(e, bound, scope, acc, seen));
            bound.truncate(depth);
        }
        Expr::MakeClosure { captures, .. } => {
            captures
                .iter()
                .for_each(|e| free_walk(e, bound, scope, acc, seen));
        }
    }
}

/// Run lambda-lifting over every function body, appending the synthetic
/// closure functions to the program.
fn lift_program(program: &mut Program) -> Result<(), CljError> {
    let mut lifter = Lifter::new();
    let mut rewritten: Vec<Function> = Vec::with_capacity(program.functions.len());
    for f in std::mem::take(&mut program.functions) {
        let scope: LiftScope = f
            .params
            .iter()
            .map(|p| (p.clone(), Expr::Var(p.clone())))
            .collect();
        let body = lifter.lift_body(f.body, &scope)?;
        rewritten.push(Function { body, ..f });
    }
    rewritten.append(&mut lifter.new_fns);
    program.functions = rewritten;
    Ok(())
}

fn lower_def(items: &[EdnValue]) -> Result<Def, CljError> {
    // (def name "doc?" value)
    if items.len() != 3 && items.len() != 4 {
        return Err(CljError::Lower(
            "def takes exactly: (def name \"doc?\" value)".into(),
        ));
    }
    let name = sym_name(&items[1], "def name")?;
    let value_idx = if items.len() == 4 && matches!(items.get(2), Some(EdnValue::String(_))) {
        3
    } else {
        2
    };
    let value = lower_expr(&items[value_idx])?;
    Ok(Def { name, value })
}

fn lower_defn(items: &[EdnValue]) -> Result<Vec<Function>, CljError> {
    // (defn name "doc?" attr-map? [params…] body…)
    // (defn name "doc?" attr-map? ([params…] body…) ([params…] body…))
    if items.len() < 3 {
        return Err(CljError::Lower(
            "defn requires: (defn name \"doc?\" attr-map? [params…] body…)".into(),
        ));
    }
    let name = sym_name(&items[1], "defn name")?;
    let mut params_idx = 2;
    if matches!(items.get(params_idx), Some(EdnValue::String(_))) {
        params_idx += 1;
    }
    let declared_effects = if let Some(EdnValue::Map(attrs)) = items.get(params_idx) {
        let declared = parse_defn_declared_effects(attrs)?;
        params_idx += 1;
        declared
    } else {
        None
    };
    if let Some(EdnValue::List(arity)) = items.get(params_idx) {
        if !items[params_idx..]
            .iter()
            .all(|item| matches!(item, EdnValue::List(_)))
        {
            return Err(CljError::Lower(format!(
                "defn `{name}` arity-list form cannot be mixed with non-arity body forms"
            )));
        }
        if items.len() == params_idx + 1 {
            return Ok(vec![lower_defn_arity(
                &name,
                arity,
                Some(name.clone()),
                declared_effects.clone(),
            )?]);
        }
        return items[params_idx..]
            .iter()
            .map(|item| match item {
                EdnValue::List(arity) => {
                    lower_defn_arity(&name, arity, None, declared_effects.clone())
                }
                _ => unreachable!("checked above"),
            })
            .collect();
    }
    let (params, destructured_params) = match items.get(params_idx) {
        Some(EdnValue::Vector(ps)) => lower_param_list(ps, "defn parameter")?,
        _ => {
            return Err(CljError::Lower(format!(
                "defn `{name}` parameter list must be a vector `[…]`"
            )));
        }
    };
    if items.len() <= params_idx + 1 {
        return Err(CljError::Lower(format!(
            "defn `{name}` requires at least one body expression"
        )));
    }
    let body_idx = skip_prepost_map(items, params_idx + 1);
    if items.len() <= body_idx {
        return Err(CljError::Lower(format!(
            "defn `{name}` requires at least one body expression after pre/post conditions"
        )));
    }
    let body = items[body_idx..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    let body = prepend_bindings(destructured_params, body);
    Ok(vec![Function {
        export_name: Some(name.clone()),
        name,
        params,
        declared_effects,
        body,
        table_slot: None,
    }])
}

fn lower_defn_arity(
    name: &str,
    items: &[EdnValue],
    export_name: Option<String>,
    declared_effects: Option<BTreeSet<String>>,
) -> Result<Function, CljError> {
    if items.len() < 2 {
        return Err(CljError::Lower(format!(
            "defn `{name}` arity-list requires: ([params…] body…)"
        )));
    }
    let (params, destructured_params) = match &items[0] {
        EdnValue::Vector(ps) => lower_param_list(ps, "defn parameter")?,
        _ => {
            return Err(CljError::Lower(format!(
                "defn `{name}` arity-list must begin with a parameter vector"
            )));
        }
    };
    let body_idx = skip_prepost_map(items, 1);
    if items.len() <= body_idx {
        return Err(CljError::Lower(format!(
            "defn `{name}` arity-list requires at least one body expression after pre/post conditions"
        )));
    }
    let body = items[body_idx..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    let body = prepend_bindings(destructured_params, body);
    Ok(Function {
        name: name.to_string(),
        export_name,
        params,
        declared_effects,
        body,
        table_slot: None,
    })
}

fn parse_defn_declared_effects(
    attrs: &std::collections::BTreeMap<EdnValue, EdnValue>,
) -> Result<Option<BTreeSet<String>>, CljError> {
    let Some(value) = attrs.get(&EdnValue::kw_bare("effects")) else {
        return Ok(None);
    };
    let set = match value {
        EdnValue::Set(set) => set,
        _ => {
            return Err(CljError::Effect(
                "`:effects` must be a set of keywords (e.g. #{:graph-write})".into(),
            ));
        }
    };
    let mut declared = BTreeSet::new();
    for effect in set {
        let keyword = effect
            .as_keyword()
            .ok_or_else(|| CljError::Effect("`:effects` entries must be keywords".into()))?;
        declared.insert(keyword.0.name.clone());
    }
    Ok(Some(declared))
}

type LoweredBindings = Vec<(String, Expr)>;
type LoweredParams = (Vec<String>, LoweredBindings);

fn lower_param_list(params: &[EdnValue], ctx: &str) -> Result<LoweredParams, CljError> {
    let mut lowered = Vec::with_capacity(params.len());
    let mut destructured = Vec::new();
    for (idx, param) in params.iter().enumerate() {
        match param {
            EdnValue::Symbol(_) => lowered.push(sym_name(param, ctx)?),
            EdnValue::Vector(_) | EdnValue::Map(_) => {
                let temp = format!("\0kotoba_param_{idx}");
                collect_destructuring(param, Expr::Var(temp.clone()), &mut destructured, ctx)?;
                lowered.push(temp);
            }
            other => {
                return Err(CljError::Lower(format!(
                    "{ctx} must be a symbol or destructuring form, found {other:?}"
                )));
            }
        }
    }
    Ok((lowered, destructured))
}

fn prepend_bindings(bindings: LoweredBindings, body: Vec<Expr>) -> Vec<Expr> {
    if bindings.is_empty() {
        body
    } else {
        vec![Expr::Let { bindings, body }]
    }
}

fn skip_prepost_map(items: &[EdnValue], body_idx: usize) -> usize {
    match items.get(body_idx) {
        Some(EdnValue::Map(m)) if is_prepost_map(m) => body_idx + 1,
        _ => body_idx,
    }
}

fn is_prepost_map(m: &std::collections::BTreeMap<EdnValue, EdnValue>) -> bool {
    !m.is_empty()
        && m.keys().all(|k| {
            matches!(
                k,
                EdnValue::Keyword(keyword)
                    if keyword.namespace().is_none()
                        && matches!(keyword.name(), "pre" | "post")
            )
        })
}

fn lower_expr(v: &EdnValue) -> Result<Expr, CljError> {
    match v {
        EdnValue::Nil => Ok(Expr::Int(0)),
        EdnValue::Integer(i) => Ok(Expr::Int(*i)),
        EdnValue::Float(f) => Ok(Expr::Float(f.into_inner())),
        EdnValue::Bool(b) => Ok(Expr::Int(if *b { 1 } else { 0 })),
        EdnValue::String(s) => Ok(Expr::Str(s.clone().into_bytes())),
        EdnValue::Keyword(_) => Ok(Expr::Str(edn_to_string(v).into_bytes())),
        EdnValue::Symbol(s) => Ok(Expr::Var(s.to_qualified())),
        EdnValue::List(items) => lower_call(items),
        EdnValue::Vector(items) => lower_vector_literal(items),
        EdnValue::Map(items) => lower_map_literal(items),
        // set literals (e.g. `#{:bot}`) lower to the same growable container as vectors;
        // membership is `(some #(= % x) the-set)` (or `vec-contains?`) in the subset.
        EdnValue::Set(items) => lower_vector_literal(&items.iter().cloned().collect::<Vec<_>>()),
        other => Err(CljError::Lower(format!(
            "unsupported expression: {other:?} (only integers, booleans, strings, keywords, symbols, lists, vectors, maps and sets are supported)"
        ))),
    }
}

fn lower_vector_literal(items: &[EdnValue]) -> Result<Expr, CljError> {
    let name = "\0kotoba_vec_literal".to_string();
    let mut body = Vec::with_capacity(items.len() + 1);
    for item in items {
        body.push(Expr::Call {
            name: "vec-conj!".to_string(),
            args: vec![Expr::Var(name.clone()), lower_expr(item)?],
        });
    }
    body.push(Expr::Var(name.clone()));
    Ok(Expr::Let {
        bindings: vec![(
            name,
            Expr::Call {
                name: "vec-make".to_string(),
                args: vec![Expr::Int(items.len() as i64)],
            },
        )],
        body,
    })
}

fn lower_map_literal(
    items: &std::collections::BTreeMap<EdnValue, EdnValue>,
) -> Result<Expr, CljError> {
    let name = "\0kotoba_map_literal".to_string();
    let mut body = Vec::with_capacity(items.len() + 1);
    for (key, value) in items {
        body.push(Expr::Call {
            name: "map-assoc!".to_string(),
            args: vec![
                Expr::Var(name.clone()),
                lower_expr(key)?,
                lower_expr(value)?,
            ],
        });
    }
    body.push(Expr::Var(name.clone()));
    Ok(Expr::Let {
        bindings: vec![(
            name,
            Expr::Call {
                name: "map-make".to_string(),
                args: vec![Expr::Int(items.len() as i64)],
            },
        )],
        body,
    })
}

fn lower_call(items: &[EdnValue]) -> Result<Expr, CljError> {
    // A call whose head is not a symbol — e.g. `((fn [x] …) 1)` or `((get m :f) 1)`
    // — is an indirect call of a closure value.
    let head = match items.first() {
        Some(EdnValue::Symbol(s)) => s,
        Some(other) => {
            let f = lower_expr(other)?;
            let args = items[1..]
                .iter()
                .map(lower_expr)
                .collect::<Result<Vec<_>, _>>()?;
            return Ok(Expr::CallValue {
                f: Box::new(f),
                args,
            });
        }
        None => return Err(CljError::Lower("cannot call an empty list `()`".into())),
    };
    let args = &items[1..];
    let special = head
        .namespace
        .as_deref()
        .filter(|ns| *ns == "clojure.core")
        .map(|_| head.name.as_str())
        .unwrap_or(head.name.as_str());
    match special {
        "if" => lower_if(args),
        "if-not" => lower_if_not(args),
        "when" => lower_when(args),
        "when-not" => lower_when_not(args),
        "if-let" => lower_if_let(args),
        "when-let" => lower_when_let(args),
        "let" => lower_let(args),
        "cond" => lower_cond(args),
        "case" => lower_case(args),
        "loop" => lower_loop(args),
        "fn" | "fn*" => lower_fn(args),
        "recur" => Ok(Expr::Recur(
            args.iter().map(lower_expr).collect::<Result<_, _>>()?,
        )),
        "quote" => lower_quote(args),
        "var" => lower_var(args),
        "->" => lower_thread(args, ThreadPosition::First),
        "->>" => lower_thread(args, ThreadPosition::Last),
        "cond->" => lower_cond_thread(args, ThreadPosition::First),
        "cond->>" => lower_cond_thread(args, ThreadPosition::Last),
        "some->" => lower_some_thread(args, ThreadPosition::First),
        "some->>" => lower_some_thread(args, ThreadPosition::Last),
        "as->" => lower_as_thread(args),
        "do" => Ok(Expr::Do(
            args.iter().map(lower_expr).collect::<Result<_, _>>()?,
        )),
        // `(if-some [x e] then else?)` / `(when-some [x e] body…)`: in this
        // i64/nil-as-0 value model a non-nil value is exactly a truthy value, so
        // some-binding has the same lowering as the let-binding forms.
        "if-some" => lower_if_let(args),
        "when-some" => lower_when_let(args),
        // Iteration sugars — pure desugaring into `loop`/`recur` (no new runtime
        // node). They evaluate their body for side effects and yield nil (0).
        // `doseq` walks a vector via the prelude `vec-count`/`vec-nth`, so it
        // requires the prelude (the default).
        "while" => lower_while(args),
        "dotimes" => lower_dotimes(args),
        "doseq" => lower_doseq(args),
        "comment" => Ok(Expr::Int(0)),
        // `(str ...)` desugar: 0 args → "" literal; 1 arg → the arg; n≥2 args →
        // left-fold of `str-cat` calls (prelude function). This avoids adding a
        // codegen case that would need to emit a function-call into the prelude.
        "str" => {
            let lowered: Vec<Expr> = args.iter().map(lower_expr).collect::<Result<_, _>>()?;
            if lowered.is_empty() {
                Ok(Expr::Str(vec![]))
            } else if lowered.len() == 1 {
                Ok(lowered.into_iter().next().unwrap())
            } else {
                // fold: str-cat(str-cat(a, b), c) …
                let mut acc = Expr::Call {
                    name: "str-cat".to_string(),
                    args: vec![lowered[0].clone(), lowered[1].clone()],
                };
                for extra in &lowered[2..] {
                    acc = Expr::Call {
                        name: "str-cat".to_string(),
                        args: vec![acc, extra.clone()],
                    };
                }
                Ok(acc)
            }
        }
        name => {
            let lowered: Vec<Expr> = args.iter().map(lower_expr).collect::<Result<_, _>>()?;
            // Builtins keyed by bare name (`+`, `inc`, …) try `name`; builtins
            // keyed by a host-class-qualified name (`Math/round`, `Math/abs`)
            // need the fully-qualified form. When the head IS namespaced (e.g.
            // `Math/abs`) the qualified lookup must win — otherwise `Math/abs`
            // would collide with the bare `abs` (integer) builtin.
            let builtin = if head.namespace.is_some() {
                Builtin::from_name(&head.to_qualified()).or_else(|| Builtin::from_name(name))
            } else {
                Builtin::from_name(name)
            };
            if let Some(op) = builtin {
                check_builtin_arity(op, lowered.len())?;
                Ok(Expr::Builtin { op, args: lowered })
            } else {
                Ok(Expr::Call {
                    name: head.to_qualified(),
                    args: lowered,
                })
            }
        }
    }
}

fn lower_quote(args: &[EdnValue]) -> Result<Expr, CljError> {
    if args.len() != 1 {
        return Err(CljError::Lower("quote takes: (quote form)".into()));
    }
    Ok(Expr::Str(edn_to_string(&args[0]).into_bytes()))
}

fn lower_var(args: &[EdnValue]) -> Result<Expr, CljError> {
    if args.len() != 1 {
        return Err(CljError::Lower("var takes: (var symbol)".into()));
    }
    match &args[0] {
        EdnValue::Symbol(_) => Ok(Expr::Str(edn_to_string(&args[0]).into_bytes())),
        other => Err(CljError::Lower(format!(
            "var requires a symbol, found {other:?}"
        ))),
    }
}

// ---- desugaring helpers for iteration sugars -------------------------------
// Each builds an equivalent EDN s-expression out of existing special forms and
// re-lowers it, so no new AST node or codegen path is introduced.

fn dsym(name: &str) -> EdnValue {
    EdnValue::Symbol(Symbol {
        namespace: None,
        name: name.into(),
    })
}
fn dlist(items: Vec<EdnValue>) -> EdnValue {
    EdnValue::List(items)
}
fn dvec(items: Vec<EdnValue>) -> EdnValue {
    EdnValue::Vector(items)
}

/// `(while test body…)` → `(loop [_while 0] (if test (do body… (recur 0)) 0))`.
fn lower_while(args: &[EdnValue]) -> Result<Expr, CljError> {
    let test = args
        .first()
        .ok_or_else(|| CljError::Lower("while takes: (while test body…)".into()))?
        .clone();
    let mut do_items = vec![dsym("do")];
    do_items.extend(args[1..].iter().cloned());
    do_items.push(dlist(vec![dsym("recur"), EdnValue::Integer(0)]));
    let if_form = dlist(vec![
        dsym("if"),
        test,
        dlist(do_items),
        EdnValue::Integer(0),
    ]);
    let loop_form = dlist(vec![
        dsym("loop"),
        dvec(vec![dsym("_while"), EdnValue::Integer(0)]),
        if_form,
    ]);
    lower_expr(&loop_form)
}

/// `(dotimes [i n] body…)` →
/// `(let [_dotimes_n n] (loop [i 0] (if (< i _dotimes_n) (do body… (recur (+ i 1))) 0)))`.
fn lower_dotimes(args: &[EdnValue]) -> Result<Expr, CljError> {
    let binding = match args.first() {
        Some(EdnValue::Vector(v)) if v.len() == 2 => v,
        _ => {
            return Err(CljError::Lower(
                "dotimes takes: (dotimes [i n] body…)".into(),
            ));
        }
    };
    let i = binding[0].clone();
    let n = binding[1].clone();
    let limit = dsym("_dotimes_n");
    let mut do_items = vec![dsym("do")];
    do_items.extend(args[1..].iter().cloned());
    do_items.push(dlist(vec![
        dsym("recur"),
        dlist(vec![dsym("+"), i.clone(), EdnValue::Integer(1)]),
    ]));
    let if_form = dlist(vec![
        dsym("if"),
        dlist(vec![dsym("<"), i.clone(), limit.clone()]),
        dlist(do_items),
        EdnValue::Integer(0),
    ]);
    let loop_form = dlist(vec![
        dsym("loop"),
        dvec(vec![i, EdnValue::Integer(0)]),
        if_form,
    ]);
    let let_form = dlist(vec![dsym("let"), dvec(vec![limit, n]), loop_form]);
    lower_expr(&let_form)
}

/// `(doseq [x coll] body…)` →
/// `(let [_doseq_v coll _doseq_n (vec-count _doseq_v)]
///    (loop [_doseq_i 0]
///      (if (< _doseq_i _doseq_n)
///        (do (let [x (vec-nth _doseq_v _doseq_i)] body…) (recur (+ _doseq_i 1)))
///        0)))`.
/// Single-binding only; needs the prelude (`vec-count`/`vec-nth`).
fn lower_doseq(args: &[EdnValue]) -> Result<Expr, CljError> {
    let binding = match args.first() {
        Some(EdnValue::Vector(v)) if v.len() == 2 => v,
        _ => {
            return Err(CljError::Lower(
                "doseq takes a single binding: (doseq [x coll] body…)".into(),
            ));
        }
    };
    let x = binding[0].clone();
    let coll = binding[1].clone();
    let v = dsym("_doseq_v");
    let n = dsym("_doseq_n");
    let i = dsym("_doseq_i");
    let mut inner_let = vec![
        dsym("let"),
        dvec(vec![x, dlist(vec![dsym("vec-nth"), v.clone(), i.clone()])]),
    ];
    inner_let.extend(args[1..].iter().cloned());
    let do_form = dlist(vec![
        dsym("do"),
        dlist(inner_let),
        dlist(vec![
            dsym("recur"),
            dlist(vec![dsym("+"), i.clone(), EdnValue::Integer(1)]),
        ]),
    ]);
    let if_form = dlist(vec![
        dsym("if"),
        dlist(vec![dsym("<"), i.clone(), n.clone()]),
        do_form,
        EdnValue::Integer(0),
    ]);
    let loop_form = dlist(vec![
        dsym("loop"),
        dvec(vec![i, EdnValue::Integer(0)]),
        if_form,
    ]);
    let let_form = dlist(vec![
        dsym("let"),
        dvec(vec![v.clone(), coll, n, dlist(vec![dsym("vec-count"), v])]),
        loop_form,
    ]);
    lower_expr(&let_form)
}

#[derive(Debug, Clone, Copy)]
enum ThreadPosition {
    First,
    Last,
}

fn lower_thread(args: &[EdnValue], position: ThreadPosition) -> Result<Expr, CljError> {
    let Some((first, steps)) = args.split_first() else {
        return Err(CljError::Lower("threading macro requires a value".into()));
    };
    let mut acc = first.clone();
    for step in steps {
        acc = thread_step(acc, step, position)?;
    }
    lower_expr(&acc)
}

fn thread_step(
    value: EdnValue,
    step: &EdnValue,
    position: ThreadPosition,
) -> Result<EdnValue, CljError> {
    match step {
        EdnValue::List(items) => {
            let Some((head, args)) = items.split_first() else {
                return Err(CljError::Lower(
                    "threading macro step cannot be an empty list".into(),
                ));
            };
            let mut out = Vec::with_capacity(items.len() + 1);
            out.push(head.clone());
            match position {
                ThreadPosition::First => {
                    out.push(value);
                    out.extend(args.iter().cloned());
                }
                ThreadPosition::Last => {
                    out.extend(args.iter().cloned());
                    out.push(value);
                }
            }
            Ok(EdnValue::List(out))
        }
        EdnValue::Symbol(_) => Ok(EdnValue::List(vec![step.clone(), value])),
        other => Err(CljError::Lower(format!(
            "threading macro step must be a list or symbol, found: {other:?}"
        ))),
    }
}

fn lower_cond_thread(args: &[EdnValue], position: ThreadPosition) -> Result<Expr, CljError> {
    let Some((first, clauses)) = args.split_first() else {
        return Err(CljError::Lower(
            "conditional threading macro requires a value".into(),
        ));
    };
    if clauses.len() % 2 != 0 {
        return Err(CljError::Lower(
            "conditional threading macro requires test/step pairs".into(),
        ));
    }
    let thread_value = "__kotoba_cond_thread_value".to_string();
    let mut body = Expr::Var(thread_value.clone());
    for pair in clauses.chunks_exact(2).rev() {
        let threaded = thread_step(
            EdnValue::Symbol(Symbol::bare(thread_value.clone())),
            &pair[1],
            position,
        )?;
        body = Expr::Let {
            bindings: vec![(
                thread_value.clone(),
                Expr::If {
                    cond: Box::new(lower_expr(&pair[0])?),
                    then: Box::new(lower_expr(&threaded)?),
                    els: Box::new(Expr::Var(thread_value.clone())),
                },
            )],
            body: vec![body],
        };
    }
    Ok(Expr::Let {
        bindings: vec![(thread_value, lower_expr(first)?)],
        body: vec![body],
    })
}

fn lower_some_thread(args: &[EdnValue], position: ThreadPosition) -> Result<Expr, CljError> {
    let Some((first, steps)) = args.split_first() else {
        return Err(CljError::Lower(
            "nil-aware threading macro requires a value".into(),
        ));
    };
    let thread_value = "__kotoba_some_thread_value".to_string();
    let mut body = Expr::Var(thread_value.clone());
    for step in steps.iter().rev() {
        let threaded = thread_step(
            EdnValue::Symbol(Symbol::bare(thread_value.clone())),
            step,
            position,
        )?;
        body = Expr::Let {
            bindings: vec![(
                thread_value.clone(),
                Expr::If {
                    cond: Box::new(Expr::Var(thread_value.clone())),
                    then: Box::new(lower_expr(&threaded)?),
                    els: Box::new(Expr::Int(0)),
                },
            )],
            body: vec![body],
        };
    }
    Ok(Expr::Let {
        bindings: vec![(thread_value, lower_expr(first)?)],
        body: vec![body],
    })
}

fn lower_as_thread(args: &[EdnValue]) -> Result<Expr, CljError> {
    if args.len() < 2 {
        return Err(CljError::Lower("as-> takes: (as-> expr name form…)".into()));
    }
    let name = sym_name(&args[1], "as-> binding name")?;
    let mut forms = args[2..].iter().rev();
    let mut body = match forms.next() {
        Some(last) => lower_expr(last)?,
        None => Expr::Var(name.clone()),
    };
    for form in forms {
        body = Expr::Let {
            bindings: vec![(name.clone(), lower_expr(form)?)],
            body: vec![body],
        };
    }
    Ok(Expr::Let {
        bindings: vec![(name, lower_expr(&args[0])?)],
        body: vec![body],
    })
}

fn lower_if(args: &[EdnValue]) -> Result<Expr, CljError> {
    if args.len() < 2 || args.len() > 3 {
        return Err(CljError::Lower("if takes: (if cond then else?)".into()));
    }
    Ok(Expr::If {
        cond: Box::new(lower_expr(&args[0])?),
        then: Box::new(lower_expr(&args[1])?),
        els: Box::new(match args.get(2) {
            Some(els) => lower_expr(els)?,
            None => Expr::Int(0),
        }),
    })
}

fn lower_if_not(args: &[EdnValue]) -> Result<Expr, CljError> {
    if args.len() < 2 || args.len() > 3 {
        return Err(CljError::Lower(
            "if-not takes: (if-not cond then else?)".into(),
        ));
    }
    Ok(Expr::If {
        cond: Box::new(lower_expr(&args[0])?),
        then: Box::new(match args.get(2) {
            Some(els) => lower_expr(els)?,
            None => Expr::Int(0),
        }),
        els: Box::new(lower_expr(&args[1])?),
    })
}

fn lower_when(args: &[EdnValue]) -> Result<Expr, CljError> {
    // (when c body…) == (if c (do body…) 0)
    if args.is_empty() {
        return Err(CljError::Lower("when takes: (when cond body…)".into()));
    }
    let cond = lower_expr(&args[0])?;
    let body = args[1..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Expr::If {
        cond: Box::new(cond),
        then: Box::new(Expr::Do(body)),
        els: Box::new(Expr::Int(0)),
    })
}

fn lower_when_not(args: &[EdnValue]) -> Result<Expr, CljError> {
    // (when-not c body…) == (if c 0 (do body…))
    if args.is_empty() {
        return Err(CljError::Lower(
            "when-not takes: (when-not cond body…)".into(),
        ));
    }
    let cond = lower_expr(&args[0])?;
    let body = args[1..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Expr::If {
        cond: Box::new(cond),
        then: Box::new(Expr::Int(0)),
        els: Box::new(Expr::Do(body)),
    })
}

fn lower_if_let(args: &[EdnValue]) -> Result<Expr, CljError> {
    if args.len() < 2 || args.len() > 3 {
        return Err(CljError::Lower(
            "if-let takes: (if-let [name init] then else?)".into(),
        ));
    }
    let (truthy_name, bindings) = lower_single_binding(args.first(), "if-let")?;
    let then = lower_expr(&args[1])?;
    let els = match args.get(2) {
        Some(els) => lower_expr(els)?,
        None => Expr::Int(0),
    };
    Ok(Expr::Let {
        bindings,
        body: vec![Expr::If {
            cond: Box::new(Expr::Var(truthy_name)),
            then: Box::new(then),
            els: Box::new(els),
        }],
    })
}

fn lower_when_let(args: &[EdnValue]) -> Result<Expr, CljError> {
    if args.len() < 2 {
        return Err(CljError::Lower(
            "when-let takes: (when-let [name init] body…)".into(),
        ));
    }
    let (truthy_name, bindings) = lower_single_binding(args.first(), "when-let")?;
    let body = args[1..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Expr::Let {
        bindings,
        body: vec![Expr::If {
            cond: Box::new(Expr::Var(truthy_name)),
            then: Box::new(Expr::Do(body)),
            els: Box::new(Expr::Int(0)),
        }],
    })
}

fn lower_single_binding(
    binding_form: Option<&EdnValue>,
    form_name: &str,
) -> Result<(String, LoweredBindings), CljError> {
    let binding_vec = match binding_form {
        Some(EdnValue::Vector(v)) => v,
        _ => {
            return Err(CljError::Lower(format!(
                "{form_name} requires a binding vector: ({form_name} [name init] …)"
            )));
        }
    };
    if binding_vec.len() != 2 {
        return Err(CljError::Lower(format!(
            "{form_name} binding vector must contain exactly one name/init pair"
        )));
    }
    let init = lower_expr(&binding_vec[1])?;
    lower_binding_pattern(
        &binding_vec[0],
        init,
        0,
        &format!("{form_name} binding name"),
    )
}

fn lower_let(args: &[EdnValue]) -> Result<Expr, CljError> {
    // (let [b v b v …] body…)
    let binding_vec = match args.first() {
        Some(EdnValue::Vector(v)) => v,
        _ => {
            return Err(CljError::Lower(
                "let requires a binding vector: (let [b v …] …)".into(),
            ));
        }
    };
    if binding_vec.len() % 2 != 0 {
        return Err(CljError::Lower(
            "let binding vector must have an even number of forms".into(),
        ));
    }
    let mut bindings = Vec::with_capacity(binding_vec.len() / 2);
    let mut it = binding_vec.iter();
    let mut idx = 0;
    while let (Some(name), Some(val)) = (it.next(), it.next()) {
        let (_, mut lowered) =
            lower_binding_pattern(name, lower_expr(val)?, idx, "let binding name")?;
        bindings.append(&mut lowered);
        idx += 1;
    }
    let body = args[1..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    if body.is_empty() {
        return Err(CljError::Lower(
            "let requires at least one body expression".into(),
        ));
    }
    Ok(Expr::Let { bindings, body })
}

fn lower_binding_pattern(
    pattern: &EdnValue,
    init: Expr,
    idx: usize,
    ctx: &str,
) -> Result<(String, LoweredBindings), CljError> {
    match pattern {
        EdnValue::Symbol(_) => {
            let name = sym_name(pattern, ctx)?;
            Ok((name.clone(), vec![(name, init)]))
        }
        EdnValue::Vector(_) | EdnValue::Map(_) => {
            let temp = format!("\0kotoba_destructure_{idx}");
            let mut bindings = vec![(temp.clone(), init)];
            collect_destructuring(pattern, Expr::Var(temp.clone()), &mut bindings, ctx)?;
            Ok((temp, bindings))
        }
        other => Err(CljError::Lower(format!(
            "{ctx} must be a symbol or destructuring form, found {other:?}"
        ))),
    }
}

fn collect_destructuring(
    pattern: &EdnValue,
    source: Expr,
    out: &mut LoweredBindings,
    ctx: &str,
) -> Result<(), CljError> {
    match pattern {
        EdnValue::Vector(_) => collect_vector_destructuring(pattern, source, out, ctx),
        EdnValue::Map(_) => collect_map_destructuring(pattern, source, out, ctx),
        other => Err(CljError::Lower(format!(
            "{ctx} must be a destructuring form, found {other:?}"
        ))),
    }
}

fn collect_vector_destructuring(
    pattern: &EdnValue,
    source: Expr,
    out: &mut LoweredBindings,
    ctx: &str,
) -> Result<(), CljError> {
    let EdnValue::Vector(items) = pattern else {
        return Err(CljError::Lower(format!(
            "{ctx} must be a vector destructuring form"
        )));
    };

    let mut item_idx = 0;
    let mut value_idx = 0;
    let mut rest_seen = false;
    while item_idx < items.len() {
        let item = &items[item_idx];
        if is_destructure_as(item) {
            let Some(name) = items.get(item_idx + 1) else {
                return Err(CljError::Lower(format!(
                    "{ctx} vector destructuring `:as` requires a following symbol"
                )));
            };
            if item_idx + 2 != items.len() {
                return Err(CljError::Lower(format!(
                    "{ctx} vector destructuring `:as` must be the final option"
                )));
            }
            let name = sym_name(name, ctx)?;
            if name != "_" {
                out.push((name, source.clone()));
            }
            item_idx += 2;
            continue;
        }

        if is_destructure_rest(item) {
            let Some(rest) = items.get(item_idx + 1) else {
                return Err(CljError::Lower(format!(
                    "{ctx} vector destructuring `&` requires a following symbol"
                )));
            };
            let name = sym_name(rest, ctx)?;
            if name != "_" {
                out.push((
                    name,
                    Expr::Call {
                        name: "subvec".to_string(),
                        args: vec![source.clone(), Expr::Int(value_idx as i64)],
                    },
                ));
            }
            rest_seen = true;
            item_idx += 2;
            continue;
        }

        if rest_seen {
            return Err(CljError::Lower(format!(
                "{ctx} vector destructuring only allows `:as` after `& rest`"
            )));
        }

        let value = Expr::Call {
            name: "nth".to_string(),
            args: vec![source.clone(), Expr::Int(value_idx as i64)],
        };
        match item {
            EdnValue::Symbol(_) => {
                let name = sym_name(item, ctx)?;
                if name != "_" {
                    out.push((name, value));
                }
            }
            EdnValue::Vector(_) => {
                let temp = format!("\0kotoba_nested_destructure_{}", out.len());
                out.push((temp.clone(), value));
                collect_destructuring(item, Expr::Var(temp), out, ctx)?;
            }
            EdnValue::Map(_) => {
                let temp = format!("\0kotoba_nested_destructure_{}", out.len());
                out.push((temp.clone(), value));
                collect_destructuring(item, Expr::Var(temp), out, ctx)?;
            }
            other => {
                return Err(CljError::Lower(format!(
                    "{ctx} vector destructuring entries must be symbols or nested destructuring forms, found {other:?}"
                )));
            }
        }
        item_idx += 1;
        value_idx += 1;
    }
    Ok(())
}

fn collect_map_destructuring(
    pattern: &EdnValue,
    source: Expr,
    out: &mut LoweredBindings,
    ctx: &str,
) -> Result<(), CljError> {
    let EdnValue::Map(items) = pattern else {
        return Err(CljError::Lower(format!(
            "{ctx} must be a map destructuring form"
        )));
    };

    let defaults = map_destructure_defaults(items, ctx)?;

    for (binding, key) in items {
        if map_destructure_option(binding, "or") || map_destructure_option(binding, "keys") {
            continue;
        }
        if map_destructure_option(binding, "strs") {
            let EdnValue::Vector(names) = key else {
                return Err(CljError::Lower(format!(
                    "{ctx} map destructuring `:strs` requires a vector of symbols"
                )));
            };
            for name in names {
                let name = sym_name(name, ctx)?;
                if name != "_" {
                    let key = Expr::Str(name.as_bytes().to_vec());
                    out.push((
                        name.clone(),
                        map_destructure_get(source.clone(), key, Some((&name, &defaults)))?,
                    ));
                }
            }
            continue;
        }
        if map_destructure_option(binding, "as") {
            let name = sym_name(key, ctx)?;
            if name != "_" {
                out.push((name, source.clone()));
            }
            continue;
        }

        if map_destructure_option(binding, "keys") {
            unreachable!("handled above")
        }

        lower_map_destructure_entry(binding, key, source.clone(), &defaults, out, ctx)?;
    }

    if let Some(keys) = items
        .iter()
        .find_map(|(k, v)| map_destructure_option(k, "keys").then_some(v))
    {
        let EdnValue::Vector(names) = keys else {
            return Err(CljError::Lower(format!(
                "{ctx} map destructuring `:keys` requires a vector of symbols"
            )));
        };
        for name in names {
            let name = sym_name(name, ctx)?;
            if name != "_" {
                let key = Expr::Str(format!(":{name}").into_bytes());
                out.push((
                    name.clone(),
                    map_destructure_get(source.clone(), key, Some((&name, &defaults)))?,
                ));
            }
        }
    }

    Ok(())
}

fn lower_map_destructure_entry(
    binding: &EdnValue,
    key: &EdnValue,
    source: Expr,
    defaults: &std::collections::BTreeMap<String, Expr>,
    out: &mut LoweredBindings,
    ctx: &str,
) -> Result<(), CljError> {
    let lookup = lower_expr(key)?;
    match binding {
        EdnValue::Symbol(_) => {
            let name = sym_name(binding, ctx)?;
            if name != "_" {
                out.push((
                    name.clone(),
                    map_destructure_get(source, lookup, Some((&name, defaults)))?,
                ));
            }
        }
        EdnValue::Vector(_) | EdnValue::Map(_) => {
            let temp = format!("\0kotoba_nested_destructure_{}", out.len());
            out.push((temp.clone(), map_destructure_get(source, lookup, None)?));
            collect_destructuring(binding, Expr::Var(temp), out, ctx)?;
        }
        other => {
            return Err(CljError::Lower(format!(
                "{ctx} map destructuring entries must bind symbols or nested destructuring forms, found {other:?}"
            )));
        }
    }
    Ok(())
}

fn map_destructure_get(
    source: Expr,
    key: Expr,
    default: Option<(&str, &std::collections::BTreeMap<String, Expr>)>,
) -> Result<Expr, CljError> {
    let get = Expr::Call {
        name: "get".to_string(),
        args: vec![source.clone(), key.clone()],
    };
    let Some((name, defaults)) = default else {
        return Ok(get);
    };
    let Some(default_expr) = defaults.get(name) else {
        return Ok(get);
    };
    Ok(Expr::If {
        cond: Box::new(Expr::Call {
            name: "contains-key?".to_string(),
            args: vec![source, key],
        }),
        then: Box::new(get),
        els: Box::new(default_expr.clone()),
    })
}

fn map_destructure_defaults(
    items: &std::collections::BTreeMap<EdnValue, EdnValue>,
    ctx: &str,
) -> Result<std::collections::BTreeMap<String, Expr>, CljError> {
    let mut defaults = std::collections::BTreeMap::new();
    let Some(default_map) = items
        .iter()
        .find_map(|(k, v)| map_destructure_option(k, "or").then_some(v))
    else {
        return Ok(defaults);
    };
    let EdnValue::Map(entries) = default_map else {
        return Err(CljError::Lower(format!(
            "{ctx} map destructuring `:or` requires a map of symbol defaults"
        )));
    };
    for (name, value) in entries {
        defaults.insert(sym_name(name, ctx)?, lower_expr(value)?);
    }
    Ok(defaults)
}

fn map_destructure_option(v: &EdnValue, name: &str) -> bool {
    matches!(v, EdnValue::Keyword(k) if k.namespace().is_none() && k.name() == name)
}

fn is_destructure_rest(v: &EdnValue) -> bool {
    matches!(v, EdnValue::Symbol(s) if s.namespace.is_none() && s.name == "&")
}

fn is_destructure_as(v: &EdnValue) -> bool {
    matches!(v, EdnValue::Keyword(k) if k.namespace().is_none() && k.name() == "as")
}

fn lower_case(args: &[EdnValue]) -> Result<Expr, CljError> {
    let Some((value, clauses)) = args.split_first() else {
        return Err(CljError::Lower(
            "case takes: (case expr test result … default?)".into(),
        ));
    };
    if clauses.len() < 2 {
        return Err(CljError::Lower(
            "case requires at least one test/result clause".into(),
        ));
    }
    let default = if clauses.len() % 2 == 1 {
        lower_expr(clauses.last().expect("default exists"))?
    } else {
        Expr::Int(0)
    };
    let pairs = &clauses[..clauses.len() - (clauses.len() % 2)];
    let case_value = "__kotoba_case_value".to_string();
    let mut acc = default;
    for pair in pairs.chunks_exact(2).rev() {
        let tests = case_tests(&pair[0]);
        let then = lower_expr(&pair[1])?;
        let cond = lower_case_tests(&case_value, tests)?;
        acc = Expr::If {
            cond: Box::new(cond),
            then: Box::new(then),
            els: Box::new(acc),
        };
    }
    Ok(Expr::Let {
        bindings: vec![(case_value, lower_expr(value)?)],
        body: vec![acc],
    })
}

fn case_tests(test: &EdnValue) -> Vec<&EdnValue> {
    match test {
        EdnValue::List(xs) | EdnValue::Vector(xs) => xs.iter().collect(),
        EdnValue::Set(xs) => xs.iter().collect(),
        other => vec![other],
    }
}

fn lower_case_tests(case_value: &str, tests: Vec<&EdnValue>) -> Result<Expr, CljError> {
    if tests.is_empty() {
        return Ok(Expr::Int(0));
    }
    let mut iter = tests.into_iter().rev();
    let first = iter.next().expect("non-empty case tests");
    let mut acc = case_eq(case_value, first)?;
    for test in iter {
        acc = Expr::Builtin {
            op: Builtin::Or,
            args: vec![case_eq(case_value, test)?, acc],
        };
    }
    Ok(acc)
}

fn case_eq(case_value: &str, test: &EdnValue) -> Result<Expr, CljError> {
    Ok(Expr::Builtin {
        op: Builtin::Eq,
        args: vec![Expr::Var(case_value.to_string()), lower_expr(test)?],
    })
}

/// `(cond t1 e1 t2 e2 … [:else ed])` → right-nested `if`. A `:else` keyword (or
/// literal `true`) test marks the default clause; with no default the value is
/// `0` (nil-ish) when every test fails.
fn lower_cond(args: &[EdnValue]) -> Result<Expr, CljError> {
    if !args.len().is_multiple_of(2) {
        return Err(CljError::Lower(
            "cond requires an even number of test/expr forms".into(),
        ));
    }
    // Fold right-to-left so the first clause ends up outermost.
    let mut acc = Expr::Int(0);
    for pair in args.chunks_exact(2).rev() {
        let (test, expr) = (&pair[0], &pair[1]);
        let then = lower_expr(expr)?;
        if is_else_test(test) {
            // Default clause: its expr becomes the running accumulator.
            acc = then;
        } else {
            acc = Expr::If {
                cond: Box::new(lower_expr(test)?),
                then: Box::new(then),
                els: Box::new(acc),
            };
        }
    }
    Ok(acc)
}

/// A `cond` test that always fires: the `:else` keyword or literal `true`.
fn is_else_test(v: &EdnValue) -> bool {
    match v {
        EdnValue::Keyword(k) => k.0.name == "else",
        EdnValue::Bool(true) => true,
        _ => false,
    }
}

/// `(loop [b v …] body…)` — same binding shape as `let`, plus a `recur` target.
fn lower_loop(args: &[EdnValue]) -> Result<Expr, CljError> {
    let binding_vec = match args.first() {
        Some(EdnValue::Vector(v)) => v,
        _ => {
            return Err(CljError::Lower(
                "loop requires a binding vector: (loop [b v …] …)".into(),
            ));
        }
    };
    if binding_vec.len() % 2 != 0 {
        return Err(CljError::Lower(
            "loop binding vector must have an even number of forms".into(),
        ));
    }
    let mut bindings = Vec::with_capacity(binding_vec.len() / 2);
    let mut destructured_bindings = Vec::new();
    let mut it = binding_vec.iter();
    let mut idx = 0;
    while let (Some(name), Some(val)) = (it.next(), it.next()) {
        let (_, lowered) = lower_binding_pattern(name, lower_expr(val)?, idx, "loop binding name")?;
        let mut lowered = lowered.into_iter();
        let Some(loop_binding) = lowered.next() else {
            return Err(CljError::Lower(
                "loop binding lowering unexpectedly produced no binding".into(),
            ));
        };
        bindings.push(loop_binding);
        destructured_bindings.extend(lowered);
        idx += 1;
    }
    let body = args[1..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    if body.is_empty() {
        return Err(CljError::Lower(
            "loop requires at least one body expression".into(),
        ));
    }
    let body = prepend_bindings(destructured_bindings, body);
    Ok(Expr::Loop { bindings, body })
}

/// `(fn [params…] body…)` / `(fn name [params…] body…)` / `(fn* …)`.
///
/// Produces a transient [`Expr::Fn`]; the lambda-lifting pass turns it into a
/// synthetic top-level function plus a [`Expr::MakeClosure`] at this site. An
/// optional self-name (for `(fn rec [..] …)`) is accepted but not yet bound for
/// self-recursion — milestone-1 closures are non-self-referential.
fn lower_fn(args: &[EdnValue]) -> Result<Expr, CljError> {
    // Skip an optional self-name symbol.
    let rest = match args.first() {
        Some(EdnValue::Symbol(_)) => &args[1..],
        _ => args,
    };
    // Multi-arity `(fn ([a] …) ([a b] …))` is not supported yet.
    if matches!(rest.first(), Some(EdnValue::List(_))) {
        return Err(CljError::Lower(
            "multi-arity `(fn ([params] …) …)` is not yet supported in the Kotoba compiler; use a single `[params]` vector".into(),
        ));
    }
    let param_vec = match rest.first() {
        Some(EdnValue::Vector(ps)) => ps,
        _ => {
            return Err(CljError::Lower(
                "fn requires a parameter vector: (fn [params…] body…)".into(),
            ));
        }
    };
    if param_vec.iter().any(is_amp_symbol) {
        return Err(CljError::Lower(
            "variadic `& rest` params in `(fn …)` / `#(… %&)` are not yet supported in the Kotoba compiler"
                .into(),
        ));
    }
    let (params, destructured) = lower_param_list(param_vec, "fn parameter")?;
    let body = rest[1..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    if body.is_empty() {
        return Err(CljError::Lower(
            "fn requires at least one body expression".into(),
        ));
    }
    let body = prepend_bindings(destructured, body);
    Ok(Expr::Fn { params, body })
}

fn is_amp_symbol(v: &EdnValue) -> bool {
    matches!(v, EdnValue::Symbol(s) if s.namespace.is_none() && s.name == "&")
}

// ---- defgraph: a langgraph-shaped control-flow graph as data ---------------

/// `(defgraph name :entry :n0 :nodes {:n0 fn0 :n1 fn1 …} :edges {:n0 :n1 …})`
///
/// Lowers to **three generated `defn`s** (no new runtime machinery — pure
/// desugar into the existing AST):
///   - `name-dispatch [nid state]` — `cond` on the node id → call that node fn
///     `(fnK state)`; default returns `state` unchanged.
///   - `name-next [nid state]` — `cond` on the node id → the next node id. A
///     static edge `:a :b` yields `id(:b)`; a conditional edge
///     `:a (if-edge pred? :then :else)` yields `(if (pred? state) id(:then)
///     id(:else))`. `:end` (and any unlisted node) yields the `-1` terminator.
///   - `name [state]` — `loop [nid entry s state]`: while `nid >= 0`, run the
///     node (`dispatch`), compute the successor (`next`) from the new state, and
///     `recur`; return the final state when `nid` reaches `-1` (END).
///
/// Node fns are ordinary `(defn nodeK [state] …)` returning the next state map
/// (they mutate/assoc the Stage-B `map`); predicates are `(defn pred? [state]
/// …)` returning truthy/falsy. Keywords are compile-time only — node ids are
/// assigned here, so nothing keyword-shaped exists at runtime.
fn lower_defgraph(items: &[EdnValue]) -> Result<Vec<Function>, CljError> {
    // (defgraph name :k v :k v …)
    let name = match items.get(1) {
        Some(EdnValue::Symbol(s)) => s.to_qualified(),
        _ => {
            return Err(CljError::Lower(
                "defgraph requires a name: (defgraph name …)".into(),
            ));
        }
    };
    let kwargs = &items[2..];
    if !kwargs.len().is_multiple_of(2) {
        return Err(CljError::Lower(
            "defgraph options must be :key value pairs".into(),
        ));
    }
    let mut entry: Option<String> = None;
    let mut nodes: Option<&std::collections::BTreeMap<EdnValue, EdnValue>> = None;
    let mut edges: Option<&std::collections::BTreeMap<EdnValue, EdnValue>> = None;
    let mut state_decl: Option<&std::collections::BTreeMap<EdnValue, EdnValue>> = None;
    let mut it = kwargs.iter();
    while let (Some(k), Some(v)) = (it.next(), it.next()) {
        let key = match k {
            EdnValue::Keyword(kw) => kw.name().to_string(),
            other => {
                return Err(CljError::Lower(format!(
                    "defgraph option key must be a keyword, found {other:?}"
                )));
            }
        };
        match key.as_str() {
            "entry" => entry = Some(kw_name(v, "defgraph :entry")?),
            "nodes" => nodes = Some(as_map(v, "defgraph :nodes")?),
            "edges" => edges = Some(as_map(v, "defgraph :edges")?),
            "state" => state_decl = Some(as_map(v, "defgraph :state")?),
            other => {
                return Err(CljError::Lower(format!(
                    "unknown defgraph option `:{other}`"
                )));
            }
        }
    }
    let nodes = nodes.ok_or_else(|| CljError::Lower("defgraph requires :nodes".into()))?;
    let entry = entry.ok_or_else(|| CljError::Lower("defgraph requires :entry".into()))?;
    let empty = std::collections::BTreeMap::new();
    let edges = edges.unwrap_or(&empty);

    // Assign each node keyword a stable int id (BTreeMap key order). `:end` and
    // any unlisted target resolve to the -1 terminator.
    let mut node_order: Vec<(String, String)> = Vec::new(); // (node-kw-name, node-fn-name)
    let mut id_of: std::collections::HashMap<String, i64> = std::collections::HashMap::new();
    for (k, v) in nodes.iter() {
        let kw = kw_name(k, "defgraph node key")?;
        let func = match v {
            EdnValue::Symbol(s) => s.to_qualified(),
            other => {
                return Err(CljError::Lower(format!(
                    "defgraph node `{kw}` must map to a fn symbol, found {other:?}"
                )));
            }
        };
        id_of.insert(kw.clone(), node_order.len() as i64);
        node_order.push((kw, func));
    }
    let resolve_id = |target: &str| -> Result<i64, CljError> {
        if target == "end" {
            Ok(-1)
        } else {
            id_of.get(target).copied().ok_or_else(|| {
                CljError::Lower(format!("defgraph edge targets unknown node `:{target}`"))
            })
        }
    };
    let entry_id = resolve_id(&entry)?;
    if entry_id < 0 {
        return Err(CljError::Lower("defgraph :entry cannot be :end".into()));
    }

    let dispatch_name = format!("{name}-dispatch");
    let next_name = format!("{name}-next");
    let merge_name = format!("{name}-merge");
    let nid = || Expr::Var("__nid".to_string());
    let state = || Expr::Var("__state".to_string());
    let eq_id = |id: i64| Expr::Builtin {
        op: Builtin::Eq,
        args: vec![nid(), Expr::Int(id)],
    };

    // When `:state` is declared, switch on the langgraph reducer semantics: a
    // node returns a *partial update* map that `name-merge` folds into the
    // running state per the channel's reducer (append vs override). Without
    // `:state`, the node returns the full next state directly (no merge).
    let mut extra_fns: Vec<Function> = Vec::new();
    let has_state = state_decl.is_some();
    if let Some(decl) = state_decl {
        extra_fns.push(build_merge_fn(&merge_name, decl)?);
    }

    // dispatch: nested if over node ids → run node (optionally merged); default __state.
    let mut dispatch_body = state();
    for (i, (_, func)) in node_order.iter().enumerate().rev() {
        let node_call = Expr::Call {
            name: func.clone(),
            args: vec![state()],
        };
        let then = if has_state {
            // (name-merge __state (fnK __state))
            Expr::Call {
                name: merge_name.clone(),
                args: vec![state(), node_call],
            }
        } else {
            node_call
        };
        dispatch_body = Expr::If {
            cond: Box::new(eq_id(i as i64)),
            then: Box::new(then),
            els: Box::new(dispatch_body),
        };
    }
    let dispatch_fn = Function {
        name: dispatch_name.clone(),
        export_name: Some(dispatch_name.clone()),
        params: vec!["__nid".into(), "__state".into()],
        declared_effects: None,
        body: vec![dispatch_body],
        table_slot: None,
    };

    // next: nested if over node ids → successor id (static / if-edge); default -1.
    let mut next_body = Expr::Int(-1);
    for (i, (kw, _)) in node_order.iter().enumerate().rev() {
        let target_expr = match edges.get(&EdnValue::Keyword(kotoba_edn::Keyword::bare(kw.clone())))
        {
            None => Expr::Int(-1), // no outgoing edge → terminate
            Some(EdnValue::Keyword(t)) => Expr::Int(resolve_id(t.name())?),
            Some(EdnValue::List(parts)) => lower_if_edge(parts, &resolve_id, &state)?,
            Some(other) => {
                return Err(CljError::Lower(format!(
                    "defgraph edge for `:{kw}` must be a target keyword or (if-edge …), found {other:?}"
                )));
            }
        };
        next_body = Expr::If {
            cond: Box::new(eq_id(i as i64)),
            then: Box::new(target_expr),
            els: Box::new(next_body),
        };
    }
    let next_fn = Function {
        name: next_name.clone(),
        export_name: Some(next_name.clone()),
        params: vec!["__nid".into(), "__state".into()],
        declared_effects: None,
        body: vec![next_body],
        table_slot: None,
    };

    // runner: loop [__nid entry __s state] — dispatch then advance until -1.
    let runner = Function {
        name: name.clone(),
        export_name: Some(name.clone()),
        params: vec!["state".into()],
        declared_effects: None,
        body: vec![Expr::Loop {
            bindings: vec![
                ("__nid".into(), Expr::Int(entry_id)),
                ("__s".into(), Expr::Var("state".into())),
            ],
            body: vec![Expr::If {
                cond: Box::new(Expr::Builtin {
                    op: Builtin::Lt,
                    args: vec![Expr::Var("__nid".into()), Expr::Int(0)],
                }),
                then: Box::new(Expr::Var("__s".into())),
                els: Box::new(Expr::Let {
                    bindings: vec![(
                        "__s2".into(),
                        Expr::Call {
                            name: dispatch_name.clone(),
                            args: vec![Expr::Var("__nid".into()), Expr::Var("__s".into())],
                        },
                    )],
                    body: vec![Expr::Recur(vec![
                        Expr::Call {
                            name: next_name.clone(),
                            args: vec![Expr::Var("__nid".into()), Expr::Var("__s2".into())],
                        },
                        Expr::Var("__s2".into()),
                    ])],
                }),
            }],
        }],
        table_slot: None,
    };

    let mut out = vec![dispatch_fn, next_fn, runner];
    out.append(&mut extra_fns);
    Ok(out)
}

/// Build `name-merge [state update]` from a `:state` channel→reducer map. Folds
/// every entry of the partial-update map into `state`: an `add-messages` channel
/// extends the existing vector (or adopts the update's vector on first write); a
/// `:override` (default) channel does last-write-wins `map-assoc!`. Generated as
/// source and lowered through the normal path — clearer than hand-built AST.
fn build_merge_fn(
    merge_name: &str,
    decl: &std::collections::BTreeMap<EdnValue, EdnValue>,
) -> Result<Function, CljError> {
    let mut append_clauses = String::new();
    for (k, v) in decl.iter() {
        let ch = kw_name(k, "defgraph :state channel")?;
        let is_append = matches!(v, EdnValue::Symbol(s) if s.name == "add-messages");
        if is_append {
            // extend the existing channel vector, or adopt the update's on first write
            append_clauses.push_str(&format!(
                "(str-eq? __k \"{ch}\") (if (= (map-get __state __k) 0) (map-assoc! __state __k __v) (vec-extend! (map-get __state __k) __v)) "
            ));
        }
        // override channels need no clause — they fall through to the :else assoc
    }
    let src = format!(
        "(defn {merge_name} [__state __update]
           (loop [__i 0]
             (if (>= __i (map-count __update))
               __state
               (let [__k (map-key-at __update __i) __v (map-val-at __update __i)]
                 (do
                   (cond {append_clauses} :else (map-assoc! __state __k __v))
                   (recur (+ __i 1)))))))"
    );
    parse_one_defn(&src)
}

/// Parse a single `(defn …)` from generated source and lower it to a [`Function`].
fn parse_one_defn(src: &str) -> Result<Function, CljError> {
    let forms = kotoba_edn::parse_all(src).map_err(|e| CljError::Read(e.to_string()))?;
    match forms.first() {
        Some(EdnValue::List(items)) => {
            let mut functions = lower_defn(items)?;
            if functions.len() == 1 {
                Ok(functions.remove(0))
            } else {
                Err(CljError::Lower(
                    "generated merge fn unexpectedly lowered to multiple arities".into(),
                ))
            }
        }
        _ => Err(CljError::Lower(
            "generated merge fn did not parse as a defn".into(),
        )),
    }
}

/// Lower a conditional edge `(if-edge pred? :then :else)` to
/// `(if (pred? __state) id(:then) id(:else))`.
fn lower_if_edge(
    parts: &[EdnValue],
    resolve_id: &dyn Fn(&str) -> Result<i64, CljError>,
    state: &dyn Fn() -> Expr,
) -> Result<Expr, CljError> {
    // (if-edge pred-sym :then :else)
    let head = parts.first().and_then(|h| match h {
        EdnValue::Symbol(s) => Some(s.name.as_str()),
        _ => None,
    });
    if head != Some("if-edge") || parts.len() != 4 {
        return Err(CljError::Lower(
            "conditional edge must be (if-edge pred? :then :else)".into(),
        ));
    }
    let pred = match &parts[1] {
        EdnValue::Symbol(s) => s.to_qualified(),
        other => {
            return Err(CljError::Lower(format!(
                "if-edge predicate must be a fn symbol, found {other:?}"
            )));
        }
    };
    let then_id = resolve_id(&kw_name(&parts[2], "if-edge :then")?)?;
    let else_id = resolve_id(&kw_name(&parts[3], "if-edge :else")?)?;
    Ok(Expr::If {
        cond: Box::new(Expr::Call {
            name: pred,
            args: vec![state()],
        }),
        then: Box::new(Expr::Int(then_id)),
        els: Box::new(Expr::Int(else_id)),
    })
}

/// The bare name of a keyword value (`:foo` → `"foo"`).
fn kw_name(v: &EdnValue, ctx: &str) -> Result<String, CljError> {
    match v {
        EdnValue::Keyword(k) => Ok(k.name().to_string()),
        other => Err(CljError::Lower(format!(
            "{ctx} must be a keyword, found {other:?}"
        ))),
    }
}

fn as_map<'a>(
    v: &'a EdnValue,
    ctx: &str,
) -> Result<&'a std::collections::BTreeMap<EdnValue, EdnValue>, CljError> {
    match v {
        EdnValue::Map(m) => Ok(m),
        other => Err(CljError::Lower(format!(
            "{ctx} must be a map `{{…}}`, found {other:?}"
        ))),
    }
}

fn check_builtin_arity(op: Builtin, n: usize) -> Result<(), CljError> {
    let ok = match op {
        Builtin::Not
        | Builtin::Inc
        | Builtin::Dec
        | Builtin::Abs
        | Builtin::Zero
        | Builtin::Some
        | Builtin::Pos
        | Builtin::Neg
        | Builtin::Even
        | Builtin::Odd
        | Builtin::Double
        | Builtin::Int
        | Builtin::MathRound
        | Builtin::MathFloor
        | Builtin::MathCeil
        | Builtin::MathAbs
        | Builtin::MathSqrt
        | Builtin::StrLen => n == 1,
        Builtin::BytesAlloc | Builtin::BytesLen | Builtin::BytesFinish => n == 1,
        Builtin::Alloc | Builtin::Load64 | Builtin::Load32 => n == 1,
        Builtin::Store64 | Builtin::Store32 | Builtin::HasCapability | Builtin::LlmInfer => n == 2,
        Builtin::Sub => n >= 1, // unary negate or n-ary subtract
        Builtin::Min | Builtin::Max => n >= 1,
        Builtin::Add | Builtin::Mul | Builtin::And | Builtin::Or => n >= 1,
        Builtin::BitAnd | Builtin::BitOr | Builtin::BitXor => n >= 1,
        Builtin::BitShiftLeft | Builtin::BitShiftRight => n == 2,
        Builtin::Div | Builtin::Mod | Builtin::Rem | Builtin::ByteAt | Builtin::ByteAppend => {
            n == 2
        }
        Builtin::Eq | Builtin::NotEq => n >= 1,
        Builtin::Lt | Builtin::Gt | Builtin::Le | Builtin::Ge => n >= 1,
        Builtin::KqeAssert | Builtin::KqeRetract => n == 4,
        Builtin::KqeGetObjects => n == 3,
        Builtin::KqeQuery => n == 1,
    };
    if ok {
        Ok(())
    } else {
        Err(CljError::Lower(format!(
            "builtin {op:?} called with wrong number of arguments ({n})"
        )))
    }
}

fn sym_name(v: &EdnValue, ctx: &str) -> Result<String, CljError> {
    match v {
        EdnValue::Symbol(s) => Ok(s.to_qualified()),
        other => Err(CljError::Lower(format!(
            "{ctx} must be a symbol, found {other:?}"
        ))),
    }
}
