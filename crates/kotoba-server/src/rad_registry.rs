//! kotoba-rad delegate registry (ADR-2606251200 A-1/A-2, "journal → node datom
//! projection").
//!
//! The per-actor sovereign-identity journals
//! (`80-data/kotoba-rad/<name>.identity.journal.edn`, ADR-2606231200) ARE Datoms
//! — EDN tuples `["<entity>" :rad/<attr> <value> <tx> :add]`. This module reads
//! them with `kotoba_edn` and projects the `:rad/delegate` / `:rad/name` /
//! `:rad/repo` facts of each genesis identity (entity == the RID) into an
//! in-memory map. The git push gate (`git_http::push_gate`) resolves the pushed
//! repo to its RID + delegate set and roots push authority there instead of in
//! the node operator DID.
//!
//! `sigref:<RID>` entities (the signed-head attestations) are skipped — they are
//! not identity facts. The journal dir is supplied via `KOTOBA_RAD_JOURNAL_DIR`;
//! unset (or missing dir) yields an empty registry, and the push gate then falls
//! back to the operator-rooted path — so this is purely additive.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use kotoba_edn::{parse_all, EdnValue};

/// One sovereign repo identity projected from a journal.
#[derive(Debug, Clone, Default)]
pub struct RadRepo {
    /// Repository Identity = CIDv1 of the genesis block (entity key of the datoms).
    pub rid: String,
    /// `:rad/name` (the actor slug), if present.
    pub name: Option<String>,
    /// `:rad/repo` (the GitHub mirror), if present.
    pub repo: Option<String>,
    /// `:rad/delegate` did:key holders authorized to push (any encoding form).
    pub delegates: Vec<String>,
    /// The journal file this identity was read from — the append target for A-3
    /// sigref attestation. `None` when ingested from a string (tests).
    pub journal_path: Option<PathBuf>,
}

/// RID-keyed registry with a name→RID alias index.
#[derive(Debug, Clone, Default)]
pub struct RadRegistry {
    by_rid: HashMap<String, RadRepo>,
    name_to_rid: HashMap<String, String>,
}

impl RadRegistry {
    /// Project one journal's datoms (one actor) into the registry. Public so the
    /// push gate's behavior can be unit-tested without touching the filesystem.
    pub fn ingest_journal(&mut self, edn_src: &str) -> Result<(), String> {
        self.ingest(edn_src, None)
    }

    fn ingest(&mut self, edn_src: &str, path: Option<&Path>) -> Result<(), String> {
        let forms = parse_all(edn_src).map_err(|e| e.to_string())?;
        for form in &forms {
            let cells = match form {
                EdnValue::Vector(c) => c,
                _ => continue,
            };
            if cells.len() < 3 {
                continue;
            }
            let entity = match as_str(&cells[0]) {
                Some(s) => s,
                None => continue,
            };
            // Skip signed-head attestations — not identity facts.
            if entity.starts_with("sigref:") {
                continue;
            }
            let attr = match as_kw(&cells[1]) {
                Some(a) => a,
                None => continue,
            };
            let rid = entity.to_string();
            let entry = self.by_rid.entry(rid.clone()).or_insert_with(|| RadRepo {
                rid: rid.clone(),
                ..Default::default()
            });
            if let Some(p) = path {
                if entry.journal_path.is_none() {
                    entry.journal_path = Some(p.to_path_buf());
                }
            }
            match attr.as_str() {
                "rad/name" => {
                    if let Some(v) = as_str(&cells[2]) {
                        entry.name = Some(v.to_string());
                        self.name_to_rid.insert(v.to_string(), rid.clone());
                    }
                }
                "rad/repo" => {
                    if let Some(v) = as_str(&cells[2]) {
                        entry.repo = Some(v.to_string());
                    }
                }
                "rad/delegate" => {
                    if let Some(v) = as_str(&cells[2]) {
                        if !entry.delegates.iter().any(|d| d == v) {
                            entry.delegates.push(v.to_string());
                        }
                    }
                }
                _ => {}
            }
        }
        Ok(())
    }

    /// Load every `*.identity.journal.edn` under `dir`. A missing/unreadable dir
    /// yields an empty registry (the push gate then uses the operator path).
    pub fn from_journal_dir(dir: impl AsRef<Path>) -> Self {
        let mut reg = RadRegistry::default();
        let entries = match std::fs::read_dir(dir.as_ref()) {
            Ok(e) => e,
            Err(_) => return reg,
        };
        for ent in entries.flatten() {
            let path = ent.path();
            if !path.to_string_lossy().ends_with(".identity.journal.edn") {
                continue;
            }
            if let Ok(src) = std::fs::read_to_string(&path) {
                // A single malformed journal must not poison the whole registry.
                let _ = reg.ingest(&src, Some(&path));
            }
        }
        reg
    }

