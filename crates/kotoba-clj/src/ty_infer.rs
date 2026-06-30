//! # Type inference over the AST (`compile_safe_kotoba` phase S1b — typed-HIR core)
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
//! Cross-function inference is included: each user function's return type is
//! closed to a fixpoint over the call graph (keyed by name + arity, so the
//! arity-resolved overloads of a multi-arity `defn` are typed independently and
//! mutual recursion converges), so a `Call`'s result type is the callee's
//! inferred return type rather than `Unknown`. Container literals
//! (vector/map/set) that lowering turns into prelude `Call`s stay `Unknown`
//! unless the prelude function provably returns a concrete type, so the literal
//! check remains complementary.

use std::collections::{HashMap, HashSet};

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

/// Map a user function (keyed by name **and arity**, since multi-arity `defn`s
/// share a name and are resolved by argument count) to its inferred return type.
type RetMap = HashMap<(String, usize), Ty>;

/// Map a user function (name + arity) to the inferred type requirement of each
/// of its parameters, by position. A parameter with no usage constraint, a
/// conflicting one, or one that is shadowed in the body is [`Req::Any`].
type ReqMap = HashMap<(String, usize), Vec<Req>>;

/// Shared inference context threaded through [`infer`].
///
/// `reqs` is `None` while [`infer_return_types`] computes return signatures (no
/// argument checking yet, and the requirement map is not built); `Some` during
/// the final checking pass, which then also enforces parameter requirements at
/// call sites.
struct Ctx<'a> {
    rets: &'a RetMap,
    reqs: Option<&'a ReqMap>,
}

/// Type-check every function in `program`.
///
/// Phases: (1) close every user function's **return type** to a fixpoint over
/// the call graph; (2) infer each function's **parameter requirements**;
/// (3) run the forward checking pass, which reports operation-boundary
/// mismatches *and*, at each call site, arguments that conflict with the
/// callee's parameter requirements. Together these type a call in both
/// directions — its result and its arguments.
pub fn check(program: &Program) -> Result<(), CljError> {
    let rets = infer_return_types(program);
    let reqs = infer_param_reqs(program);
    let ctx = Ctx {
        rets: &rets,
        reqs: Some(&reqs),
    };
    for f in &program.functions {
        let mut env: HashMap<String, Ty> = HashMap::new();
        for p in &f.params {
            env.insert(p.clone(), Ty::Unknown);
        }
        for e in &f.body {
            infer(e, &env, &ctx)?;
        }
    }
    Ok(())
}

