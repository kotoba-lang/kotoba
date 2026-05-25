/// Sender Keys — group messaging (Signal specification).
///
/// Each group member distributes a SenderKeyState (chain_key + signing_key).
/// Group messages are encrypted with a symmetric ratchet derived from chain_key.
/// Other members verify + decrypt using the distributed sender key.
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use ed25519_dalek::{SigningKey, VerifyingKey, Signer, Verifier, Signature};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use zeroize::ZeroizeOnDrop;

use kotoba_crypto::hkdf::ratchet_chain;
use kotoba_crypto::aead::{seal, open};
use crate::SignalError;

/// Per-member sender key state (private).
#[derive(ZeroizeOnDrop)]
pub struct SenderKeyState {
    pub group_id:     String,
    pub member_did:   String,
    pub chain_id:     u32,   // increments on each ratchet epoch
    pub chain_key:    [u8; 32],
    pub chain_iter:   u32,
    pub signing:      SigningKey,
}

/// Public distribution record shared with group members.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SenderKeyDistribution {
    pub group_id:        String,
    pub sender_did:      String,
    pub chain_id:        u32,
    pub chain_iter:      u32,
    /// Current sender chain key (public representation: the chain_key itself, ONLY shared
    /// to group members already trusted — encrypted 1:1 per member via Double Ratchet).
    pub chain_key:       Vec<u8>,
    /// Ed25519 verifying key (32 bytes).
    pub signing_key_pub: Vec<u8>,
}

/// An encrypted group message.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SenderKeyMessage {
    pub group_id:    String,
    pub sender_did:  String,
    pub chain_id:    u32,
    pub n:           u32,
    /// AES-256-GCM ciphertext (nonce || ct).
    pub ciphertext:  Vec<u8>,
    /// Ed25519 signature over `chain_id || n || ciphertext`.
    pub signature:   Vec<u8>,
}

impl SenderKeyState {
    pub fn generate(group_id: impl Into<String>, member_did: impl Into<String>) -> Self {
        let signing   = SigningKey::generate(&mut OsRng);
        let chain_key = {
            let mut k = [0u8; 32];
            rand::RngCore::fill_bytes(&mut OsRng, &mut k);
            k
        };
        Self {
            group_id:   group_id.into(),
            member_did: member_did.into(),
            chain_id:   0,
            chain_key,
            chain_iter: 0,
            signing,
        }
    }

    /// Produce the public distribution record (to be encrypted 1:1 to each group member).
    pub fn distribution(&self) -> SenderKeyDistribution {
        SenderKeyDistribution {
            group_id:        self.group_id.clone(),
            sender_did:      self.member_did.clone(),
            chain_id:        self.chain_id,
            chain_iter:      self.chain_iter,
            chain_key:       self.chain_key.to_vec(),
            signing_key_pub: self.signing.verifying_key().to_bytes().to_vec(),
        }
    }

    /// Encrypt `plaintext` as a group message and advance the chain.
    pub fn encrypt(&mut self, plaintext: &[u8]) -> Result<SenderKeyMessage, SignalError> {
        let (new_ck, mk) = ratchet_chain(&self.chain_key);
        self.chain_key = new_ck;
        let n = self.chain_iter;
        self.chain_iter += 1;

        let ciphertext = seal(&mk, plaintext).map_err(SignalError::Crypto)?;

        // Sign chain_id || n || ciphertext
        let mut sig_data = Vec::with_capacity(8 + ciphertext.len());
        sig_data.extend_from_slice(&self.chain_id.to_le_bytes());
        sig_data.extend_from_slice(&n.to_le_bytes());
        sig_data.extend_from_slice(&ciphertext);
        let signature = self.signing.sign(&sig_data).to_bytes().to_vec();

        Ok(SenderKeyMessage {
            group_id:   self.group_id.clone(),
            sender_did: self.member_did.clone(),
            chain_id:   self.chain_id,
            n,
            ciphertext,
            signature,
        })
    }
}

/// Per-member decryption state derived from a received SenderKeyDistribution.
pub struct GroupSession {
    pub group_id:        String,
    pub sender_did:      String,
    pub chain_id:        u32,
    pub chain_key:       [u8; 32],
    pub chain_iter:      u32,
    pub signing_key_pub: VerifyingKey,
    /// Cached message keys for out-of-order delivery.
    skipped_keys: HashMap<(u32, u32), [u8; 32]>,  // (chain_id, n) → mk
}

