//! Project a parsed [`GitObject`] into datomic tx-data (a queryable EAVT view).
//!
//! The block store already holds the lossless framed bytes; here we emit the
//! structured datoms that make the commit DAG Datalog-queryable and that record
//! the SHA↔CID bridge (`:git/oid` ↔ `:git.object/cid`).

use crate::object::{GitObject, GitObjectKind};
use crate::oid::GitOid;
use crate::schema;
use kotoba_core::cid::KotobaCid;
use kotoba_edn::{EdnValue, Keyword};

fn kw(s: &str) -> EdnValue {
    // Constants carry the leading EDN colon (`:git/oid`); Keyword::parse expects
    // the bare `ns/name` form, so strip it before parsing.
    EdnValue::Keyword(Keyword::parse(s.strip_prefix(':').unwrap_or(s)))
}

/// Build the single-entity tx-data vector for one git object.
///
/// `oid` is `obj.oid()` (passed in to avoid recomputing) and `cid` is the
/// `KotobaCid` of the framed bytes already written to the block store.
pub fn object_tx(obj: &GitObject, oid: GitOid, cid: &KotobaCid) -> EdnValue {
    let oid_hex = oid.to_hex();
    let mut pairs: Vec<(EdnValue, EdnValue)> = vec![
        // tempid bound to :git/oid (unique-identity) → idempotent upsert
        (kw(":db/id"), EdnValue::string(format!("git-obj:{oid_hex}"))),
        (kw(schema::GIT_OID), EdnValue::string(oid_hex.clone())),
        (
            kw(schema::OBJECT_KIND),
            EdnValue::Keyword(Keyword::bare(obj.kind.as_str())),
        ),
        (
            kw(schema::OBJECT_CID),
            EdnValue::tagged("cid", EdnValue::string(cid.to_multibase())),
        ),
        (
            kw(schema::OBJECT_SIZE),
            EdnValue::int(obj.body.len() as i64),
        ),
    ];

    match obj.kind {
        GitObjectKind::Blob => {}
        GitObjectKind::Commit => {
            if let Some(tree) = obj.header_value("tree") {
                pairs.push((kw(schema::COMMIT_TREE), EdnValue::string(tree)));
            }
            let parents = obj.header_values("parent");
            if !parents.is_empty() {
                pairs.push((
                    kw(schema::COMMIT_PARENT),
                    EdnValue::vector(parents.into_iter().map(EdnValue::string)),
                ));
            }
            if let Some(a) = obj.header_value("author") {
                pairs.push((kw(schema::COMMIT_AUTHOR), EdnValue::string(a)));
            }
            if let Some(c) = obj.header_value("committer") {
                pairs.push((kw(schema::COMMIT_COMMITTER), EdnValue::string(c)));
            }
            let (_h, msg) = obj.split_header_message();
            pairs.push((
                kw(schema::COMMIT_MESSAGE),
                EdnValue::string(String::from_utf8_lossy(msg).into_owned()),
            ));
        }
        GitObjectKind::Tree => {
            if let Ok(entries) = obj.tree_entries() {
                let rows: Vec<EdnValue> = entries
                    .iter()
                    .map(|e| {
                        EdnValue::string(format!(
                            "{} {} {}",
                            String::from_utf8_lossy(&e.mode),
                            e.oid.to_hex(),
                            String::from_utf8_lossy(&e.name)
                        ))
                    })
                    .collect();
                if !rows.is_empty() {
                    pairs.push((kw(schema::TREE_ENTRY), EdnValue::vector(rows)));
                }
            }
        }
        GitObjectKind::Tag => {
            if let Some(o) = obj.header_value("object") {
                pairs.push((kw(schema::TAG_OBJECT), EdnValue::string(o)));
            }
            if let Some(t) = obj.header_value("type") {
                pairs.push((kw(schema::TAG_TYPE), EdnValue::string(t)));
            }
            if let Some(n) = obj.header_value("tag") {
                pairs.push((kw(schema::TAG_NAME), EdnValue::string(n)));
            }
            if let Some(g) = obj.header_value("tagger") {
                pairs.push((kw(schema::TAG_TAGGER), EdnValue::string(g)));
            }
            let (_h, msg) = obj.split_header_message();
            pairs.push((
                kw(schema::TAG_MESSAGE),
                EdnValue::string(String::from_utf8_lossy(msg).into_owned()),
            ));
        }
    }

    EdnValue::vector(vec![EdnValue::map(pairs)])
}

/// Build tx-data for a direct ref (`refs/heads/main` → oid).
pub fn ref_tx(name: &str, target: GitOid) -> EdnValue {
    EdnValue::vector(vec![EdnValue::map(vec![
        (kw(":db/id"), EdnValue::string(format!("git-ref:{name}"))),
        (kw(schema::REF_NAME), EdnValue::string(name.to_string())),
        (kw(schema::REF_TARGET), EdnValue::string(target.to_hex())),
    ])])
}

/// Build tx-data for a symbolic ref (`HEAD` → `refs/heads/main`).
pub fn symbolic_ref_tx(name: &str, target_ref: &str) -> EdnValue {
    EdnValue::vector(vec![EdnValue::map(vec![
        (kw(":db/id"), EdnValue::string(format!("git-ref:{name}"))),
        (kw(schema::REF_NAME), EdnValue::string(name.to_string())),
        (
            kw(schema::REF_SYMBOLIC),
            EdnValue::string(target_ref.to_string()),
        ),
    ])])
}
