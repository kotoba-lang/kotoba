//! # Type inference over the AST (`compile_safe_clj` phase S1b — typed-HIR core)
//!
//! The literal type check ([`crate::ty`]) is leaf-level: it catches a bad
//! *literal* in an operation. This pass is the first real slice of a typed HIR
//! — a **forward type inference** over the lowered AST that propagates types
//! through `let` bindings and operation results, so a mismatch on a *variable*
//! is caught too:
//!
//! ```clojure
//! (let [s "x"] (+ s 1))   ; s : Str, used in `+` → type error
//! (let [n 5]   (str-len n)) ; n : Num, used in `str-len` → type error
//! ```
//!
//! ## Lattice and soundness
//!
//! Types are `Num` (integers/floats and the i64 results of arithmetic,
//! comparison, and logic), `Str` (string handles), `Bytes` (mutable byte
//! buffers), and `Unknown`. Function parameters, `def` constants, container
//! handles, and user-function results are `Unknown` — and **`Unknown` is
//! permissive** (it satisfies every requirement), so the pass never produces a
//! false positive: it errors only when a *statically-known* `Str`/`Bytes`/`Num`
//! value flows into an operation that cannot accept it.
//!
//! Cross-function inference (typing `Call` results from callee signatures) is a
//! later slice; `Call` is `Unknown` here. This pass and the literal check are
//! complementary — the literal check still covers container literals
//! (vector/map/set) that lowering turns into `Call`s.

use std::collections::HashMap;

use crate::ast::{Builtin, Expr, Program};
use crate::CljError;

/// A coarse value type. `Unknown` is the top element (satisfies any requirement).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Ty {
    Num,
    Str,
    Bytes,
    Unknown,
}

impl Ty {
    fn name(self) -> &'static str {
        match self {
            Ty::Num => "number",
            Ty::Str => "string",
            Ty::Bytes => "byte-buffer",
            Ty::Unknown => "unknown",
        }
    }
}

/// What an operation requires of an argument position.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Req {
    Num,
    Str,
    Bytes,
    Any,
}

impl Req {
    /// Does an inferred type satisfy this requirement? `Unknown` always does.
    fn accepts(self, t: Ty) -> bool {
        matches!(
            (self, t),
            (_, Ty::Unknown)
                | (Req::Any, _)
                | (Req::Num, Ty::Num)
                | (Req::Str, Ty::Str)
                | (Req::Bytes, Ty::Bytes)
        )
    }
    fn name(self) -> &'static str {
        match self {
            Req::Num => "number",
            Req::Str => "string",
            Req::Bytes => "byte-buffer",
            Req::Any => "any",
        }
    }
}

/// Type-check every function in `program`.
pub fn check(program: &Program) -> Result<(), CljError> {
    for f in &program.functions {
        let mut env: HashMap<String, Ty> = HashMap::new();
        for p in &f.params {
            env.insert(p.clone(), Ty::Unknown);
        }
        for e in &f.body {
            infer(e, &env)?;
        }
    }
    Ok(())
}

/// Infer the type of `e`, checking operation requirements along the way. `env`
/// maps in-scope locals to their inferred types (params/unknowns absent → top).
fn infer(e: &Expr, env: &HashMap<String, Ty>) -> Result<Ty, CljError> {
    Ok(match e {
        Expr::Int(_) | Expr::Float(_) => Ty::Num,
        Expr::Str(_) => Ty::Str,
        Expr::Var(x) => env.get(x).copied().unwrap_or(Ty::Unknown),

        Expr::If { cond, then, els } => {
            infer(cond, env)?;
            let t = infer(then, env)?;
            let u = infer(els, env)?;
            if t == u {
                t
            } else {
                Ty::Unknown
            }
        }

        // `let` / `loop` open a fresh scope; bindings are sequential.
        Expr::Let { bindings, body } | Expr::Loop { bindings, body } => {
            let mut local = env.clone();
            for (name, val) in bindings {
                let t = infer(val, &local)?;
                local.insert(name.clone(), t);
            }
            let mut last = Ty::Unknown;
            for b in body {
                last = infer(b, &local)?;
            }
            last
        }

        Expr::Do(es) => {
            let mut last = Ty::Unknown;
            for x in es {
                last = infer(x, env)?;
            }
            last
        }

        Expr::Recur(args) => {
            for a in args {
                infer(a, env)?;
            }
            Ty::Unknown
        }

        Expr::Builtin { op, args } => {
            for (i, a) in args.iter().enumerate() {
                let at = infer(a, env)?;
                let req = builtin_arg_req(*op, i);
                if !req.accepts(at) {
                    return Err(CljError::Type(format!(
                        "`{}` expects a {} for argument {} but the value there is inferred to be \
                         a {} — safe-clj type inference (S1b). The i64 value model would compute \
                         on the handle bits, silently.",
                        builtin_name(*op),
                        req.name(),
                        i + 1,
                        at.name(),
                    )));
                }
            }
            builtin_result(*op)
        }

        Expr::Call { args, .. } => {
            for a in args {
                infer(a, env)?;
            }
            Ty::Unknown // cross-function result inference is a later slice
        }
        Expr::CallValue { f, args } => {
            infer(f, env)?;
            for a in args {
                infer(a, env)?;
            }
            Ty::Unknown
        }
        Expr::Fn { body, .. } => {
            for b in body {
                infer(b, env)?;
            }
            Ty::Unknown
        }
        Expr::MakeClosure { captures, .. } => {
            for c in captures {
                infer(c, env)?;
            }
            Ty::Unknown
        }
        Expr::ClosureRef(_) => Ty::Unknown,
    })
}

