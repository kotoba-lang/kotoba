//! Read/write a git object database on disk (loose objects + refs) and
//! import/export it against a [`GitStore`].
//!
//! Loose objects are zlib-compressed framed bytes; refs are plain files plus an
//! optional `packed-refs`. **Packfiles are not yet decoded** — a repo that has
//! had `git gc` / `git repack` will have most objects in `objects/pack/*.pack`;
//! [`import_loose_repo`] reports `packs_present` so callers can `git unpack-objects`
//! first. The on-disk *compression* bytes need not match git's exactly: fidelity
//! is defined over the framed object bytes (hence the oid), not the zlib stream.

use crate::object::GitObject;
use crate::oid::GitOid;
use crate::{GitError, GitStore, RefTarget, Result};
use flate2::read::ZlibDecoder;
use flate2::write::ZlibEncoder;
use flate2::Compression;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

/// Summary of an import run.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ImportReport {
    pub objects: usize,
    pub refs: usize,
    /// True if `objects/pack/*.pack` exist (those objects were NOT imported).
    pub packs_present: bool,
}

fn loose_path(git_dir: &Path, oid: GitOid) -> PathBuf {
    let hex = oid.to_hex();
    git_dir.join("objects").join(&hex[..2]).join(&hex[2..])
}

/// Read and decode a single loose object.
pub fn read_loose_object(git_dir: &Path, oid: GitOid) -> Result<GitObject> {
    let path = loose_path(git_dir, oid);
    let compressed = std::fs::read(&path)?;
    // Bound decompression so a malicious loose object in a cloned repo cannot
    // inflate to gigabytes and exhaust memory (zlib bomb). 1 GiB matches the pack
    // decoder's cap; generous for legit blobs, finite against a bomb.
    const MAX_LOOSE_INFLATE: u64 = 1 << 30;
    let mut decoder = ZlibDecoder::new(&compressed[..]).take(MAX_LOOSE_INFLATE + 1);
    let mut framed = Vec::new();
    decoder.read_to_end(&mut framed)?;
    if framed.len() as u64 > MAX_LOOSE_INFLATE {
        return Err(GitError::MalformedHeader); // decompressed object exceeds cap
    }
    let obj = GitObject::parse_framed(&framed)?;
    // sanity: stored object must hash to the path it lives under
    if obj.oid() != oid {
        return Err(GitError::OidMismatch {
            oid: oid.to_hex(),
            recomputed: obj.oid().to_hex(),
        });
    }
    Ok(obj)
}

/// Write a git object to disk as a loose object. Returns its oid.
pub fn write_loose_object(git_dir: &Path, obj: &GitObject) -> Result<GitOid> {
    let framed = obj.framed();
    let oid = GitOid::of_framed(&framed);
    let path = loose_path(git_dir, oid);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut encoder = ZlibEncoder::new(Vec::new(), Compression::default());
    encoder.write_all(&framed)?;
    let compressed = encoder.finish()?;
    std::fs::write(&path, compressed)?;
    Ok(oid)
}

/// Enumerate all loose object oids under `objects/??/*`.
pub fn iter_loose_oids(git_dir: &Path) -> Result<Vec<GitOid>> {
    let objects = git_dir.join("objects");
    let mut out = Vec::new();
    let Ok(top) = std::fs::read_dir(&objects) else {
        return Ok(out);
    };
    for shard in top.flatten() {
        let name = shard.file_name();
        let Some(prefix) = name.to_str() else { continue };
        // shard dirs are exactly 2 hex chars; skip "pack", "info", etc.
        if prefix.len() != 2 || !prefix.bytes().all(|b| b.is_ascii_hexdigit()) {
            continue;
        }
        let Ok(entries) = std::fs::read_dir(shard.path()) else {
            continue;
        };
        for entry in entries.flatten() {
            let rest = entry.file_name();
            let Some(rest) = rest.to_str() else { continue };
            if rest.len() != 38 {
                continue;
            }
            if let Ok(oid) = GitOid::from_hex(&format!("{prefix}{rest}")) {
                out.push(oid);
            }
        }
    }
    Ok(out)
}

fn packs_present(git_dir: &Path) -> bool {
    let pack_dir = git_dir.join("objects").join("pack");
    std::fs::read_dir(&pack_dir)
        .map(|rd| {
            rd.flatten().any(|e| {
                e.path()
                    .extension()
                    .map(|ext| ext == "pack")
                    .unwrap_or(false)
            })
        })
        .unwrap_or(false)
}

