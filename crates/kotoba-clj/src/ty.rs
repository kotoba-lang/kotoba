//! # Literal type checking (`compile_safe_clj` phase S1b, first slice)
//!
//! The scaffold for a typed HIR. The phase-1 value model is **i64-only**: a
//! string/keyword is a packed `(offset << 32) | len` *handle*, not a number.
//! So `(+ "a" 1)` does not error — it silently computes on the handle bits.
//! That is a whole class of bugs the legacy compiler accepts.
//!
//! This pass is the smallest sound slice of static typing: it rejects a
//! **numeric operator applied to a string/keyword literal argument**, where the
//! result is provably meaningless. It works on literals only (an i64-typed
//! variable could legitimately hold a number at runtime), so it never has false
//! positives — the certain core a fuller [`Ty`]-based HIR will subsume.
//!
//! It runs only on safe-clj (`compile_safe_clj`); the legacy [`crate::compile_str`]
//! path keeps its permissive behaviour.

use kotoba_edn::EdnValue;

use crate::CljError;

/// Builtins whose every argument must be a number. A string/keyword literal in
/// any of these positions is a type error.
const NUMERIC_OPS: &[&str] = &[
    "+", "-", "*", "/", "quot", "mod", "rem", "inc", "dec", "abs", "min", "max", "pos?", "neg?",
    "zero?", "even?", "odd?",
];

/// Ordered numeric comparisons. Their operands must be numbers — comparing a
/// string/keyword *handle* as a number is meaningless. (`=` is excluded: handle
/// equality is a separate, more defensible case; use `str-eq?` for strings.)
const NUMERIC_COMPARISON_OPS: &[&str] = &["<", ">", "<=", ">="];

/// Integer division/modulo operators. A literal-zero divisor always traps at
/// run time and is statically rejected.
const DIVISION_OPS: &[&str] = &["/", "mod", "rem", "quot"];

/// Builtins whose **first** argument must be a string. A numeric literal there
/// is a type error (the i64 model would read it as a string handle = garbage
/// offset/len). `byte-at`'s index argument is numeric and not checked here.
const STRING_FIRST_ARG_OPS: &[&str] = &["str-len", "byte-at"];

/// Check every form for a numeric operator applied to a non-numeric literal.
pub fn check_forms(forms: &[EdnValue]) -> Result<(), CljError> {
    for f in forms {
        check(f)?;
    }
    Ok(())
}

fn check(v: &EdnValue) -> Result<(), CljError> {
    match v {
        EdnValue::List(items) => {
            if let Some(EdnValue::Symbol(head)) = items.first() {
                // Inert forms (`quote`/`var`/`comment`) are never executed — do
                // not type-check their contents.
                if crate::ast::is_inert_form(&head.name) {
                    return Ok(());
                }
                if NUMERIC_OPS.contains(&head.name.as_str()) {
                    for arg in &items[1..] {
                        if let Some(desc) = non_numeric_literal(arg) {
                            return Err(CljError::Type(format!(
                                "numeric operator `{}` applied to {desc} — it is not a number. \
                                 safe-clj rejects this: the i64 value model would compute on the \
                                 string/keyword *handle*, silently (S1b literal type check). \
                                 Use a numeric value, or a string operator like `str-len`.",
                                head.name
                            )));
                        }
                    }
                }
                if NUMERIC_COMPARISON_OPS.contains(&head.name.as_str()) {
                    for arg in &items[1..] {
                        if let Some(desc) = non_numeric_literal(arg) {
                            return Err(CljError::Type(format!(
                                "numeric comparison `{}` applied to {desc} — it is not a number. \
                                 safe-clj rejects this: the i64 value model would order the \
                                 string/keyword *handle* as an integer, silently (S1b literal \
                                 type check). Compare numbers, or use `str-eq?` for strings.",
                                head.name
                            )));
                        }
                    }
                }
                if DIVISION_OPS.contains(&head.name.as_str()) {
                    // Any divisor (every argument after the first) that is a
                    // literal zero is a guaranteed trap.
                    for divisor in items.iter().skip(2) {
                        if matches!(divisor, EdnValue::Integer(0)) {
                            return Err(CljError::Type(format!(
                                "`{}` by a literal zero always traps at run time — safe-clj \
                                 rejects it statically (S1b). Guard the divisor, or use a \
                                 non-zero value.",
                                head.name
                            )));
                        }
                    }
                }
                if STRING_FIRST_ARG_OPS.contains(&head.name.as_str()) {
                    if let Some(desc) = items.get(1).and_then(non_numeric_literal_num) {
                        return Err(CljError::Type(format!(
                            "string operator `{}` applied to {desc} as its string argument — \
                             it is not a string. safe-clj rejects this: the i64 value model \
                             would read the number as a string *handle* (garbage offset/len) \
                             (S1b literal type check). Pass a string.",
                            head.name
                        )));
                    }
                }
            }
            for it in items {
                check(it)?;
            }
        }
        EdnValue::Vector(items) => {
            for it in items {
                check(it)?;
            }
        }
        EdnValue::Set(items) => {
            for it in items {
                check(it)?;
            }
        }
        EdnValue::Map(m) => {
            for (k, val) in m {
                check(k)?;
                check(val)?;
            }
        }
        EdnValue::Tagged { value, .. } => check(value)?,
        _ => {}
    }
    Ok(())
}

/// If `v` is a non-numeric literal (string or keyword), a human description of
/// it; otherwise `None` (numbers, bools, nil, and any non-literal pass — they
/// are i64-compatible or not statically known).
fn non_numeric_literal(v: &EdnValue) -> Option<String> {
    match v {
        EdnValue::String(s) => Some(format!("a string literal {s:?}")),
        EdnValue::Keyword(k) => Some(format!("a keyword literal `:{}`", k.0.to_qualified())),
        // Container literals are heap handles, not numbers — arithmetic on them
        // computes on the handle bits, silently.
        EdnValue::Vector(_) => Some("a vector literal".to_string()),
        EdnValue::Map(_) => Some("a map literal".to_string()),
        EdnValue::Set(_) => Some("a set literal".to_string()),
        _ => None,
    }
}

/// If `v` is a numeric literal (the kind that is *not* a valid string), a
/// description; otherwise `None`. Used to type-check string operators.
fn non_numeric_literal_num(v: &EdnValue) -> Option<String> {
    match v {
        EdnValue::Integer(i) => Some(format!("an integer literal `{i}`")),
        EdnValue::Float(f) => Some(format!("a float literal `{f}`")),
        EdnValue::BigInt(s) => Some(format!("an integer literal `{s}`")),
        EdnValue::BigDec(s) => Some(format!("a decimal literal `{s}`")),
        _ => None,
    }
}
