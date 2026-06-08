//! git **smart-HTTP** service layer — the glue that lets a real `git` client
//! clone / fetch / push against a [`GitStore`] (datomic projection + IPFS
//! blocks).
//!
//! Three entry points mirror the three HTTP requests git makes:
//!
//! | git operation        | HTTP                                   | fn |
//! |----------------------|----------------------------------------|----|
//! | ref discovery        | `GET  …/info/refs?service=…`           | [`advertise_refs`] |
//! | clone / fetch        | `POST …/git-upload-pack`               | [`upload_pack`] |
//! | push                 | `POST …/git-receive-pack`              | [`receive_pack`] |
//!
//! We speak protocol **v0** (the most broadly compatible), advertise a minimal
//! capability set, and emit **undeltified** packs. Negotiation uses the basic
//! (non-multi_ack) ACK/NAK handshake, which terminates cleanly over git's
//! stateless-HTTP transport. See the inline notes for the precise wire shapes.

use crate::oid::GitOid;
use crate::wire::pack_encode::encode_pack;
use crate::wire::pack_ingest::parse_pack;
use crate::wire::pktline::{self, PktLine, PktLineReader};
use crate::{list_refs, object_cid, resolve_ref, GitStore, RefTarget, Result};
use kotoba_datomic::Db;
use std::collections::HashSet;

const AGENT: &str = "agent=kotoba-git/0.1";
/// Capabilities advertised for fetch. `side-band-64k` lets us multiplex the
/// pack (and is what modern git prefers); `ofs-delta` is harmless to advertise
/// even though we currently emit full objects.
const UPLOAD_CAPS: &str = "side-band-64k ofs-delta";
/// Capabilities advertised for push. `report-status` lets the client learn the
/// per-ref outcome. (We do not advertise `delete-refs` — see [`receive_pack`].)
const RECEIVE_CAPS: &str = "report-status ofs-delta";

const ZERO_OID: &str = "0000000000000000000000000000000000000000";

/// The two git wire services.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GitService {
    UploadPack,
    ReceivePack,
}

impl GitService {
    pub fn as_str(self) -> &'static str {
        match self {
            GitService::UploadPack => "git-upload-pack",
            GitService::ReceivePack => "git-receive-pack",
        }
    }

    /// Parse the `service=` query value git sends to `info/refs`.
    pub fn from_query(s: &str) -> Option<Self> {
        match s {
            "git-upload-pack" => Some(GitService::UploadPack),
            "git-receive-pack" => Some(GitService::ReceivePack),
            _ => None,
        }
    }

    fn caps(self) -> &'static str {
        match self {
            GitService::UploadPack => UPLOAD_CAPS,
            GitService::ReceivePack => RECEIVE_CAPS,
        }
    }
}

// ───────────────────────────────────────────────────────────────────────────
// GET /info/refs?service=…
// ───────────────────────────────────────────────────────────────────────────

/// Build the smart-HTTP `info/refs` advertisement body for `service`.
///
/// Layout (protocol v0 over HTTP):
/// ```text
/// <pkt> "# service=git-upload-pack\n"
/// 0000
/// <pkt> "<oid> HEAD\0<caps> symref=HEAD:refs/heads/main\n"
/// <pkt> "<oid> refs/heads/main\n"
/// …
/// 0000
/// ```
/// An empty repository advertises the canonical zero-id `capabilities^{}` line
/// so `git clone` of an empty repo (and the first `git push`) work.
pub fn advertise_refs(git: &GitStore, service: GitService) -> Result<Vec<u8>> {
    let db = git.db();
    let caps = format!("{} {}", service.caps(), AGENT);

    let mut out = Vec::new();
    pktline::write_str(&mut out, &format!("# service={}\n", service.as_str()))?;
    pktline::write_flush(&mut out);

    let lines = ref_advert_lines(&db);
    if lines.is_empty() {
        pktline::write_str(&mut out, &format!("{ZERO_OID} capabilities^{{}}\0{caps}\n"))?;
    } else {
        let head_symref = head_symref_target(&db);
        for (i, (oid_hex, name)) in lines.iter().enumerate() {
            if i == 0 {
                let mut capstr = caps.clone();
                if let Some(target) = &head_symref {
                    capstr.push_str(&format!(" symref=HEAD:{target}"));
                }
                pktline::write_str(&mut out, &format!("{oid_hex} {name}\0{capstr}\n"))?;
            } else {
                pktline::write_str(&mut out, &format!("{oid_hex} {name}\n"))?;
            }
        }
    }
    pktline::write_flush(&mut out);
    Ok(out)
}