/// Read all refs: `HEAD`, files under `refs/`, and `packed-refs`.
pub fn read_refs(git_dir: &Path) -> Result<Vec<(String, RefTarget)>> {
    let mut out = Vec::new();

    // HEAD (often symbolic)
    let head_path = git_dir.join("HEAD");
    if let Ok(content) = std::fs::read_to_string(&head_path) {
        let content = content.trim();
        if let Some(target) = content.strip_prefix("ref: ") {
            out.push(("HEAD".to_string(), RefTarget::Symbolic(target.to_string())));
        } else if let Ok(oid) = GitOid::from_hex(content) {
            out.push(("HEAD".to_string(), RefTarget::Oid(oid)));
        }
    }

    // loose refs under refs/
    let refs_root = git_dir.join("refs");
    walk_refs(&refs_root, &refs_root, &mut out)?;

    // packed-refs
    if let Ok(content) = std::fs::read_to_string(git_dir.join("packed-refs")) {
        for line in content.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') || line.starts_with('^') {
                continue; // comment or peeled-tag annotation
            }
            if let Some((oid_str, name)) = line.split_once(' ') {
                if let Ok(oid) = GitOid::from_hex(oid_str) {
                    // a loose ref of the same name takes precedence (already pushed)
                    if !out.iter().any(|(n, _)| n == name) {
                        out.push((name.to_string(), RefTarget::Oid(oid)));
                    }
                }
            }
        }
    }

    Ok(out)
}

fn walk_refs(root: &Path, dir: &Path, out: &mut Vec<(String, RefTarget)>) -> Result<()> {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return Ok(());
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            walk_refs(root, &path, out)?;
        } else if let Ok(content) = std::fs::read_to_string(&path) {
            let content = content.trim();
            // ref name relative to git_dir, e.g. "refs/heads/main"
            let rel = path
                .strip_prefix(root.parent().unwrap_or(root))
                .unwrap_or(&path);
            let name = rel.to_string_lossy().replace('\\', "/");
            if let Some(target) = content.strip_prefix("ref: ") {
                out.push((name, RefTarget::Symbolic(target.to_string())));
            } else if let Ok(oid) = GitOid::from_hex(content) {
                out.push((name, RefTarget::Oid(oid)));
            }
        }
    }
    Ok(())
}

/// Import every loose object and ref from `git_dir` into the [`GitStore`].
///
/// Does **not** decode packfiles — see [`import_repo`] for the full importer.
/// `packs_present` flags whether packed objects exist (and were skipped here).
pub async fn import_loose_repo(git_dir: &Path, git: &GitStore<'_>) -> Result<ImportReport> {
    let mut report = ImportReport {
        packs_present: packs_present(git_dir),
        ..Default::default()
    };
    for oid in iter_loose_oids(git_dir)? {
        let obj = read_loose_object(git_dir, oid)?;
        git.put_object(&obj).await?;
        report.objects += 1;
    }
    report.refs += import_refs(git_dir, git).await?;
    Ok(report)
}

/// Import **all** objects (loose + packed) and refs from `git_dir`.
///
/// This is the importer to use on a real repository (cloned / `git gc`'d), where
/// most objects live in `objects/pack/*.pack`. `packs_present` reflects whether
/// any packs were found (and thus decoded). Re-importing is idempotent
/// (`:git/oid` upsert), so loose/packed overlap is harmless.
pub async fn import_repo(git_dir: &Path, git: &GitStore<'_>) -> Result<ImportReport> {
    let mut report = ImportReport::default();

    for oid in iter_loose_oids(git_dir)? {
        let obj = read_loose_object(git_dir, oid)?;
        git.put_object(&obj).await?;
        report.objects += 1;
    }

    let packs = crate::pack::PackSet::open(git_dir)?;
    report.packs_present = !packs.is_empty();
    for oid in packs.oids() {
        if let Some(obj) = packs.get(oid)? {
            git.put_object(&obj).await?;
            report.objects += 1;
        }
    }

    report.refs += import_refs(git_dir, git).await?;
    Ok(report)
}

async fn import_refs(git_dir: &Path, git: &GitStore<'_>) -> Result<usize> {
    let mut n = 0;
    for (name, target) in read_refs(git_dir)? {
        match target {
            RefTarget::Oid(oid) => git.put_ref(&name, oid).await?,
            RefTarget::Symbolic(inner) => git.put_symbolic_ref(&name, &inner).await?,
        }
        n += 1;
    }
    Ok(n)
}

