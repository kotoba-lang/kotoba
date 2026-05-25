/// Session = lifecycle wrapper around X3DH + Double Ratchet.
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use x25519_dalek::StaticSecret;
use serde::{Deserialize, Serialize};

use crate::{
    identity::IdentityKeyPair,
    prekey::{PreKey, PreKeyBundle, SignedPreKey},
    ratchet::{RatchetMessage, RatchetState},
    x3dh::{x3dh_init_receiver, x3dh_init_sender},
    SignalError,
};

/// An established 1:1 session between two peers.
pub struct Session {
    pub peer_did:   String,
    pub device_id:  String,
    pub ratchet:    RatchetState,
}

impl Session {
    /// Sender: establish a new session from a PreKeyBundle.
    pub fn initiate(
        local_ik:  &IdentityKeyPair,
        bundle:    &PreKeyBundle,
    ) -> Result<(Self, Vec<u8>), SignalError> {
        let out = x3dh_init_sender(local_ik, bundle)?;
        let ep = out.ephemeral_public.expect("sender always has ephemeral public");

        let spk_pub: [u8; 32] = bundle
            .signed_prekey
            .as_slice()
            .try_into()
            .map_err(|_| SignalError::BadSignature)?;

        let ratchet = RatchetState::init_sender(out.shared_secret, spk_pub);
        let session = Session {
            peer_did:  bundle.did.clone(),
            device_id: bundle.device_id.clone(),
            ratchet,
        };
        Ok((session, ep.to_vec()))
    }

    /// Receiver: establish a session from an incoming initial message.
    pub fn accept(
        local_ik:        &IdentityKeyPair,
        signed_prekey:   &SignedPreKey,
        one_time_prekey: Option<&PreKey>,
        sender_ik_pub:   &crate::identity::IdentityKey,
        ephemeral_pub:   &[u8; 32],
        sender_did:      &str,
        sender_device:   &str,
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
            peer_did:  sender_did.to_string(),
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
        &self, peer_did: &str, device_id: &str,
    ) -> impl std::future::Future<Output = Option<SerializedSession>> + Send;

    fn store_session(
        &self, peer_did: &str, device_id: &str, session: SerializedSession,
    ) -> impl std::future::Future<Output = ()> + Send;
}

/// Serializable session snapshot (ratchet state is persisted as opaque bytes).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializedSession {
    pub peer_did:   String,
    pub device_id:  String,
    /// CBOR or JSON blob of ratchet state (implementation-defined).
    pub state_blob: Vec<u8>,
}

// ── In-memory store ────────────────────────────────────────────────────────────

#[derive(Default, Clone)]
pub struct InMemorySessionStore {
    sessions: Arc<RwLock<HashMap<String, SerializedSession>>>,
}

impl InMemorySessionStore {
    pub fn new() -> Self { Self::default() }

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
