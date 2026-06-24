//! dna_integrity — ENGINE-tier enforcement of Actor DNA integrity rulesets.
//!
//! Companion to the actor/client tier in etzhayyim/root `50-infra/actor-dna/` (ADR-2606112000),
//! which validates datoms before a push. This is the engine half: the kotoba `datomic.transact`
//! path validates INCOMING datoms against a graph's registered DNA integrity ruleset BEFORE
//! commit — so a PEER's writes are checked too, not just the well-behaved actor's. That is the
//! Holochain integrity-zome property kotoba previously lacked (it was append-only + CACAO auth,
//! which governs WHO writes, with nothing governing WHAT is written).
//!
//! AUTHORITATIVE server-side: the ruleset is the node's, loaded from config (env
//! `KOTOBA_DNA_RULES` = a directory of `<graph-cid-multibase>.integrity.edn` files), never
//! supplied by the caller. BACKWARD-COMPATIBLE: a graph with no registered ruleset is a no-op
//! (the registry is empty unless the env var is set), so existing graphs are unaffected.
//!
//! The ruleset format is `kotoba-integrity/v0` (the same content-addressed EDN the actor tier
//! emits, so a node and an actor enforce byte-identical rules):
//!   `{:integrity/spec "kotoba-integrity/v0" :integrity/graph "<name>"
//!     :integrity/append-only true :integrity/deny-attrs [:published]
//!     :integrity/closed-attrs [:a/b :c/d]}`

use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

use kotoba_edn::{EdnValue, Keyword};

const SPEC: &str = "kotoba-integrity/v0";

#[derive(Debug, Clone, Default)]
pub struct IntegrityRuleset {
    pub graph: Option<String>,
    pub append_only: bool,
    pub deny_attrs: HashSet<String>,
    pub closed_attrs: Option<HashSet<String>>,
}

impl IntegrityRuleset {
    /// Content-address the *rules* — a stable DNA id so a ruleset can be
    /// published, pinned, and matched across nodes: "same DNA id = same shared
    /// physics = same network" (GROWTH p9, the Holochain DNA-hash property).
    ///
    /// Independent of `graph` (which graph the ruleset is bound to — two graphs
    /// running identical rules share a DNA id) and of attribute insertion order
    /// (the sets are sorted into a canonical form before hashing).
    pub fn dna_id(&self) -> kotoba_core::cid::KotobaCid {
        let mut deny: Vec<&str> = self.deny_attrs.iter().map(String::as_str).collect();
        deny.sort_unstable();
        let closed = self.closed_attrs.as_ref().map(|c| {
            let mut v: Vec<&str> = c.iter().map(String::as_str).collect();
            v.sort_unstable();
            v.join(",")
        });
        let canon = format!(
            "{SPEC}\nappend_only={}\ndeny={}\nclosed={}\n",
            self.append_only,
            deny.join(","),
            closed.as_deref().unwrap_or("<open>"),
        );
        kotoba_core::cid::KotobaCid::from_bytes(canon.as_bytes())
    }
}

/// Render a keyword back to its `:ns/name` (or `:name`) textual form for rule matching.
fn kw_str(k: &Keyword) -> String {
    match &k.0.namespace {
        Some(ns) => format!(":{ns}/{}", k.0.name),
        None => format!(":{}", k.0.name),
    }
}

