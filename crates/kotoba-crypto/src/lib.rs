//! kotoba-crypto — AEAD, HKDF, HPKE, key-wrap, and the passkey-rooted key tree.
//!
//! No `unsafe` is permitted in this crate: low-level nonce/key manipulation must
//! go through the audited RustCrypto primitives, never hand-rolled (ADR-2606014000 D5).
#![deny(unsafe_code)]

pub mod aead;
pub mod agent_crypto;
pub mod envelope;
pub mod hkdf;
pub mod hpke;
pub mod key_tree;
pub mod key_wrap;

pub use aead::{
    open, open_with_aad, seal, seal_with_aad, seal_with_aad_nonce, CryptoError, KEY_LEN, NONCE_LEN,
    TAG_LEN,
};
pub use agent_crypto::{AgentCrypto, VaultKeyedCrypto};
pub use envelope::{decode_envelope, encode_envelope, SIGNAL_VAL_PREFIX};
pub use hkdf::{derive_key, derive_key_with_salt, HKDF_KEY_LEN};
pub use hpke::{hpke_open, hpke_seal};
pub use key_tree::{
    derive_session_seed, derive_signal_seed, derive_storage_key, generate_ark, unwrap_ark,
    wrap_ark, KeyTreeError,
};
pub use key_wrap::{unwrap_key, wrap_key};
