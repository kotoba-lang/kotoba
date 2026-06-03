use serde::{Deserialize, Serialize};
/// Session = lifecycle wrapper around X3DH + Double Ratchet.
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use x25519_dalek::StaticSecret;

use crate::{
    identity::IdentityKeyPair,
    prekey::{PreKey, PreKeyBundle, SignedPreKey},
    ratchet::{RatchetMessage, RatchetState},
    x3dh::{x3dh_init_receiver, x3dh_init_sender},
    SignalError,
};

/// An established 1:1 session between two peers.
pub struct Session {
    pub peer_did: String,
    pub device_id: String,
    pub ratchet: RatchetState,
}

impl Session {
    /// Sender: establish a new session from a PreKeyBundle.
    pub fn initiate(
        local_ik: &IdentityKeyPair,
        bundle: &PreKeyBundle,
    ) -> Result<(Self, Vec<u8>), SignalError> {
        let out = x3dh_init_sender(local_ik, bundle)?;
        let ep = out
            .ephemeral_public
            .expect("sender always has ephemeral public");

        let spk_pub: [u8; 32] = bundle
            .signed_prekey
            .as_slice()
            .try_into()
            .map_err(|_| SignalError::BadSignature)?;

        let ratchet = RatchetState::init_sender(out.shared_secret, spk_pub);
        let session = Session {
            peer_did: bundle.did.clone(),
            device_id: bundle.device_id.clone(),
            ratchet,
        };
        Ok((session, ep.to_vec()))
    }

    /// Receiver: establish a session from an incoming initial message.
    pub fn accept(
        local_ik: &IdentityKeyPair,
        signed_prekey: &SignedPreKey,
        one_time_prekey: Option<&PreKey>,
        sender_ik_pub: &crate::identity::IdentityKey,
        ephemeral_pub: &[u8; 32],
        sender_did: &str,
        sender_device: &str,
    ) -> Result<Self, SignalError> {
        let out = x3dh_init_receiver(
            local_ik,
            signed_prekey,
            one_time_prekey,
            sender_ik_pub,
            ephemeral_pub,
        )?;

        // Receiver uses SPK private as the initial ratchet key
        let spk_priv_bytes: [u8; 32] = signed_prekey.private.to_bytes();
        let spk_priv = StaticSecret::from(spk_priv_bytes);
        let ratchet = RatchetState::init_receiver(out.shared_secret, spk_priv);

        Ok(Session {
            peer_did: sender_did.to_string(),
            device_id: sender_device.to_string(),
            ratchet,
        })
    }

    pub fn encrypt(&mut self, plaintext: &[u8]) -> Result<RatchetMessage, SignalError> {
        self.ratchet.encrypt(plaintext)
    }

    pub fn decrypt(&mut self, msg: &RatchetMessage) -> Result<Vec<u8>, SignalError> {
        self.ratchet.decrypt(msg)
    }
}

// ── Store trait ────────────────────────────────────────────────────────────────

pub trait SessionStore: Send + Sync {
    fn load_session(
        &self,
        peer_did: &str,
        device_id: &str,
    ) -> impl std::future::Future<Output = Option<SerializedSession>> + Send;

    fn store_session(
        &self,
        peer_did: &str,
        device_id: &str,
        session: SerializedSession,
    ) -> impl std::future::Future<Output = ()> + Send;
}

/// Serializable session snapshot (ratchet state is persisted as opaque bytes).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializedSession {
    pub peer_did: String,
    pub device_id: String,
    /// CBOR or JSON blob of ratchet state (implementation-defined).
    pub state_blob: Vec<u8>,
}

// ── In-memory store ────────────────────────────────────────────────────────────

#[derive(Default, Clone)]
pub struct InMemorySessionStore {
    sessions: Arc<RwLock<HashMap<String, SerializedSession>>>,
}

impl InMemorySessionStore {
    pub fn new() -> Self {
        Self::default()
    }

    fn session_key(peer_did: &str, device_id: &str) -> String {
        format!("{peer_did}:{device_id}")
    }
}

impl SessionStore for InMemorySessionStore {
    async fn load_session(&self, peer_did: &str, device_id: &str) -> Option<SerializedSession> {
        self.sessions
            .read()
            .await
            .get(&Self::session_key(peer_did, device_id))
            .cloned()
    }

