//! Mesh policy (KOTOBA Mesh M5): capability **links** + out-of-process provider
//! routing.
//!
//! A [`Link`] (ADR §5) is a CACAO-rooted grant binding a component to a
//! capability/provider — equivalent to a wasmCloud link definition AND a
//! Holochain cap grant/claim. This module owns the **policy decision** over the
//! active link set ("may component X invoke ability A on target T?") and the
//! **routing decision** for out-of-proc capabilities (local host-import vs a
//! remote provider node).
//!
//! Cryptographic CACAO chain verification is delegated to a [`LinkVerifier`]
//! hook (the server wires a `kotoba-auth`-backed impl), keeping this crate pure
//! — the same I/O-free-core + injected-verifier pattern as `kotoba-auth`'s
//! `EthRpc`.

use std::collections::BTreeMap;

use crate::protocol::{Heartbeat, Link};

/// Result of a [`LinkTable::authorize`] check.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinkDecision {
    pub allowed: bool,
    /// The link id that granted access (when allowed).
    pub link_id: Option<String>,
    pub reason: String,
}

impl LinkDecision {
    fn allow(link_id: &str) -> Self {
        Self {
            allowed: true,
            link_id: Some(link_id.to_string()),
            reason: "linked".into(),
        }
    }
    fn deny(reason: impl Into<String>) -> Self {
        Self {
            allowed: false,
            link_id: None,
            reason: reason.into(),
        }
    }
}

/// Verifies a link's CACAO delegation chain. Implemented in `kotoba-server`
/// against `kotoba-auth`; the pure default trusts links (verification done at
/// ingest elsewhere) so tests and the control-plane core need no crypto.
pub trait LinkVerifier {
    /// Return `Ok(delegator_did)` if `link`'s CACAO chain authorizes
    /// `link.ability` on `link.target` for `link.source`, else `Err(reason)`.
    fn verify(&self, link: &Link) -> Result<String, String>;
}

/// Permissive verifier (no crypto) — for the pure core and tests.
#[derive(Debug, Default, Clone, Copy)]
pub struct TrustOnIngest;

impl LinkVerifier for TrustOnIngest {
    fn verify(&self, link: &Link) -> Result<String, String> {
        Ok(link.source.clone())
    }
}

/// The active set of capability links — the mesh authorization policy.
#[derive(Debug, Clone, Default)]
pub struct LinkTable {
    links: BTreeMap<String, Link>, // link id → Link
}

impl LinkTable {
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert/replace a link **after** verifying its CACAO chain. Returns the
    /// delegator DID on success, or the rejection reason.
    pub fn put_verified<V: LinkVerifier>(
        &mut self,
        link: Link,
        verifier: &V,
    ) -> Result<String, String> {
        let did = verifier.verify(&link)?;
        self.links.insert(link.id.clone(), link);
        Ok(did)
    }

    /// Insert/replace a link without verification (use only when the caller has
    /// already verified, e.g. `put_verified` was done on another node).
    pub fn put(&mut self, link: Link) {
        self.links.insert(link.id.clone(), link);
    }

    pub fn remove(&mut self, id: &str) -> Option<Link> {
        self.links.remove(id)
    }

    pub fn len(&self) -> usize {
        self.links.len()
    }
    pub fn is_empty(&self) -> bool {
        self.links.is_empty()
    }
    pub fn iter(&self) -> impl Iterator<Item = &Link> {
        self.links.values()
    }

    /// May `source` invoke `ability` on `target`? Allowed iff an active link
    /// grants exactly that (source, target, ability). This is the runtime gate
    /// the host consults before letting a component reach a capability/provider.
    pub fn authorize(&self, source: &str, target: &str, ability: &str) -> LinkDecision {
        for l in self.links.values() {
            if l.source == source && l.target == target && l.ability == ability {
                return LinkDecision::allow(&l.id);
            }
        }
        LinkDecision::deny(format!(
            "no link grants {source} → {target} ({ability})"
        ))
    }
}

/// Where a capability invocation should run.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProviderRoute {
    /// The executing node supplies the capability in-process (host-import).
    Local,
    /// Forward to this provider node over the lattice (wRPC, out-of-proc).
    Remote(String),
    /// No node supplies the capability.
    Unavailable,
}

