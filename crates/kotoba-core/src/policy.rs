use crate::cid::KotobaCid;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

/// Versioned envelope manifest for DEK/KEK-separated encryption.
///
/// `ct_cid` points at ciphertext encrypted by a random data-encryption key
/// (DEK). `dek_wraps` contains one or more wrapped copies of that DEK for
/// recipients/devices/policy engines. Re-keying can publish a new manifest with
/// different wraps while leaving `ct_cid` unchanged.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EnvelopeManifest {
    pub version: u16,
    pub ct_cid: KotobaCid,
    pub content_alg: String,
    #[serde(with = "serde_bytes")]
    pub aad: Vec<u8>,
    pub dek_wraps: Vec<EnvelopeKeyWrap>,
}

impl EnvelopeManifest {
    pub const VERSION: u16 = 1;
    pub const CONTENT_ALG_AES_256_GCM: &'static str = "AES-256-GCM";
    /// Maximum associated-data bytes accepted in an envelope manifest.
    pub const MAX_AAD_LEN: usize = 64 * 1024;
    /// Maximum recipient identifier bytes accepted in a DEK wrap.
    pub const MAX_RECIPIENT_LEN: usize = 512;
    /// Maximum wrap algorithm label bytes accepted in a DEK wrap.
    pub const MAX_WRAP_ALG_LEN: usize = 64;
    /// Maximum number of DEK wraps accepted in one envelope manifest.
    pub const MAX_DEK_WRAP_COUNT: usize = 1024;
    /// Maximum wrapped-DEK bytes accepted in one DEK wrap.
    pub const MAX_WRAPPED_DEK_LEN: usize = 64 * 1024;

    pub fn new(ct_cid: KotobaCid, aad: Vec<u8>, dek_wraps: Vec<EnvelopeKeyWrap>) -> Self {
        Self {
            version: Self::VERSION,
            ct_cid,
            content_alg: Self::CONTENT_ALG_AES_256_GCM.to_string(),
            aad,
            dek_wraps,
        }
    }

    pub fn wrap_for(&self, recipient: &str) -> Option<&EnvelopeKeyWrap> {
        self.dek_wraps
            .iter()
            .find(|wrap| wrap.recipient == recipient)
    }

    pub fn validate(&self) -> Result<(), EnvelopeManifestError> {
        if self.version != Self::VERSION {
            return Err(EnvelopeManifestError::UnsupportedVersion(self.version));
        }
        if self.content_alg != Self::CONTENT_ALG_AES_256_GCM {
            return Err(EnvelopeManifestError::UnsupportedContentAlg(
                self.content_alg.clone(),
            ));
        }
        if self.dek_wraps.is_empty() {
            return Err(EnvelopeManifestError::NoKeyWraps);
        }
        if self.aad.len() > Self::MAX_AAD_LEN {
            return Err(EnvelopeManifestError::AadTooLarge {
                len: self.aad.len(),
                max: Self::MAX_AAD_LEN,
            });
        }
        if self.dek_wraps.len() > Self::MAX_DEK_WRAP_COUNT {
            return Err(EnvelopeManifestError::TooManyKeyWraps {
                len: self.dek_wraps.len(),
                max: Self::MAX_DEK_WRAP_COUNT,
            });
        }

        let mut seen = BTreeSet::new();
        for wrap in &self.dek_wraps {
            if wrap.recipient.is_empty() {
                return Err(EnvelopeManifestError::EmptyRecipient);
            }
            if wrap.recipient.len() > Self::MAX_RECIPIENT_LEN {
                return Err(EnvelopeManifestError::RecipientTooLarge {
                    recipient: wrap.recipient.clone(),
                    len: wrap.recipient.len(),
                    max: Self::MAX_RECIPIENT_LEN,
                });
            }
            if !wrap
                .recipient
                .bytes()
                .all(|byte| (0x21..=0x7e).contains(&byte))
            {
                return Err(EnvelopeManifestError::InvalidRecipient(
                    wrap.recipient.clone(),
                ));
            }
            if wrap.wrap_alg.len() > Self::MAX_WRAP_ALG_LEN {
                return Err(EnvelopeManifestError::WrapAlgTooLarge {
                    wrap_alg: wrap.wrap_alg.clone(),
                    len: wrap.wrap_alg.len(),
                    max: Self::MAX_WRAP_ALG_LEN,
                });
            }
            if wrap.wrap_alg != EnvelopeKeyWrap::WRAP_ALG_AES_256_GCM {
                return Err(EnvelopeManifestError::UnsupportedWrapAlg(
                    wrap.wrap_alg.clone(),
                ));
            }
            if wrap.wrapped_dek.is_empty() {
                return Err(EnvelopeManifestError::EmptyWrappedDek {
                    recipient: wrap.recipient.clone(),
                });
            }
            if wrap.wrapped_dek.len() > Self::MAX_WRAPPED_DEK_LEN {
                return Err(EnvelopeManifestError::WrappedDekTooLarge {
                    recipient: wrap.recipient.clone(),
                    len: wrap.wrapped_dek.len(),
                    max: Self::MAX_WRAPPED_DEK_LEN,
                });
            }
            if !seen.insert(wrap.recipient.as_str()) {
                return Err(EnvelopeManifestError::DuplicateRecipient(
                    wrap.recipient.clone(),
                ));
            }
        }
        Ok(())
    }
}

