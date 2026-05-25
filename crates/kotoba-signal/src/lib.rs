//! Signal Protocol E2E for Kotoba.
//! SSoT replacing `@gftd/signal` (`10-protocol/signal/`).
//!
//! Wire format `signal:v1:{base64url}` is preserved for compatibility.

pub mod identity;
pub mod prekey;
pub mod x3dh;
pub mod ratchet;
pub mod session;
pub mod group;
pub mod store;
pub mod message;

pub use identity::{IdentityKey, IdentityKeyPair, DeviceId};
pub use prekey::{PreKey, SignedPreKey, PreKeyBundle, PreKeyId, SignedPreKeyId};
pub use x3dh::{x3dh_init_sender, x3dh_init_receiver, X3dhOutput};
pub use ratchet::{RatchetState, RatchetMessage};
pub use session::{Session, SessionStore, InMemorySessionStore};
pub use group::{SenderKeyState, SenderKeyMessage, GroupSession, InMemorySenderKeyStore};
pub use store::{SignalStore, InMemorySignalStore};
pub use message::{SignalMessage, MessageType, ThreadMessage, Reaction};

pub use kotoba_crypto::envelope::{SIGNAL_VAL_PREFIX, encrypt_field, decrypt_field};

#[derive(Debug, thiserror::Error)]
pub enum SignalError {
    #[error("crypto: {0}")]
    Crypto(#[from] kotoba_crypto::aead::CryptoError),
    #[error("no session for {0}")]
    NoSession(String),
    #[error("no pre-key {0}")]
    NoPreKey(u32),
    #[error("no signed pre-key {0}")]
    NoSignedPreKey(u32),
    #[error("signature verification failed")]
    BadSignature,
    #[error("message counter mismatch")]
    CounterMismatch,
    #[error("serialization: {0}")]
    Serde(#[from] serde_json::Error),
    #[error("store error: {0}")]
    Store(String),
}