/// Decide where to run `cap`: in-proc if `local` advertises it, else the live
/// provider node with the most free capacity (deterministic tie-break by DID).
/// `fleet` is the set of live heartbeats (including, possibly, `local`).
pub fn route_capability(cap: &str, local: &Heartbeat, fleet: &[Heartbeat]) -> ProviderRoute {
    if local.caps.iter().any(|c| c == cap) {
        return ProviderRoute::Local;
    }
    let mut providers: Vec<&Heartbeat> = fleet
        .iter()
        .filter(|hb| hb.node_did != local.node_did && hb.caps.iter().any(|c| c == cap))
        .collect();
    providers.sort_by(|a, b| {
        b.free_gas
            .cmp(&a.free_gas)
            .then_with(|| a.node_did.cmp(&b.node_did))
    });
    match providers.first() {
        Some(hb) => ProviderRoute::Remote(hb.node_did.clone()),
        None => ProviderRoute::Unavailable,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::NodeRole;

    fn link(id: &str, source: &str, target: &str, ability: &str) -> Link {
        Link {
            id: id.into(),
            source: source.into(),
            target: target.into(),
            config: None,
            cacao: "bafyCacao".into(),
            ability: ability.into(),
        }
    }

    fn hb(did: &str, caps: &[&str], free_gas: u64) -> Heartbeat {
        Heartbeat {
            node_did: did.into(),
            roles: vec![NodeRole::Compute],
            labels: BTreeMap::new(),
            caps: caps.iter().map(|s| s.to_string()).collect(),
            free_gas,
            hosted: vec![],
            lat_ms: 0,
        }
    }

    #[test]
    fn authorize_allows_only_linked_triples() {
        let mut t = LinkTable::new();
        t.put(link("l1", "did:A", "cap/llm", "infer"));
        assert!(t.authorize("did:A", "cap/llm", "infer").allowed);
        // wrong ability / target / source all denied
        assert!(!t.authorize("did:A", "cap/llm", "train").allowed);
        assert!(!t.authorize("did:A", "cap/kqe", "infer").allowed);
        assert!(!t.authorize("did:B", "cap/llm", "infer").allowed);
    }

    #[test]
    fn deny_reason_is_descriptive() {
        let t = LinkTable::new();
        let d = t.authorize("did:A", "cap/llm", "infer");
        assert!(!d.allowed && d.link_id.is_none());
        assert!(d.reason.contains("did:A") && d.reason.contains("cap/llm"));
    }

    #[test]
    fn put_verified_runs_the_hook_and_remove_revokes() {
        let mut t = LinkTable::new();
        let did = t.put_verified(link("l1", "did:A", "cap/llm", "infer"), &TrustOnIngest).unwrap();
        assert_eq!(did, "did:A");
        assert!(t.authorize("did:A", "cap/llm", "infer").allowed);
        t.remove("l1");
        assert!(!t.authorize("did:A", "cap/llm", "infer").allowed);
    }

    #[test]
    fn verifier_rejection_blocks_the_link() {
        struct DenyAll;
        impl LinkVerifier for DenyAll {
            fn verify(&self, _l: &Link) -> Result<String, String> {
                Err("bad cacao".into())
            }
        }
        let mut t = LinkTable::new();
        let r = t.put_verified(link("l1", "did:A", "cap/llm", "infer"), &DenyAll);
        assert_eq!(r, Err("bad cacao".into()));
        assert!(t.is_empty());
    }

    #[test]
    fn link_table_len_is_empty_iter() {
        let mut t = LinkTable::new();
        assert!(t.is_empty() && t.len() == 0);
        t.put(link("l1", "did:A", "cap/llm", "infer"));
        t.put(link("l2", "did:B", "cap/kqe", "read"));
        assert_eq!(t.len(), 2);
        assert!(!t.is_empty());
        let ids: Vec<&str> = t.iter().map(|l| l.id.as_str()).collect();
        assert!(ids.contains(&"l1") && ids.contains(&"l2"));
    }

    #[test]
    fn route_remote_tie_break_is_by_did_when_gas_equal() {
        let local = hb("did:self", &["cap/kqe"], 100);
        let fleet = vec![
            hb("did:zzz", &["cap/llm"], 500),
            hb("did:aaa", &["cap/llm"], 500),
        ];
        assert_eq!(
            route_capability("cap/llm", &local, &fleet),
            ProviderRoute::Remote("did:aaa".into())
        );
    }

    #[test]
    fn route_prefers_local_then_richest_remote() {
        let local = hb("did:self", &["cap/kqe"], 100);
        let fleet = vec![
            hb("did:self", &["cap/kqe"], 100),
            hb("did:p1", &["cap/llm"], 500),
            hb("did:p2", &["cap/llm"], 900),
        ];
        // local supplies kqe
        assert_eq!(route_capability("cap/kqe", &local, &fleet), ProviderRoute::Local);
        // llm only remote → richest (p2)
        assert_eq!(
            route_capability("cap/llm", &local, &fleet),
            ProviderRoute::Remote("did:p2".into())
        );
        // nobody supplies evm
        assert_eq!(route_capability("cap/evm", &local, &fleet), ProviderRoute::Unavailable);
    }
}