    async fn store_session(&self, peer_did: &str, device_id: &str, session: SerializedSession) {
        self.sessions
            .write()
            .await
            .insert(Self::session_key(peer_did, device_id), session);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_session(peer_did: &str, device_id: &str) -> SerializedSession {
        SerializedSession {
            peer_did: peer_did.to_string(),
            device_id: device_id.to_string(),
            state_blob: b"opaque-ratchet-state".to_vec(),
        }
    }

    // ── X3DH establishment via the public Session API ─────────────────────────

    /// A well-formed bundle for `ik`, with a valid signed-prekey signature.
    fn valid_bundle(ik: &IdentityKeyPair, spk: &SignedPreKey, opk: &PreKey) -> PreKeyBundle {
        PreKeyBundle {
            did: "did:plc:bob".into(),
            device_id: "dev-1".into(),
            identity_key: ik.public_key(),
            signed_prekey: spk.public_bytes().to_vec(),
            signed_prekey_id: spk.id,
            signed_prekey_sig: spk.signature.clone(),
            one_time_prekey: Some(opk.public_bytes().to_vec()),
            one_time_prekey_id: Some(opk.id),
        }
    }

    #[test]
    fn initiate_accept_roundtrip_succeeds() {
        // Positive control: a valid bundle establishes a session end-to-end through
        // the public API. Without this, the rejection tests below could pass
        // vacuously (e.g. if initiate always errored).
        let alice_ik = IdentityKeyPair::generate();
        let bob_ik = IdentityKeyPair::generate();
        let bob_spk = SignedPreKey::generate(1, &bob_ik);
        let bob_opk = PreKey::generate(100);
        let bundle = valid_bundle(&bob_ik, &bob_spk, &bob_opk);

        let (mut alice, ep) = Session::initiate(&alice_ik, &bundle).expect("valid bundle");
        let ep: [u8; 32] = ep.try_into().unwrap();
        let mut bob = Session::accept(
            &bob_ik,
            &bob_spk,
            Some(&bob_opk),
            &alice_ik.public_key(),
            &ep,
            "did:plc:alice",
            "dev-a",
        )
        .expect("accept valid X3DH");

        let ct = alice.encrypt(b"hello").unwrap();
        assert_eq!(bob.decrypt(&ct).unwrap(), b"hello");
    }

    #[test]
    fn initiate_rejects_forged_signed_prekey_signature() {
        // Anti-MITM at the PUBLIC entry point: x3dh_init_sender verifies the SPK
        // signature, but callers go through Session::initiate — this proves the
        // rejection propagates there. A bundle whose signature is tampered must not
        // establish a session.
        let alice_ik = IdentityKeyPair::generate();
        let bob_ik = IdentityKeyPair::generate();
        let bob_spk = SignedPreKey::generate(1, &bob_ik);
        let bob_opk = PreKey::generate(100);
        let mut bundle = valid_bundle(&bob_ik, &bob_spk, &bob_opk);
        bundle.signed_prekey_sig[0] ^= 0xFF; // flip a byte of the signature

        assert!(
            matches!(
                Session::initiate(&alice_ik, &bundle),
                Err(SignalError::BadSignature)
            ),
            "a forged signed-prekey signature must be rejected by Session::initiate"
        );
    }

    #[test]
    fn initiate_rejects_substituted_prekey_with_stale_signature() {
        // The realistic substitution: a malicious PDS swaps the signed pre-key for
        // an attacker-controlled key but cannot re-sign it with the victim's identity
        // key, so it leaves the original (now-mismatched) signature. The signature is
        // over the SPK bytes, so the swap must be detected as BadSignature.
        let alice_ik = IdentityKeyPair::generate();
        let bob_ik = IdentityKeyPair::generate();
        let bob_spk = SignedPreKey::generate(1, &bob_ik);
        let bob_opk = PreKey::generate(100);
        let mut bundle = valid_bundle(&bob_ik, &bob_spk, &bob_opk);

        // Attacker's own SPK (signed by a DIFFERENT identity), pubkey substituted in
        // while the bundle keeps bob's original signature.
        let attacker_ik = IdentityKeyPair::generate();
        let attacker_spk = SignedPreKey::generate(1, &attacker_ik);
        bundle.signed_prekey = attacker_spk.public_bytes().to_vec();

        assert!(
            matches!(
                Session::initiate(&alice_ik, &bundle),
                Err(SignalError::BadSignature)
            ),
            "a substituted pre-key under a stale signature must be rejected"
        );
    }

    #[tokio::test]
    async fn load_returns_none_when_empty() {
        let store = InMemorySessionStore::new();
        assert!(store.load_session("did:key:zA", "device-1").await.is_none());
    }

    #[tokio::test]
    async fn store_and_load_roundtrip() {
        let store = InMemorySessionStore::new();
        let session = make_session("did:key:zA", "device-1");
        store
            .store_session("did:key:zA", "device-1", session.clone())
            .await;
        let loaded = store.load_session("did:key:zA", "device-1").await;
        assert!(loaded.is_some());
        let loaded = loaded.unwrap();
        assert_eq!(loaded.peer_did, session.peer_did);
        assert_eq!(loaded.device_id, session.device_id);
        assert_eq!(loaded.state_blob, session.state_blob);
    }

    #[tokio::test]
    async fn different_devices_are_isolated() {
        let store = InMemorySessionStore::new();
        store
            .store_session(
                "did:key:zA",
                "device-1",
                make_session("did:key:zA", "device-1"),
            )
            .await;
        assert!(store.load_session("did:key:zA", "device-2").await.is_none());
    }

    #[tokio::test]
    async fn overwrite_session_updates_blob() {
        let store = InMemorySessionStore::new();
        let s1 = make_session("did:key:zA", "d1");
        let s2 = SerializedSession {
            state_blob: b"updated-blob".to_vec(),
            ..s1.clone()
        };
        store.store_session("did:key:zA", "d1", s1).await;
        store.store_session("did:key:zA", "d1", s2.clone()).await;
        let loaded = store.load_session("did:key:zA", "d1").await.unwrap();
        assert_eq!(loaded.state_blob, b"updated-blob");
    }

    #[test]
    fn serialized_session_json_roundtrip() {
        let s = make_session("did:key:zA", "dev");
        let json = serde_json::to_string(&s).unwrap();
        let back: SerializedSession = serde_json::from_str(&json).unwrap();
        assert_eq!(back.peer_did, s.peer_did);
        assert_eq!(back.state_blob, s.state_blob);
    }

    #[test]
    fn serialized_session_clone_is_independent() {
        let s = make_session("did:key:zB", "dev-2");
        let c = s.clone();
        assert_eq!(c.peer_did, s.peer_did);
        assert_eq!(c.device_id, s.device_id);
        assert_eq!(c.state_blob, s.state_blob);
    }

    #[test]
    fn serialized_session_debug_contains_did() {
        let s = make_session("did:key:zDebug", "dev");
        let dbg = format!("{s:?}");
        assert!(dbg.contains("did:key:zDebug"));
    }

    #[tokio::test]
    async fn multiple_peers_stored_independently() {
        let store = InMemorySessionStore::new();
        let s1 = make_session("did:key:zA", "d1");
        let s2 = make_session("did:key:zB", "d1");
        store.store_session("did:key:zA", "d1", s1).await;
        store.store_session("did:key:zB", "d1", s2).await;

        let loaded_a = store.load_session("did:key:zA", "d1").await;
        let loaded_b = store.load_session("did:key:zB", "d1").await;
        assert!(loaded_a.is_some());
        assert!(loaded_b.is_some());
        assert_eq!(loaded_a.unwrap().peer_did, "did:key:zA");
        assert_eq!(loaded_b.unwrap().peer_did, "did:key:zB");
    }

    #[tokio::test]
    async fn store_clone_shares_state() {
        let store = InMemorySessionStore::new();
        let cloned = store.clone();
        let s = make_session("did:key:zC", "dev-c");
        store.store_session("did:key:zC", "dev-c", s).await;
        // The clone wraps the same Arc<RwLock> so it must see the new entry
        let loaded = cloned.load_session("did:key:zC", "dev-c").await;
        assert!(loaded.is_some(), "clone should share the underlying map");
    }

    #[test]
    fn serialized_session_empty_blob() {
        let s = SerializedSession {
            peer_did: "did:key:zA".to_string(),
            device_id: "d1".to_string(),
            state_blob: vec![],
        };
        let json = serde_json::to_string(&s).unwrap();
        let back: SerializedSession = serde_json::from_str(&json).unwrap();
        assert!(back.state_blob.is_empty());
    }

    #[tokio::test]
    async fn new_and_default_produce_equivalent_stores() {
        let s1 = InMemorySessionStore::new();
        let s2 = InMemorySessionStore::default();
        // Both should start empty
        assert!(s1.load_session("any", "any").await.is_none());
        assert!(s2.load_session("any", "any").await.is_none());
    }
}
