use ordered_float::OrderedFloat;
use std::collections::{BTreeMap, BTreeSet};

/// A namespaced symbol. `namespace` is `None` for bare symbols.
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Symbol {
    pub namespace: Option<String>,
    pub name: String,
}

impl Symbol {
    pub fn bare<S: Into<String>>(name: S) -> Self {
        Self {
            namespace: None,
            name: name.into(),
        }
    }
    pub fn namespaced<N: Into<String>, S: Into<String>>(ns: N, name: S) -> Self {
        Self {
            namespace: Some(ns.into()),
            name: name.into(),
        }
    }
    /// Parse a `ns/name` or `name` string into a Symbol.
    pub fn parse(s: &str) -> Self {
        match s.find('/') {
            Some(i) if i > 0 && i < s.len() - 1 => Self {
                namespace: Some(s[..i].to_string()),
                name: s[i + 1..].to_string(),
            },
            _ => Self::bare(s),
        }
    }
    pub fn to_qualified(&self) -> String {
        match &self.namespace {
            Some(ns) => format!("{}/{}", ns, self.name),
            None => self.name.clone(),
        }
    }
}

/// A namespaced keyword (`:ns/name` or `:name`).
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Keyword(pub Symbol);

impl Keyword {
    pub fn bare<S: Into<String>>(name: S) -> Self {
        Self(Symbol::bare(name))
    }
    pub fn namespaced<N: Into<String>, S: Into<String>>(ns: N, name: S) -> Self {
        Self(Symbol::namespaced(ns, name))
    }
    pub fn parse(s: &str) -> Self {
        Self(Symbol::parse(s))
    }
    pub fn to_qualified(&self) -> String {
        self.0.to_qualified()
    }
    pub fn namespace(&self) -> Option<&str> {
        self.0.namespace.as_deref()
    }
    pub fn name(&self) -> &str {
        &self.0.name
    }
}

/// EDN values. `Map` and `Set` use ordered collections so equality and CID
/// hashing are deterministic regardless of insertion order.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub enum EdnValue {
    Nil,
    Bool(bool),
    Integer(i64),
    /// Arbitrary-precision integer (decimal string with optional leading `-` and
    /// trailing `N`). Preserved verbatim — interop layers convert as needed.
    BigInt(String),
    Float(OrderedFloat<f64>),
    /// Arbitrary-precision decimal (string with trailing `M`).
    BigDec(String),
    Char(char),
    String(String),
    Symbol(Symbol),
    Keyword(Keyword),
    List(Vec<EdnValue>),
    Vector(Vec<EdnValue>),
    Map(BTreeMap<EdnValue, EdnValue>),
    Set(BTreeSet<EdnValue>),
    /// `#tag value` — tag is a Symbol.
    Tagged {
        tag: Symbol,
        value: Box<EdnValue>,
    },
}

impl EdnValue {
    pub fn kw<N: Into<String>, S: Into<String>>(ns: N, name: S) -> Self {
        Self::Keyword(Keyword::namespaced(ns, name))
    }
    pub fn kw_bare<S: Into<String>>(name: S) -> Self {
        Self::Keyword(Keyword::bare(name))
    }
    pub fn sym<S: Into<String>>(name: S) -> Self {
        Self::Symbol(Symbol::bare(name))
    }
    pub fn string<S: Into<String>>(s: S) -> Self {
        Self::String(s.into())
    }
    pub fn int(i: i64) -> Self {
        Self::Integer(i)
    }
    pub fn float(f: f64) -> Self {
        Self::Float(OrderedFloat(f))
    }
    pub fn nil() -> Self {
        Self::Nil
    }
    pub fn bool(b: bool) -> Self {
        Self::Bool(b)
    }
    pub fn vector<I: IntoIterator<Item = EdnValue>>(items: I) -> Self {
        Self::Vector(items.into_iter().collect())
    }
    pub fn list<I: IntoIterator<Item = EdnValue>>(items: I) -> Self {
        Self::List(items.into_iter().collect())
    }
    pub fn map<I: IntoIterator<Item = (EdnValue, EdnValue)>>(items: I) -> Self {
        Self::Map(items.into_iter().collect())
    }
    pub fn set<I: IntoIterator<Item = EdnValue>>(items: I) -> Self {
        Self::Set(items.into_iter().collect())
    }
    pub fn tagged<S: Into<String>>(tag: S, value: EdnValue) -> Self {
        Self::Tagged {
            tag: Symbol::parse(&tag.into()),
            value: Box::new(value),
        }
    }