/// Close every function's return type to a fixpoint over the call graph.
///
/// **Only `Str` return signatures are propagated across function boundaries.**
/// This is a soundness boundary, not just a conservatism knob: in the i64 value
/// model a string/bytes *handle* is built by arithmetic (`(off << 32) | len`),
/// so a function that constructs and returns a handle types its body as `Num`
/// even though the value is semantically a string. Propagating that `Num` would
/// mis-flag the handle when a caller passes it to a string op — and the trusted
/// container/CBOR prelude does exactly this handle-packing. `Str`, by contrast,
/// arises only from string literals, `bytes-finish`, `llm-infer`, and other
/// `Str`-returning calls — never from arithmetic — so a `Str` return is always a
/// genuine string handle, and flagging arithmetic on it is a real bug. `Num` and
/// `Bytes` returns therefore collapse to `Unknown` (top, permissive) at the
/// boundary; within a function body the full lattice still applies.
///
/// The fixpoint starts from all-`Unknown` and only ever promotes toward `Str`,
/// so it is monotone and converges; the iteration cap is a belt-and-braces
/// guard. Errors hit while typing a body are ignored here (treated as
/// `Unknown`); the checking pass in [`check`] re-runs and reports them.
fn infer_return_types(program: &Program) -> RetMap {
    let mut rets: RetMap = HashMap::new();
    // A monotone height-2 lattice (`Unknown` → `Str`) over N functions needs at
    // most N propagation rounds; `+ 1` lets the final no-change round break.
    for _ in 0..=program.functions.len() {
        // Compute every function's signature against the *start-of-round* map
        // (Jacobi iteration), then apply — so the read-only `ctx` borrow and the
        // mutation of `rets` don't overlap. `reqs: None` ⇒ no argument checking.
        let updates: Vec<((String, usize), Ty)> = {
            let ctx = Ctx {
                rets: &rets,
                reqs: None,
            };
            program
                .functions
                .iter()
                .map(|f| {
                    let mut env: HashMap<String, Ty> = HashMap::new();
                    for p in &f.params {
                        env.insert(p.clone(), Ty::Unknown);
                    }
                    // The return type is the type of the last body expression
                    // (implicit `do`); an empty body or a typing error → Unknown.
                    let mut ret = Ty::Unknown;
                    for e in &f.body {
                        ret = infer(e, &env, &ctx).unwrap_or(Ty::Unknown);
                    }
                    // Collapse everything but `Str` to `Unknown` at the boundary
                    // (only `Str` is a non-arithmetic, genuine handle).
                    let signature = if ret == Ty::Str { Ty::Str } else { Ty::Unknown };
                    ((f.name.clone(), f.params.len()), signature)
                })
                .collect()
        };
        let mut changed = false;
        for (key, signature) in updates {
            if rets.get(&key) != Some(&signature) {
                rets.insert(key, signature);
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    rets
}

/// Infer each function's per-parameter type requirement from how the parameter
/// is used *directly* as a typed builtin argument in the body.
///
/// Soundness against the i64 handle pun (enforced where this map is consulted,
/// in [`infer`]'s `Call` arm): a **literal** argument has an unambiguous type (a
/// string literal is a genuine string, an integer literal a genuine number) and
/// is checked in either direction. A **non-literal** argument is only flagged
/// when it is inferred to be concretely `Str` — a genuine string handle that can
/// never be an arithmetic-built `Num`/`Bytes` handle — passed where a different
/// type is required. Inferred `Num`/`Bytes`/`Unknown` arguments are never
/// constrained, since they may be packed handles.
///
/// A parameter rebound anywhere in the body (shadowed by a `let`/`loop`/`fn`)
/// gets [`Req::Any`] — a conservative whole-parameter opt-out that keeps the
/// single-pass scan sound without per-scope liveness tracking. A parameter used
/// under two different concrete requirements (e.g. both numeric and string) is
/// also [`Req::Any`]: the value is used polymorphically (a deliberate handle
/// pun), so no single requirement is sound.
fn infer_param_reqs(program: &Program) -> ReqMap {
    let mut map = ReqMap::new();
    for f in &program.functions {
        // Parameters rebound anywhere in the body are opted out (see doc).
        let mut shadowed: HashSet<&str> = HashSet::new();
        for e in &f.body {
            collect_bound_names(e, &mut shadowed);
        }
        let live: HashSet<&str> = f
            .params
            .iter()
            .map(|p| p.as_str())
            .filter(|p| !shadowed.contains(p))
            .collect();

        let mut sites: HashMap<&str, Vec<Req>> = HashMap::new();
        for e in &f.body {
            collect_param_reqs(e, &live, &mut sites);
        }

        let reqs: Vec<Req> = f
            .params
            .iter()
            .map(|p| reduce_reqs(sites.get(p.as_str())))
            .collect();

        // Only record functions that actually constrain at least one parameter.
        if reqs.iter().any(|r| !matches!(r, Req::Any)) {
            map.insert((f.name.clone(), f.params.len()), reqs);
        }
    }
    map
}

/// Reduce a parameter's recorded requirement sites to one requirement: a single
/// agreed concrete requirement, else [`Req::Any`].
fn reduce_reqs(sites: Option<&Vec<Req>>) -> Req {
    match sites {
        None => Req::Any,
        Some(v) => {
            let mut it = v.iter().copied();
            match it.next() {
                None => Req::Any,
                Some(first) if it.all(|r| r == first) => first,
                _ => Req::Any,
            }
        }
    }
}

/// Record, for each live parameter used *directly* as a typed builtin argument,
/// the requirement of that position.
fn collect_param_reqs<'a>(
    e: &'a Expr,
    live: &HashSet<&'a str>,
    out: &mut HashMap<&'a str, Vec<Req>>,
) {
    if let Expr::Builtin { op, args } = e {
        for (i, a) in args.iter().enumerate() {
            if let Expr::Var(n) = a {
                if live.contains(n.as_str()) {
                    let r = builtin_arg_req(*op, i);
                    if !matches!(r, Req::Any) {
                        out.entry(n.as_str()).or_default().push(r);
                    }
                }
            }
        }
    }
    for c in child_exprs(e) {
        collect_param_reqs(c, live, out);
    }
}

/// Collect every name a `let`/`loop` binding or `fn` parameter introduces in the
/// subtree — the names that may shadow a function parameter.
fn collect_bound_names<'a>(e: &'a Expr, out: &mut HashSet<&'a str>) {
    match e {
        Expr::Let { bindings, .. } | Expr::Loop { bindings, .. } => {
            for (n, _) in bindings {
                out.insert(n.as_str());
            }
        }
        Expr::Fn { params, .. } => {
            for p in params {
                out.insert(p.as_str());
            }
        }
        _ => {}
    }
    for c in child_exprs(e) {
        collect_bound_names(c, out);
    }
}

/// The unambiguous type of a literal expression, or `None` if `e` is not a
/// literal — used at call sites to check arguments against parameter
/// requirements (see [`infer_param_reqs`]).
fn literal_ty(e: &Expr) -> Option<Ty> {
    match e {
        Expr::Int(_) | Expr::Float(_) => Some(Ty::Num),
        Expr::Str(_) => Some(Ty::Str),
        _ => None,
    }
}

/// Every immediate sub-expression of `e`, for structural recursion.
fn child_exprs(e: &Expr) -> Vec<&Expr> {
    match e {
        Expr::Int(_) | Expr::Float(_) | Expr::Str(_) | Expr::Var(_) | Expr::ClosureRef(_) => vec![],
        Expr::If { cond, then, els } => vec![cond, then, els],
        Expr::Let { bindings, body } | Expr::Loop { bindings, body } => {
            let mut v: Vec<&Expr> = bindings.iter().map(|(_, x)| x).collect();
            v.extend(body.iter());
            v
        }
        Expr::Do(es) | Expr::Recur(es) => es.iter().collect(),
        Expr::Builtin { args, .. } | Expr::Call { args, .. } => args.iter().collect(),
        Expr::Fn { body, .. } => body.iter().collect(),
        Expr::MakeClosure { captures, .. } => captures.iter().collect(),
        Expr::CallValue { f, args } => {
            let mut v = vec![f.as_ref()];
            v.extend(args.iter());
            v
        }
    }
}

/// Infer the type of `e`, checking operation requirements along the way. `env`
/// maps in-scope locals to their inferred types (params/unknowns absent → top);
/// `ctx` carries the function return signatures and (during the checking pass)
/// the parameter requirements enforced at call sites.
fn infer(e: &Expr, env: &HashMap<String, Ty>, ctx: &Ctx) -> Result<Ty, CljError> {
    Ok(match e {
        Expr::Int(_) | Expr::Float(_) => Ty::Num,
        Expr::Str(_) => Ty::Str,
        Expr::Var(x) => env.get(x).copied().unwrap_or(Ty::Unknown),

        Expr::If { cond, then, els } => {
            infer(cond, env, ctx)?;
            let t = infer(then, env, ctx)?;
            let u = infer(els, env, ctx)?;
            if t == u {
                t
            } else {
                Ty::Unknown
            }
        }

        // `let` / `loop` open a fresh scope; bindings are sequential.
        //
        // Note: a `loop` variable's type can *change* across iterations via
        // `recur` (e.g. start numeric, recur with a string). This pass types it
        // from the initial value only — a conservative *false negative* (it may
        // miss a handle-pun that appears only after a `recur`), never a false
        // positive. Catching it soundly needs a per-loop fixpoint over the
        // post-`recur` types; deferred to keep this pass free of false positives
        // on the handle-as-number patterns the prelude relies on.
        Expr::Let { bindings, body } | Expr::Loop { bindings, body } => {
            let mut local = env.clone();
            for (name, val) in bindings {
                let t = infer(val, &local, ctx)?;
                local.insert(name.clone(), t);
            }
            let mut last = Ty::Unknown;
            for b in body {
                last = infer(b, &local, ctx)?;
            }
            last
        }

        Expr::Do(es) => {
            let mut last = Ty::Unknown;
            for x in es {
                last = infer(x, env, ctx)?;
            }
            last
        }

        Expr::Recur(args) => {
            for a in args {
                infer(a, env, ctx)?;
            }
            Ty::Unknown
        }

        Expr::Builtin { op, args } => {
            for (i, a) in args.iter().enumerate() {
                let at = infer(a, env, ctx)?;
                let req = builtin_arg_req(*op, i);
                if !req.accepts(at) {
                    return Err(CljError::Type(format!(
                        "`{}` expects a {} for argument {} but the value there is inferred to be \
                         a {} — safe Kotoba type inference (S1b). The i64 value model would compute \
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

        Expr::Call { name, args } => {
            // Infer (and check) every argument, retaining its type.
            let mut arg_tys = Vec::with_capacity(args.len());
            for a in args {
                arg_tys.push(infer(a, env, ctx)?);
            }
            // During the checking pass, enforce the callee's parameter
            // requirements (built only there, so `reqs` is `Some`).
            if let Some(reqs) = ctx.reqs {
                if let Some(param_reqs) = reqs.get(&(name.clone(), args.len())) {
                    for (i, a) in args.iter().enumerate() {
                        check_arg(name, i, a, arg_tys[i], param_reqs[i])?;
                    }
                }
            }
            // The callee's inferred return type, resolved by name + arity.
            // Unknown (top) if the function is absent or not yet typed.
            ctx.rets
                .get(&(name.clone(), args.len()))
                .copied()
                .unwrap_or(Ty::Unknown)
        }
        Expr::CallValue { f, args } => {
            infer(f, env, ctx)?;
            for a in args {
                infer(a, env, ctx)?;
            }
            Ty::Unknown
        }
        Expr::Fn { body, .. } => {
            for b in body {
                infer(b, env, ctx)?;
            }
            Ty::Unknown
        }
        Expr::MakeClosure { captures, .. } => {
            for c in captures {
                infer(c, env, ctx)?;
            }
            Ty::Unknown
        }
        Expr::ClosureRef(_) => Ty::Unknown,
    })
}

/// Check one call argument against the callee parameter's requirement. The
/// effective type is the literal's unambiguous type when `arg` is a literal
/// (checked in either direction), otherwise the inferred type but **only** when
/// it is concretely `Str` — a genuine string handle that can never be an
/// arithmetic-built `Num`/`Bytes` handle (the i64 handle pun). Inferred
/// `Num`/`Bytes`/`Unknown` arguments are left unconstrained.
fn check_arg(name: &str, idx: usize, arg: &Expr, arg_ty: Ty, req: Req) -> Result<(), CljError> {
    let effective = match literal_ty(arg) {
        Some(t) => Some((t, "literal")),
        None if arg_ty == Ty::Str => Some((Ty::Str, "value")),
        None => None,
    };
    if let Some((t, kind)) = effective {
        if !req.accepts(t) {
            return Err(CljError::Type(format!(
                "function `{name}` requires a {} for argument {} but the call passes a {} {kind} \
                 — safe Kotoba signature inference (S1b). The i64 value model would use its bits as \
                 the wrong kind of value, silently.",
                req.name(),
                idx + 1,
                t.name(),
            )));
        }
    }
    Ok(())
}

/// The type requirement of `op`'s argument at `idx`. Unlisted ops/positions are
/// `Any` (permissive) — only the ops with a hard primitive contract are typed.
fn builtin_arg_req(op: Builtin, idx: usize) -> Req {
    use Builtin::*;
    match op {
        // Arithmetic + ordered comparison + numeric predicates + bitwise →
        // all-number. (The prelude packs handles in codegen, not via these
        // clojure-level bit ops, so requiring numbers here is false-positive
        // free; a bit op on a string handle is exactly the unsafe manual
        // handle-punning that safe Kotoba steers away from.)
        Add | Sub | Mul | Div | Mod | Rem | Inc | Dec | Abs | Min | Max | Lt | Gt | Le | Ge
        | Zero | Pos | Neg | Even | Odd | BitAnd | BitOr | BitXor | BitShiftLeft
        | BitShiftRight | Double | Int | MathRound | MathFloor | MathCeil | MathAbs | MathSqrt => {
            Req::Num
        }

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
        | Alloc | Load64 | Load32 | HasCapability | KqeAssert | KqeRetract | BitAnd | BitOr
        | BitXor | BitShiftLeft | BitShiftRight | Double | Int | MathRound | MathFloor
        | MathCeil | MathAbs | MathSqrt => Ty::Num,
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
        BitAnd => "bit-and",
        BitOr => "bit-or",
        BitXor => "bit-xor",
        BitShiftLeft => "bit-shift-left",
        BitShiftRight => "bit-shift-right",
        Double => "double",
        Int => "int",
        MathRound => "Math/round",
        MathFloor => "Math/floor",
        MathCeil => "Math/ceil",
        MathAbs => "Math/abs",
        MathSqrt => "Math/sqrt",
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
