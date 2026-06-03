//! BIP-322 generic message signing — boundary + R0 status.
//!
//! BIP-322 defines two proofs of address ownership over an arbitrary message:
//!   - **simple**  — a single-input witness over a virtual `to_spend` /
//!     `to_sign` transaction pair.
//!   - **full**    — a complete (possibly multi-input) signed virtual tx.
//!
//! Both require constructing the BIP-322 virtual transactions and running the
//! Bitcoin **Script** interpreter (witness program execution) to validate the
//! proof. That script engine is **out of R0 scope** — kotoba's address surface
//! is verify-only and we will not vendor a full consensus Script VM here.
//!
//! What R0 ships instead, in [`crate::btc::verify_message`]: the **legacy
//! "Bitcoin Signed Message"** scheme (Bitcoin Core `signmessage`/`verifymessage`,
//! Electrum legacy), a 65-byte recoverable ECDSA signature over the
//! double-SHA256 of the magic-prefixed message. It covers P2PKH and P2WPKH
//! ownership — the common wallet case — and is the Bitcoin analogue of the
//! EIP-191 `personal_sign` path on the EVM side.
//!
//! When full BIP-322 lands (P2TR / arbitrary-script ownership), it belongs here
//! as `verify_simple` / `verify_full`, fronted by a Script interpreter behind a
//! feature flag, keeping `kotoba-auth` I/O- and consensus-VM-free by default.

/// Signature scheme used to prove Bitcoin address ownership.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SignatureScheme {
    /// Legacy "Bitcoin Signed Message" — implemented (P2PKH / P2WPKH).
    LegacyEcdsa,
    /// BIP-322 `simple` — **not yet implemented** (needs Script VM).
    Bip322Simple,
    /// BIP-322 `full` — **not yet implemented** (needs Script VM).
    Bip322Full,
}

impl SignatureScheme {
    /// Whether kotoba can currently verify this scheme.
    pub fn is_supported(self) -> bool {
        matches!(self, SignatureScheme::LegacyEcdsa)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_legacy_supported_in_r0() {
        assert!(SignatureScheme::LegacyEcdsa.is_supported());
        assert!(!SignatureScheme::Bip322Simple.is_supported());
        assert!(!SignatureScheme::Bip322Full.is_supported());
    }
}
