//! Lowering from the EDN reader (`kotoba_edn::EdnValue`) into a typed AST for
//! the i64 Clojure subset this compiler supports.
//!
//! Subset (everything is a 64-bit signed integer; booleans are 1/0):
//!   top-level   `(def name <const-expr>)`     compile-time integer constant
//!               `(defn name [a b …] body…)` / `(defn- …)` wasm function
//!               multi-arity `(defn name ([a] …) ([a b] …))`
//!               `(defonce name <const-expr>)` compile-time integer constant
//!               top-level `(do …)` wrapping definitions
//!               `(ns …)` namespace management decls, `(require …)` `(use …)` `(refer-clojure …)` `(import …)` `(gen-class …)` `(set! …)` record/type/protocol/multimethod decls, `(defmacro …)`, `(comment …)`, `(declare …)` ignored
//!   expressions integer literal, `true`/`false`, symbol
//!               `(if c t e)`  `(when c body…)` `(if-let [b v] t e)`
//!               `(when-let [b v] body…)` `(case e test result … default?)`
//!               `(let [b v …] body…)`  `(do e…)`, vector/map literals
//!               `(-> x step…)` `(->> x step…)` `(cond-> x test step …)`
//!               `(cond->> x test step …)` `(some-> x step…)`
//!               `(some->> x step…)` `(as-> x name form …)`
//!               vector and map destructuring in `defn`, `let`, `if-let`,
//!               `when-let`
//!               builtins: + - * / mod  = < > <= >=  and or not
//!               `(f args…)`  call a user `defn`

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
    /// Implicit `do`: the last expression is the return value.
    pub body: Vec<Expr>,
}

/// Builtin operators recognised in call position.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Builtin {
    Add,
    Sub,
    Mul,
    Div,
    Mod,
    Inc,
    Dec,
    Abs,
    Eq,
    NotEq,
    Lt,
    Gt,
    Le,
    Ge,
    Zero,
    Pos,
    Neg,
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

impl HostImport {
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

impl Builtin {
    fn from_name(s: &str) -> Option<Builtin> {
        let s = s.strip_prefix("clojure.core/").unwrap_or(s);
        Some(match s {
            "+" => Builtin::Add,
            "-" => Builtin::Sub,
            "*" => Builtin::Mul,
            "/" | "quot" => Builtin::Div,
            "mod" | "rem" => Builtin::Mod,
            "inc" => Builtin::Inc,
            "dec" => Builtin::Dec,
            "abs" => Builtin::Abs,
            "=" => Builtin::Eq,
            "!=" | "not=" => Builtin::NotEq,
            "<" => Builtin::Lt,
            ">" => Builtin::Gt,
            "<=" => Builtin::Le,
            ">=" => Builtin::Ge,
            "zero?" => Builtin::Zero,
            "pos?" => Builtin::Pos,
            "neg?" => Builtin::Neg,
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
            _ => return None,
        })
    }
}

/// Expression AST.
#[derive(Debug, Clone)]
pub enum Expr {
    /// Integer literal (booleans lower to 1/0 here).
    Int(i64),
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
}

/// Parse Clojure-subset source text into a [`Program`].
pub fn parse_program(src: &str) -> Result<Program, CljError> {
    let forms = kotoba_edn::parse_all(src).map_err(|e| CljError::Read(e.to_string()))?;
    let mut defs = Vec::new();
    let mut functions = Vec::new();

    for form in &forms {
        parse_top_level_form(form, &mut defs, &mut functions)?;
    }

    Ok(Program { defs, functions })
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
            )))
        }
    };
    let head = list_head_symbol(items)?;
    match head.name.as_str() {
        "ns" | "require" | "require-macros" | "use" | "use-macros" | "refer-clojure"
        | "in-ns" | "alias" | "create-ns" | "remove-ns" | "import" | "gen-class" | "set!"
        | "defrecord" | "deftype" | "defprotocol" | "extend-type" | "extend-protocol"
        | "defmulti" | "defmethod" | "defmacro" | "defstruct" | "create-struct" | "comment"
        | "declare" => {
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
            )))
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
    if matches!(items.get(params_idx), Some(EdnValue::Map(_))) {
        params_idx += 1;
    }
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
            return Ok(vec![lower_defn_arity(&name, arity, Some(name.clone()))?]);
        }
        return items[params_idx..]
            .iter()
            .map(|item| match item {
                EdnValue::List(arity) => lower_defn_arity(&name, arity, None),
                _ => unreachable!("checked above"),
            })
            .collect();
    }
    let (params, destructured_params) = match items.get(params_idx) {
        Some(EdnValue::Vector(ps)) => lower_param_list(ps, "defn parameter")?,
        _ => {
            return Err(CljError::Lower(format!(
                "defn `{name}` parameter list must be a vector `[…]`"
            )))
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
        body,
    }])
}