/// `(oid_hex, refname)` advertisement lines: `HEAD` first (resolved), then each
/// direct ref sorted by name (git's canonical ordering).
fn ref_advert_lines(db: &Db) -> Vec<(String, String)> {
    let mut lines = Vec::new();
    if let Some(head) = resolve_ref(db, "HEAD") {
        lines.push((head.to_hex(), "HEAD".to_string()));
    }
    let mut direct: Vec<(String, GitOid)> = list_refs(db)
        .into_iter()
        .filter_map(|(name, target)| match target {
            RefTarget::Oid(oid) if name != "HEAD" => Some((name, oid)),
            _ => None,
        })
        .collect();
    direct.sort_by(|a, b| a.0.cmp(&b.0));
    for (name, oid) in direct {
        lines.push((oid.to_hex(), name));
    }
    lines
}

fn head_symref_target(db: &Db) -> Option<String> {
    list_refs(db).into_iter().find_map(|(name, target)| match target {
        RefTarget::Symbolic(t) if name == "HEAD" => Some(t),
        _ => None,
    })
}

// ───────────────────────────────────────────────────────────────────────────
// POST /git-upload-pack   (clone / fetch)
// ───────────────────────────────────────────────────────────────────────────

#[derive(Default)]
struct UploadRequest {
    wants: Vec<GitOid>,
    haves: Vec<GitOid>,
    done: bool,
    side_band_64k: bool,
}

fn parse_upload_request(body: &[u8]) -> Result<UploadRequest> {
    let mut req = UploadRequest::default();
    let mut reader = PktLineReader::new(body);
    while let Some(pkt) = reader.next_pkt()? {
        if let PktLine::Data(data) = pkt {
            let line = String::from_utf8_lossy(&data);
            let line = line.trim_end_matches('\n');
            if let Some(rest) = line.strip_prefix("want ") {
                // `want <oid>[ <cap> <cap> …]` — caps ride on the first want.
                let mut parts = rest.splitn(2, ' ');
                if let Some(oid_hex) = parts.next() {
                    if let Ok(oid) = GitOid::from_hex(oid_hex) {
                        req.wants.push(oid);
                    }
                }
                if let Some(caps) = parts.next() {
                    if caps.split(' ').any(|c| c == "side-band-64k") {
                        req.side_band_64k = true;
                    }
                }
            } else if let Some(oid_hex) = line.strip_prefix("have ") {
                if let Ok(oid) = GitOid::from_hex(oid_hex.trim()) {
                    req.haves.push(oid);
                }
            } else if line == "done" {
                req.done = true;
            }
        }
    }
    Ok(req)
}

/// Handle a `git-upload-pack` request body, returning the response body.
///
/// * Negotiation round (no `done`): reply `ACK <oid>` if we share a `have`,
///   else `NAK` — and nothing else. git then sends `done` and we send the pack.
/// * Terminal round (`done`): final `ACK <oid>`/`NAK`, then the packfile of
///   everything reachable from the wants minus what the shared haves already
///   cover (so a `fetch` ships only the delta of history, a `clone` ships all).
pub fn upload_pack(git: &GitStore, body: &[u8]) -> Result<Vec<u8>> {
    let db = git.db();
    let req = parse_upload_request(body)?;

    // Which of the client's haves do we actually possess?
    let common: Vec<GitOid> = req
        .haves
        .iter()
        .copied()
        .filter(|oid| object_cid(&db, *oid).is_ok())
        .collect();

    let mut out = Vec::new();
    match common.last() {
        Some(oid) => pktline::write_str(&mut out, &format!("ACK {}\n", oid.to_hex()))?,
        None => pktline::write_str(&mut out, "NAK\n")?,
    }
    if !req.done {
        // Negotiation continues; no pack yet.
        return Ok(out);
    }

    // Reachable(wants) − Reachable(common) = the objects the client lacks.
    let exclude = collect_reachable(git, &db, &common)?;
    let mut send: Vec<GitOid> = collect_reachable(git, &db, &req.wants)?
        .into_iter()
        .filter(|oid| !exclude.contains(oid))
        .collect();
    send.sort();

    let mut objects = Vec::with_capacity(send.len());
    for oid in send {
        objects.push(git.materialize_object(&db, oid)?);
    }
    let pack = encode_pack(&objects)?;

    if req.side_band_64k {
        write_sideband_pack(&mut out, &pack)?;
    } else {
        out.extend_from_slice(&pack);
    }
    Ok(out)
}