/// Export every projected object as a loose object and write refs to `git_dir`.
/// Verifies each object's SHA-1 on the way out (via [`GitStore::materialize_object`]).
pub async fn export_repo(db: &kotoba_datomic::Db, git: &GitStore<'_>, git_dir: &Path) -> Result<usize> {
    let mut written = 0;
    for (oid, _cid) in crate::all_objects(db) {
        let obj = git.materialize_object(db, oid)?;
        let out_oid = write_loose_object(git_dir, &obj)?;
        debug_assert_eq!(out_oid, oid);
        written += 1;
    }
    for (name, target) in crate::list_refs(db) {
        let path = git_dir.join(&name);
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let line = match target {
            RefTarget::Oid(oid) => format!("{}\n", oid.to_hex()),
            RefTarget::Symbolic(inner) => format!("ref: {inner}\n"),
        };
        std::fs::write(&path, line)?;
    }
    Ok(written)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::object::{GitObjectKind, TreeEntry};
    use kotoba_datomic::Connection;
    use kotoba_store::MemoryBlockStore;
    use std::sync::atomic::{AtomicUsize, Ordering};

    static COUNTER: AtomicUsize = AtomicUsize::new(0);

    struct TempGitDir(PathBuf);
    impl TempGitDir {
        fn new() -> Self {
            let n = COUNTER.fetch_add(1, Ordering::SeqCst);
            let dir = std::env::temp_dir().join(format!(
                "kotoba-git-test-{}-{}",
                std::process::id(),
                n
            ));
            std::fs::create_dir_all(dir.join("objects")).unwrap();
            std::fs::create_dir_all(dir.join("refs").join("heads")).unwrap();
            Self(dir)
        }
        fn path(&self) -> &Path {
            &self.0
        }
    }
    impl Drop for TempGitDir {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn loose_object_disk_roundtrip() {
        let dir = TempGitDir::new();
        let blob = GitObject::blob(b"hello\n".to_vec());
        let oid = write_loose_object(dir.path(), &blob).unwrap();
        assert_eq!(oid.to_hex(), "ce013625030ba8dba906f756967f9e9ca394464a");
        let read = read_loose_object(dir.path(), oid).unwrap();
        assert_eq!(read, blob);
    }

    #[tokio::test]
    async fn import_then_export_is_byte_identical() {
        // Build a small repo on disk (no `git` binary needed).
        let src = TempGitDir::new();
        let blob = GitObject::blob(b"hello\n".to_vec());
        let blob_oid = write_loose_object(src.path(), &blob).unwrap();
        let tree = GitObject::tree(&[TreeEntry {
            mode: b"100644".to_vec(),
            name: b"f.txt".to_vec(),
            oid: blob_oid,
        }]);
        let tree_oid = write_loose_object(src.path(), &tree).unwrap();
        let commit = GitObject::new(
            GitObjectKind::Commit,
            b"tree b4ed918248039b78f24383523fa4e51f80994fac\n\
author t <t@t> 1700000000 +0000\n\
committer t <t@t> 1700000000 +0000\n\
\n\
first\n"
                .to_vec(),
        );
        let commit_oid = write_loose_object(src.path(), &commit).unwrap();
        std::fs::write(
            src.path().join("refs").join("heads").join("main"),
            format!("{}\n", commit_oid.to_hex()),
        )
        .unwrap();
        std::fs::write(src.path().join("HEAD"), "ref: refs/heads/main\n").unwrap();

        // Import into kotoba.
        let conn = Connection::new();
        let store = MemoryBlockStore::new();
        let git = GitStore::new(&conn, &store);
        git.install_schema().await.unwrap();
        let report = import_loose_repo(src.path(), &git).await.unwrap();
        assert_eq!(report.objects, 3);
        assert!(!report.packs_present);
        assert_eq!(crate::resolve_ref(&conn.db(), "HEAD"), Some(commit_oid));

        // Export back out and compare framed bytes object-for-object.
        let dst = TempGitDir::new();
        let written = export_repo(&conn.db(), &git, dst.path()).await.unwrap();
        assert_eq!(written, 3);

        for oid in [blob_oid, tree_oid, commit_oid] {
            let original = read_loose_object(src.path(), oid).unwrap();
            let exported = read_loose_object(dst.path(), oid).unwrap();
            assert_eq!(original, exported, "framed bytes must match for {oid}");
            assert_eq!(exported.oid(), oid);
        }
    }
}
