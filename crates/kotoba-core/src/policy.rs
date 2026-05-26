use crate::cid::KotobaCid;
use serde::{Deserialize, Serialize};

/// Access policy attached to any datum in kotoba.
///
/// The CID always refers to the ciphertext block and is iroh-public regardless
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
        /// CID of the AES-GCM ciphertext block stored in BlockStore / iroh.
        ct_cid: KotobaCid,
        /// CID of the PRE key-registry entry: maps (owner_did, accessor_did) → re-key.
        policy_cid: KotobaCid,
    },
}

impl DataPolicy {
    #[inline] pub fn is_open(&self) -> bool { matches!(self, DataPolicy::Open) }
    #[inline] pub fn is_encrypted(&self) -> bool { !self.is_open() }
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
        let p   = DataPolicy::Encrypted { ct_cid: cid, policy_cid: pol };
        assert!(p.is_encrypted());
        assert!(!p.is_open());
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
        let ct  = KotobaCid::from_bytes(b"ct-data");
        let pol = KotobaCid::from_bytes(b"policy-data");
        let p   = DataPolicy::Encrypted { ct_cid: ct.clone(), policy_cid: pol.clone() };
        let mut buf = Vec::new();
        ciborium::into_writer(&p, &mut buf).unwrap();
        let back: DataPolicy = ciborium::from_reader(buf.as_slice()).unwrap();
        assert_eq!(back, p);
    }
}