/// Pack data on side-band channel 1, each chunk a pkt-line, terminated by a
/// flush-pkt. Band byte (`0x01`) + payload must fit one pkt-line.
fn write_sideband_pack(out: &mut Vec<u8>, pack: &[u8]) -> Result<()> {
    const CHUNK: usize = pktline::MAX_PAYLOAD - 1; // leave room for the band byte
    for chunk in pack.chunks(CHUNK) {
        let mut payload = Vec::with_capacity(chunk.len() + 1);
        payload.push(1u8);
        payload.extend_from_slice(chunk);
        pktline::write_data(out, &payload)?;
    }
    pktline::write_flush(out);
    Ok(())
}

/// Transitive closure of the object DAG from `roots`: commits pull in their
/// tree and parents, trees pull in their entries (sub-trees + blobs), tags pull
/// in their target. Objects not present in the store are skipped (a `have` the
/// client cited that we lack simply doesn't expand).
fn collect_reachable(git: &GitStore, db: &Db, roots: &[GitOid]) -> Result<HashSet<GitOid>> {
    use crate::object::GitObjectKind::*;
    let mut seen = HashSet::new();
    let mut stack: Vec<GitOid> = roots.to_vec();
    while let Some(oid) = stack.pop() {
        if !seen.insert(oid) {
            continue;
        }
        // A cited oid we don't have: skip it (don't fail the whole walk).
        let Ok(obj) = git.materialize_object(db, oid) else {
            seen.remove(&oid);
            continue;
        };
        match obj.kind {
            Commit => {
                if let Some(tree) = obj.header_value("tree") {
                    if let Ok(t) = GitOid::from_hex(&tree) {
                        stack.push(t);
                    }
                }
                for parent in obj.header_values("parent") {
                    if let Ok(p) = GitOid::from_hex(&parent) {
                        stack.push(p);
                    }
                }
            }
            Tree => {
                for entry in obj.tree_entries()? {
                    stack.push(entry.oid);
                }
            }
            Tag => {
                if let Some(target) = obj.header_value("object") {
                    if let Ok(t) = GitOid::from_hex(&target) {
                        stack.push(t);
                    }
                }
            }
            Blob => {}
        }
    }
    Ok(seen)
}

// ───────────────────────────────────────────────────────────────────────────
// POST /git-receive-pack   (push)
// ───────────────────────────────────────────────────────────────────────────

/// One ref-update command from a push.
struct RefCommand {
    old: GitOid,
    new: GitOid,
    name: String,
}

struct ReceiveRequest {
    commands: Vec<RefCommand>,
    report_status: bool,
    pack: Vec<u8>,
}

fn parse_receive_request(body: &[u8]) -> Result<ReceiveRequest> {
    let mut commands = Vec::new();
    let mut report_status = false;
    let mut reader = PktLineReader::new(body);
    let mut first = true;
    while let Some(pkt) = reader.next_pkt()? {
        match pkt {
            PktLine::Flush => break,
            PktLine::Delim => continue,
            PktLine::Data(data) => {
                // First command: `<old> <new> <ref>\0<caps>`; rest: `<old> <new> <ref>`.
                let (cmd_bytes, caps) = match data.iter().position(|&b| b == 0) {
                    Some(nul) => (&data[..nul], Some(&data[nul + 1..])),
                    None => (&data[..], None),
                };
                if first {
                    if let Some(caps) = caps {
                        let caps = String::from_utf8_lossy(caps);
                        if caps.split([' ', '\n']).any(|c| c == "report-status") {
                            report_status = true;
                        }
                    }
                    first = false;
                }
                let line = String::from_utf8_lossy(cmd_bytes);
                let line = line.trim_end_matches('\n');
                let mut parts = line.splitn(3, ' ');
                let (Some(old), Some(new), Some(name)) =
                    (parts.next(), parts.next(), parts.next())
                else {
                    return Err(crate::error::GitError::MalformedHeader);
                };
                commands.push(RefCommand {
                    old: GitOid::from_hex(old)?,
                    new: GitOid::from_hex(new)?,
                    name: name.to_string(),
                });
            }
        }
    }
    // Everything after the flush-pkt is the raw packfile (absent for pure deletes).
    let pack = reader.remaining().to_vec();
    Ok(ReceiveRequest {
        commands,
        report_status,
        pack,
    })
}

