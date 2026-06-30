//! # Safe-subset form gate (`compile_safe_kotoba` phase S1, first slice)
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
                // Inert forms (`quote`/`var`/`comment`) are never executed —
                // don't scan their contents.
                if crate::ast::is_inert_form(&head.name) {
                    return Ok(());
                }
                // Host-interop call syntax (no host interop): `(.method obj)` /
                // the `(. obj …)` member-access form start with `.`; a host
                // constructor `(Class. args)` ends with `.`.
                if head.name.starts_with('.') {
                    return Err(deny(
                        &head.to_qualified(),
                        "host method call / member access",
                    ));
                }
                if head.name.len() > 1 && head.name.ends_with('.') {
                    return Err(deny(&head.to_qualified(), "host constructor"));
                }
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
                    "forbidden `ns` clause `:{}` — {reason}. safe Kotoba denies it \
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
        "forbidden form `({form} …)` — {reason}. safe Kotoba denies it \
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

        // ── no mutable reference types / STM / agents (no shared mutable state) ─
        "atom" => "creates a mutable atom (no shared mutable state)",
        "swap!" => "mutates an atom (no shared mutable state)",
        "swap-vals!" => "mutates an atom (no shared mutable state)",
        "reset!" => "mutates an atom (no shared mutable state)",
        "reset-vals!" => "mutates an atom (no shared mutable state)",
        "compare-and-set!" => "mutates an atom (no shared mutable state)",
        "volatile!" => "creates a mutable volatile (no shared mutable state)",
        "vswap!" => "mutates a volatile (no shared mutable state)",
        "vreset!" => "mutates a volatile (no shared mutable state)",
        "ref" => "creates an STM ref (no shared mutable state)",
        "ref-set" => "mutates an STM ref (no shared mutable state)",
        "alter" => "mutates an STM ref (no shared mutable state)",
        "commute" => "mutates an STM ref (no shared mutable state)",
        "ensure" => "protects an STM ref (no shared mutable state)",
        "dosync" => "opens an STM transaction (no shared mutable state)",
        "agent" => "creates an agent (no shared mutable state)",
        "send" => "dispatches work to an agent (no shared mutable state)",
        "send-off" => "dispatches work to an agent (no shared mutable state)",
        "send-via" => "dispatches work to an agent (no shared mutable state)",
        "add-watch" => "installs a mutation watcher (no shared mutable state)",
        "remove-watch" => "removes a mutation watcher (no shared mutable state)",

        // ── no ambient I/O (I/O must flow through an explicit capability) ───
        "slurp" => "reads a file/URL (ambient I/O — use a capability)",
        "spit" => "writes a file (ambient I/O — use a capability)",
        "print" => "writes to stdout (ambient I/O — use a capability)",
        "println" => "writes to stdout (ambient I/O — use a capability)",
        "pr" => "writes to stdout (ambient I/O — use a capability)",
        "prn" => "writes to stdout (ambient I/O — use a capability)",
        "printf" => "writes to stdout (ambient I/O — use a capability)",
        "print-str" => "renders via the print machinery (ambient I/O)",
        "read-line" => "reads from stdin (ambient I/O — use a capability)",
        "flush" => "flushes an output stream (ambient I/O)",
        "with-out-str" => "captures stdout (ambient I/O)",

        // ── no non-determinism (needs the :random capability) ──────────────
        "rand" => "draws a random number (non-determinism — needs the :random capability)",
        "rand-int" => "draws a random integer (non-determinism — needs the :random capability)",
        "rand-nth" => "picks a random element (non-determinism — needs the :random capability)",
        "shuffle" => "randomly permutes (non-determinism — needs the :random capability)",
        "random-uuid" => "draws a random UUID (non-determinism — needs the :random capability)",

        // ── no ambient concurrency ─────────────────────────────────────────
        "future" => "spawns a concurrent future (no ambient concurrency)",
        "future-call" => "spawns a concurrent future (no ambient concurrency)",
        "promise" => "creates a promise (no ambient concurrency)",
        "deliver" => "delivers a promise (no ambient concurrency)",
        "pmap" => "parallel map (no ambient concurrency)",
        "pcalls" => "parallel calls (no ambient concurrency)",
        "pvalues" => "parallel values (no ambient concurrency)",
        "locking" => "takes a monitor lock (no ambient concurrency)",

        // ── no raw linear-memory access (T1 memory safety) ─────────────────
        // These read/write an *arbitrary* offset in the module's linear memory
        // with no bounds or structure — the one way user safe Kotoba could corrupt
        // its own heap, string handles, or container records (a `store64!` to a
        // bad address silently scribbles over another value). Memory is reached
        // only through the bounds-respecting accessors: `bytes-alloc` /
        // `byte-append!` / `bytes-finish` / `byte-at` / `str-len` and the vector
        // / map prelude. The trusted container/CBOR prelude — exempt from this
        // gate (it runs on user source only) — still builds on these primitives.
        "alloc" => {
            "allocates raw linear memory by offset (no raw memory — use bytes-alloc or a container)"
        }
        "load64" => "reads an arbitrary 64-bit word from linear memory (no raw memory access)",
        "store64!" => "writes an arbitrary 64-bit word to linear memory (no raw memory access)",
        "load32" => "reads an arbitrary 32-bit word from linear memory (no raw memory access)",
        "store32!" => "writes an arbitrary 32-bit word to linear memory (no raw memory access)",

        // ── no reflection / runtime resolution ─────────────────────────────
        "resolve" => "resolves a symbol at runtime (no reflection)",
        "ns-resolve" => "resolves a symbol in a namespace at runtime (no reflection)",
        "find-var" => "looks a var up by name at runtime (no reflection)",
        "gen-class" => "generates a host class (no host interop)",
        "proxy" => "generates a host proxy (no host interop)",
        "reify" => "generates an anonymous host type (no host interop)",
        "new" => "constructs a host object (no host interop)",

        // ── restricted hygienic macro: only the built-in allowlist expands ─
        "defmacro" => "defines a macro (only the built-in macro allowlist may expand)",
        "definline" => "defines an inline macro (only the built-in allowlist may expand)",

        _ => return None,
    })
}
