//! Datom projection schema for git objects.
//!
//! These attributes are the *queryable projection* of the git object DAG. The
//! lossless, byte-exact representation of every object is its content-addressed
//! block in the [`BlockStore`](kotoba_store::BlockStore) (keyed by the
//! [`KotobaCid`](kotoba_core::cid::KotobaCid) of the framed bytes); the datoms
//! index that block and make the commit DAG Datalog-queryable. This mirrors
//! ADR-2605312345 (Datom log = first-class state, blocks = backend).

use kotoba_edn::{EdnValue, Keyword};

// ---- object identity / framing -------------------------------------------
/// 40-hex SHA-1 git oid; `:db.unique/identity` (the SHA side of SHA↔CID).
pub const GIT_OID: &str = ":git/oid";
/// `:blob` / `:tree` / `:commit` / `:tag` (keyword).
pub const OBJECT_KIND: &str = ":git.object/kind";
/// `#cid "b…"` of the framed object bytes (the CID side of SHA↔CID).
pub const OBJECT_CID: &str = ":git.object/cid";
/// Body length in bytes (long).
pub const OBJECT_SIZE: &str = ":git.object/size";

// ---- commit ---------------------------------------------------------------
pub const COMMIT_TREE: &str = ":git.commit/tree";
pub const COMMIT_PARENT: &str = ":git.commit/parent"; // cardinality many
pub const COMMIT_AUTHOR: &str = ":git.commit/author";
pub const COMMIT_COMMITTER: &str = ":git.commit/committer";
pub const COMMIT_MESSAGE: &str = ":git.commit/message";

// ---- tree -----------------------------------------------------------------
/// One per entry, formatted `"<mode> <oid-hex> <name>"`; cardinality many.
pub const TREE_ENTRY: &str = ":git.tree/entry";

// ---- tag ------------------------------------------------------------------
pub const TAG_OBJECT: &str = ":git.tag/object";
pub const TAG_TYPE: &str = ":git.tag/type";
pub const TAG_NAME: &str = ":git.tag/name";
pub const TAG_TAGGER: &str = ":git.tag/tagger";
pub const TAG_MESSAGE: &str = ":git.tag/message";

// ---- refs -----------------------------------------------------------------
/// e.g. `"refs/heads/main"`, `"HEAD"`; `:db.unique/identity`.
pub const REF_NAME: &str = ":git.ref/name";
/// Target git oid (40-hex) for direct refs.
pub const REF_TARGET: &str = ":git.ref/target";
/// Target ref name for symbolic refs (e.g. `HEAD` → `refs/heads/main`).
pub const REF_SYMBOLIC: &str = ":git.ref/symbolic";

const STRING: &str = ":db.type/string";
const KEYWORD: &str = ":db.type/keyword";
const LONG: &str = ":db.type/long";

fn kw(s: &str) -> EdnValue {
    // Constants carry the leading EDN colon (`:db/id`); Keyword::parse expects
    // the bare `ns/name` form, so strip it before parsing.
    EdnValue::Keyword(Keyword::parse(s.strip_prefix(':').unwrap_or(s)))
}

/// Build one schema-attribute entity map.
fn attr(ident: &str, value_type: &str, many: bool, unique_identity: bool) -> EdnValue {
    let mut pairs = vec![
        (kw(":db/ident"), kw(ident)),
        (kw(":db/valueType"), kw(value_type)),
        (
            kw(":db/cardinality"),
            kw(if many {
                ":db.cardinality/many"
            } else {
                ":db.cardinality/one"
            }),
        ),
    ];
    if unique_identity {
        pairs.push((kw(":db/unique"), kw(":db.unique/identity")));
    }
    EdnValue::map(pairs)
}

/// The full git-projection schema, as a single transaction's tx-data vector.
/// Install once per [`Connection`](kotoba_datomic::Connection) before importing.
pub fn schema_tx() -> EdnValue {
    EdnValue::vector(vec![
        attr(GIT_OID, STRING, false, true),
        attr(OBJECT_KIND, KEYWORD, false, false),
        attr(OBJECT_SIZE, LONG, false, false),
        attr(COMMIT_TREE, STRING, false, false),
        attr(COMMIT_PARENT, STRING, true, false),
        attr(COMMIT_AUTHOR, STRING, false, false),
        attr(COMMIT_COMMITTER, STRING, false, false),
        attr(COMMIT_MESSAGE, STRING, false, false),
        attr(TREE_ENTRY, STRING, true, false),
        attr(TAG_OBJECT, STRING, false, false),
        attr(TAG_TYPE, STRING, false, false),
        attr(TAG_NAME, STRING, false, false),
        attr(TAG_TAGGER, STRING, false, false),
        attr(TAG_MESSAGE, STRING, false, false),
        attr(REF_NAME, STRING, false, true),
        attr(REF_TARGET, STRING, false, false),
        attr(REF_SYMBOLIC, STRING, false, false),
    ])
}
