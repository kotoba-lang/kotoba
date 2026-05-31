//! EIP-1271 — contract (smart-account) signature verification.
//!
//! EOA signatures are recovered with [`super::recover_eth_address`]. But the
//! platform's ERC-4337 Smart Wallets are **contracts**: their signatures are
//! NOT ECDSA-recoverable. They are verified by calling the wallet contract's
//! `isValidSignature(bytes32,bytes)` (EIP-1271) and checking for the magic
//! return value `0x1626ba7e`.
//!
//! This module builds the `eth_call` calldata and decodes the magic value. The
//! call itself is a read-only `eth_call` (no transaction, no signing), so it is
//! within the read+verify boundary. The caller (host EVM bridge / kotoba-server)
//! performs the RPC round-trip.
//!
//! Verification flow for a CACAO/SIWE signature from a smart account:
//! ```ignore
//! let hash = eth::personal_sign_hash(siwe_message.as_bytes());
//! let calldata = eip1271::is_valid_signature_calldata(&hash, &sig_bytes);
//! let ret = evm.eth_call(rpc, wallet_addr_hex, calldata, None)?;
//! let ok = eip1271::is_magic_value(&ret);
//! ```
//!
//! Reference: <https://eips.ethereum.org/EIPS/eip-1271>

use super::abi::{self, WORD};

/// EIP-1271 magic value returned by a valid `isValidSignature` call
/// (the function selector of `isValidSignature(bytes32,bytes)`).
pub const MAGIC_VALUE: [u8; 4] = [0x16, 0x26, 0xba, 0x7e];

/// Build calldata for `isValidSignature(bytes32 hash, bytes signature)`.
///
/// Layout: selector ‖ hash(word) ‖ offset(0x40) ‖ sig-length(word) ‖ sig(padded).
pub fn is_valid_signature_calldata(hash: &[u8; 32], signature: &[u8]) -> Vec<u8> {
    let selector = abi::selector("isValidSignature(bytes32,bytes)");
    debug_assert_eq!(selector, MAGIC_VALUE, "EIP-1271 selector == magic value");

    let mut out = Vec::with_capacity(4 + WORD * 3 + signature.len());
    out.extend_from_slice(&selector);

    // arg0: bytes32 hash (static word)
    out.extend_from_slice(hash);

    // arg1: dynamic `bytes` — head holds the offset to the tail (0x40 = 2 words
    // after the start of the argument block).
    let mut offset = [0u8; WORD];
    offset[WORD - 1] = 0x40;
    out.extend_from_slice(&offset);

    // tail: length word + data, right-padded to a 32-byte boundary.
    let mut len_word = [0u8; WORD];
    let len = signature.len();
    len_word[WORD - 8..].copy_from_slice(&(len as u64).to_be_bytes());
    out.extend_from_slice(&len_word);
    out.extend_from_slice(signature);
    let pad = (WORD - (len % WORD)) % WORD;
    out.extend(std::iter::repeat(0u8).take(pad));

    out
}

/// Return true if the `eth_call` return data carries the EIP-1271 magic value.
///
/// `isValidSignature` returns `bytes4`, ABI-encoded as a 32-byte word with the
/// 4 magic bytes left-aligned (followed by zero padding).
pub fn is_magic_value(ret: &[u8]) -> bool {
    ret.len() >= 4 && ret[..4] == MAGIC_VALUE
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selector_equals_magic_value() {
        assert_eq!(
            abi::selector("isValidSignature(bytes32,bytes)"),
            MAGIC_VALUE
        );
    }

    #[test]
    fn calldata_layout_65_byte_sig() {
        let hash = [0xAAu8; 32];
        let sig = [0xBBu8; 65]; // typical r||s||v
        let cd = is_valid_signature_calldata(&hash, &sig);

        // 4 selector + hash word + offset word + length word + 65 sig + 31 pad = 160
        assert_eq!(cd.len(), 4 + 32 + 32 + 32 + 65 + 31);
        assert_eq!(&cd[..4], &MAGIC_VALUE);
        assert_eq!(&cd[4..36], &hash); // hash word
        assert_eq!(cd[67], 0x40); // offset low byte
        assert_eq!(cd[99], 65); // length low byte
        assert_eq!(&cd[100..165], &sig); // signature bytes
        assert!(cd[165..].iter().all(|&b| b == 0)); // padding
    }

    #[test]
    fn magic_value_detection() {
        // Valid: magic left-aligned in a word
        let mut ok = [0u8; 32];
        ok[..4].copy_from_slice(&MAGIC_VALUE);
        assert!(is_magic_value(&ok));

        // Invalid: zero word (failed verification)
        assert!(!is_magic_value(&[0u8; 32]));
        // Too short
        assert!(!is_magic_value(&[0x16, 0x26]));
    }
}
