//! Lowering from the EDN reader (`kotoba_edn::EdnValue`) into a typed AST for
//! the i64 Clojure subset this compiler supports.
//!
//! Subset (everything is a 64-bit signed integer; booleans are 1/0):
//!   top-level   `(def name <const-expr>)`     compile-time integer constant
//!               `(defn name [a b …] body…)`   exported wasm function
//!               `(ns …)`                        ignored (namespace decl)
//!   expressions integer literal, `true`/`false`, symbol
//!               `(if c t e)`  `(when c body…)`
//!               `(let [b v …] body…)`  `(do e…)`
//!               builtins: + - * / mod  = < > <= >=  and or not
//!               `(f args…)`  call a user `defn`

use kotoba_edn::{EdnValue, Symbol};

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

/// `(defn name [params…] body…)` — becomes an exported wasm function.
#[derive(Debug, Clone)]
pub struct Function {
    pub name: String,
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
    Eq,
    Lt,
    Gt,
    Le,
    Ge,
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
}

impl Builtin {
    /// If this builtin is a host-import call, the `(interface, function)` it
    /// lowers to in the `kotoba:kais` world. Used to emit the wasm import
    /// section and bind it through the Component Model.
    pub fn host_import(self) -> Option<HostImport> {
        match self {
            Builtin::HasCapability => Some(HostImport::HasCapability),
            Builtin::LlmInfer => Some(HostImport::LlmInfer),
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
}

impl HostImport {
    /// The wasm import `(module, field)` the Component encoder matches against
    /// the WIT world's interface import.
    pub fn module_field(self) -> (&'static str, &'static str) {
        match self {
            HostImport::HasCapability => ("kotoba:kais/auth@0.1.0", "has-capability"),
            HostImport::LlmInfer => ("kotoba:kais/llm@0.1.0", "infer"),
        }
    }
}

impl Builtin {
    fn from_name(s: &str) -> Option<Builtin> {
        Some(match s {
            "+" => Builtin::Add,
            "-" => Builtin::Sub,
            "*" => Builtin::Mul,
            "/" => Builtin::Div,
            "mod" | "rem" => Builtin::Mod,
            "=" => Builtin::Eq,
            "<" => Builtin::Lt,
            ">" => Builtin::Gt,
            "<=" => Builtin::Le,
            ">=" => Builtin::Ge,
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
            "ns" => { /* namespace declaration — accepted and ignored */ }
            "def" => defs.push(lower_def(items)?),
            "defn" => functions.push(lower_defn(items)?),
            "defgraph" => functions.extend(lower_defgraph(items)?),
            other => {
                return Err(CljError::Lower(format!(
                    "unsupported top-level form `({other} …)` — expected def/defn/ns/defgraph"
                )))
            }
        }
    }

    Ok(Program { defs, functions })
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
    // (def name value)
    if items.len() != 3 {
        return Err(CljError::Lower("def takes exactly: (def name value)".into()));
    }
    let name = sym_name(&items[1], "def name")?;
    let value = lower_expr(&items[2])?;
    Ok(Def { name, value })
}

fn lower_defn(items: &[EdnValue]) -> Result<Function, CljError> {
    // (defn name [params…] body…)
    if items.len() < 4 {
        return Err(CljError::Lower(
            "defn requires: (defn name [params…] body…)".into(),
        ));
    }
    let name = sym_name(&items[1], "defn name")?;
    let params = match &items[2] {
        EdnValue::Vector(ps) => ps
            .iter()
            .map(|p| sym_name(p, "defn parameter"))
            .collect::<Result<Vec<_>, _>>()?,
        _ => {
            return Err(CljError::Lower(format!(
                "defn `{name}` parameter list must be a vector `[…]`"
            )))
        }
    };
    let body = items[3..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Function { name, params, body })
}

fn lower_expr(v: &EdnValue) -> Result<Expr, CljError> {
    match v {
        EdnValue::Integer(i) => Ok(Expr::Int(*i)),
        EdnValue::Bool(b) => Ok(Expr::Int(if *b { 1 } else { 0 })),
        EdnValue::String(s) => Ok(Expr::Str(s.clone().into_bytes())),
        EdnValue::Symbol(s) => Ok(Expr::Var(s.to_qualified())),
        EdnValue::List(items) => lower_call(items),
        other => Err(CljError::Lower(format!(
            "unsupported expression: {other:?} (only integers, booleans, symbols and lists are supported)"
        ))),
    }
}

fn lower_call(items: &[EdnValue]) -> Result<Expr, CljError> {
    let head = list_head_symbol(items)?;
    let args = &items[1..];
    match head.name.as_str() {
        "if" => lower_if(args),
        "when" => lower_when(args),
        "let" => lower_let(args),
        "cond" => lower_cond(args),
        "loop" => lower_loop(args),
        "recur" => Ok(Expr::Recur(
            args.iter().map(lower_expr).collect::<Result<_, _>>()?,
        )),
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

fn lower_let(args: &[EdnValue]) -> Result<Expr, CljError> {
    // (let [b v b v …] body…)
    let binding_vec = match args.first() {
        Some(EdnValue::Vector(v)) => v,
        _ => return Err(CljError::Lower("let requires a binding vector: (let [b v …] …)".into())),
    };
    if binding_vec.len() % 2 != 0 {
        return Err(CljError::Lower(
            "let binding vector must have an even number of forms".into(),
        ));
    }
    let mut bindings = Vec::with_capacity(binding_vec.len() / 2);
    let mut it = binding_vec.iter();
    while let (Some(name), Some(val)) = (it.next(), it.next()) {
        bindings.push((sym_name(name, "let binding name")?, lower_expr(val)?));
    }
    let body = args[1..]
        .iter()
        .map(lower_expr)
        .collect::<Result<Vec<_>, _>>()?;
    if body.is_empty() {
        return Err(CljError::Lower("let requires at least one body expression".into()));
    }
    Ok(Expr::Let { bindings, body })
}

/// `(cond t1 e1 t2 e2 … [:else ed])` → right-nested `if`. A `:else` keyword (or
/// literal `true`) test marks the default clause; with no default the value is
/// `0` (nil-ish) when every test fails.
fn lower_cond(args: &[EdnValue]) -> Result<Expr, CljError> {
    if args.len() % 2 != 0 {
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
        _ => return Err(CljError::Lower("loop requires a binding vector: (loop [b v …] …)".into())),
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
        return Err(CljError::Lower("loop requires at least one body expression".into()));
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
        _ => return Err(CljError::Lower("defgraph requires a name: (defgraph name …)".into())),
    };
    let kwargs = &items[2..];
    if kwargs.len() % 2 != 0 {
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
            other => return Err(CljError::Lower(format!("defgraph option key must be a keyword, found {other:?}"))),
        };
        match key.as_str() {
            "entry" => entry = Some(kw_name(v, "defgraph :entry")?),
            "nodes" => nodes = Some(as_map(v, "defgraph :nodes")?),
            "edges" => edges = Some(as_map(v, "defgraph :edges")?),
            "state" => state_decl = Some(as_map(v, "defgraph :state")?),
            other => return Err(CljError::Lower(format!("unknown defgraph option `:{other}`"))),
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
            other => return Err(CljError::Lower(format!("defgraph node `{kw}` must map to a fn symbol, found {other:?}"))),
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
        params: vec!["__nid".into(), "__state".into()],
        body: vec![next_body],
    };

    // runner: loop [__nid entry __s state] — dispatch then advance until -1.
    let runner = Function {
        name: name.clone(),
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
        Some(EdnValue::List(items)) => lower_defn(items),
        _ => Err(CljError::Lower("generated merge fn did not parse as a defn".into())),
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
        other => return Err(CljError::Lower(format!("if-edge predicate must be a fn symbol, found {other:?}"))),
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
        other => Err(CljError::Lower(format!("{ctx} must be a keyword, found {other:?}"))),
    }
}

fn as_map<'a>(
    v: &'a EdnValue,
    ctx: &str,
) -> Result<&'a std::collections::BTreeMap<EdnValue, EdnValue>, CljError> {
    match v {
        EdnValue::Map(m) => Ok(m),
        other => Err(CljError::Lower(format!("{ctx} must be a map `{{…}}`, found {other:?}"))),
    }
}

fn check_builtin_arity(op: Builtin, n: usize) -> Result<(), CljError> {
    let ok = match op {
        Builtin::Not | Builtin::StrLen => n == 1,
        Builtin::BytesAlloc | Builtin::BytesLen | Builtin::BytesFinish => n == 1,
        Builtin::Alloc | Builtin::Load64 | Builtin::Load32 => n == 1,
        Builtin::Store64 | Builtin::Store32 | Builtin::HasCapability | Builtin::LlmInfer => n == 2,
        Builtin::Sub => n >= 1, // unary negate or n-ary subtract
        Builtin::Add | Builtin::Mul | Builtin::And | Builtin::Or => n >= 1,
        Builtin::Div | Builtin::Mod | Builtin::ByteAt | Builtin::ByteAppend => n == 2,
        Builtin::Eq | Builtin::Lt | Builtin::Gt | Builtin::Le | Builtin::Ge => n == 2,
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
        other => Err(CljError::Lower(format!("{ctx} must be a symbol, found {other:?}"))),
    }
}
