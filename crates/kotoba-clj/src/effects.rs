//! # Effect-soundness checking (`compile_safe_kotoba` phase S3)
//!
//! Theorem **T2 (Effect Soundness)** from `docs/ADR-safe-capability-language.md`
//! §5/§7: if a function declares an effect row `{:effects #{…}}`, then the
//! effects it can actually perform at run time must be **contained in** that
//! declaration. A function that says it is pure must not write the graph.
//!
//! ```text
//! Γ ⊢ e : T ! E      ⇒   observable-effects(e) ⊆ E
//! ```
//!
//! ## Interprocedural: effects propagate through user calls
//!
//! A function's effects are not only the effectful builtins it names *directly*
//! — they include the effects of every user function it (transitively) calls.
//! `(defn run {:effects #{}} [] (helper))` where `helper` writes the graph is
//! **under-declaration**: `run` is not pure. The checker builds the call graph
//! and closes effects to a fixpoint over it (handling mutual recursion), so an
//! effect cannot hide behind a helper.
//!
//! Builtins that perform a host effect (`kqe-assert!`, `llm-infer`, …) are the
//! leaves; the trusted prelude's container accessors are pure, and its `kqe`
//! read accessors wrap values already lifted by a *directly-written* host call,
//! so no effect escapes by routing through the prelude.
//!
//! ## Opt-in, and why that's still sound
//!
//! Effect annotations are optional — an un-annotated function is not checked
//! here (its effects are still capability-gated by [`crate::policy`], so it
//! cannot reach a resource it was not granted). When a function *does* declare
//! `{:effects …}`, this gate enforces it: it rejects **under-declaration**
//! (performing, directly or transitively, an effect the row omits) and
//! **unknown effects** (a typo'd or non-existent effect name). Over-declaration
//! (listing an effect you never perform) is allowed — conservative, not unsound.

use std::collections::{BTreeMap, BTreeSet, HashMap};

use kotoba_edn::EdnValue;

use crate::CljError;

/// The effect vocabulary. One-to-one with the host-induced capability classes.
const KNOWN_EFFECTS: &[&str] = &["graph-read", "graph-write", "infer", "auth"];

/// The effect an effectful builtin induces, or `None` for pure builtins. Kept
/// in sync with `ast::Builtin::host_import` / `policy::CapClass::of`.
fn effect_of_call(name: &str) -> Option<&'static str> {
    Some(match name {
        "kqe-assert!" | "kqe-retract!" => "graph-write",
        "kqe-get-objects" | "kqe-query" => "graph-read",
        "llm-infer" => "infer",
        "has-capability?" => "auth",
        _ => return None,
    })
}

/// A user `defn` form and its name.
struct Defn<'a> {
    name: String,
    items: &'a [EdnValue],
}