/// Parse a `{:integrity/...}` ruleset EDN map (the `kotoba-integrity/v0` format).
pub fn parse_ruleset(edn: &str) -> Result<IntegrityRuleset, String> {
    let v = kotoba_edn::parse(edn).map_err(|e| format!("ruleset parse: {e}"))?;
    let m = v.as_map().ok_or("ruleset must be a map")?;
    let get = |ns: &str, name: &str| -> Option<&EdnValue> { m.get(&EdnValue::kw(ns, name)) };

    match get("integrity", "spec").and_then(|x| x.as_string()) {
        Some(SPEC) => {}
        other => {
            return Err(format!(
                "unsupported ruleset spec {other:?} (expected {SPEC:?})"
            ))
        }
    }
    let mut rs = IntegrityRuleset {
        graph: get("integrity", "graph")
            .and_then(|x| x.as_string())
            .map(String::from),
        append_only: get("integrity", "append-only")
            .and_then(|x| x.as_bool())
            .unwrap_or(false),
        ..Default::default()
    };
    if let Some(d) = get("integrity", "deny-attrs").and_then(|x| x.as_vector()) {
        rs.deny_attrs = d
            .iter()
            .filter_map(|x| x.as_keyword())
            .map(kw_str)
            .collect();
    }
    if let Some(c) = get("integrity", "closed-attrs").and_then(|x| x.as_vector()) {
        rs.closed_attrs = Some(
            c.iter()
                .filter_map(|x| x.as_keyword())
                .map(kw_str)
                .collect(),
        );
    }
    Ok(rs)
}

/// Validate a parsed tx (`[[:op e a v] ...]`) against the ruleset. `Err` on the first violation
/// (the engine rejects the whole transact — append-only / closed-vocabulary / forbidden-attr).
pub fn validate_tx(tx: &EdnValue, rs: &IntegrityRuleset) -> Result<(), String> {
    let forms = tx.as_seq().ok_or("tx must be a vector of datom forms")?;
    for (i, form) in forms.iter().enumerate() {
        let d = form
            .as_seq()
            .ok_or_else(|| format!("datom {i} is not a vector"))?;
        if d.len() < 3 {
            return Err(format!("datom {i}: too few elements (need [:op e a v])"));
        }
        let op = d[0].as_keyword().map(kw_str).unwrap_or_default();
        if rs.append_only && op != ":db/add" {
            return Err(format!(
                "datom {i}: op {op} violates :integrity/append-only (only :db/add)"
            ));
        }
        if let Some(attr) = d.get(2).and_then(|x| x.as_keyword()).map(kw_str) {
            if rs.deny_attrs.contains(&attr) {
                return Err(format!(
                    "datom {i}: attribute {attr} is structurally forbidden (:integrity/deny-attrs)"
                ));
            }
            if let Some(closed) = &rs.closed_attrs {
                if !closed.contains(&attr) {
                    return Err(format!("datom {i}: attribute {attr} not in :integrity/closed-attrs (closed vocabulary)"));
                }
            }
        }
    }
    Ok(())
}

/// The node's DNA ruleset registry: graph-cid-multibase → ruleset, loaded ONCE from
/// `KOTOBA_DNA_RULES` (a directory of `<graph-cid-multibase>.integrity.edn`). Empty if unset
/// (→ every graph is a no-op, fully backward-compatible).
static REGISTRY: LazyLock<HashMap<String, IntegrityRuleset>> = LazyLock::new(load_registry);

fn load_registry() -> HashMap<String, IntegrityRuleset> {
    let mut out = HashMap::new();
    let dir = match std::env::var("KOTOBA_DNA_RULES") {
        Ok(d) if !d.is_empty() => d,
        _ => return out,
    };
    let rd = match std::fs::read_dir(&dir) {
        Ok(r) => r,
        Err(_) => return out,
    };
    for entry in rd.flatten() {
        let path = entry.path();
        let Some(fname) = path.file_name().and_then(|s| s.to_str()) else {
            continue;
        };
        let Some(graph) = fname.strip_suffix(".integrity.edn") else {
            continue;
        };
        if let Ok(text) = std::fs::read_to_string(&path) {
            match parse_ruleset(&text) {
                Ok(rs) => {
                    out.insert(graph.to_string(), rs);
                }
                Err(e) => {
                    tracing::warn!(graph, error = %e, "skipping malformed DNA integrity ruleset");
                }
            }
        }
    }
    out
}