fn is_zero(oid: &GitOid) -> bool {
    oid.0 == [0u8; 20]
}

/// Handle a `git-receive-pack` request body (a push): ingest the packfile into
/// the store, then apply the ref updates. Returns the `report-status` body when
/// the client asked for it (the default), else an empty body.
///
/// **Concurrency / fast-forward policy.** Each command carries the `old` value
/// the client believed the ref held; we reject (`ng … stale`) when it disagrees
/// with the stored ref, which is git's lost-update protection. We do *not*
/// additionally enforce fast-forward-only (no force signal exists on the wire),
/// so this behaves like `receive.denyNonFastForwards=false`.
///
/// Ref **deletion** (`new` = zero-oid) is reported `ng` — the append-only Datom
/// projection has no retract path here yet, and we deliberately do not advertise
/// `delete-refs`.
pub async fn receive_pack(git: &GitStore<'_>, body: &[u8]) -> Result<Vec<u8>> {
    let req = parse_receive_request(body)?;

    // ── Ingest the packfile (if any). Thin-pack bases resolve from the store. ──
    let mut unpack_status = "ok".to_string();
    if req.pack.starts_with(b"PACK") {
        let db = git.db();
        let resolver = |oid: GitOid| -> Result<Option<(crate::object::GitObjectKind, Vec<u8>)>> {
            match git.materialize_object(&db, oid) {
                Ok(obj) => Ok(Some((obj.kind, obj.body))),
                Err(_) => Ok(None),
            }
        };
        match parse_pack(&req.pack, resolver) {
            Ok(objects) => {
                for (obj, _oid) in objects {
                    git.put_object(&obj).await?;
                }
            }
            Err(e) => unpack_status = format!("unpack-failed: {e}"),
        }
    }

    // ── Apply ref updates (only if the pack unpacked cleanly). ─────────────────
    let mut results: Vec<(String, std::result::Result<(), String>)> = Vec::new();
    if unpack_status == "ok" {
        let db = git.db();
        for cmd in &req.commands {
            let outcome = apply_command(git, &db, cmd).await;
            results.push((cmd.name.clone(), outcome));
        }
        // Adopt a default branch: a bare repo needs `HEAD` to resolve so clients
        // know which branch to check out on clone. If `HEAD` is dangling after
        // this push (e.g. the very first push to a fresh repo), point it at the
        // pushed branch — preferring `main`, then `master`, then any branch.
        let db = git.db();
        if resolve_ref(&db, "HEAD").is_none() {
            if let Some(branch) = pick_default_branch(&db) {
                let _ = git.put_symbolic_ref("HEAD", &branch).await;
            }
        }
    } else {
        for cmd in &req.commands {
            results.push((cmd.name.clone(), Err("unpack failed".into())));
        }
    }

    if !req.report_status {
        return Ok(Vec::new());
    }

    let mut out = Vec::new();
    pktline::write_str(&mut out, &format!("unpack {unpack_status}\n"))?;
    for (name, outcome) in results {
        match outcome {
            Ok(()) => pktline::write_str(&mut out, &format!("ok {name}\n"))?,
            Err(reason) => pktline::write_str(&mut out, &format!("ng {name} {reason}\n"))?,
        }
    }
    pktline::write_flush(&mut out);
    Ok(out)
}

/// Choose a default branch for `HEAD` among the `refs/heads/*` present:
/// `refs/heads/main`, else `refs/heads/master`, else the first by name.
fn pick_default_branch(db: &Db) -> Option<String> {
    let mut branches: Vec<String> = list_refs(db)
        .into_iter()
        .filter_map(|(name, target)| match target {
            RefTarget::Oid(_) if name.starts_with("refs/heads/") => Some(name),
            _ => None,
        })
        .collect();
    branches.sort();
    if branches.iter().any(|b| b == "refs/heads/main") {
        return Some("refs/heads/main".to_string());
    }
    if branches.iter().any(|b| b == "refs/heads/master") {
        return Some("refs/heads/master".to_string());
    }
    branches.into_iter().next()
}