/// Infer the **transitive** effect set of every user `defn` in `forms`, closing
/// the call graph to a fixpoint. This is the analysis core behind
/// [`check_forms`]; it ignores `{:effects …}` declarations entirely — it
/// computes what each function *actually* does.
///
/// Exposed so callers can *audit* a cell ("what effects does each function
/// perform?") without writing annotations. The returned set for a function is a
/// subset of `{graph-read, graph-write, infer, auth}`. A function absent from
/// the map (or with an empty set) is pure.
pub fn infer_effects(forms: &[EdnValue]) -> BTreeMap<String, BTreeSet<String>> {
    let mut defns: Vec<Defn> = Vec::new();
    for f in forms {
        collect_defns(f, &mut defns);
    }
    let names: BTreeSet<&str> = defns.iter().map(|d| d.name.as_str()).collect();

    // Per-defn direct effects + the user functions it calls.
    let mut effects: HashMap<&str, BTreeSet<String>> = HashMap::new();
    let mut callees: HashMap<&str, BTreeSet<String>> = HashMap::new();
    for d in &defns {
        let mut eff = BTreeSet::new();
        let mut cal = BTreeSet::new();
        for it in d.items {
            collect(it, &names, &mut eff, &mut cal);
        }
        effects.insert(d.name.as_str(), eff);
        callees.insert(d.name.as_str(), cal);
    }

    // Close effects over the call graph to a fixpoint (mutual recursion safe).
    loop {
        let mut changed = false;
        for d in &defns {
            let name = d.name.as_str();
            let mut acc = effects[name].clone();
            for callee in &callees[name] {
                if let Some(ce) = effects.get(callee.as_str()) {
                    for e in ce {
                        acc.insert(e.clone());
                    }
                }
            }
            if acc.len() != effects[name].len() {
                effects.insert(name, acc);
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }

    effects
        .into_iter()
        .map(|(k, v)| (k.to_string(), v))
        .collect()
}

/// Check every annotated `defn` against the effects it can transitively perform.
pub fn check_forms(forms: &[EdnValue]) -> Result<(), CljError> {
    let inferred = infer_effects(forms);

    let mut defns: Vec<Defn> = Vec::new();
    for f in forms {
        collect_defns(f, &mut defns);
    }

    for d in &defns {
        // Parse + vocabulary-check this defn's effect row (typo guard).
        let Some(declared) = parse_effect_row(d.items)? else {
            continue; // un-annotated → not checked here (still capability-gated)
        };
        let empty = BTreeSet::new();
        let used = inferred.get(&d.name).unwrap_or(&empty);
        let missing: Vec<&str> = used
            .iter()
            .filter(|e| !declared.contains(*e))
            .map(String::as_str)
            .collect();
        if !missing.is_empty() {
            return Err(CljError::Effect(format!(
                "effect soundness: `{}` performs effect(s) {{{}}} not in its declared \
                 `:effects` row {{{}}} — a function may not exceed the effects it \
                 declares, directly or through the functions it calls (T2). Add them \
                 to `:effects` or remove the offending call.",
                d.name,
                missing.join(", "),
                declared.iter().cloned().collect::<Vec<_>>().join(", "),
            )));
        }
    }
    Ok(())
}

/// Recurse, recording each `defn`/`defn-` form.
fn collect_defns<'a>(v: &'a EdnValue, out: &mut Vec<Defn<'a>>) {
    if let EdnValue::List(items) = v {
        if let Some(EdnValue::Symbol(head)) = items.first() {
            // A `(defn …)` inside an inert form (quote/comment) is not a real
            // definition.
            if crate::ast::is_inert_form(&head.name) {
                return;
            }
            if head.name == "defn" || head.name == "defn-" {
                out.push(Defn {
                    name: defn_name(items),
                    items,
                });
            }
        }
        for it in items {
            collect_defns(it, out);
        }
    }
}

/// The validated `:effects` set among a defn form's *direct* children (the
/// metadata attr-map), or `None` if absent. Errors on a non-keyword entry or an
/// unknown effect name (typo guard).
fn parse_effect_row(defn_items: &[EdnValue]) -> Result<Option<BTreeSet<String>>, CljError> {
    let mut found = None;
    for item in defn_items {
        if let EdnValue::Map(m) = item {
            if let Some(val) = m.get(&EdnValue::kw_bare("effects")) {
                let set = match val {
                    EdnValue::Set(s) => s,
                    _ => {
                        return Err(CljError::Effect(
                            "`:effects` must be a set of keywords (e.g. #{:graph-write})".into(),
                        ));
                    }
                };
                let mut declared = BTreeSet::new();
                for e in set {
                    let kw = e.as_keyword().ok_or_else(|| {
                        CljError::Effect("`:effects` entries must be keywords".into())
                    })?;
                    let name = kw.0.name.as_str();
                    if !KNOWN_EFFECTS.contains(&name) {
                        return Err(CljError::Effect(format!(
                            "unknown effect `:{name}` in `:effects` — valid effects are {}. \
                             (typo? see docs/ADR-safe-capability-language.md §5)",
                            vocab()
                        )));
                    }
                    declared.insert(name.to_string());
                }
                found = Some(declared);
            }
        }
    }
    Ok(found)
}

/// Collect, from `v`, the direct host effects and the user-function callees.
fn collect(
    v: &EdnValue,
    user_fns: &BTreeSet<&str>,
    eff: &mut BTreeSet<String>,
    callees: &mut BTreeSet<String>,
) {
    match v {
        EdnValue::List(items) => {
            if let Some(EdnValue::Symbol(head)) = items.first() {
                // Inert forms (quote/var/comment) are never executed — no effects.
                if crate::ast::is_inert_form(&head.name) {
                    return;
                }
                if let Some(e) = effect_of_call(&head.name) {
                    eff.insert(e.to_string());
                }
                if user_fns.contains(head.name.as_str()) {
                    callees.insert(head.name.clone());
                }
            }
            for it in items {
                collect(it, user_fns, eff, callees);
            }
        }
        EdnValue::Vector(items) => items
            .iter()
            .for_each(|it| collect(it, user_fns, eff, callees)),
        EdnValue::Set(items) => items
            .iter()
            .for_each(|it| collect(it, user_fns, eff, callees)),
        EdnValue::Map(m) => m.iter().for_each(|(k, val)| {
            collect(k, user_fns, eff, callees);
            collect(val, user_fns, eff, callees);
        }),
        EdnValue::Tagged { value, .. } => collect(value, user_fns, eff, callees),
        _ => {}
    }
}

/// Best-effort function name for diagnostics (`defn` head's first symbol arg).
fn defn_name(defn_items: &[EdnValue]) -> String {
    defn_items
        .get(1)
        .and_then(EdnValue::as_symbol)
        .map(|s| s.name.clone())
        .unwrap_or_else(|| "<anon>".to_string())
}

fn vocab() -> String {
    KNOWN_EFFECTS
        .iter()
        .map(|e| format!(":{e}"))
        .collect::<Vec<_>>()
        .join(" ")
}