/// One wrapped DEK entry inside an `EnvelopeManifest`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EnvelopeKeyWrap {
    /// DID, device ID, policy subject, or other stable recipient label.
    pub recipient: String,
    /// Algorithm used to wrap the DEK. The current implementation accepts
    /// AES-256-GCM key wrap; future hybrid/PQC wraps must be added explicitly.
    pub wrap_alg: String,
    #[serde(with = "serde_bytes")]
    pub wrapped_dek: Vec<u8>,
}

impl EnvelopeKeyWrap {
    pub const WRAP_ALG_AES_256_GCM: &'static str = "AES-256-GCM-KW";

    pub fn aes_256_gcm(recipient: impl Into<String>, wrapped_dek: Vec<u8>) -> Self {
        Self {
            recipient: recipient.into(),
            wrap_alg: Self::WRAP_ALG_AES_256_GCM.to_string(),
            wrapped_dek,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum EnvelopeManifestError {
    #[error("unsupported envelope version: {0}")]
    UnsupportedVersion(u16),
    #[error("unsupported envelope content algorithm: {0}")]
    UnsupportedContentAlg(String),
    #[error("envelope manifest has no DEK wraps")]
    NoKeyWraps,
    #[error("envelope manifest AAD is too large: {len} bytes > {max}")]
    AadTooLarge { len: usize, max: usize },
    #[error("envelope manifest has too many DEK wraps: {len} > {max}")]
    TooManyKeyWraps { len: usize, max: usize },
    #[error("envelope key wrap has empty recipient")]
    EmptyRecipient,
    #[error("envelope key wrap recipient is too large for {recipient}: {len} bytes > {max}")]
    RecipientTooLarge {
        recipient: String,
        len: usize,
        max: usize,
    },
    #[error("envelope key wrap recipient must be visible ASCII: {0}")]
    InvalidRecipient(String),
    #[error("envelope key wrap algorithm is too large for {wrap_alg}: {len} bytes > {max}")]
    WrapAlgTooLarge {
        wrap_alg: String,
        len: usize,
        max: usize,
    },
    #[error("unsupported envelope key wrap algorithm: {0}")]
    UnsupportedWrapAlg(String),
    #[error("envelope key wrap for {recipient} has empty wrapped DEK")]
    EmptyWrappedDek { recipient: String },
    #[error("envelope key wrap for {recipient} is too large: {len} bytes > {max}")]
    WrappedDekTooLarge {
        recipient: String,
        len: usize,
        max: usize,
    },
    #[error("duplicate envelope key wrap recipient: {0}")]
    DuplicateRecipient(String),
}

/// Access policy attached to any datum in kotoba.
///
/// The CID always refers to the ciphertext block and is ipfs-public regardless
/// of policy — the network carries ciphertext freely; only key holders can decrypt.
///
/// `Open`      — plaintext; no key required.
/// `Encrypted` — AES-GCM ciphertext.  Symmetric data-key is delivered via PRE
///               after CACAO authorisation (see `PreKeyRegistry` + `PreProxy`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum DataPolicy {
    #[default]
    Open,
    Encrypted {
        /// CID of the AES-GCM ciphertext block stored in BlockStore / kubo.
        ct_cid: KotobaCid,
        /// CID of the PRE key-registry entry: maps (owner_did, accessor_did) → re-key.
        policy_cid: KotobaCid,
    },
    Enveloped {
        /// CID of the DEK-encrypted ciphertext block.
        ct_cid: KotobaCid,
        /// CID of an `EnvelopeManifest` block carrying DEK wraps.
        manifest_cid: KotobaCid,
    },
}

impl DataPolicy {
    #[inline]
    pub fn is_open(&self) -> bool {
        matches!(self, DataPolicy::Open)
    }
    #[inline]
    pub fn is_encrypted(&self) -> bool {
        !self.is_open()
    }

    #[inline]
    pub fn ct_cid(&self) -> Option<&KotobaCid> {
        match self {
            DataPolicy::Open => None,
            DataPolicy::Encrypted { ct_cid, .. } | DataPolicy::Enveloped { ct_cid, .. } => {
                Some(ct_cid)
            }
        }
    }

    #[inline]
    pub fn policy_cid(&self) -> Option<&KotobaCid> {
        match self {
            DataPolicy::Open => None,
            DataPolicy::Encrypted { policy_cid, .. } => Some(policy_cid),
            DataPolicy::Enveloped { manifest_cid, .. } => Some(manifest_cid),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn open_policy_is_open() {
        let p = DataPolicy::Open;
        assert!(p.is_open());
        assert!(!p.is_encrypted());
    }

    #[test]
    fn encrypted_policy_is_encrypted() {
        let cid = KotobaCid::from_bytes(b"ct");
        let pol = KotobaCid::from_bytes(b"policy");
        let p = DataPolicy::Encrypted {
            ct_cid: cid,
            policy_cid: pol,
        };
        assert!(p.is_encrypted());
        assert!(!p.is_open());
    }

    #[test]
    fn enveloped_policy_is_encrypted_and_points_to_manifest() {
        let ct = KotobaCid::from_bytes(b"ct");
        let manifest = KotobaCid::from_bytes(b"manifest");
        let p = DataPolicy::Enveloped {
            ct_cid: ct.clone(),
            manifest_cid: manifest.clone(),
        };
        assert!(p.is_encrypted());
        assert_eq!(p.ct_cid(), Some(&ct));
        assert_eq!(p.policy_cid(), Some(&manifest));
    }

    #[test]
    fn default_policy_is_open() {
        let p = DataPolicy::default();
        assert!(p.is_open());
    }

    #[test]
    fn cbor_roundtrip_open() {
        let p = DataPolicy::Open;
        let mut buf = Vec::new();
        ciborium::into_writer(&p, &mut buf).unwrap();
        let back: DataPolicy = ciborium::from_reader(buf.as_slice()).unwrap();
        assert_eq!(back, DataPolicy::Open);
    }

    #[test]
    fn cbor_roundtrip_encrypted() {
        let ct = KotobaCid::from_bytes(b"ct-data");
        let pol = KotobaCid::from_bytes(b"policy-data");
        let p = DataPolicy::Encrypted {
            ct_cid: ct.clone(),
            policy_cid: pol.clone(),
        };
        let mut buf = Vec::new();
        ciborium::into_writer(&p, &mut buf).unwrap();
        let back: DataPolicy = ciborium::from_reader(buf.as_slice()).unwrap();
        assert_eq!(back, p);
    }

    #[test]
    fn open_policy_clone_equals_original() {
        let p = DataPolicy::Open;
        let q = p.clone();
        assert_eq!(p, q);
    }

    #[test]
    fn encrypted_policy_clone_equals_original() {
        let ct = KotobaCid::from_bytes(b"ct");
        let pol = KotobaCid::from_bytes(b"pol");
        let p = DataPolicy::Encrypted {
            ct_cid: ct,
            policy_cid: pol,
        };
        let q = p.clone();
        assert_eq!(p, q);
    }

    #[test]
    fn encrypted_different_policy_cid_not_equal() {
        let ct = KotobaCid::from_bytes(b"ct");
        let pol1 = KotobaCid::from_bytes(b"pol1");
        let pol2 = KotobaCid::from_bytes(b"pol2");
        let p1 = DataPolicy::Encrypted {
            ct_cid: ct.clone(),
            policy_cid: pol1,
        };
        let p2 = DataPolicy::Encrypted {
            ct_cid: ct,
            policy_cid: pol2,
        };
        assert_ne!(p1, p2, "different policy_cid must not be equal");
    }

    #[test]
    fn open_and_encrypted_not_equal() {
        let p_open = DataPolicy::Open;
        let ct = KotobaCid::from_bytes(b"ct");
        let pol = KotobaCid::from_bytes(b"pol");
        let p_enc = DataPolicy::Encrypted {
            ct_cid: ct,
            policy_cid: pol,
        };
        assert_ne!(p_open, p_enc);
    }

    #[test]
    fn debug_format_is_non_empty() {
        let p = DataPolicy::Open;
        let s = format!("{:?}", p);
        assert!(!s.is_empty(), "Debug output must be non-empty");
    }

    #[test]
    fn encrypted_debug_contains_encrypted() {
        let ct = KotobaCid::from_bytes(b"ct");
        let pol = KotobaCid::from_bytes(b"pol");
        let p = DataPolicy::Encrypted {
            ct_cid: ct,
            policy_cid: pol,
        };
        let s = format!("{:?}", p);
        assert!(
            s.contains("Encrypted"),
            "Debug for Encrypted variant should say 'Encrypted': {s}"
        );
    }

    #[test]
    fn envelope_manifest_cbor_roundtrip() {
        let ct = KotobaCid::from_bytes(b"ciphertext");
        let wrap = EnvelopeKeyWrap::aes_256_gcm("did:example:alice", vec![1, 2, 3]);
        let manifest = EnvelopeManifest::new(ct.clone(), b"slot".to_vec(), vec![wrap]);
        let mut buf = Vec::new();
        ciborium::into_writer(&manifest, &mut buf).unwrap();
        let back: EnvelopeManifest = ciborium::from_reader(buf.as_slice()).unwrap();
        assert_eq!(back, manifest);
        assert_eq!(back.ct_cid, ct);
        assert!(back.wrap_for("did:example:alice").is_some());
        assert!(back.wrap_for("did:example:bob").is_none());
        assert!(back.validate().is_ok());
    }

    #[test]
    fn envelope_manifest_validation_rejects_empty_and_duplicate_wraps() {
        let ct = KotobaCid::from_bytes(b"ciphertext");
        let no_wraps = EnvelopeManifest::new(ct.clone(), b"slot".to_vec(), vec![]);
        assert!(matches!(
            no_wraps.validate(),
            Err(EnvelopeManifestError::NoKeyWraps)
        ));

        let duplicate = EnvelopeManifest::new(
            ct,
            b"slot".to_vec(),
            vec![
                EnvelopeKeyWrap::aes_256_gcm("did:example:alice", vec![1]),
                EnvelopeKeyWrap::aes_256_gcm("did:example:alice", vec![2]),
            ],
        );
        assert!(matches!(
            duplicate.validate(),
            Err(EnvelopeManifestError::DuplicateRecipient(_))
        ));
    }

    #[test]
    fn envelope_manifest_validation_rejects_resource_exhaustion_shapes() {
        let ct = KotobaCid::from_bytes(b"ciphertext");

        let oversized_aad = EnvelopeManifest::new(
            ct.clone(),
            vec![0; EnvelopeManifest::MAX_AAD_LEN + 1],
            vec![EnvelopeKeyWrap::aes_256_gcm("did:example:alice", vec![1])],
        );
        assert!(matches!(
            oversized_aad.validate(),
            Err(EnvelopeManifestError::AadTooLarge { .. })
        ));

        let oversized_recipient = EnvelopeManifest::new(
            ct.clone(),
            b"slot".to_vec(),
            vec![EnvelopeKeyWrap::aes_256_gcm(
                "r".repeat(EnvelopeManifest::MAX_RECIPIENT_LEN + 1),
                vec![1],
            )],
        );
        assert!(matches!(
            oversized_recipient.validate(),
            Err(EnvelopeManifestError::RecipientTooLarge { .. })
        ));

        for recipient in [
            "did:example:alice bob",
            "did:example:alice\nbob",
            "did:例:alice",
        ] {
            let invalid_recipient = EnvelopeManifest::new(
                ct.clone(),
                b"slot".to_vec(),
                vec![EnvelopeKeyWrap::aes_256_gcm(recipient, vec![1])],
            );
            assert!(matches!(
                invalid_recipient.validate(),
                Err(EnvelopeManifestError::InvalidRecipient(_))
            ));
        }

        let mut oversized_wrap_alg = EnvelopeKeyWrap::aes_256_gcm("did:example:alice", vec![1]);
        oversized_wrap_alg.wrap_alg = "A".repeat(EnvelopeManifest::MAX_WRAP_ALG_LEN + 1);
        let oversized_wrap_alg_manifest =
            EnvelopeManifest::new(ct.clone(), b"slot".to_vec(), vec![oversized_wrap_alg]);
        assert!(matches!(
            oversized_wrap_alg_manifest.validate(),
            Err(EnvelopeManifestError::WrapAlgTooLarge { .. })
        ));

        let mut unsupported_wrap_alg = EnvelopeKeyWrap::aes_256_gcm("did:example:alice", vec![1]);
        unsupported_wrap_alg.wrap_alg = "ML-KEM-768+AES-256-GCM-KW".to_string();
        let unsupported_wrap_alg_manifest =
            EnvelopeManifest::new(ct.clone(), b"slot".to_vec(), vec![unsupported_wrap_alg]);
        assert!(matches!(
            unsupported_wrap_alg_manifest.validate(),
            Err(EnvelopeManifestError::UnsupportedWrapAlg(_))
        ));

        let oversized_wrapped_dek = EnvelopeManifest::new(
            ct.clone(),
            b"slot".to_vec(),
            vec![EnvelopeKeyWrap::aes_256_gcm(
                "did:example:alice",
                vec![1; EnvelopeManifest::MAX_WRAPPED_DEK_LEN + 1],
            )],
        );
        assert!(matches!(
            oversized_wrapped_dek.validate(),
            Err(EnvelopeManifestError::WrappedDekTooLarge { .. })
        ));

        let too_many_wraps = EnvelopeManifest::new(
            ct,
            b"slot".to_vec(),
            (0..=EnvelopeManifest::MAX_DEK_WRAP_COUNT)
                .map(|i| EnvelopeKeyWrap::aes_256_gcm(format!("did:example:{i}"), vec![1]))
                .collect(),
        );
        assert!(matches!(
            too_many_wraps.validate(),
            Err(EnvelopeManifestError::TooManyKeyWraps { .. })
        ));
    }
}
