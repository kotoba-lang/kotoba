//! Git object id (SHA-1, 20 bytes / 40 lowercase-hex chars).
//!
//! Git's native object id is SHA-1 over the *framed* object bytes
//! (`<type> <size>\0<body>`). kotoba addresses the same bytes by
//! [`KotobaCid`](kotoba_core::cid::KotobaCid) (CIDv1 dag-cbor sha2-256). The two
//! live in different hash spaces; [`GitOid`] is the git side of that bridge.

use crate::error::GitError;
use sha1::{Digest, Sha1};

/// A git object id: raw 20-byte SHA-1 digest.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct GitOid(pub [u8; 20]);

impl GitOid {
    /// Compute the git oid of already-framed object bytes
    /// (`<type> <size>\0<body>`). This is exactly what `git hash-object` hashes.
    pub fn of_framed(framed: &[u8]) -> Self {
        let mut hasher = Sha1::new();
        hasher.update(framed);
        let digest = hasher.finalize();
        let mut out = [0u8; 20];
        out.copy_from_slice(&digest);
        Self(out)
    }

    /// Parse a 40-char lowercase/uppercase hex string into a `GitOid`.
    pub fn from_hex(s: &str) -> Result<Self, GitError> {
        let bytes = hex::decode(s).map_err(|_| GitError::InvalidOid(s.to_string()))?;
        if bytes.len() != 20 {
            return Err(GitError::InvalidOid(s.to_string()));
        }
        let mut out = [0u8; 20];
        out.copy_from_slice(&bytes);
        Ok(Self(out))
    }

    /// Build from the raw 20-byte form (as embedded in tree entries).
    pub fn from_raw(bytes: &[u8]) -> Result<Self, GitError> {
        if bytes.len() != 20 {
            return Err(GitError::InvalidOid(hex::encode(bytes)));
        }
        let mut out = [0u8; 20];
        out.copy_from_slice(bytes);
        Ok(Self(out))
    }

    /// 40-char lowercase hex (canonical git display + storage form).
    pub fn to_hex(&self) -> String {
        hex::encode(self.0)
    }

    /// Raw 20-byte digest (as embedded in a tree entry).
    pub fn raw(&self) -> &[u8; 20] {
        &self.0
    }
}

impl std::fmt::Display for GitOid {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.to_hex())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_blob_oid_matches_git() {
        // Authoritative: `printf '' | git hash-object --stdin`
        let framed = b"blob 0\0";
        assert_eq!(
            GitOid::of_framed(framed).to_hex(),
            "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
        );
    }

    #[test]
    fn hello_blob_oid_matches_git() {
        // Authoritative: `printf 'hello\n' | git hash-object --stdin`
        let framed = b"blob 6\0hello\n";
        assert_eq!(
            GitOid::of_framed(framed).to_hex(),
            "ce013625030ba8dba906f756967f9e9ca394464a"
        );
    }

    #[test]
    fn hex_roundtrip() {
        let oid = GitOid::of_framed(b"blob 6\0hello\n");
        let parsed = GitOid::from_hex(&oid.to_hex()).unwrap();
        assert_eq!(oid, parsed);
    }

    #[test]
    fn raw_roundtrip() {
        let oid = GitOid::of_framed(b"blob 6\0hello\n");
        let parsed = GitOid::from_raw(oid.raw()).unwrap();
        assert_eq!(oid, parsed);
    }

    #[test]
    fn from_hex_rejects_short() {
        assert!(GitOid::from_hex("abcd").is_err());
    }
}