fn lower_defn_arity(
    name: &str,
    items: &[EdnValue],
    export_name: Option<String>,
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
            )))
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
        body,
    })
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
                )))
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
        EdnValue::Bool(b) => Ok(Expr::Int(if *b { 1 } else { 0 })),
        EdnValue::String(s) => Ok(Expr::Str(s.clone().into_bytes())),
        EdnValue::Keyword(_) => Ok(Expr::Str(edn_to_string(v).into_bytes())),
        EdnValue::Symbol(s) => Ok(Expr::Var(s.to_qualified())),
        EdnValue::List(items) => lower_call(items),
        EdnValue::Vector(items) => lower_vector_literal(items),
        EdnValue::Map(items) => lower_map_literal(items),
        other => Err(CljError::Lower(format!(
            "unsupported expression: {other:?} (only integers, booleans, strings, keywords, symbols, lists, vectors and maps are supported)"
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
    let head = list_head_symbol(items)?;
    let args = &items[1..];
    let special = head
        .namespace
        .as_deref()
        .filter(|ns| *ns == "clojure.core")
        .map(|_| head.name.as_str())
        .unwrap_or(head.name.as_str());
    match special {
        "if" => lower_if(args),
        "when" => lower_when(args),
        "if-let" => lower_if_let(args),
        "when-let" => lower_when_let(args),
        "let" => lower_let(args),
        "cond" => lower_cond(args),
        "case" => lower_case(args),
        "loop" => lower_loop(args),
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
        name => {
            let lowered: Vec<Expr> = args.iter().map(lower_expr).collect::<Result<_, _>>()?;
            if let Some(op) = Builtin::from_name(name) {
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
    if args.len() != 3 {
        return Err(CljError::Lower("if takes: (if cond then else)".into()));
    }
    Ok(Expr::If {
        cond: Box::new(lower_expr(&args[0])?),
        then: Box::new(lower_expr(&args[1])?),
        els: Box::new(lower_expr(&args[2])?),
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
            )))
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
            ))
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
                )))
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
            )))
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
            ))
        }
    };
    if binding_vec.len() % 2 != 0 {
        return Err(CljError::Lower(
            "loop binding vector must have an even number of forms".into(),
        ));
    }
    let mut bindings = Vec::with_capacity(binding_vec.len() / 2);
    let mut it = binding_vec.iter();
    while let (Some(name), Some(val)) = (it.next(), it.next()) {
        bindings.push((sym_name(name, "loop binding name")?, lower_expr(val)?));
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
    Ok(Expr::Loop { bindings, body })
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
            ))
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
                )))
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
                )))
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
                )))
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
        body: vec![dispatch_body],
    };

    // next: nested if over node ids → successor id (static / if-edge); default -1.
    let mut next_body = Expr::Int(-1);
    for (i, (kw, _)) in node_order.iter().enumerate().rev() {
        let target_expr = match edges.get(&EdnValue::Keyword(kotoba_edn::Keyword::bare(kw.clone()))) {
            None => Expr::Int(-1), // no outgoing edge → terminate
            Some(EdnValue::Keyword(t)) => Expr::Int(resolve_id(t.name())?),
            Some(EdnValue::List(parts)) => lower_if_edge(parts, &resolve_id, &state)?,
            Some(other) => {
                return Err(CljError::Lower(format!(
                    "defgraph edge for `:{kw}` must be a target keyword or (if-edge …), found {other:?}"
                )))
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
        body: vec![next_body],
    };

    // runner: loop [__nid entry __s state] — dispatch then advance until -1.
    let runner = Function {
        name: name.clone(),
        export_name: Some(name.clone()),
        params: vec!["state".into()],
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
            )))
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
        | Builtin::Pos
        | Builtin::Neg
        | Builtin::StrLen => n == 1,
        Builtin::BytesAlloc | Builtin::BytesLen | Builtin::BytesFinish => n == 1,
        Builtin::Alloc | Builtin::Load64 | Builtin::Load32 => n == 1,
        Builtin::Store64 | Builtin::Store32 | Builtin::HasCapability | Builtin::LlmInfer => n == 2,
        Builtin::Sub => n >= 1, // unary negate or n-ary subtract
        Builtin::Add | Builtin::Mul | Builtin::And | Builtin::Or => n >= 1,
        Builtin::Div | Builtin::Mod | Builtin::ByteAt | Builtin::ByteAppend => n == 2,
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
