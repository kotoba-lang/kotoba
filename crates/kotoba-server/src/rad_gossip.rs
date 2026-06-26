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

use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};

/// Why a [`SigrefAnnounce`] failed verification (ADR-2606251200 G1, A path).
#[derive(Debug, PartialEq, Eq)]
pub enum AnnounceError {
    /// `by` is not one of the repo's rad delegates.
    NotADelegate,
    /// `by` is not a parseable Ed25519 `did:key`.
    BadDid(String),
    /// `head` is not a decodable multibase CID.
    BadHeadCid(String),
    /// `sig` is not valid hex or not a 64-byte Ed25519 signature.
    BadSig(String),
    /// The signature did not verify over the head bytes.
    SigVerifyFailed,
    /// An incoming gossip payload did not decode to a [`SigrefAnnounce`].
    BadPayload(String),
    /// No registered rad identity (delegates) for the announced RID.
    UnknownRid(String),
}

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
    /// The kotoba-git snapshot **manifest** CID (multibase), advisory — lets a
    /// peer fetch the repo's objects for G2 replication. Unsigned: a peer trusts
    /// it only after the manifest [`crate::rad_sync::Manifest::binds_head`] this
    /// announcement's verified `head`. Absent on CACAO-backed (local) sigrefs.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub manifest: Option<String>,
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

    /// Verify the announcement (ADR-2606251200 G1, the **A** sig-binding):
    /// `by` is one of the repo's `delegates` AND `sig` is `by`'s Ed25519
    /// signature over the head's CID bytes — the `kotoba_rad.cljc` / kotoba.cljs
    /// convention, where the signed message is `multibase::decode(head)` (the
    /// `b`-prefixed base32lower CID, decoded — exactly cljc's `cid->bytes`). This
    /// binds `by → head` cryptographically, so any peer can verify offline before
    /// advancing the repo's head to `self.head` — no node trust, no-server-key.
    pub fn verify(&self, delegates: &[String]) -> Result<(), AnnounceError> {
        if !self.by_is_delegate(delegates) {
            return Err(AnnounceError::NotADelegate);
        }
        let pk_bytes = kotoba_auth::did_key::parse_ed25519_did_key(&self.by)
            .map_err(|e| AnnounceError::BadDid(e.to_string()))?;
        let vk = VerifyingKey::from_bytes(&pk_bytes)
            .map_err(|e| AnnounceError::BadDid(e.to_string()))?;
        let (_, msg) =
            multibase::decode(&self.head).map_err(|e| AnnounceError::BadHeadCid(e.to_string()))?;
        let sig_bytes = hex::decode(&self.sig).map_err(|e| AnnounceError::BadSig(e.to_string()))?;
        let sig =
            Signature::from_slice(&sig_bytes).map_err(|e| AnnounceError::BadSig(e.to_string()))?;
        vk.verify(&msg, &sig)
            .map_err(|_| AnnounceError::SigVerifyFailed)
    }
}

