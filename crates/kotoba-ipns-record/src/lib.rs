//! Wasm-safe kotoba IPNS head record (ADR-2606066000 / ADR-2606013600).
//!
//! An IPNS name resolves to the latest commit CID for a graph/database — the
//! mutable-name boundary of the distributed Datomic target. This crate holds the
//! **record type and its Ed25519 sign/verify ONLY**, with no native I/O, so the
//! exact same self-verifying record can be produced by:
//!
//!   - the native registries in `kotoba-ipfs` (which re-exports these types), and
//!   - the **browser node** (`kotoba-wasm`) when a member publishes a head.
//!
//! Keeping one record type (rather than a parallel browser format) is required by
//! ADR-2605262130 (no parallel substrate): a `kotoba-wasm`-signed record verifies
//! byte-identically under this crate's verifier, which `kotoba-ipfs` re-exports.
//!
//! The signing payload is the deterministic CBOR (ciborium) of the record fields
//! **excluding the signature**; the signature and public key are base58btc
//! multibase. `sequence` is the monotonic stale-guard / CAS ordering.

use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};
use ipld_core::cid::Cid as IpldCid;
use multibase::Base;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct IpnsName(pub String);

impl IpnsName {
    pub fn new(name: impl Into<String>) -> Self {
        Self(name.into())
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// A Kotoba IPNS record.
///
/// `value` is the CID string of the latest DAG-CBOR commit block. `sequence`
/// is monotonically increasing per name; stale records are rejected by the
/// registries in `kotoba-ipfs`. `valid_until` uses strict UTC text so the record
/// is stable in DAG-CBOR and JSON.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IpnsRecord {
    pub name: IpnsName,
    pub value: String,
    pub sequence: u64,
    pub valid_until: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ttl_secs: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub controller_did: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub public_key_multibase: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub signature_multibase: Option<String>,
}

impl IpnsRecord {
    pub fn new(
        name: impl Into<String>,
        value: &IpldCid,
        sequence: u64,
        valid_until: impl Into<String>,
    ) -> Self {
        Self::with_value_string(name, value.to_string(), sequence, valid_until)
    }

    /// Construct from a CID *string* (multibase) directly — the form the browser
    /// node has on hand (`KotobaCid::to_multibase`), so `kotoba-wasm` does not need
    /// to depend on the CID crate just to build a head record.
    pub fn with_value_string(
        name: impl Into<String>,
        value: impl Into<String>,
        sequence: u64,
        valid_until: impl Into<String>,
    ) -> Self {
        Self {
            name: IpnsName::new(name),
            value: value.into(),
            sequence,
            valid_until: valid_until.into(),
            ttl_secs: None,
            controller_did: None,
            public_key_multibase: None,
            signature_multibase: None,
        }
    }

    pub fn value_cid(&self) -> Result<IpldCid, IpnsRegistryError> {
        self.value
            .parse::<IpldCid>()
            .map_err(|e| IpnsRegistryError::InvalidCid(e.to_string()))
    }

    pub fn signing_payload(&self) -> Result<Vec<u8>, IpnsRegistryError> {
        #[derive(Serialize)]
        struct Payload<'a> {
            name: &'a IpnsName,
            value: &'a str,
            sequence: u64,
            valid_until: &'a str,
            ttl_secs: Option<u64>,
            controller_did: Option<&'a str>,
            public_key_multibase: Option<&'a str>,
        }

        let payload = Payload {
            name: &self.name,
            value: &self.value,
            sequence: self.sequence,
            valid_until: &self.valid_until,
            ttl_secs: self.ttl_secs,
            controller_did: self.controller_did.as_deref(),
            public_key_multibase: self.public_key_multibase.as_deref(),
        };
        let mut bytes = Vec::new();
        ciborium::into_writer(&payload, &mut bytes)
            .map_err(|e| IpnsRegistryError::Signature(e.to_string()))?;
        Ok(bytes)
    }

    pub fn sign_ed25519(&mut self, signing_key: &SigningKey) -> Result<(), IpnsRegistryError> {
        self.public_key_multibase = Some(multibase::encode(
            Base::Base58Btc,
            signing_key.verifying_key().as_bytes(),
        ));
        let payload = self.signing_payload()?;
        let signature = signing_key.sign(&payload);
        self.signature_multibase = Some(multibase::encode(Base::Base58Btc, signature.to_bytes()));
        Ok(())
    }

    pub fn verify_ed25519_signature(&self) -> Result<(), IpnsRegistryError> {
        let public_key_multibase = self
            .public_key_multibase
            .as_deref()
            .ok_or(IpnsRegistryError::MissingPublicKey)?;
        let signature_multibase = self
            .signature_multibase
            .as_deref()
            .ok_or(IpnsRegistryError::MissingSignature)?;
        let (_, public_key_bytes) = multibase::decode(public_key_multibase)
            .map_err(|e| IpnsRegistryError::InvalidSignature(e.to_string()))?;
        let verifying_key = VerifyingKey::from_bytes(
            public_key_bytes
                .as_slice()
                .try_into()
                .map_err(|_| IpnsRegistryError::InvalidPublicKey(public_key_bytes.len()))?,
        )
        .map_err(|e| IpnsRegistryError::InvalidSignature(e.to_string()))?;
        let (_, signature_bytes) = multibase::decode(signature_multibase)
            .map_err(|e| IpnsRegistryError::InvalidSignature(e.to_string()))?;
        let signature = Signature::from_slice(&signature_bytes)
            .map_err(|e| IpnsRegistryError::InvalidSignature(e.to_string()))?;
        verifying_key
            .verify_strict(&self.signing_payload()?, &signature)
            .map_err(|e| IpnsRegistryError::InvalidSignature(e.to_string()))
    }

