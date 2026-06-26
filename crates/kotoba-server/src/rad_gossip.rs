//! kotoba-rad sigref gossip (ADR-2606251200 G1) — announce signed sigref heads
//! over gossipsub so peers learn a repo's new head + who attested it WITHOUT a
//! central HTTP node (the Heartwood-style "gossip of signed refs", reusing (a)'s
//! `did:key`/delegate model as the auth root).
//!
//! This module is the **transport-independent core**: the topic, the wire
//! payload, and the delegate-membership check. The two layers on top are:
//!  - publish/subscribe wiring over `kotoba_net::KotobaSwarm` (`publish(topic,
//!    bytes)` / `subscribe(topic)`) — a follow-up slice, and
//!  - the cryptographic head→signer binding (§sig-binding) — see below.
//!
//! §sig-binding: a `SigrefAnnounce.sig` may be EITHER the member's Ed25519 over
//! the head (the `kotoba_rad.cljc` / kotoba.cljs form, which binds by→head and is
//! peer-verifiable offline) OR the push CACAO the server received (the
//! `git_http::rad_attest_push` form, which proves a delegate pushed but does NOT
//! itself bind the specific head — no-server-key means the node cannot mint an
//! over-head signature). Full gossip verification therefore needs the canonical
//! sigref to carry the over-head signature; `by_is_delegate` here is the
//! delegate-membership gate that BOTH forms must pass first.

use serde::{Deserialize, Serialize};

/// gossipsub topic for a repo's signed heads: `rad/sigref/<RID>`. `KotobaSwarm`
/// prefixes `kotoba/`, yielding `kotoba/rad/sigref/<RID>`. The RID is the genesis
/// CID (ASCII multibase, well under the 256-byte topic cap).
pub fn sigref_topic(rid: &str) -> String {
    format!("rad/sigref/{rid}")
}

/// A signed-head announcement — the `:rad/sigref` datoms in wire form.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SigrefAnnounce {
    /// Repository Identity (genesis CID) the head belongs to.
    pub rid: String,
    /// The attested git head (KotobaCid multibase of the head commit object).
    pub head: String,
    /// The attesting delegate's `did:key` (any encoding form).
    pub by: String,
    /// Member signature over `head` — Ed25519-over-head hex OR the push CACAO
    /// (see the module §sig-binding note).
    pub sig: String,
}

impl SigrefAnnounce {
    /// CBOR (dag-cbor-compatible) wire bytes for gossipsub publish.
    pub fn encode(&self) -> Vec<u8> {
        let mut v = Vec::new();
        ciborium::into_writer(self, &mut v).expect("cbor encode SigrefAnnounce");
        v
    }

    /// Decode a gossipsub payload back into an announcement.
    pub fn decode(bytes: &[u8]) -> Result<Self, String> {
        ciborium::from_reader(bytes).map_err(|e| e.to_string())
    }

    /// True iff `by` is one of the repo's rad delegates, compared by KEY across
    /// encodings (W3C `z6Mk…` ⇄ kotoba-rad `z<hex>`) via
    /// [`kotoba_auth::did_key::did_keys_equal`]. This is the membership gate every
    /// announcement must pass before its signature is trusted to advance a head.
    pub fn by_is_delegate(&self, delegates: &[String]) -> bool {
        delegates
            .iter()
            .any(|d| kotoba_auth::did_key::did_keys_equal(d, &self.by))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_auth::did_key::{ed25519_pubkey_to_did_key, ed25519_pubkey_to_did_key_hex};
    use ed25519_dalek::SigningKey;

    const RID: &str = "bafrid0000000000000000000000000000000000000000000000000000";

    #[test]
    fn topic_is_rad_sigref_rid() {
        let t = sigref_topic(RID);
        assert_eq!(t, format!("rad/sigref/{RID}"));
        // Must satisfy KotobaSwarm's gossipsub-topic invariant once `kotoba/`-
        // prefixed: visible ASCII, < 256 bytes (mirrors checked_gossipsub_topic,
        // asserted here without the optional kotoba-net dependency).
        let full = format!("kotoba/{t}");
        assert!(full.len() < 256);
        assert!(full.bytes().all(|b| (0x21..=0x7e).contains(&b)));
    }

    #[test]
    fn encode_decode_round_trips() {
        let a = SigrefAnnounce {
            rid: RID.into(),
            head: "bafhead123".into(),
            by: "did:key:z6MkExample".into(),
            sig: "deadbeef".into(),
        };
        let bytes = a.encode();
        assert_eq!(SigrefAnnounce::decode(&bytes).unwrap(), a);
    }

    #[test]
    fn decode_rejects_garbage() {
        assert!(SigrefAnnounce::decode(&[0xff, 0x00, 0x13, 0x37]).is_err());
    }

    #[test]
    fn by_is_delegate_matches_across_encodings() {
        let sk = SigningKey::from_bytes(&[9u8; 32]);
        let pk = sk.verifying_key();
        let announce = SigrefAnnounce {
            rid: RID.into(),
            head: "bafhead".into(),
            by: ed25519_pubkey_to_did_key(pk.as_bytes()), // W3C z6Mk… form
            sig: "sig".into(),
        };
        // delegate registered in the kotoba-rad z<hex> form for the SAME key
        let delegates = vec![ed25519_pubkey_to_did_key_hex(pk.as_bytes())];
        assert!(announce.by_is_delegate(&delegates), "cross-encoding match");

        // a different key is not a delegate
        let other = ed25519_pubkey_to_did_key(SigningKey::from_bytes(&[1u8; 32]).verifying_key().as_bytes());
        assert!(!announce.by_is_delegate(&[other]));
        assert!(!announce.by_is_delegate(&[]));
    }
}
