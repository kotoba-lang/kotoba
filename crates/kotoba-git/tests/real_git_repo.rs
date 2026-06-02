//! End-to-end fidelity against a *real* git repository.
//!
//! Builds an actual repo with the `git` CLI (loose objects), imports it into
//! kotoba via [`import_loose_repo`], then materializes every object back and
//! checks that the recomputed SHA-1 matches git's own oid. Skips gracefully if
//! `git` is not on PATH or the repo ends up packed.

use kotoba_datomic::Connection;
use kotoba_git::repo::{import_loose_repo, import_repo, read_refs};
use kotoba_git::{resolve_ref, GitObject, GitOid, GitStore, RefTarget};
use kotoba_store::MemoryBlockStore;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};

static COUNTER: AtomicUsize = AtomicUsize::new(0);

fn git_available() -> bool {
    Command::new("git")
        .arg("--version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

fn run_git(dir: &Path, args: &[&str]) {
    let status = Command::new("git")
        .current_dir(dir)
        .args(args)
        .env("GIT_AUTHOR_DATE", "1700000000 +0000")
        .env("GIT_COMMITTER_DATE", "1700000000 +0000")
        .status()
        .expect("git command runs");
    assert!(status.success(), "git {args:?} failed");
}

fn git_out(dir: &Path, args: &[&str]) -> String {
    let out = Command::new("git")
        .current_dir(dir)
        .args(args)
        .output()
        .expect("git command runs");
    assert!(out.status.success(), "git {args:?} failed");
    String::from_utf8(out.stdout).unwrap().trim().to_string()
}

struct TempDir(PathBuf);
impl TempDir {
    fn new() -> Self {
        let n = COUNTER.fetch_add(1, Ordering::SeqCst);
        let dir =
            std::env::temp_dir().join(format!("kotoba-git-real-{}-{}", std::process::id(), n));
        std::fs::create_dir_all(&dir).unwrap();
        Self(dir)
    }
    fn path(&self) -> &Path {
        &self.0
    }
}
impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[tokio::test]
async fn real_git_repo_roundtrips_through_kotoba() {
    if !git_available() {
        eprintln!("skipping: `git` not available on PATH");
        return;
    }

    // 1. Build a real repo with two commits (objects stay loose).
    let work = TempDir::new();
    let wd = work.path();
    run_git(wd, &["init", "-q"]);
    run_git(wd, &["config", "user.email", "t@t"]);
    run_git(wd, &["config", "user.name", "t"]);
    run_git(wd, &["config", "commit.gpgsign", "false"]);
    std::fs::write(wd.join("a.txt"), "alpha\n").unwrap();
    std::fs::write(wd.join("b.txt"), "beta\n").unwrap();
    run_git(wd, &["add", "."]);
    run_git(wd, &["commit", "-q", "-m", "first"]);
    std::fs::write(wd.join("a.txt"), "alpha v2\n").unwrap();
    run_git(wd, &["add", "."]);
    run_git(wd, &["commit", "-q", "-m", "second"]);

    let git_dir = wd.join(".git");
    let head_oid = GitOid::from_hex(&git_out(wd, &["rev-parse", "HEAD"])).unwrap();

    // 2. Import the loose object DB into kotoba.
    let conn = Connection::new();
    let store = MemoryBlockStore::new();
    let git = GitStore::new(&conn, &store);
    git.install_schema().await.unwrap();
    let report = import_loose_repo(&git_dir, &git).await.unwrap();

    if report.packs_present {
        eprintln!("skipping: repo became packed, loose import incomplete");
        return;
    }
    assert!(report.objects >= 5, "expected blob+tree+commit objects");

    // 3. Every object git knows about must materialize back byte-exact.
    let rev_list = git_out(wd, &["rev-list", "--objects", "--all"]);
    let db = conn.db();
    let mut checked = 0;
    for line in rev_list.lines() {
        let oid_str = line.split_whitespace().next().unwrap();
        // rev-list --objects can include tag-peel lines; only 40-hex are oids
        let Ok(oid) = GitOid::from_hex(oid_str) else {
            continue;
        };
        let framed = git
            .materialize_framed(&db, oid)
            .unwrap_or_else(|e| panic!("materialize {oid}: {e}"));
        // recomputed SHA-1 == git's own oid
        assert_eq!(GitObject::parse_framed(&framed).unwrap().oid(), oid);
        // and it parses to the right kind / size that git reports
        let kind = git_out(wd, &["cat-file", "-t", &oid.to_hex()]);
        assert_eq!(
            GitObject::parse_framed(&framed).unwrap().kind.as_str(),
            kind
        );
        checked += 1;
    }
    assert!(checked >= 5, "checked {checked} objects");

    // 4. HEAD resolves to the same commit git reports.
    assert_eq!(resolve_ref(&db, "HEAD"), Some(head_oid));

    // 5. The branch ref imported correctly too.
    let refs = read_refs(&git_dir).unwrap();
    assert!(refs.iter().any(|(n, t)| {
        let is_default_branch = n == "refs/heads/main" || n == "refs/heads/master";
        is_default_branch && matches!(t, RefTarget::Oid(o) if *o == head_oid)
    }));
}

#[tokio::test]
async fn packed_git_repo_roundtrips_through_kotoba() {
    if !git_available() {
        eprintln!("skipping: `git` not available on PATH");
        return;
    }

    // Build a repo with several commits, then force everything into a packfile
    // (delta-compressed) so the loose importer would see nothing.
    let work = TempDir::new();
    let wd = work.path();
    run_git(wd, &["init", "-q"]);
    run_git(wd, &["config", "user.email", "t@t"]);
    run_git(wd, &["config", "user.name", "t"]);
    run_git(wd, &["config", "commit.gpgsign", "false"]);
    // A file that changes across commits → produces delta-able objects.
    for i in 0..4 {
        let mut content = String::new();
        for line in 0..=i {
            content.push_str(&format!("line {line}\n"));
        }
        std::fs::write(wd.join("doc.txt"), content).unwrap();
        run_git(wd, &["add", "."]);
        run_git(wd, &["commit", "-q", "-m", &format!("rev {i}")]);
    }
    // Pack everything and drop the now-redundant loose objects.
    run_git(wd, &["repack", "-a", "-d", "-q"]);
    run_git(wd, &["gc", "-q", "--prune=now"]);

    let git_dir = wd.join(".git");
    let head_oid = GitOid::from_hex(&git_out(wd, &["rev-parse", "HEAD"])).unwrap();

    // Sanity: the loose importer must now find (almost) nothing but report packs.
    {
        let conn = Connection::new();
        let store = MemoryBlockStore::new();
        let git = GitStore::new(&conn, &store);
        git.install_schema().await.unwrap();
        let loose = import_loose_repo(&git_dir, &git).await.unwrap();
        assert!(loose.packs_present, "expected a packfile after repack");
    }

    // Full importer decodes the pack and ingests everything.
    let conn = Connection::new();
    let store = MemoryBlockStore::new();
    let git = GitStore::new(&conn, &store);
    git.install_schema().await.unwrap();
    let report = import_repo(&git_dir, &git).await.unwrap();
    assert!(report.packs_present);
    assert!(report.objects >= 8, "got {} objects", report.objects);

    // Every object git knows must materialize back to git's own oid.
    let db = conn.db();
    let rev_list = git_out(wd, &["rev-list", "--objects", "--all"]);
    let mut checked = 0;
    for line in rev_list.lines() {
        let oid_str = line.split_whitespace().next().unwrap();
        let Ok(oid) = GitOid::from_hex(oid_str) else {
            continue;
        };
        let framed = git
            .materialize_framed(&db, oid)
            .unwrap_or_else(|e| panic!("materialize {oid}: {e}"));
        assert_eq!(GitObject::parse_framed(&framed).unwrap().oid(), oid);
        let kind = git_out(wd, &["cat-file", "-t", &oid.to_hex()]);
        assert_eq!(
            GitObject::parse_framed(&framed).unwrap().kind.as_str(),
            kind
        );
        checked += 1;
    }
    assert!(checked >= 8, "checked {checked} objects");
    assert_eq!(resolve_ref(&db, "HEAD"), Some(head_oid));
}