/// The registered ruleset for a graph (by its multibase CID), if any.
pub fn ruleset_for(graph_multibase: &str) -> Option<&'static IntegrityRuleset> {
    REGISTRY.get(graph_multibase)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rules() -> IntegrityRuleset {
        parse_ruleset(
            r#"{:integrity/spec "kotoba-integrity/v0" :integrity/graph "ibuki"
                :integrity/append-only true
                :integrity/deny-attrs [:published]
                :integrity/closed-attrs [:joucho/mood :heartbeat/beat]}"#,
        )
        .unwrap()
    }

    #[test]
    fn parse_extracts_all_fields() {
        let rs = rules();
        assert_eq!(rs.graph.as_deref(), Some("ibuki"));
        assert!(rs.append_only);
        assert!(rs.deny_attrs.contains(":published"));
        assert!(rs.closed_attrs.as_ref().unwrap().contains(":joucho/mood"));
    }

    #[test]
    fn dna_id_is_stable_graph_independent_and_order_independent() {
        // same rules, different attr order in the EDN → same DNA id.
        let a = parse_ruleset(
            r#"{:integrity/spec "kotoba-integrity/v0" :integrity/graph "g1"
                :integrity/append-only true
                :integrity/closed-attrs [:b/y :a/x]}"#,
        )
        .unwrap();
        let b = parse_ruleset(
            r#"{:integrity/spec "kotoba-integrity/v0" :integrity/graph "g2"
                :integrity/append-only true
                :integrity/closed-attrs [:a/x :b/y]}"#,
        )
        .unwrap();
        assert_eq!(
            a.dna_id(),
            b.dna_id(),
            "same physics → same DNA id (graph-independent)"
        );
        assert_eq!(a.dna_id(), a.dna_id(), "deterministic");
    }

    #[test]
    fn dna_id_changes_with_the_rules() {
        let base = rules();
        let mut stricter = base.clone();
        stricter.deny_attrs.insert(":secret".into());
        assert_ne!(
            base.dna_id(),
            stricter.dna_id(),
            "an added deny changes the DNA id"
        );

        let mut not_append = base.clone();
        not_append.append_only = false;
        assert_ne!(
            base.dna_id(),
            not_append.dna_id(),
            "append-only flag changes id"
        );

        // open (no closed-attrs) differs from any closed schema.
        let mut open = base.clone();
        open.closed_attrs = None;
        assert_ne!(base.dna_id(), open.dna_id(), "open vs closed schema differ");
    }

    #[test]
    fn parse_rejects_bad_spec() {
        assert!(parse_ruleset(r#"{:integrity/spec "nope"}"#).is_err());
    }

    #[test]
    fn conforming_tx_passes() {
        let tx = kotoba_edn::parse(
            r#"[[:db/add "o1" :joucho/mood :flourishing] [:db/add "o1" :heartbeat/beat 7]]"#,
        )
        .unwrap();
        assert!(validate_tx(&tx, &rules()).is_ok());
    }

    #[test]
    fn append_only_is_enforced() {
        let tx = kotoba_edn::parse(r#"[[:db/retract "o1" :joucho/mood :x]]"#).unwrap();
        let e = validate_tx(&tx, &rules()).unwrap_err();
        assert!(e.contains("append-only"), "{e}");
    }

    #[test]
    fn forbidden_attribute_is_rejected() {
        let tx = kotoba_edn::parse(r#"[[:db/add "o1" :published true]]"#).unwrap();
        let e = validate_tx(&tx, &rules()).unwrap_err();
        assert!(e.contains("structurally forbidden"), "{e}");
    }

    #[test]
    fn closed_vocabulary_rejects_unknown_attr() {
        let tx = kotoba_edn::parse(r#"[[:db/add "o1" :mystery/attr 1]]"#).unwrap();
        let e = validate_tx(&tx, &rules()).unwrap_err();
        assert!(e.contains("closed vocabulary"), "{e}");
    }

    #[test]
    fn empty_registry_is_the_default() {
        // with no KOTOBA_DNA_RULES set in the test env, no graph has a ruleset
        assert!(ruleset_for("bafyreitestnonexistent").is_none());
    }
}