async fn apply_command(
    git: &GitStore<'_>,
    db: &Db,
    cmd: &RefCommand,
) -> std::result::Result<(), String> {
    if is_zero(&cmd.new) {
        return Err("deletion unsupported".into());
    }
    // Lost-update guard: the client's expected `old` must match the stored ref.
    let current = resolve_ref(db, &cmd.name);
    let expected = if is_zero(&cmd.old) { None } else { Some(cmd.old) };
    if current != expected {
        return Err("stale info: fetch first".into());
    }
    // Connectivity: the new tip must actually be in the store after ingest.
    if object_cid(db, cmd.new).is_err() {
        return Err("missing necessary objects".into());
    }
    git.put_ref(&cmd.name, cmd.new)
        .await
        .map_err(|e| format!("ref update failed: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::object::{GitObject, GitObjectKind, TreeEntry};
    use crate::GitStore;
    use kotoba_datomic::Connection;
    use kotoba_store::MemoryBlockStore;

    async fn fixture() -> (Connection, MemoryBlockStore) {
        let conn = Connection::new();
        let store = MemoryBlockStore::new();
        GitStore::new(&conn, &store).install_schema().await.unwrap();
        (conn, store)
    }

    /// Seed a blob→tree→commit chain on `refs/heads/main` + HEAD symref.
    async fn seed_commit(git: &GitStore<'_>) -> GitOid {
        let blob = GitObject::blob(b"hello\n".to_vec());
        let (blob_oid, _) = git.put_object(&blob).await.unwrap();
        let tree = GitObject::tree(&[TreeEntry {
            mode: b"100644".to_vec(),
            name: b"f.txt".to_vec(),
            oid: blob_oid,
        }]);
        let (tree_oid, _) = git.put_object(&tree).await.unwrap();
        let commit = GitObject::new(
            GitObjectKind::Commit,
            format!(
                "tree {tree_oid}\nauthor t <t@t> 1700000000 +0000\ncommitter t <t@t> 1700000000 +0000\n\nfirst\n"
            )
            .into_bytes(),
        );
        let (commit_oid, _) = git.put_object(&commit).await.unwrap();
        git.put_ref("refs/heads/main", commit_oid).await.unwrap();
        git.put_symbolic_ref("HEAD", "refs/heads/main").await.unwrap();
        commit_oid
    }

    #[tokio::test]
    async fn advertise_lists_head_and_branch_with_caps() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let commit = seed_commit(&git).await;

        let body = advertise_refs(&git, GitService::UploadPack).unwrap();
        let text = String::from_utf8_lossy(&body);
        assert!(text.contains("# service=git-upload-pack"));
        assert!(text.contains(&commit.to_hex()));
        assert!(text.contains("refs/heads/main"));
        assert!(text.contains("symref=HEAD:refs/heads/main"));
        assert!(text.contains("side-band-64k"));
    }

    #[tokio::test]
    async fn advertise_empty_repo_uses_zero_capabilities_line() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let body = advertise_refs(&git, GitService::ReceivePack).unwrap();
        let text = String::from_utf8_lossy(&body);
        assert!(text.contains(&format!("{ZERO_OID} capabilities^{{}}")));
        assert!(text.contains("report-status"));
    }

    #[tokio::test]
    async fn upload_pack_clone_sends_all_reachable_objects() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let commit = seed_commit(&git).await;

        // A clone: `want <commit>` + flush + done, no haves, no side-band.
        let mut body = Vec::new();
        pktline::write_str(&mut body, &format!("want {}\n", commit.to_hex())).unwrap();
        pktline::write_flush(&mut body);
        pktline::write_str(&mut body, "done\n").unwrap();

        let resp = upload_pack(&git, &body).unwrap();
        // NAK pkt-line, then a raw pack.
        assert!(resp.starts_with(b"0008NAK\n"));
        let pack = &resp[8..];
        let got = parse_pack(pack, |_| Ok(None)).unwrap();
        assert_eq!(got.len(), 3, "blob + tree + commit");
    }

    #[tokio::test]
    async fn upload_pack_negotiation_round_acks_without_pack() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let commit = seed_commit(&git).await;

        // Client already has `commit`: send want + have, NO done.
        let mut body = Vec::new();
        pktline::write_str(&mut body, &format!("want {}\n", commit.to_hex())).unwrap();
        pktline::write_flush(&mut body);
        pktline::write_str(&mut body, &format!("have {}\n", commit.to_hex())).unwrap();

        let resp = upload_pack(&git, &body).unwrap();
        let text = String::from_utf8_lossy(&resp);
        assert!(text.contains(&format!("ACK {}", commit.to_hex())));
        assert!(!text.contains("PACK"), "no pack until the client says done");
    }

    #[tokio::test]
    async fn receive_pack_ingests_and_updates_ref() {
        // Source store with a commit; produce a pack of its objects.
        let (src_conn, src_store) = fixture().await;
        let src = GitStore::new(&src_conn, &src_store);
        let commit = seed_commit(&src).await;
        let objs: Vec<GitObject> = {
            let db = src.db();
            let reach = collect_reachable(&src, &db, &[commit]).unwrap();
            let mut v: Vec<GitOid> = reach.into_iter().collect();
            v.sort();
            v.into_iter().map(|o| src.materialize_object(&db, o).unwrap()).collect()
        };
        let pack = encode_pack(&objs).unwrap();

        // Empty destination receives a push creating refs/heads/main.
        let (dst_conn, dst_store) = fixture().await;
        let dst = GitStore::new(&dst_conn, &dst_store);

        let mut body = Vec::new();
        pktline::write_data(
            &mut body,
            format!("{ZERO_OID} {} refs/heads/main\0report-status\n", commit.to_hex())
                .as_bytes(),
        )
        .unwrap();
        pktline::write_flush(&mut body);
        body.extend_from_slice(&pack);

        let resp = receive_pack(&dst, &body).await.unwrap();
        let text = String::from_utf8_lossy(&resp);
        assert!(text.contains("unpack ok"), "got: {text}");
        assert!(text.contains("ok refs/heads/main"), "got: {text}");

        // The ref now resolves and every object round-trips byte-exact.
        let db = dst.db();
        assert_eq!(resolve_ref(&db, "refs/heads/main"), Some(commit));
        // The first push to a fresh repo adopts a default branch for HEAD so a
        // subsequent `git clone` knows which branch to check out.
        assert_eq!(resolve_ref(&db, "HEAD"), Some(commit));
        for obj in &objs {
            let framed = dst.materialize_framed(&db, obj.oid()).unwrap();
            assert_eq!(GitOid::of_framed(&framed), obj.oid());
        }
    }

    #[tokio::test]
    async fn upload_pack_side_band_64k_frames_the_pack_on_channel_1() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let commit = seed_commit(&git).await;

        // Clone requesting side-band-64k (as real git does).
        let mut body = Vec::new();
        pktline::write_str(
            &mut body,
            &format!("want {} side-band-64k\n", commit.to_hex()),
        )
        .unwrap();
        pktline::write_flush(&mut body);
        pktline::write_str(&mut body, "done\n").unwrap();

        let resp = upload_pack(&git, &body).unwrap();
        // NAK line, then side-band pkt-lines (band byte 0x01), then flush.
        assert!(resp.starts_with(b"0008NAK\n"));
        let mut reader = PktLineReader::new(&resp[8..]);
        let mut pack = Vec::new();
        let mut saw_band1 = false;
        while let Some(p) = reader.next_pkt().unwrap() {
            match p {
                PktLine::Data(d) => {
                    assert_eq!(d[0], 1, "pack must ride side-band channel 1");
                    saw_band1 = true;
                    pack.extend_from_slice(&d[1..]);
                }
                PktLine::Flush => break,
                PktLine::Delim => {}
            }
        }
        assert!(saw_band1);
        // The de-multiplexed bytes are a valid pack of all 3 objects.
        assert_eq!(parse_pack(&pack, |_| Ok(None)).unwrap().len(), 3);
    }

    #[tokio::test]
    async fn upload_pack_fetch_excludes_objects_reachable_from_common_haves() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let c1 = seed_commit(&git).await; // blob+tree+commit

        // A second commit on top, reusing nothing new but a fresh tree/blob.
        let blob2 = GitObject::blob(b"world\n".to_vec());
        let (b2, _) = git.put_object(&blob2).await.unwrap();
        let tree2 = GitObject::tree(&[TreeEntry {
            mode: b"100644".to_vec(),
            name: b"g.txt".to_vec(),
            oid: b2,
        }]);
        let (t2, _) = git.put_object(&tree2).await.unwrap();
        let commit2 = GitObject::new(
            GitObjectKind::Commit,
            format!("tree {t2}\nparent {c1}\n\nsecond\n").into_bytes(),
        );
        let (c2, _) = git.put_object(&commit2).await.unwrap();
        git.put_ref("refs/heads/main", c2).await.unwrap();

        // Fetch c2 while already having c1: pack must omit c1's closure.
        let mut body = Vec::new();
        pktline::write_str(&mut body, &format!("want {}\n", c2.to_hex())).unwrap();
        pktline::write_flush(&mut body);
        pktline::write_str(&mut body, &format!("have {}\n", c1.to_hex())).unwrap();
        pktline::write_str(&mut body, "done\n").unwrap();

        let resp = upload_pack(&git, &body).unwrap();
        // ACK <c1> then a raw pack (no side-band requested).
        let text = String::from_utf8_lossy(&resp);
        assert!(text.contains(&format!("ACK {}", c1.to_hex())));
        let pack_start = resp
            .windows(4)
            .position(|w| w == b"PACK")
            .expect("a pack follows the ACK");
        let got = parse_pack(&resp[pack_start..], |_| Ok(None)).unwrap();
        let oids: std::collections::HashSet<_> = got.iter().map(|(_, o)| *o).collect();
        // Only c2's new objects (commit2 + tree2 + blob2); NOT c1's closure.
        assert!(oids.contains(&c2) && oids.contains(&t2) && oids.contains(&b2));
        assert!(!oids.contains(&c1), "objects reachable from the have must be excluded");
        assert_eq!(oids.len(), 3);
    }

    #[tokio::test]
    async fn upload_pack_serves_annotated_tag_and_its_target_closure() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let commit = seed_commit(&git).await;
        let tag = GitObject::new(
            GitObjectKind::Tag,
            format!(
                "object {commit}\ntype commit\ntag v1\ntagger t <t@t> 1700000000 +0000\n\nrel\n"
            )
            .into_bytes(),
        );
        let (tag_oid, _) = git.put_object(&tag).await.unwrap();
        git.put_ref("refs/tags/v1", tag_oid).await.unwrap();

        let mut body = Vec::new();
        pktline::write_str(&mut body, &format!("want {}\n", tag_oid.to_hex())).unwrap();
        pktline::write_flush(&mut body);
        pktline::write_str(&mut body, "done\n").unwrap();

        let resp = upload_pack(&git, &body).unwrap();
        let pack = &resp[resp.windows(4).position(|w| w == b"PACK").unwrap()..];
        let oids: std::collections::HashSet<_> =
            parse_pack(pack, |_| Ok(None)).unwrap().into_iter().map(|(_, o)| o).collect();
        // tag → commit → tree → blob, all four reachable from the tag.
        assert!(oids.contains(&tag_oid) && oids.contains(&commit));
        assert_eq!(oids.len(), 4);
    }

    #[tokio::test]
    async fn receive_pack_reports_unpack_failed_on_corrupt_pack() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let commit = GitObject::blob(b"x".to_vec()).oid(); // arbitrary

        let mut body = Vec::new();
        pktline::write_data(
            &mut body,
            format!("{ZERO_OID} {} refs/heads/main\0report-status\n", commit.to_hex())
                .as_bytes(),
        )
        .unwrap();
        pktline::write_flush(&mut body);
        body.extend_from_slice(b"PACK\x00\x00\x00\x02corrupt-not-a-real-pack-trailer!!"); // bad

        let resp = receive_pack(&git, &body).await.unwrap();
        let text = String::from_utf8_lossy(&resp);
        assert!(text.contains("unpack unpack-failed"), "got: {text}");
        assert!(text.contains("ng refs/heads/main"), "got: {text}");
    }

    #[tokio::test]
    async fn receive_pack_reports_per_command_ok_and_ng_independently() {
        // One push carrying two commands: a valid create of refs/heads/feature
        // and a stale update of refs/heads/main. The pack supplies the objects.
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let commit = seed_commit(&git).await; // main is at `commit`; objects present

        let objs: Vec<GitObject> = {
            let db = git.db();
            let mut v: Vec<GitOid> = collect_reachable(&git, &db, &[commit]).unwrap().into_iter().collect();
            v.sort();
            v.into_iter().map(|o| git.materialize_object(&db, o).unwrap()).collect()
        };
        let pack = encode_pack(&objs).unwrap();

        let mut body = Vec::new();
        // cmd 1 (first → carries caps): create refs/heads/feature @ commit  → ok
        pktline::write_data(
            &mut body,
            format!("{ZERO_OID} {} refs/heads/feature\0report-status\n", commit.to_hex())
                .as_bytes(),
        )
        .unwrap();
        // cmd 2: update main claiming old=zero (but it exists @ commit) → stale ng
        pktline::write_data(
            &mut body,
            format!("{ZERO_OID} {} refs/heads/main\n", commit.to_hex()).as_bytes(),
        )
        .unwrap();
        pktline::write_flush(&mut body);
        body.extend_from_slice(&pack);

        let resp = receive_pack(&git, &body).await.unwrap();
        let text = String::from_utf8_lossy(&resp);
        assert!(text.contains("unpack ok"), "got: {text}");
        assert!(text.contains("ok refs/heads/feature"), "create must succeed: {text}");
        assert!(text.contains("ng refs/heads/main"), "stale update must be rejected: {text}");
        // The accepted ref took effect; the rejected one did not change.
        let db = git.db();
        assert_eq!(resolve_ref(&db, "refs/heads/feature"), Some(commit));
    }

    #[tokio::test]
    async fn receive_pack_rejects_ref_deletion() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let commit = seed_commit(&git).await;

        // Delete request: new-oid = zero. No pack.
        let mut body = Vec::new();
        pktline::write_data(
            &mut body,
            format!("{} {ZERO_OID} refs/heads/main\0report-status\n", commit.to_hex())
                .as_bytes(),
        )
        .unwrap();
        pktline::write_flush(&mut body);

        let resp = receive_pack(&git, &body).await.unwrap();
        let text = String::from_utf8_lossy(&resp);
        assert!(text.contains("unpack ok"), "got: {text}");
        assert!(text.contains("ng refs/heads/main deletion unsupported"), "got: {text}");
    }

    #[test]
    fn pick_default_branch_prefers_main_then_master_then_first() {
        use crate::object::GitObjectKind;
        // We need a Db with some refs/heads/* present. Build via a Connection.
        let rt = tokio::runtime::Builder::new_current_thread()
            .build()
            .unwrap();
        rt.block_on(async {
            let (conn, store) = fixture().await;
            let git = GitStore::new(&conn, &store);
            let c = GitObject::new(GitObjectKind::Commit, b"tree x\n\nm\n".to_vec());
            let (oid, _) = git.put_object(&c).await.unwrap();
            git.put_ref("refs/heads/zeta", oid).await.unwrap();
            git.put_ref("refs/heads/master", oid).await.unwrap();
            assert_eq!(
                pick_default_branch(&git.db()).as_deref(),
                Some("refs/heads/master"),
                "master preferred over an alphabetically-first branch"
            );
            git.put_ref("refs/heads/main", oid).await.unwrap();
            assert_eq!(
                pick_default_branch(&git.db()).as_deref(),
                Some("refs/heads/main"),
                "main preferred over master"
            );
        });
    }

    #[tokio::test]
    async fn receive_pack_rejects_stale_old_value() {
        let (conn, store) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let commit = seed_commit(&git).await; // ref is at `commit`

        // Push claims old=zero (i.e. "ref doesn't exist") but it does → stale.
        let mut body = Vec::new();
        pktline::write_data(
            &mut body,
            format!("{ZERO_OID} {} refs/heads/main\0report-status\n", commit.to_hex())
                .as_bytes(),
        )
        .unwrap();
        pktline::write_flush(&mut body);
        // No pack needed — the command is rejected before connectivity matters,
        // but the object already exists so connectivity would pass anyway.

        let resp = receive_pack(&git, &body).await.unwrap();
        let text = String::from_utf8_lossy(&resp);
        assert!(text.contains("ng refs/heads/main"), "got: {text}");
    }
}
