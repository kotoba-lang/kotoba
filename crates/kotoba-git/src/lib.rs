//! # kotoba-git
//!
//! Represent **git** in kotoba in a datomic + CID-based way, with **round-trip
//! fidelity**.
//!
//! Git is already a content-addressed object DAG (blob / tree / commit / tag,
//! each keyed by the SHA-1 of its framed bytes). kotoba is a content-addressed
//! Datalog database (every block keyed by a [`KotobaCid`] = CIDv1 dag-cbor
//! sha2-256). This crate bridges the two:
//!
//! * **Lossless anchor** — every git object's exact framed bytes
//!   (`<type> <size>\0<body>`) are stored as a `KotobaCid` block. Because the
//!   block is content-addressed, the git oid (SHA-1) is always recomputable and
//!   verifiable from the bytes. This is what makes the round-trip byte-exact.
//! * **Datom projection** — each object also becomes a small set of datoms that
//!   record the SHA↔CID bridge (`:git/oid` ↔ `:git.object/cid`) and make the
//!   commit DAG, trees and refs Datalog-queryable.
//!
//! This layering matches ADR-2605312345: the content-addressed blocks are the
//! block backend; the Datom log is the first-class, queryable state over them.
//!
//! ```no_run
//! use kotoba_git::{GitStore, object::GitObject};
//! use kotoba_datomic::Connection;
//! use kotoba_store::MemoryBlockStore;
//!
//! # async fn demo() -> kotoba_git::Result<()> {
//! let conn = Connection::new();
//! let store = MemoryBlockStore::new();
//! let git = GitStore::new(&conn, &store);
//! git.install_schema().await?;
//!
//! let (oid, _cid) = git.put_object(&GitObject::blob(b"hello\n".to_vec())).await?;
//! // round-trip: read the block back and verify SHA-1 == git oid
//! let framed = git.materialize_framed(&conn.db(), oid)?;
//! assert_eq!(framed, b"blob 6\0hello\n");
//! # Ok(()) }
//! ```

pub mod datafy;
pub mod error;
pub mod object;
pub mod oid;
pub mod pack;
pub mod repo;
pub mod schema;

pub use error::{GitError, Result};
pub use object::{GitObject, GitObjectKind, TreeEntry};
pub use oid::GitOid;

use kotoba_core::cid::KotobaCid;
use kotoba_datomic::{Connection, Db};
use kotoba_edn::EdnValue;
use kotoba_store::{put_verified, BlockStore};

/// A direct (`Oid`) or symbolic (`Symbolic`) ref target.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RefTarget {
    Oid(GitOid),
    Symbolic(String),
}

/// Facade pairing a datomic [`Connection`] (the queryable projection) with a
/// [`BlockStore`] (the lossless content-addressed object blocks).
pub struct GitStore<'a> {
    conn: &'a Connection,
    store: &'a dyn BlockStore,
}

impl<'a> GitStore<'a> {
    pub fn new(conn: &'a Connection, store: &'a dyn BlockStore) -> Self {
        Self { conn, store }
    }

    /// Install the `:git/*` schema. Idempotent — safe to call once per process.
    pub async fn install_schema(&self) -> Result<()> {
        self.conn.transact(schema::schema_tx()).await?;
        Ok(())
    }

    /// Store one git object: write its framed bytes as a `KotobaCid` block and
    /// project it into datoms. Returns `(git oid, KotobaCid)` — the SHA↔CID pair.
    pub async fn put_object(&self, obj: &GitObject) -> Result<(GitOid, KotobaCid)> {
        let framed = obj.framed();
        let oid = GitOid::of_framed(&framed);
        let cid = KotobaCid::from_bytes(&framed);
        put_verified(self.store, &cid, &framed).map_err(|e| GitError::Store(e.to_string()))?;
        self.conn
            .transact(datafy::object_tx(obj, oid, &cid))
            .await?;
        Ok((oid, cid))
    }

    /// Record a direct ref (`refs/heads/main` → oid).
    pub async fn put_ref(&self, name: &str, target: GitOid) -> Result<()> {
        self.conn.transact(datafy::ref_tx(name, target)).await?;
        Ok(())
    }

    /// Record a symbolic ref (`HEAD` → `refs/heads/main`).
    pub async fn put_symbolic_ref(&self, name: &str, target_ref: &str) -> Result<()> {
        self.conn
            .transact(datafy::symbolic_ref_tx(name, target_ref))
            .await?;
        Ok(())
    }

    /// The `KotobaCid` of the framed block for `oid`, from the projection.
    pub fn object_cid(&self, db: &Db, oid: GitOid) -> Result<KotobaCid> {
        object_cid(db, oid)
    }