/// The type requirement of `op`'s argument at `idx`. Unlisted ops/positions are
/// `Any` (permissive) — only the ops with a hard primitive contract are typed.
fn builtin_arg_req(op: Builtin, idx: usize) -> Req {
    use Builtin::*;
    match op {
        // Arithmetic + ordered comparison + numeric predicates → all-number.
        Add | Sub | Mul | Div | Mod | Rem | Inc | Dec | Abs | Min | Max | Lt | Gt | Le | Ge
        | Zero | Pos | Neg | Even | Odd => Req::Num,

        StrLen => Req::Str,
        ByteAt => {
            if idx == 0 {
                Req::Str
            } else {
                Req::Num
            }
        }
        BytesAlloc => Req::Num,
        ByteAppend => {
            if idx == 0 {
                Req::Bytes
            } else {
                Req::Num
            }
        }
        BytesLen | BytesFinish => Req::Bytes,
        Alloc | Load64 | Load32 => Req::Num,
        Store64 | Store32 => {
            if idx == 0 {
                Req::Num
            } else {
                Req::Any
            }
        }
        // String-handle host imports take string args.
        HasCapability | LlmInfer => Req::Str,
        KqeAssert | KqeRetract | KqeGetObjects | KqeQuery => Req::Str,

        // Equality, logic, nil-checks, and anything else: no constraint.
        _ => Req::Any,
    }
}

/// The result type of `op`. Unlisted ops are `Unknown`.
fn builtin_result(op: Builtin) -> Ty {
    use Builtin::*;
    match op {
        Add | Sub | Mul | Div | Mod | Rem | Inc | Dec | Abs | Min | Max | Lt | Gt | Le | Ge
        | Zero | Pos | Neg | Even | Odd | Some | Not | Eq | NotEq | StrLen | ByteAt | BytesLen
        | Alloc | Load64 | Load32 | HasCapability | KqeAssert | KqeRetract => Ty::Num,
        BytesAlloc | ByteAppend => Ty::Bytes,
        BytesFinish | LlmInfer => Ty::Str,
        _ => Ty::Unknown,
    }
}

/// A human name for `op` in diagnostics.
fn builtin_name(op: Builtin) -> &'static str {
    use Builtin::*;
    match op {
        Add => "+",
        Sub => "-",
        Mul => "*",
        Div => "/",
        Mod => "mod",
        Rem => "rem",
        Inc => "inc",
        Dec => "dec",
        Abs => "abs",
        Min => "min",
        Max => "max",
        Lt => "<",
        Gt => ">",
        Le => "<=",
        Ge => ">=",
        Zero => "zero?",
        Pos => "pos?",
        Neg => "neg?",
        Even => "even?",
        Odd => "odd?",
        StrLen => "str-len",
        ByteAt => "byte-at",
        BytesAlloc => "bytes-alloc",
        ByteAppend => "byte-append!",
        BytesLen => "bytes-len",
        BytesFinish => "bytes-finish",
        Alloc => "alloc",
        Load64 => "load64",
        Load32 => "load32",
        Store64 => "store64!",
        Store32 => "store32!",
        HasCapability => "has-capability?",
        LlmInfer => "llm-infer",
        KqeAssert => "kqe-assert!",
        KqeRetract => "kqe-retract!",
        KqeGetObjects => "kqe-get-objects",
        KqeQuery => "kqe-query",
        _ => "operator",
    }
}
