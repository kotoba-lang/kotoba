//! # Safe-subset form gate (`compile_safe_clj` phase S1, first slice)
//!
//! Deny-by-default for *language features*, the companion to the
//! [`crate::policy`] gate's deny-by-default for *capabilities*
//! (`docs/ADR-safe-capability-language.md` §6).
//!
//! ## Why a separate gate
//!
//! The legacy [`crate::compile_str`] path **silently ignores** a large set of
//! Clojure forms — `ns`, `require`, `use`, `import`, `set!`, `defmacro`,
//! `gen-class`, … ("macros are accepted but not expanded; ignored where
//! noted"). Silent acceptance is fine for a convenience compiler, but for a
//! *confined* one it is a hole: a program that says `(eval untrusted)` or
//! `(require '[evil.ns])` would compile to a module that simply *drops* those
//! forms — giving the author no signal that the construct is unsupported, and
//! normalising code that, on a real Clojure runtime, would be an arbitrary-code
//! or arbitrary-effect vector.
//!
//! Safe mode turns silent-ignore into explicit rejection. The forbidden set is
//! exactly the constructs the ADR's minimal spec rules out: **no eval / no
//! runtime require / no dynamic var / no reflection / no unrestricted macro**.
//! The built-in macro allowlist the compiler already expands (`->`, `cond`,
//! `case`, threading, …) is unaffected — only *user-defined* `defmacro` is
//! denied.

use kotoba_edn::EdnValue;

use crate::CljError;

/// Check every top-level form (and all nested forms) against the safe subset.
/// `Err(CljError::Subset(..))` names the first forbidden construct found.
///
/// This runs on the *user* source only — the trusted container/CBOR prelude is
/// not subject to the gate.
pub fn check_forms(forms: &[EdnValue]) -> Result<(), CljError> {
    for f in forms {
        check_value(f)?;
    }
    Ok(())
}

/// Recursively walk a form, rejecting any list whose head is a forbidden
/// operator, plus `ns` forms carrying loading/interop clauses.
fn check_value(v: &EdnValue) -> Result<(), CljError> {
    match v {
        EdnValue::List(items) => {
            if let Some(EdnValue::Symbol(head)) = items.first() {
                // Match on the *unqualified* name so `clojure.core/eval` and a
                // bare `eval` are both caught.
                if let Some(reason) = forbidden_op(&head.name) {
                    return Err(deny(&head.to_qualified(), reason));
                }
                if head.name == "ns" {
                    check_ns_clauses(items)?;
                }
            }
            for it in items {
                check_value(it)?;
            }
            Ok(())
        }
        EdnValue::Vector(items) => {
            for it in items {
                check_value(it)?;
            }
            Ok(())
        }
        EdnValue::Set(items) => {
            for it in items {
                check_value(it)?;
            }
            Ok(())
        }
        EdnValue::Map(m) => {
            for (k, val) in m {
                check_value(k)?;
                check_value(val)?;
            }
            Ok(())
        }
        EdnValue::Tagged { value, .. } => check_value(value),
        _ => Ok(()),
    }
}

/// `(ns name (:require …) (:use …) (:import …) …)` — the dangerous clauses are
/// keyword-headed, so they are not caught by [`forbidden_op`]. A bare
/// `(ns foo.bar)` or `(ns foo "doc")` passes; a clause that pulls code or host
/// classes is rejected.
fn check_ns_clauses(ns_items: &[EdnValue]) -> Result<(), CljError> {
    for clause in ns_items.iter().skip(1) {
        let head_kw = match clause {
            EdnValue::List(xs) | EdnValue::Vector(xs) => xs.first().and_then(EdnValue::as_keyword),
            _ => None,
        };
        if let Some(kw) = head_kw {
            if let Some(reason) = forbidden_op(&kw.0.name) {
                return Err(CljError::Subset(format!(
                    "forbidden `ns` clause `:{}` — {reason}. safe-clj denies it \
                     (docs/ADR-safe-capability-language.md §6); a safe module \
                     declares no runtime dependencies or host imports here.",
                    kw.0.name
                )));
            }
        }
    }
    Ok(())
}

fn deny(form: &str, reason: &str) -> CljError {
    CljError::Subset(format!(
        "forbidden form `({form} …)` — {reason}. safe-clj denies it \
         (docs/ADR-safe-capability-language.md §6). Use the safe subset; \
         capabilities are passed as values, not summoned by name.",
    ))
}

/// The denylist. Each entry's rationale ties back to the ADR's minimal spec.
/// Matched on the unqualified symbol/keyword name.
fn forbidden_op(name: &str) -> Option<&'static str> {
    Some(match name {
        // ── no eval / no read-as-code ──────────────────────────────────────
        "eval" => "evaluates code at runtime (no eval)",
        "read" => "reads code/data from a stream at runtime (no eval)",
        "read-string" => "parses code/data from a string at runtime (no eval)",
        "load" => "loads code at runtime (no runtime load)",
        "load-string" => "loads code from a string at runtime (no eval)",
        "load-file" => "loads code from a file at runtime (no runtime load)",
        "load-reader" => "loads code from a reader at runtime (no runtime load)",

        // ── no runtime require / namespace mutation ────────────────────────
        "require" => "loads a namespace at runtime (no runtime require)",
        "use" => "loads + refers a namespace at runtime (no runtime require)",
        "import" => "imports a host class (no host interop)",
        "in-ns" => "switches namespace at runtime",
        "refer" => "refers a namespace at runtime",
        "alias" => "aliases a namespace at runtime",
        "create-ns" => "creates a namespace at runtime",
        "remove-ns" => "removes a namespace at runtime",

        // ── no dynamic var / global mutation ───────────────────────────────
        "set!" => "mutates a var or field in place (no dynamic global mutation)",
        "binding" => "dynamically rebinds vars (no dynamic var)",
        "with-redefs" => "dynamically redefines vars (no dynamic var)",
        "alter-var-root" => "mutates a var root (no dynamic global mutation)",
        "intern" => "interns a var at runtime (no dynamic global mutation)",

        // ── no reflection / runtime resolution ─────────────────────────────
        "resolve" => "resolves a symbol at runtime (no reflection)",
        "ns-resolve" => "resolves a symbol in a namespace at runtime (no reflection)",
        "find-var" => "looks a var up by name at runtime (no reflection)",
        "gen-class" => "generates a host class (no host interop)",
        "proxy" => "generates a host proxy (no host interop)",
        "reify" => "generates an anonymous host type (no host interop)",

        // ── restricted hygienic macro: only the built-in allowlist expands ─
        "defmacro" => "defines a macro (only the built-in macro allowlist may expand)",
        "definline" => "defines an inline macro (only the built-in allowlist may expand)",

        _ => return None,
    })
}
