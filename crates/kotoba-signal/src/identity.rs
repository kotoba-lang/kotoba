use ed25519_dalek::{SigningKey, VerifyingKey, Signer, Verifier, Signature};
use x25519_dalek::{StaticSecret, PublicKey as X25519Public};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use zeroize::ZeroizeOnDrop;

pub type DeviceId = String;

/// Long-term identity key pair.
/// - `signing`: Ed25519 — used to sign signed pre-keys and Sender Key distributions
/// - `dh`: X25519  — used in X3DH DH calculations (DH1 / DH2)
#[derive(ZeroizeOnDrop)]
pub struct IdentityKeyPair {
    pub signing: SigningKey,
    // StaticSecret implements ZeroizeOnDrop
    pub dh:      StaticSecret,
}

/// Public half of an identity key pair (serializable, shareable).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct IdentityKey {
    /// Ed25519 verifying key (32 bytes, base64url).
    pub signing: Vec<u8>,
    /// X25519 public key (32 bytes, base64url).
    pub dh:      Vec<u8>,
}

impl IdentityKeyPair {
    pub fn generate() -> Self {
        let signing = SigningKey::generate(&mut OsRng);
        let dh      = StaticSecret::random_from_rng(OsRng);
        Self { signing, dh }
    }

    pub fn public_key(&self) -> IdentityKey {
        IdentityKey {
            signing: self.signing.verifying_key().to_bytes().to_vec(),
            dh:      X25519Public::from(&self.dh).to_bytes().to_vec(),
        }
    }

    /// Sign `msg` with the Ed25519 signing key.
    pub fn sign(&self, msg: &[u8]) -> Vec<u8> {
        self.signing.sign(msg).to_bytes().to_vec()
    }

    /// X25519 DH with a remote public key.
    pub fn dh(&self, remote: &[u8; 32]) -> [u8; 32] {
        let pub_key = X25519Public::from(*remote);
        self.dh.diffie_hellman(&pub_key).to_bytes()
    }
}

impl IdentityKey {
    pub fn verify(&self, msg: &[u8], sig: &[u8]) -> bool {
        let Ok(vk)  = VerifyingKey::from_bytes(self.signing.as_slice().try_into().unwrap_or(&[0u8; 32])) else { return false };
        let Ok(sig) = Signature::from_slice(sig) else { return false };
        vk.verify(msg, &sig).is_ok()
    }

    pub fn dh_public(&self) -> Option<[u8; 32]> {
        self.dh.as_slice().try_into().ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generate_and_sign_verify() {
        let kp = IdentityKeyPair::generate();
        let pk = kp.public_key();
        let msg = b"hello kotoba-signal";
        let sig = kp.sign(msg);
        assert!(pk.verify(msg, &sig));
        assert!(!pk.verify(b"wrong", &sig));
    }

    #[test]
    fn dh_symmetry() {
        let a = IdentityKeyPair::generate();
        let b = IdentityKeyPair::generate();
        let a_pub = X25519Public::from(&a.dh);
        let b_pub = X25519Public::from(&b.dh);
        let ab = a.dh(&b_pub.to_bytes());
        let ba = b.dh(&a_pub.to_bytes());
        assert_eq!(ab, ba);
    }
}