impl GroupSession {
    /// Create from a received `SenderKeyDistribution`.
    pub fn from_distribution(dist: &SenderKeyDistribution) -> Result<Self, SignalError> {
        let chain_key: [u8; 32] = dist
            .chain_key
            .as_slice()
            .try_into()
            .map_err(|_| SignalError::CounterMismatch)?;
        let vk_bytes: [u8; 32] = dist
            .signing_key_pub
            .as_slice()
            .try_into()
            .map_err(|_| SignalError::BadSignature)?;
        let signing_key_pub =
            VerifyingKey::from_bytes(&vk_bytes).map_err(|_| SignalError::BadSignature)?;
        Ok(Self {
            group_id:        dist.group_id.clone(),
            sender_did:      dist.sender_did.clone(),
            chain_id:        dist.chain_id,
            chain_key,
            chain_iter:      dist.chain_iter,
            signing_key_pub,
            skipped_keys: HashMap::new(),
        })
    }

    /// Verify + decrypt a `SenderKeyMessage`.
    pub fn decrypt(&mut self, msg: &SenderKeyMessage) -> Result<Vec<u8>, SignalError> {
        if msg.group_id != self.group_id || msg.sender_did != self.sender_did {
            return Err(SignalError::NoSession(msg.sender_did.clone()));
        }
        // Verify signature
        let mut sig_data = Vec::with_capacity(8 + msg.ciphertext.len());
        sig_data.extend_from_slice(&msg.chain_id.to_le_bytes());
        sig_data.extend_from_slice(&msg.n.to_le_bytes());
        sig_data.extend_from_slice(&msg.ciphertext);
        let sig = Signature::from_slice(&msg.signature).map_err(|_| SignalError::BadSignature)?;
        self.signing_key_pub
            .verify(&sig_data, &sig)
            .map_err(|_| SignalError::BadSignature)?;

        // Check skipped key cache
        let key = (msg.chain_id, msg.n);
        if let Some(mk) = self.skipped_keys.remove(&key) {
            let pt = open(&mk, &msg.ciphertext).map_err(SignalError::Crypto)?;
            return Ok(pt.to_vec());
        }

        // Advance chain to msg.n
        if msg.n < self.chain_iter {
            return Err(SignalError::CounterMismatch);
        }
        while self.chain_iter < msg.n {
            let (new_ck, mk) = ratchet_chain(&self.chain_key);
            self.chain_key = new_ck;
            self.skipped_keys.insert((self.chain_id, self.chain_iter), mk);
            self.chain_iter += 1;
        }

        let (new_ck, mk) = ratchet_chain(&self.chain_key);
        self.chain_key = new_ck;
        self.chain_iter += 1;

        let pt = open(&mk, &msg.ciphertext).map_err(SignalError::Crypto)?;
        Ok(pt.to_vec())
    }
}

// ── In-memory sender key store ─────────────────────────────────────────────────

#[derive(Default, Clone)]
pub struct InMemorySenderKeyStore {
    states:   Arc<RwLock<HashMap<String, SenderKeyDistribution>>>,
}

impl InMemorySenderKeyStore {
    pub fn new() -> Self { Self::default() }

    pub async fn store(&self, dist: SenderKeyDistribution) {
        let k = format!("{}:{}", dist.group_id, dist.sender_did);
        self.states.write().await.insert(k, dist);
    }

    pub async fn load(&self, group_id: &str, sender_did: &str) -> Option<SenderKeyDistribution> {
        let k = format!("{group_id}:{sender_did}");
        self.states.read().await.get(&k).cloned()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn group_send_recv_roundtrip() {
        let mut sender = SenderKeyState::generate("group-1", "did:plc:alice");
        let dist = sender.distribution();
        let mut receiver = GroupSession::from_distribution(&dist).unwrap();

        let msg = sender.encrypt(b"hello group").unwrap();
        let pt  = receiver.decrypt(&msg).unwrap();
        assert_eq!(pt, b"hello group");
    }

    #[test]
    fn group_multiple_messages_in_order() {
        let mut sender = SenderKeyState::generate("group-1", "did:plc:alice");
        let dist = sender.distribution();
        let mut receiver = GroupSession::from_distribution(&dist).unwrap();

        for i in 0u8..5 {
            let msg = sender.encrypt(&[i]).unwrap();
            let pt  = receiver.decrypt(&msg).unwrap();
            assert_eq!(pt, &[i]);
        }
    }

    #[test]
    fn tampered_signature_rejected() {
        let mut sender = SenderKeyState::generate("group-1", "did:plc:alice");
        let dist = sender.distribution();
        let mut receiver = GroupSession::from_distribution(&dist).unwrap();

        let mut msg = sender.encrypt(b"secret").unwrap();
        msg.signature[0] ^= 0xFF;
        assert!(receiver.decrypt(&msg).is_err());
    }
}
