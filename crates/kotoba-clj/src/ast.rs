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
            other => {
                return Err(CljError::Lower(format!(
                    "unsupported top-level form `({other} …)` — expected def/defn/ns"
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

fn check_builtin_arity(op: Builtin, n: usize) -> Result<(), CljError> {
    let ok = match op {
        Builtin::Not | Builtin::StrLen => n == 1,
        Builtin::Sub => n >= 1, // unary negate or n-ary subtract
        Builtin::Add | Builtin::Mul | Builtin::And | Builtin::Or => n >= 1,
        Builtin::Div | Builtin::Mod | Builtin::ByteAt => n == 2,
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
