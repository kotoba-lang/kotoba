//! kotoba-rad object sync (ADR-2606251200 G2) — turn a gossip-verified head into
//! a full local replica by fetching the repo's git objects by CID, no central
//! node. This is the transport-independent core: parse the kotoba-git snapshot
//! **manifest** (`GitStore::snapshot_manifest`), compute which object CIDs to
//! fetch, and bind the manifest to the G1-verified head. The bitswap fetch loop
//! + `GitStore::rehydrate` are the transport layer on top.
//!
//! Why a manifest: bitswap addresses blocks by `KotobaCid` (sha2-256 of the
//! framed object), but a git object references its children by **SHA-1**, which a
//! peer cannot turn into a CID without already holding the bytes. The manifest
//! lists every object's `oid → cid`, so a peer fetches one manifest block then
//! `want`s each object CID directly. A forged manifest is harmless: the peer only
//! trusts it after [`Manifest::head_cid`] for the repo's head ref equals the
//! G1-verified head (see [`Manifest::binds_head`]).

use std::collections::HashMap;

use kotoba_core::cid::KotobaCid;

/// A parsed kotoba-git snapshot manifest (`kotoba-git-snapshot v1`).
#[derive(Debug, Default, Clone)]
pub struct Manifest {
    /// `oid-hex → object CID` for every object in the repo.
    objects: Vec<(String, KotobaCid)>,
    /// `refname → oid-hex` (direct refs).
    refs: HashMap<String, String>,
    /// `refname → target refname` (symbolic refs, e.g. HEAD).
    symbolic: HashMap<String, String>,
    oid_to_cid: HashMap<String, KotobaCid>,
}

impl Manifest {
    /// Parse the line-oriented manifest produced by `GitStore::snapshot_manifest`.
    pub fn parse(bytes: &[u8]) -> Result<Self, String> {
        let text = std::str::from_utf8(bytes).map_err(|_| "manifest not utf-8".to_string())?;
        let mut lines = text.lines();
        match lines.next() {
            Some(l) if l.starts_with("kotoba-git-snapshot ") => {}
            _ => return Err("missing kotoba-git-snapshot header".into()),
        }
        let mut m = Manifest::default();
        for line in lines {
            let mut p = line.splitn(3, ' ');
            match (p.next(), p.next(), p.next()) {
                (Some("O"), Some(oid), Some(cid_mb)) => {
                    let cid = KotobaCid::from_multibase(cid_mb)
                        .ok_or_else(|| format!("bad object cid: {cid_mb}"))?;
                    m.objects.push((oid.to_string(), cid.clone()));
                    m.oid_to_cid.insert(oid.to_string(), cid);
                }
                (Some("R"), Some(name), Some(oid)) => {
                    m.refs.insert(name.to_string(), oid.to_string());
                }
                (Some("S"), Some(name), Some(target)) => {
                    m.symbolic.insert(name.to_string(), target.to_string());
                }
                _ => {} // tolerate blank / unknown lines
            }
        }
        Ok(m)
    }

    /// Every object CID the repo comprises.
    pub fn object_cids(&self) -> Vec<KotobaCid> {
        self.objects.iter().map(|(_, c)| c.clone()).collect()
    }

    /// The subset of object CIDs not satisfied by `have` — the bitswap `want` list
    /// a peer must fetch (then `rehydrate`) to become a full replica.
    pub fn fetch_plan(&self, have: impl Fn(&KotobaCid) -> bool) -> Vec<KotobaCid> {
        self.object_cids()
            .into_iter()
            .filter(|c| !have(c))
            .collect()
    }

    /// Resolve a ref to its object CID, following one level of symbolic ref
    /// (e.g. `HEAD → refs/heads/main → <oid> → <cid>`).
    pub fn head_cid(&self, refname: &str) -> Option<KotobaCid> {
        let direct = self
            .refs
            .get(refname)
            .or_else(|| self.symbolic.get(refname).and_then(|t| self.refs.get(t)))?;
        self.oid_to_cid.get(direct).cloned()
    }

    /// True iff this manifest's head ref resolves to exactly the G1-verified
    /// `head` CID — the binding that makes a fetched manifest trustworthy. Tries
    /// `refs/heads/main` then `HEAD`.
    pub fn binds_head(&self, head: &KotobaCid) -> bool {
        self.head_cid("refs/heads/main")
            .or_else(|| self.head_cid("HEAD"))
            .map(|c| &c == head)
            .unwrap_or(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cid(seed: &[u8]) -> KotobaCid {
        KotobaCid::from_bytes(seed)
    }

    fn manifest_text(head_cid: &KotobaCid, other: &KotobaCid) -> Vec<u8> {
        format!(
            "kotoba-git-snapshot v1\n\
             O aaaa {head}\n\
             O bbbb {other}\n\
             R refs/heads/main aaaa\n\
             S HEAD refs/heads/main\n",
            head = head_cid.to_multibase(),
            other = other.to_multibase(),
        )
        .into_bytes()
    }

    #[test]
    fn parses_objects_refs_and_symbolic() {
        let head = cid(b"head-commit");
        let tree = cid(b"tree");
        let m = Manifest::parse(&manifest_text(&head, &tree)).unwrap();
        assert_eq!(m.object_cids().len(), 2);
        assert_eq!(m.head_cid("refs/heads/main"), Some(head.clone()));
        assert_eq!(m.head_cid("HEAD"), Some(head), "symbolic HEAD follows to main");
    }

    #[test]
    fn fetch_plan_excludes_already_held() {
        let head = cid(b"head-commit");
        let tree = cid(b"tree");
        let m = Manifest::parse(&manifest_text(&head, &tree)).unwrap();
        // already hold the tree → only the head must be fetched
        let plan = m.fetch_plan(|c| c == &tree);
        assert_eq!(plan, vec![head]);
        // hold nothing → fetch both
        assert_eq!(m.fetch_plan(|_| false).len(), 2);
        // hold everything → fetch none
        assert!(m.fetch_plan(|_| true).is_empty());
    }

    #[test]
    fn binds_head_only_to_the_real_head() {
        let head = cid(b"head-commit");
        let tree = cid(b"tree");
        let m = Manifest::parse(&manifest_text(&head, &tree)).unwrap();
        assert!(m.binds_head(&head), "manifest's main → head must bind");
        assert!(!m.binds_head(&tree), "a non-head CID must not bind");
        assert!(!m.binds_head(&cid(b"forged")));
    }

    #[test]
    fn rejects_bad_header_and_cid() {
        assert!(Manifest::parse(b"not a manifest\nO a b\n").is_err());
        assert!(Manifest::parse(b"kotoba-git-snapshot v1\nO aaaa not-a-cid\n").is_err());
    }
}
