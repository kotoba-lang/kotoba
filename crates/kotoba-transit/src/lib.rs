//! Transit JSON support for Kotoba's tier-1 Datomic wire.
//!
//! Kotoba keeps EDN/Datomic semantics as the data model and uses Transit JSON as
//! the default HTTP media type for Datomic requests. This crate provides media
//! type constants, deterministic JSON envelope helpers, and EDN value tagging for
//! Kotoba/Datomic values that must survive a JSON hop without losing keyword,
//! symbol, set, or tagged-literal identity.

use kotoba_edn::{EdnValue, Keyword, Symbol};
use serde::Serialize;
use serde_json::{json, Value};

pub const MEDIA_TYPE_JSON: &str = "application/transit+json";
pub const MEDIA_TYPE_MSGPACK: &str = "application/transit+msgpack";

#[derive(Debug, thiserror::Error)]
pub enum TransitError {
    #[error("transit json encode: {0}")]
    Json(#[from] serde_json::Error),
}

pub fn is_transit_json(content_type: &str) -> bool {
    content_type
        .split(';')
        .next()
        .map(str::trim)
        .is_some_and(|mime| mime.eq_ignore_ascii_case(MEDIA_TYPE_JSON))
}

pub fn accept_prefers_transit_json(accept: Option<&str>) -> bool {
    accept
        .unwrap_or_default()
        .split(',')
        .map(|part| part.split(';').next().unwrap_or("").trim())
        .any(|mime| mime.eq_ignore_ascii_case(MEDIA_TYPE_JSON))
}

pub fn to_json_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>, TransitError> {
    Ok(serde_json::to_vec(value)?)
}

pub fn to_json_string<T: Serialize>(value: &T) -> Result<String, TransitError> {
    Ok(serde_json::to_string(value)?)
}

pub fn edn_to_transit_json(value: &EdnValue) -> Value {
    match value {
        EdnValue::Nil => Value::Null,
        EdnValue::Bool(b) => Value::Bool(*b),
        EdnValue::Integer(i) => json!(i),
        EdnValue::BigInt(s) => Value::String(format!("~n{s}")),
        EdnValue::Float(f) => json!(f.0),
        EdnValue::BigDec(s) => Value::String(format!("~f{s}")),
        EdnValue::Char(c) => Value::String(format!("~c{c}")),
        EdnValue::String(s) => Value::String(escape_string(s)),
        EdnValue::Symbol(sym) => Value::String(format!("~${}", symbol_name(sym))),
        EdnValue::Keyword(kw) => Value::String(format!("~:{}", keyword_name(kw))),
        EdnValue::List(xs) => Value::Array(vec![
            Value::String("~#list".to_string()),
            Value::Array(xs.iter().map(edn_to_transit_json).collect()),
        ]),
        EdnValue::Vector(xs) => Value::Array(xs.iter().map(edn_to_transit_json).collect()),
        EdnValue::Map(m) => {
            let entries: Vec<Value> = m
                .iter()
                .map(|(k, v)| Value::Array(vec![edn_to_transit_json(k), edn_to_transit_json(v)]))
                .collect();
            Value::Array(vec![
                Value::String("~#map".to_string()),
                Value::Array(entries),
            ])
        }
        EdnValue::Set(xs) => Value::Array(vec![
            Value::String("~#set".to_string()),
            Value::Array(xs.iter().map(edn_to_transit_json).collect()),
        ]),
        EdnValue::Tagged { tag, value } => Value::Array(vec![
            Value::String(format!("~#{}", symbol_name(tag))),
            edn_to_transit_json(value),
        ]),
    }
}

fn escape_string(s: &str) -> String {
    if s.starts_with('~') {
        format!("~{s}")
    } else {
        s.to_string()
    }
}

fn symbol_name(sym: &Symbol) -> String {
    sym.to_qualified()
}

fn keyword_name(kw: &Keyword) -> String {
    kw.to_qualified()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn media_type_detection_ignores_parameters() {
        assert!(is_transit_json("application/transit+json; charset=utf-8"));
        assert!(accept_prefers_transit_json(Some(
            "application/json, application/transit+json"
        )));
        assert!(!is_transit_json("application/json"));
    }

    #[test]
    fn edn_keywords_symbols_sets_and_tags_are_tagged() {
        let value = EdnValue::vector([
            EdnValue::kw("db", "ident"),
            EdnValue::sym("pull"),
            EdnValue::set([EdnValue::int(1), EdnValue::int(2)]),
            EdnValue::tagged("inst", EdnValue::string("2026-06-30T00:00:00Z")),
        ]);
        assert_eq!(
            edn_to_transit_json(&value),
            json!([
                "~:db/ident",
                "~$pull",
                ["~#set", [1, 2]],
                ["~#inst", "2026-06-30T00:00:00Z"]
            ])
        );
    }

    #[test]
    fn envelope_json_is_deterministic_json_bytes() {
        let body = json!({"graph":"g", "tx_edn":"[[:db/add 1 :name \"a\"]]"});
        assert_eq!(
            to_json_string(&body).unwrap(),
            r#"{"graph":"g","tx_edn":"[[:db/add 1 :name \"a\"]]"}"#
        );
    }
}