    /// Load from `KOTOBA_RAD_JOURNAL_DIR`; empty when the var is unset/blank.
    pub fn from_env() -> Self {
        match std::env::var("KOTOBA_RAD_JOURNAL_DIR") {
            Ok(dir) if !dir.is_empty() => Self::from_journal_dir(dir),
            _ => RadRegistry::default(),
        }
    }

    /// Resolve a git `:repo` path segment to its sovereign identity. Accepts the
    /// RID directly, a `rad:<RID>` URI, the actor `:rad/name`, or a
    /// `com-<org>-<name>` repo slug.
    pub fn resolve(&self, repo_seg: &str) -> Option<&RadRepo> {
        let seg = repo_seg.strip_prefix("rad:").unwrap_or(repo_seg);
        if let Some(r) = self.by_rid.get(seg) {
            return Some(r);
        }
        if let Some(rid) = self.name_to_rid.get(seg) {
            return self.by_rid.get(rid);
        }
        // `com-<org>-<name>` → `<name>` (names may contain '-', so strip the known
        // org prefixes rather than splitting on the last hyphen).
        for prefix in ["com-etzhayyim-", "com-junkawasaki-"] {
            if let Some(name) = seg.strip_prefix(prefix) {
                if let Some(rid) = self.name_to_rid.get(name) {
                    return self.by_rid.get(rid);
                }
            }
        }
        None
    }

    pub fn len(&self) -> usize {
        self.by_rid.len()
    }

    pub fn is_empty(&self) -> bool {
        self.by_rid.is_empty()
    }

    /// Append a signed-head attestation (Radicle `rad/sigrefs`) for `repo_seg`'s
    /// identity to its journal (ADR-2606251200 A-3). Re-reads the file from disk
    /// to compute the next `tx` (so concurrent/earlier appends are respected),
    /// then appends the five sigref datoms. `sig` is the push CACAO — the member
    /// signature; the server only verifies it (no-server-key). Returns the tx
    /// used. Errors (rather than panics) if the repo has no known journal path.
    pub fn attest_sigref(
        &self,
        repo_seg: &str,
        head: &str,
        by: &str,
        sig: &str,
    ) -> Result<i64, String> {
        let repo = self
            .resolve(repo_seg)
            .ok_or_else(|| format!("no rad identity for repo {repo_seg}"))?;
        let path = repo
            .journal_path
            .clone()
            .ok_or_else(|| format!("no journal path for rid {}", repo.rid))?;
        append_sigref_to(&path, &repo.rid, head, by, sig)
    }
}

/// `tx` for the next datom = 1 + the max integer in slot 3 of any existing datom.
fn next_tx(src: &str) -> i64 {
    let forms = parse_all(src).unwrap_or_default();
    let mut max = 0i64;
    for form in &forms {
        if let EdnValue::Vector(c) = form {
            if c.len() >= 4 {
                if let EdnValue::Integer(t) = &c[3] {
                    if *t > max {
                        max = *t;
                    }
                }
            }
        }
    }
    max + 1
}

/// EDN-quote a string value (CIDs / dids / base64 carry no quotes or backslashes,
/// but escape defensively).
fn edn_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            _ => out.push(ch),
        }
    }
    out.push('"');
    out
}

fn append_sigref_to(
    path: &Path,
    rid: &str,
    head: &str,
    by: &str,
    sig: &str,
) -> Result<i64, String> {
    use std::io::Write;
    let src = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let tx = next_tx(&src);
    let e = edn_str(&format!("sigref:{rid}"));
    let block = format!(
        "[{e} :rad/type :sigref {tx} :add]\n\
         [{e} :rad/rid {rid_q} {tx} :add]\n\
         [{e} :rad/head {head_q} {tx} :add]\n\
         [{e} :rad/by {by_q} {tx} :add]\n\
         [{e} :rad/sig {sig_q} {tx} :add]\n",
        rid_q = edn_str(rid),
        head_q = edn_str(head),
        by_q = edn_str(by),
        sig_q = edn_str(sig),
    );
    let mut f = std::fs::OpenOptions::new()
        .append(true)
        .open(path)
        .map_err(|e| e.to_string())?;
    f.write_all(block.as_bytes()).map_err(|e| e.to_string())?;
    Ok(tx)
}