    pub fn signature_verified(&self) -> bool {
        self.verify_ed25519_signature().is_ok()
    }

    pub fn verify_signature_if_present(&self) -> Result<(), IpnsRegistryError> {
        match (&self.public_key_multibase, &self.signature_multibase) {
            (None, None) => Ok(()),
            _ => self.verify_ed25519_signature(),
        }
    }

    pub fn require_verified_signature(&self) -> Result<(), IpnsRegistryError> {
        self.verify_ed25519_signature()
    }
}

#[derive(Debug, thiserror::Error)]
pub enum IpnsRegistryError {
    #[error("IPNS name not found: {0}")]
    NotFound(String),
    #[error("stale IPNS record for {name}: current sequence {current}, incoming {incoming}")]
    StaleRecord {
        name: String,
        current: u64,
        incoming: u64,
    },
    #[error("invalid CID in IPNS value: {0}")]
    InvalidCid(String),
    #[error("missing IPNS public key")]
    MissingPublicKey,
    #[error("invalid IPNS public key length: {0}")]
    InvalidPublicKey(usize),
    #[error("missing IPNS signature")]
    MissingSignature,
    #[error("invalid IPNS signature: {0}")]
    InvalidSignature(String),
    #[error("IPNS signature payload: {0}")]
    Signature(String),
    #[error("kubo IPNS HTTP: {0}")]
    Kubo(String),
    #[error("registry lock poisoned")]
    LockPoisoned,
    #[error("persistent IPNS store io: {0}")]
    Io(String),
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::SigningKey;

    fn key() -> SigningKey {
        SigningKey::from_bytes(&[7u8; 32])
    }

    // The CID the head points at (a real CIDv1 dag-cbor sha2-256 multibase string).
    const HEAD_CID: &str = "bafyreibidp6u4y5rssjx25vjppru6xrerrrdglk4yyd4qvqc4d43daxmce";

    #[test]
    fn sign_then_verify_roundtrips() {
        let mut rec = IpnsRecord::with_value_string(
            "did:key:zfeed",
            HEAD_CID,
            1,
            "2030-01-01T00:00:00Z",
        );
        rec.sign_ed25519(&key()).unwrap();
        assert!(rec.public_key_multibase.is_some());
        assert!(rec.signature_multibase.is_some());
        rec.verify_ed25519_signature().expect("valid signature verifies");
        assert!(rec.signature_verified());
    }

    #[test]
    fn tamper_with_value_fails_verify() {
        let mut rec =
            IpnsRecord::with_value_string("did:key:zfeed", HEAD_CID, 1, "2030-01-01T00:00:00Z");
        rec.sign_ed25519(&key()).unwrap();
        rec.value = "bafyreih4tampered000000000000000000000000000000000000000000".into();
        assert!(rec.verify_ed25519_signature().is_err());
    }

    #[test]
    fn tamper_with_sequence_fails_verify() {
        let mut rec =
            IpnsRecord::with_value_string("did:key:zfeed", HEAD_CID, 1, "2030-01-01T00:00:00Z");
        rec.sign_ed25519(&key()).unwrap();
        rec.sequence = 2; // a different head ordering than was signed
        assert!(rec.verify_ed25519_signature().is_err());
    }

    #[test]
    fn unsigned_record_verify_if_present_is_ok_but_require_fails() {
        let rec =
            IpnsRecord::with_value_string("did:key:zfeed", HEAD_CID, 1, "2030-01-01T00:00:00Z");
        assert!(rec.verify_signature_if_present().is_ok());
        assert!(rec.require_verified_signature().is_err());
    }

    // Mirrors the kotoba-wasm browser publish path: controller_did set to the
    // member did:key, signed with the same key — the record a browser emits must
    // verify under this canonical verifier (the ADR-2606066000 interop guarantee).
    #[test]
    fn browser_shaped_record_verifies() {
        let sk = key();
        let did = format!(
            "did:key:z{}",
            hex::encode_upper(sk.verifying_key().to_bytes())
        )
        .to_lowercase();
        let mut rec =
            IpnsRecord::with_value_string(did.clone(), HEAD_CID, 42, "2030-06-06T00:00:00Z");
        rec.controller_did = Some(did);
        rec.sign_ed25519(&sk).unwrap();
        rec.require_verified_signature()
            .expect("browser-shaped record verifies under canonical verifier");
        assert_eq!(rec.sequence, 42);
        assert_eq!(rec.value, HEAD_CID);
    }

    // Tiny local hex (test-only) to avoid a dev-dep just for the did string.
    mod hex {
        pub fn encode_upper(bytes: impl AsRef<[u8]>) -> String {
            bytes
                .as_ref()
                .iter()
                .map(|b| format!("{b:02X}"))
                .collect()
        }
    }
}