/// Subscribe-side decision (ADR-2606251200 G1): decode an incoming gossip
/// payload, look up the announced RID's delegates in the registry, and verify.
/// On `Ok`, the caller may advance that repo's head to `announce.head`. Pure —
/// the swarm I/O (subscribe to `sigref_topic(rid)`, receive bytes) and the head
/// store are the caller's (a thin `net_actor` wire); the publish side is simply
/// `swarm.publish(&sigref_topic(&a.rid), a.encode())` on a fresh attestation.
pub fn handle_incoming_sigref(
    bytes: &[u8],
    registry: &crate::rad_registry::RadRegistry,
) -> Result<SigrefAnnounce, AnnounceError> {
    let announce = SigrefAnnounce::decode(bytes).map_err(AnnounceError::BadPayload)?;
    let delegates = registry
        .resolve(&announce.rid)
        .map(|r| r.delegates.clone())
        .ok_or_else(|| AnnounceError::UnknownRid(announce.rid.clone()))?;
    announce.verify(&delegates)?;
    Ok(announce)
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
            manifest: Some("bafmanifest".into()),
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
            manifest: None,
        };
        // delegate registered in the kotoba-rad z<hex> form for the SAME key
        let delegates = vec![ed25519_pubkey_to_did_key_hex(pk.as_bytes())];
        assert!(announce.by_is_delegate(&delegates), "cross-encoding match");

        // a different key is not a delegate
        let other = ed25519_pubkey_to_did_key(SigningKey::from_bytes(&[1u8; 32]).verifying_key().as_bytes());
        assert!(!announce.by_is_delegate(&[other]));
        assert!(!announce.by_is_delegate(&[]));
    }

    use ed25519_dalek::Signer;
    use kotoba_core::cid::KotobaCid;

    /// Build an announcement the way a member git client would: sign the head's
    /// CID bytes (`multibase::decode`) with the member key — the cljc convention.
    fn signed_announce(seed: [u8; 32], head: &str) -> SigrefAnnounce {
        let sk = SigningKey::from_bytes(&seed);
        let (_, msg) = multibase::decode(head).unwrap();
        let sig = sk.sign(&msg);
        SigrefAnnounce {
            rid: RID.into(),
            head: head.into(),
            by: ed25519_pubkey_to_did_key_hex(sk.verifying_key().as_bytes()), // z<hex> form
            sig: hex::encode(sig.to_bytes()),
            manifest: None,
        }
    }

    #[test]
    fn verify_accepts_over_head_sig_from_delegate_cross_encoding() {
        let head = KotobaCid::from_bytes(b"git-head-commit-object").to_multibase();
        let a = signed_announce([5u8; 32], &head);
        // delegate registered in the W3C z6Mk… form; announce.by is z<hex> — same key.
        let sk = SigningKey::from_bytes(&[5u8; 32]);
        let delegates = vec![ed25519_pubkey_to_did_key(sk.verifying_key().as_bytes())];
        assert_eq!(a.verify(&delegates), Ok(()));
    }

    #[test]
    fn verify_rejects_non_delegate() {
        let head = KotobaCid::from_bytes(b"h").to_multibase();
        let a = signed_announce([5u8; 32], &head); // signed by key 5
        let other = ed25519_pubkey_to_did_key(SigningKey::from_bytes(&[7u8; 32]).verifying_key().as_bytes());
        assert_eq!(a.verify(&[other]), Err(AnnounceError::NotADelegate));
    }

    #[test]
    fn verify_rejects_tampered_head() {
        // Sign head A, then announce head B with the same sig → sig is over the
        // wrong message → SigVerifyFailed (a relay cannot swap the head).
        let head_a = KotobaCid::from_bytes(b"real-head").to_multibase();
        let head_b = KotobaCid::from_bytes(b"forged-head").to_multibase();
        let mut a = signed_announce([5u8; 32], &head_a);
        a.head = head_b;
        let sk = SigningKey::from_bytes(&[5u8; 32]);
        let delegates = vec![ed25519_pubkey_to_did_key_hex(sk.verifying_key().as_bytes())];
        assert_eq!(a.verify(&delegates), Err(AnnounceError::SigVerifyFailed));
    }

    #[test]
    fn verify_rejects_bad_sig_hex() {
        let head = KotobaCid::from_bytes(b"h").to_multibase();
        let mut a = signed_announce([5u8; 32], &head);
        a.sig = "not-hex".into();
        let sk = SigningKey::from_bytes(&[5u8; 32]);
        let delegates = vec![ed25519_pubkey_to_did_key_hex(sk.verifying_key().as_bytes())];
        assert!(matches!(a.verify(&delegates), Err(AnnounceError::BadSig(_))));
    }

    // ── subscribe-side: handle_incoming_sigref (registry-driven verify) ───────

    fn registry_with_delegate(seed: [u8; 32]) -> crate::rad_registry::RadRegistry {
        let mut reg = crate::rad_registry::RadRegistry::default();
        // delegate registered in the W3C z6Mk… form; signed_announce.by is z<hex>.
        let dele = ed25519_pubkey_to_did_key(SigningKey::from_bytes(&seed).verifying_key().as_bytes());
        reg.ingest_journal(&format!(
            "[{RID:?} :rad/type :identity 1 :add]\n[{RID:?} :rad/delegate {dele:?} 1 :add]\n"
        ))
        .unwrap();
        reg
    }

    #[test]
    fn handle_incoming_accepts_verified_announce_for_known_rid() {
        let head = KotobaCid::from_bytes(b"gossiped-head").to_multibase();
        let a = signed_announce([5u8; 32], &head);
        let reg = registry_with_delegate([5u8; 32]);
        let got = handle_incoming_sigref(&a.encode(), &reg).expect("known rid + valid sig");
        assert_eq!(got.head, head);
    }

    #[test]
    fn handle_incoming_rejects_unknown_rid() {
        let head = KotobaCid::from_bytes(b"h").to_multibase();
        let a = signed_announce([5u8; 32], &head);
        let reg = crate::rad_registry::RadRegistry::default(); // empty
        assert!(matches!(
            handle_incoming_sigref(&a.encode(), &reg),
            Err(AnnounceError::UnknownRid(_))
        ));
    }

    #[test]
    fn handle_incoming_rejects_non_delegate_signer() {
        let head = KotobaCid::from_bytes(b"h").to_multibase();
        let a = signed_announce([7u8; 32], &head); // signed by key 7
        let reg = registry_with_delegate([5u8; 32]); // delegate is key 5
        assert_eq!(
            handle_incoming_sigref(&a.encode(), &reg),
            Err(AnnounceError::NotADelegate)
        );
    }

    #[test]
    fn handle_incoming_rejects_bad_payload() {
        let reg = crate::rad_registry::RadRegistry::default();
        assert!(matches!(
            handle_incoming_sigref(&[0xff, 0x00, 0x13, 0x37], &reg),
            Err(AnnounceError::BadPayload(_))
        ));
    }
}