fn as_str(v: &EdnValue) -> Option<&str> {
    match v {
        EdnValue::String(s) => Some(s),
        _ => None,
    }
}

fn as_kw(v: &EdnValue) -> Option<String> {
    match v {
        EdnValue::Keyword(k) => Some(k.to_qualified()),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // A genesis journal WITH delegates (the production journals are currently
    // delegate-less — provisioning keys is a separate step — so we synthesize one).
    const JOURNAL: &str = r#"
["bafrid000" :rad/type :identity 1 :add]
["bafrid000" :rad/name "aburi" 1 :add]
["bafrid000" :rad/repo "github.com/etzhayyim/com-etzhayyim-aburi" 1 :add]
["bafrid000" :rad/delegate "did:key:zAAA" 1 :add]
["bafrid000" :rad/delegate "did:key:zBBB" 1 :add]
["sigref:bafrid000" :rad/type :sigref 1 :add]
["sigref:bafrid000" :rad/head "bafhead000" 1 :add]
"#;

    fn reg() -> RadRegistry {
        let mut r = RadRegistry::default();
        r.ingest_journal(JOURNAL).unwrap();
        r
    }

    #[test]
    fn projects_delegates_and_skips_sigrefs() {
        let r = reg();
        assert_eq!(r.len(), 1, "sigref:* entity must not create a second repo");
        let repo = r.resolve("bafrid000").unwrap();
        assert_eq!(repo.delegates, vec!["did:key:zAAA", "did:key:zBBB"]);
        assert_eq!(repo.name.as_deref(), Some("aburi"));
    }

    #[test]
    fn resolves_by_rid_name_rad_uri_and_repo_slug() {
        let r = reg();
        assert!(r.resolve("bafrid000").is_some(), "by RID");
        assert!(r.resolve("rad:bafrid000").is_some(), "by rad: URI");
        assert!(r.resolve("aburi").is_some(), "by name");
        assert!(
            r.resolve("com-etzhayyim-aburi").is_some(),
            "by com-<org>-<name> slug"
        );
        assert!(r.resolve("unknown").is_none());
    }

    #[test]
    fn hyphenated_name_resolves_via_org_prefix_strip() {
        let mut r = RadRegistry::default();
        r.ingest_journal(
            r#"["bafX" :rad/name "business-manager" 1 :add]
["bafX" :rad/delegate "did:key:zX" 1 :add]"#,
        )
        .unwrap();
        // last-hyphen splitting would wrongly yield "manager"; prefix strip is correct.
        assert_eq!(
            r.resolve("com-etzhayyim-business-manager")
                .map(|x| x.rid.as_str()),
            Some("bafX")
        );
    }

    #[test]
    fn missing_dir_yields_empty_registry() {
        let r = RadRegistry::from_journal_dir("/nonexistent/kotoba-rad-xyz");
        assert!(r.is_empty());
    }

    #[test]
    fn attest_sigref_appends_to_journal_and_bumps_tx() {
        // Write a genesis journal to a temp dir, build the registry from it, then
        // attest a head and verify the sigref datoms land with the next tx.
        let dir = std::env::temp_dir().join(format!("kotoba-rad-attest-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("aburi.identity.journal.edn");
        std::fs::write(&path, JOURNAL).unwrap();

        let reg = RadRegistry::from_journal_dir(&dir);
        let tx = reg
            .attest_sigref("aburi", "bafheadNEW", "did:key:zAAA", "cacaoB64==")
            .expect("attest must succeed");
        assert_eq!(tx, 2, "JOURNAL max tx is 1 → next is 2");

        // The appended datoms are present and re-parse cleanly.
        let after = std::fs::read_to_string(&path).unwrap();
        assert!(after.contains("[\"sigref:bafrid000\" :rad/head \"bafheadNEW\" 2 :add]"));
        assert!(after.contains("[\"sigref:bafrid000\" :rad/by \"did:key:zAAA\" 2 :add]"));
        assert!(after.contains("[\"sigref:bafrid000\" :rad/sig \"cacaoB64==\" 2 :add]"));
        let mut check = RadRegistry::default();
        check
            .ingest_journal(&after)
            .expect("appended journal must re-parse");

        // A second attestation increments tx again.
        let tx2 = reg
            .attest_sigref("aburi", "bafheadNEW2", "did:key:zAAA", "cacaoB64b==")
            .unwrap();
        assert_eq!(tx2, 3);

        let _ = std::fs::remove_dir_all(&dir);
    }
}