    /// Reconstruct the **framed** git object bytes for `oid` and verify that the
    /// recomputed SHA-1 equals `oid` (the round-trip fidelity check).
    pub fn materialize_framed(&self, db: &Db, oid: GitOid) -> Result<Vec<u8>> {
        let cid = object_cid(db, oid)?;
        let bytes = self
            .store
            .get(&cid)
            .map_err(|e| GitError::Store(e.to_string()))?
            .ok_or_else(|| GitError::BlockMissing(cid.to_multibase()))?;
        let recomputed = GitOid::of_framed(&bytes);
        if recomputed != oid {
            return Err(GitError::OidMismatch {
                oid: oid.to_hex(),
                recomputed: recomputed.to_hex(),
            });
        }
        Ok(bytes.to_vec())
    }

    /// Reconstruct and parse the git object for `oid` (verifies SHA-1).
    pub fn materialize_object(&self, db: &Db, oid: GitOid) -> Result<GitObject> {
        let framed = self.materialize_framed(db, oid)?;
        GitObject::parse_framed(&framed)
    }
}

// --------------------------------------------------------------------------
// Query helpers over the Datom projection (pure `&Db` reads).
// --------------------------------------------------------------------------

fn datom_cid(v: &EdnValue) -> Option<KotobaCid> {
    if let EdnValue::Tagged { tag, value } = v {
        if tag.to_qualified() == "cid" {
            return value.as_string().and_then(KotobaCid::from_multibase);
        }
    }
    None
}

/// Entity holding a given git oid, if present.
fn entity_for_oid(db: &Db, oid: GitOid) -> Option<KotobaCid> {
    let hex = oid.to_hex();
    db.datoms().into_iter().find_map(|d| {
        if d.added && d.a == schema::GIT_OID {
            if let EdnValue::String(s) = &d.v {
                if *s == hex {
                    return Some(d.e);
                }
            }
        }
        None
    })
}

/// All `(attr, value)` for one entity.
fn entity_attrs(db: &Db, entity: &KotobaCid) -> Vec<(String, EdnValue)> {
    db.datoms()
        .into_iter()
        .filter(|d| d.added && &d.e == entity)
        .map(|d| (d.a, d.v))
        .collect()
}

/// The `KotobaCid` of the framed block for `oid`.
pub fn object_cid(db: &Db, oid: GitOid) -> Result<KotobaCid> {
    let entity = entity_for_oid(db, oid).ok_or_else(|| GitError::ObjectNotFound(oid.to_hex()))?;
    entity_attrs(db, &entity)
        .iter()
        .find(|(a, _)| a == schema::OBJECT_CID)
        .and_then(|(_, v)| datom_cid(v))
        .ok_or_else(|| GitError::ObjectNotFound(oid.to_hex()))
}

/// All git oids present in the projection, paired with their `KotobaCid`.
pub fn all_objects(db: &Db) -> Vec<(GitOid, KotobaCid)> {
    let mut out = Vec::new();
    for d in db.datoms() {
        if d.added && d.a == schema::OBJECT_CID {
            if let Some(cid) = datom_cid(&d.v) {
                // find the oid for this entity
                if let Some((_, EdnValue::String(hex))) = entity_attrs(db, &d.e)
                    .into_iter()
                    .find(|(a, _)| a == schema::GIT_OID)
                {
                    if let Ok(oid) = GitOid::from_hex(&hex) {
                        out.push((oid, cid));
                    }
                }
            }
        }
    }
    out
}

/// Ordered parent oids of a commit.
pub fn commit_parents(db: &Db, oid: GitOid) -> Vec<GitOid> {
    let Some(entity) = entity_for_oid(db, oid) else {
        return Vec::new();
    };
    entity_attrs(db, &entity)
        .into_iter()
        .filter(|(a, _)| a == schema::COMMIT_PARENT)
        .filter_map(|(_, v)| match v {
            EdnValue::String(s) => GitOid::from_hex(&s).ok(),
            _ => None,
        })
        .collect()
}

/// Commit-DAG log starting at `head`, following parents (first-parent first),
/// deduplicated, oldest-discovered-last (reverse-chronological-ish preorder).
pub fn log(db: &Db, head: GitOid) -> Vec<GitOid> {
    let mut out = Vec::new();
    let mut seen = std::collections::HashSet::new();
    let mut stack = vec![head];
    while let Some(oid) = stack.pop() {
        if !seen.insert(oid) {
            continue;
        }
        out.push(oid);
        // push parents in reverse so first-parent is visited first
        let mut parents = commit_parents(db, oid);
        parents.reverse();
        stack.extend(parents);
    }
    out
}