    pub fn as_keyword(&self) -> Option<&Keyword> {
        if let Self::Keyword(k) = self {
            Some(k)
        } else {
            None
        }
    }
    pub fn as_symbol(&self) -> Option<&Symbol> {
        if let Self::Symbol(s) = self {
            Some(s)
        } else {
            None
        }
    }
    pub fn as_string(&self) -> Option<&str> {
        if let Self::String(s) = self {
            Some(s.as_str())
        } else {
            None
        }
    }
    pub fn as_integer(&self) -> Option<i64> {
        if let Self::Integer(i) = self {
            Some(*i)
        } else {
            None
        }
    }
    pub fn as_float(&self) -> Option<f64> {
        if let Self::Float(f) = self {
            Some(f.0)
        } else {
            None
        }
    }
    pub fn as_bool(&self) -> Option<bool> {
        if let Self::Bool(b) = self {
            Some(*b)
        } else {
            None
        }
    }
    pub fn as_vector(&self) -> Option<&[EdnValue]> {
        if let Self::Vector(v) = self {
            Some(v.as_slice())
        } else {
            None
        }
    }
    pub fn as_list(&self) -> Option<&[EdnValue]> {
        if let Self::List(v) = self {
            Some(v.as_slice())
        } else {
            None
        }
    }
    pub fn as_seq(&self) -> Option<&[EdnValue]> {
        match self {
            Self::Vector(v) | Self::List(v) => Some(v.as_slice()),
            _ => None,
        }
    }
    pub fn as_map(&self) -> Option<&BTreeMap<EdnValue, EdnValue>> {
        if let Self::Map(m) = self {
            Some(m)
        } else {
            None
        }
    }
    pub fn as_set(&self) -> Option<&BTreeSet<EdnValue>> {
        if let Self::Set(s) = self {
            Some(s)
        } else {
            None
        }
    }
    pub fn is_nil(&self) -> bool {
        matches!(self, Self::Nil)
    }
}

#[cfg(test)]
mod ord_tests {
    use super::*;
    use ordered_float::OrderedFloat;

    // First-tier `datomic.datoms` ordering (xrpc `datomic_datoms_sort_key`) sorts
    // by `EdnValue`'s derived `Ord`, so its correctness IS this Ord. Lock it:
    // integers compare numerically (no "100" < "20" trap) and types are
    // segregated by variant order (a number never compares against a string).
    // (ADR-2606022150 §D1.1 — first-tier Datomic is canonical without keycodec.)

    #[test]
    fn integers_order_numerically_not_lexicographically() {
        assert!(EdnValue::Integer(20) < EdnValue::Integer(100));
        assert!(EdnValue::Integer(-1) < EdnValue::Integer(0));
        assert!(EdnValue::Integer(-100) < EdnValue::Integer(-20));
        assert!(EdnValue::Integer(i64::MIN) < EdnValue::Integer(i64::MAX));
    }

    #[test]
    fn floats_order_numerically() {
        assert!(EdnValue::Float(OrderedFloat(-1.0)) < EdnValue::Float(OrderedFloat(0.0)));
        assert!(EdnValue::Float(OrderedFloat(20.0)) < EdnValue::Float(OrderedFloat(100.0)));
    }

    #[test]
    fn types_are_segregated_by_variant_order() {
        // Bool < Integer < Float < String (declaration order) — a huge integer
        // never sorts among strings; a bool never collides with a float.
        assert!(EdnValue::Bool(true) < EdnValue::Integer(0));
        assert!(EdnValue::Integer(i64::MAX) < EdnValue::Float(OrderedFloat(f64::NEG_INFINITY)));
        assert!(EdnValue::Float(OrderedFloat(f64::INFINITY)) < EdnValue::String(String::new()));
    }

    #[test]
    fn as_seq_unifies_vector_and_list_others_return_none() {
        // `as_seq` is the one accessor with real branching: it must accept BOTH
        // Vector and List (the "sequence" abstraction) and reject everything else.
        // A regression handling only one variant would break seq-generic callers.
        let v = EdnValue::Vector(vec![EdnValue::Integer(1)]);
        let l = EdnValue::List(vec![EdnValue::Integer(1)]);
        assert_eq!(
            v.as_seq().map(|s| s.len()),
            Some(1),
            "as_seq accepts Vector"
        );
        assert_eq!(l.as_seq().map(|s| s.len()), Some(1), "as_seq accepts List");
        assert!(
            EdnValue::Integer(1).as_seq().is_none(),
            "as_seq rejects a scalar"
        );
        assert!(EdnValue::Bool(true).as_seq().is_none());
    }

    #[test]
    fn typed_accessors_match_their_variant_and_reject_others() {
        // Pins the variant-extraction contract: each accessor returns Some only for
        // its own variant, None otherwise — guarding against a future refactor that
        // mismatches an arm.
        assert_eq!(EdnValue::Integer(7).as_integer(), Some(7));
        assert_eq!(EdnValue::String("x".into()).as_integer(), None);
        assert_eq!(EdnValue::String("hi".into()).as_string(), Some("hi"));
        assert_eq!(EdnValue::Integer(1).as_string(), None);
        assert_eq!(EdnValue::Bool(true).as_bool(), Some(true));
        assert_eq!(
            EdnValue::Integer(0).as_bool(),
            None,
            "integer 0 is not a bool"
        );
        assert_eq!(EdnValue::Float(OrderedFloat(1.5)).as_float(), Some(1.5));
        assert_eq!(
            EdnValue::Integer(2).as_float(),
            None,
            "integer is not a float"
        );
    }
}