/// All refs in the projection.
pub fn list_refs(db: &Db) -> Vec<(String, RefTarget)> {
    let mut out = Vec::new();
    let names: Vec<(KotobaCid, String)> = db
        .datoms()
        .into_iter()
        .filter_map(|d| {
            if d.added && d.a == schema::REF_NAME {
                if let EdnValue::String(s) = d.v {
                    return Some((d.e, s));
                }
            }
            None
        })
        .collect();
    for (entity, name) in names {
        let attrs = entity_attrs(db, &entity);
        if let Some((_, EdnValue::String(target))) =
            attrs.iter().find(|(a, _)| a == schema::REF_TARGET)
        {
            if let Ok(oid) = GitOid::from_hex(target) {
                out.push((name, RefTarget::Oid(oid)));
                continue;
            }
        }
        if let Some((_, EdnValue::String(sym))) =
            attrs.iter().find(|(a, _)| a == schema::REF_SYMBOLIC)
        {
            out.push((name, RefTarget::Symbolic(sym.clone())));
        }
    }
    out
}

/// Resolve a ref name to a git oid, following one level of symbolic indirection.
pub fn resolve_ref(db: &Db, name: &str) -> Option<GitOid> {
    let refs = list_refs(db);
    let target = refs.iter().find(|(n, _)| n == name).map(|(_, t)| t)?;
    match target {
        RefTarget::Oid(oid) => Some(*oid),
        RefTarget::Symbolic(inner) => refs.iter().find(|(n, _)| n == inner).and_then(|(_, t)| {
            if let RefTarget::Oid(oid) = t {
                Some(*oid)
            } else {
                None
            }
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_datomic::q;
    use kotoba_edn::parse;
    use kotoba_store::MemoryBlockStore;

    async fn fixture() -> (Connection, MemoryBlockStore) {
        let conn = Connection::new();
        let store = MemoryBlockStore::new();
        {
            let git = GitStore::new(&conn, &store);
            git.install_schema().await.unwrap();
        }
        (conn, store)
    }

    #[tokio::test]
    async fn blob_roundtrips_through_cid_block() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let blob = GitObject::blob(b"hello\n".to_vec());
        let (oid, cid) = git.put_object(&blob).await.unwrap();
        assert_eq!(oid.to_hex(), "ce013625030ba8dba906f756967f9e9ca394464a");

        let framed = git.materialize_framed(&conn.db(), oid).unwrap();
        assert_eq!(framed, b"blob 6\0hello\n");
        // CID side of the bridge is queryable
        assert_eq!(object_cid(&conn.db(), oid).unwrap(), cid);
        // structured object reconstruction
        let obj = git.materialize_object(&conn.db(), oid).unwrap();
        assert_eq!(obj, blob);
    }

    #[tokio::test]
    async fn full_commit_dag_roundtrips_and_is_queryable() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);

        // blob -> tree -> commit (matches the authoritative fixture vectors)
        let blob = GitObject::blob(b"hello\n".to_vec());
        let (blob_oid, _) = git.put_object(&blob).await.unwrap();

        let tree = GitObject::tree(&[TreeEntry {
            mode: b"100644".to_vec(),
            name: b"f.txt".to_vec(),
            oid: blob_oid,
        }]);
        let (tree_oid, _) = git.put_object(&tree).await.unwrap();
        assert_eq!(tree_oid.to_hex(), "b4ed918248039b78f24383523fa4e51f80994fac");

        let commit_body = b"tree b4ed918248039b78f24383523fa4e51f80994fac\n\
author t <t@t> 1700000000 +0000\n\
committer t <t@t> 1700000000 +0000\n\
\n\
first\n"
            .to_vec();
        let commit = GitObject::new(GitObjectKind::Commit, commit_body);
        let (commit_oid, _) = git.put_object(&commit).await.unwrap();
        assert_eq!(
            commit_oid.to_hex(),
            "ef01bd2630efea35165770fd32ee509f62459ce3"
        );

        git.put_ref("refs/heads/main", commit_oid).await.unwrap();
        git.put_symbolic_ref("HEAD", "refs/heads/main").await.unwrap();

        let db = conn.db();

        // every object round-trips byte-exact
        for (oid, _cid) in all_objects(&db) {
            let framed = git.materialize_framed(&db, oid).unwrap();
            assert_eq!(GitOid::of_framed(&framed), oid);
        }

        // ref resolution + symbolic indirection
        assert_eq!(resolve_ref(&db, "refs/heads/main"), Some(commit_oid));
        assert_eq!(resolve_ref(&db, "HEAD"), Some(commit_oid));

        // commit DAG is queryable
        assert_eq!(log(&db, commit_oid), vec![commit_oid]);
        assert!(commit_parents(&db, commit_oid).is_empty());
        assert_eq!(all_objects(&db).len(), 3);
    }

    #[tokio::test]
    async fn merge_commit_parents_are_projected() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let body = b"tree b4ed918248039b78f24383523fa4e51f80994fac\n\
parent 1111111111111111111111111111111111111111\n\
parent 2222222222222222222222222222222222222222\n\
author t <t@t> 1700000000 +0000\n\
committer t <t@t> 1700000000 +0000\n\
\n\
merge\n"
            .to_vec();
        let commit = GitObject::new(GitObjectKind::Commit, body);
        let (oid, _) = git.put_object(&commit).await.unwrap();
        let parents = commit_parents(&conn.db(), oid);
        assert_eq!(parents.len(), 2);
        // round-trip still byte-exact despite the projection being a set
        let framed = git.materialize_framed(&conn.db(), oid).unwrap();
        assert_eq!(GitObject::parse_framed(&framed).unwrap(), commit);
    }

    #[tokio::test]
    async fn idempotent_reimport_keeps_one_entity() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let blob = GitObject::blob(b"dup\n".to_vec());
        let (oid, _) = git.put_object(&blob).await.unwrap();
        let (oid2, _) = git.put_object(&blob).await.unwrap();
        assert_eq!(oid, oid2);
        // upsert on :git/oid → exactly one object entity
        assert_eq!(all_objects(&conn.db()).len(), 1);
    }

    /// Substantiate the "datomic" promise: query the git projection through the
    /// real `kotoba_datomic::q` Datalog engine, not the typed scan helpers.
    #[tokio::test]
    async fn git_projection_is_datalog_queryable() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);

        let blob = GitObject::blob(b"hello\n".to_vec());
        let (blob_oid, _) = git.put_object(&blob).await.unwrap();
        let tree = GitObject::tree(&[TreeEntry {
            mode: b"100644".to_vec(),
            name: b"f.txt".to_vec(),
            oid: blob_oid,
        }]);
        git.put_object(&tree).await.unwrap();
        let commit = GitObject::new(
            GitObjectKind::Commit,
            b"tree b4ed918248039b78f24383523fa4e51f80994fac\n\
author t <t@t> 1700000000 +0000\n\
committer t <t@t> 1700000000 +0000\n\
\n\
first\n"
                .to_vec(),
        );
        let (commit_oid, _) = git.put_object(&commit).await.unwrap();
        let db = conn.db();

        // (1) all commit oids
        let rows = q(
            parse(
                r#"{:find [?oid]
                    :where [[?e :git.object/kind :commit]
                            [?e :git/oid ?oid]]}"#,
            )
            .unwrap(),
            &db,
            &[],
        )
        .unwrap();
        assert_eq!(
            rows,
            vec![vec![EdnValue::String(commit_oid.to_hex())]],
            "datalog should find exactly the one commit"
        );

        // (2) blobs larger than 3 bytes (predicate over :git.object/size)
        let rows = q(
            parse(
                r#"{:find [?oid]
                    :where [[?e :git.object/kind :blob]
                            [?e :git.object/size ?size]
                            [?e :git/oid ?oid]
                            [(> ?size 3)]]}"#,
            )
            .unwrap(),
            &db,
            &[],
        )
        .unwrap();
        assert_eq!(rows, vec![vec![EdnValue::String(blob_oid.to_hex())]]);

        // (3) join: the tree oid recorded by a given commit (input-bound)
        let rows = q(
            parse(
                r#"{:find [?tree]
                    :in [$ ?coid]
                    :where [[?c :git/oid ?coid]
                            [?c :git.commit/tree ?tree]]}"#,
            )
            .unwrap(),
            &db,
            &[EdnValue::String(commit_oid.to_hex())],
        )
        .unwrap();
        assert_eq!(
            rows,
            vec![vec![EdnValue::String(
                "b4ed918248039b78f24383523fa4e51f80994fac".into()
            )]]
        );
    }

    #[tokio::test]
    async fn annotated_tag_roundtrips_and_is_queryable() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);

        // tag pointing at an arbitrary commit oid
        let target = "ef01bd2630efea35165770fd32ee509f62459ce3";
        let tag = GitObject::new(
            GitObjectKind::Tag,
            format!(
                "object {target}\n\
type commit\n\
tag v1.0\n\
tagger t <t@t> 1700000000 +0000\n\
\n\
release\n"
            )
            .into_bytes(),
        );
        let (tag_oid, _) = git.put_object(&tag).await.unwrap();

        // byte-exact round-trip
        let obj = git.materialize_object(&conn.db(), tag_oid).unwrap();
        assert_eq!(obj, tag);
        assert_eq!(obj.oid(), tag_oid);

        // tag fields are projected + queryable
        let rows = q(
            parse(
                r#"{:find [?name ?obj]
                    :where [[?e :git.object/kind :tag]
                            [?e :git.tag/name ?name]
                            [?e :git.tag/object ?obj]]}"#,
            )
            .unwrap(),
            &conn.db(),
            &[],
        )
        .unwrap();
        assert_eq!(
            rows,
            vec![vec![
                EdnValue::String("v1.0".into()),
                EdnValue::String(target.into())
            ]]
        );
    }
}
