//! secp256k1 recovery + ETH address derivation for SIWE/EIP-191, plus the
//! read-only EVM surface: address checksums (EIP-55), ABI codec ([`abi`]),
//! ERC-20/721/1155 read helpers ([`token`]), CAIP identifiers ([`caip`]), and
//! EIP-1271 smart-account signature verification ([`eip1271`]).
//!
//! The submodules depend only on `sha3` + `hex` (no `kotoba-datomic`/`kotoba-core`
//! coupling) so the EVM codec stays portable — it can be lifted into a standalone
//! `kotoba-evm` crate or a wasm guest later without churn.
//!
//! Boundary note: everything here is **read + verify**. No transaction is built
//! or signed, no key is generated, no DID/on-chain state is originated — that is
//! etzhayyim-exclusive per the operating-entity boundary.

pub mod abi;
pub mod caip;
pub mod eip1271;
pub mod token;

use k256::ecdsa::{RecoveryId, Signature, VerifyingKey};
use sha3::{Digest, Keccak256};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum EthError {
    #[error("invalid signature bytes: {0}")]
    Sig(String),
    #[error("invalid DID format: {0}")]
    Did(String),
    #[error("invalid address: {0}")]
    Addr(String),
    #[error("hex decode: {0}")]
    Hex(#[from] hex::FromHexError),
}

/// keccak256 of arbitrary bytes — the EVM hash primitive.
pub fn keccak256(bytes: &[u8]) -> [u8; 32] {
    Keccak256::digest(bytes).into()
}

/// Format a 20-byte address as an EIP-55 mixed-case checksummed `0x` string.
///
/// The checksum is derived from the keccak256 of the **lowercase ASCII hex**
/// (40 chars, no `0x`): hex digit `i` is uppercased when nibble `i` of that hash
/// is ≥ 8.
///
/// Reference: <https://eips.ethereum.org/EIPS/eip-55>
pub fn to_checksum_address(addr: &[u8; 20]) -> String {
    let lower = hex::encode(addr); // 40 lowercase hex chars
    let hash = keccak256(lower.as_bytes());
    let mut out = String::with_capacity(42);
    out.push_str("0x");
    for (i, ch) in lower.chars().enumerate() {
        if ch.is_ascii_digit() {
            out.push(ch);
        } else {
            // nibble i of the hash: high nibble for even i, low nibble for odd i
            let nibble = if i % 2 == 0 {
                hash[i / 2] >> 4
            } else {
                hash[i / 2] & 0x0f
            };
            if nibble >= 8 {
                out.push(ch.to_ascii_uppercase());
            } else {
                out.push(ch);
            }
        }
    }
    out
}

/// True if `s` is a structurally valid `0x`-prefixed 20-byte hex address,
/// ignoring case (does not enforce the EIP-55 checksum).
pub fn is_valid_address(s: &str) -> bool {
    let body = match s.strip_prefix("0x").or_else(|| s.strip_prefix("0X")) {
        Some(b) => b,
        None => return false,
    };
    body.len() == 40 && body.bytes().all(|b| b.is_ascii_hexdigit())
}

/// True if `s` is a valid address whose mixed-case spelling matches its EIP-55
/// checksum. All-lowercase or all-uppercase inputs are accepted (no checksum
/// information present), matching the EIP-55 verification rule.
pub fn is_valid_checksum_address(s: &str) -> bool {
    if !is_valid_address(s) {
        return false;
    }
    let body = &s[2..];
    // No case mixing → no checksum to verify.
    let has_upper = body.chars().any(|c| c.is_ascii_uppercase());
    let has_lower = body.chars().any(|c| c.is_ascii_lowercase());
    if !(has_upper && has_lower) {
        return true;
    }
    match parse_address_unchecked(s) {
        Ok(addr) => to_checksum_address(&addr) == s,
        Err(_) => false,
    }
}

/// Parse a `0x`-prefixed hex address WITHOUT checksum verification.
fn parse_address_unchecked(s: &str) -> Result<[u8; 20], EthError> {
    let body = s
        .strip_prefix("0x")
        .or_else(|| s.strip_prefix("0X"))
        .ok_or_else(|| EthError::Addr(format!("missing 0x prefix: {s}")))?;
    if body.len() != 40 {
        return Err(EthError::Addr(format!(
            "expected 40 hex chars, got {}",
            body.len()
        )));
    }
    let bytes = hex::decode(body)?;
    let mut addr = [0u8; 20];
    addr.copy_from_slice(&bytes);
    Ok(addr)
}

/// Parse a `0x`-prefixed hex address into 20 bytes, enforcing the EIP-55
/// checksum when the input is mixed-case. All-lower / all-upper inputs are
/// accepted as-is.
pub fn parse_address(s: &str) -> Result<[u8; 20], EthError> {
    if !is_valid_checksum_address(s) {
        // Distinguish "bad checksum" from "bad format" for a clearer message.
        if is_valid_address(s) {
            return Err(EthError::Addr(format!("EIP-55 checksum mismatch: {s}")));
        }
        return Err(EthError::Addr(format!("malformed address: {s}")));
    }
    parse_address_unchecked(s)
}

/// Compute EIP-191 personal_sign hash:
///   keccak256("\x19Ethereum Signed Message:\n" + len + msg)
pub fn personal_sign_hash(msg: &[u8]) -> [u8; 32] {
    let prefix = format!("\x19Ethereum Signed Message:\n{}", msg.len());
    Keccak256::new()
        .chain_update(prefix.as_bytes())
        .chain_update(msg)
        .finalize()
        .into()
}

/// Recover the ETH address from an EIP-191 signature.
/// `sig` is 65 bytes: r(32) + s(32) + v(1).
/// Handles both legacy v ∈ {27,28} and EIP-155 v ∈ {0,1}.
pub fn recover_eth_address(hash: &[u8; 32], sig: &[u8]) -> Result<[u8; 20], EthError> {
    if sig.len() != 65 {
        return Err(EthError::Sig(format!(
            "expected 65 bytes, got {}",
            sig.len()
        )));
    }
    let v_raw = sig[64];
    let v = if v_raw >= 27 { v_raw - 27 } else { v_raw } % 2;
    let rec_id = RecoveryId::try_from(v).map_err(|e| EthError::Sig(e.to_string()))?;
    let sig65 = Signature::from_slice(&sig[..64]).map_err(|e| EthError::Sig(e.to_string()))?;
    let vk = VerifyingKey::recover_from_prehash(hash, &sig65, rec_id)
        .map_err(|e| EthError::Sig(e.to_string()))?;

    // ETH address = keccak256(uncompressed_pubkey[1..])[12..]
    let point = vk.to_encoded_point(false);
    let hash = Keccak256::digest(&point.as_bytes()[1..]);
    let mut addr = [0u8; 20];
    addr.copy_from_slice(&hash[12..]);
    Ok(addr)
}

/// Parse ETH address bytes from a DID string.
/// Accepts:
///   `did:pkh:eip155:N:0x<hex>`   — standard CAIP-74
///   `did:erc725:etzhayyim:N:0x<hex>`  — etzhayyim-internal
pub fn parse_eth_address_from_did(iss: &str) -> Result<[u8; 20], EthError> {
    let parts: Vec<&str> = iss.split(':').collect();
    // did:pkh:eip155:1:0x...  → parts[4]
    // did:erc725:etzhayyim:N:0x... → parts[4]
    let hex_addr = parts
        .last()
        .ok_or_else(|| EthError::Did(iss.to_string()))?
        .trim_start_matches("0x");
    let bytes = hex::decode(hex_addr)?;
    if bytes.len() != 20 {
        return Err(EthError::Did(format!(
            "address is {} bytes, expected 20",
            bytes.len()
        )));
    }
    let mut addr = [0u8; 20];
    addr.copy_from_slice(&bytes);
    Ok(addr)
}

/// Convert a raw 20-byte ETH address to a etzhayyim ERC-725 DID.
/// Format: `did:erc725:etzhayyim:260425:0x{hex}`
pub fn eth_address_to_erc725_did(addr: &[u8; 20]) -> String {
    format!("did:erc725:etzhayyim:260425:0x{}", hex::encode(addr))
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── eth_address_to_erc725_did ─────────────────────────────────────────────

    #[test]
    fn erc725_did_format() {
        let addr = [0x00u8; 20];
        let did = eth_address_to_erc725_did(&addr);
        assert!(did.starts_with("did:erc725:etzhayyim:260425:0x"));
        assert_eq!(did.len(), "did:erc725:etzhayyim:260425:0x".len() + 40);
    }

    #[test]
    fn erc725_did_known_address() {
        let mut addr = [0u8; 20];
        addr[19] = 0xAB;
        let did = eth_address_to_erc725_did(&addr);
        assert!(did.ends_with("ab"), "last byte 0xAB → hex 'ab': {did}");
    }

    // ── parse_eth_address_from_did ────────────────────────────────────────────

    #[test]
    fn parse_pkh_did() {
        let did = "did:pkh:eip155:1:0xabcdef1234567890abcdef1234567890abcdef12";
        let addr = parse_eth_address_from_did(did).unwrap();
        assert_eq!(addr[0], 0xab);
        assert_eq!(addr[19], 0x12);
    }

    #[test]
    fn parse_erc725_did() {
        let did = "did:erc725:etzhayyim:260425:0xabcdef1234567890abcdef1234567890abcdef12";
        let addr = parse_eth_address_from_did(did).unwrap();
        assert_eq!(addr[0], 0xab);
    }

    #[test]
    fn parse_did_rejects_wrong_length() {
        // 19 bytes hex = 38 hex chars
        let did = "did:pkh:eip155:1:0xabcdef1234567890abcdef1234567890abcdef";
        let result = parse_eth_address_from_did(did);
        assert!(result.is_err());
    }

    #[test]
    fn parse_did_rejects_invalid_hex() {
        let did = "did:pkh:eip155:1:0xGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG";
        let result = parse_eth_address_from_did(did);
        assert!(result.is_err());
    }

    // ── personal_sign_hash ────────────────────────────────────────────────────

    #[test]
    fn personal_sign_hash_deterministic() {
        let h1 = personal_sign_hash(b"hello");
        let h2 = personal_sign_hash(b"hello");
        assert_eq!(h1, h2);
    }

    #[test]
    fn personal_sign_hash_different_messages_differ() {
        let h1 = personal_sign_hash(b"hello");
        let h2 = personal_sign_hash(b"world");
        assert_ne!(h1, h2);
    }

    #[test]
    fn personal_sign_hash_is_32_bytes() {
        let h = personal_sign_hash(b"test");
        assert_eq!(h.len(), 32);
    }

    // ── EIP-55 checksum ───────────────────────────────────────────────────────

    #[test]
    fn checksum_known_vectors() {
        // Canonical EIP-55 test vectors.
        let cases = [
            "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
            "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
            "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
            "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
        ];
        for expected in cases {
            let addr = parse_address_unchecked(expected).unwrap();
            assert_eq!(
                to_checksum_address(&addr),
                expected,
                "checksum for {expected}"
            );
        }
    }

    #[test]
    fn is_valid_checksum_address_accepts_and_rejects() {
        // Correct mixed-case checksum
        assert!(is_valid_checksum_address(
            "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        ));
        // All-lowercase (no checksum info) is accepted
        assert!(is_valid_checksum_address(
            "0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed"
        ));
        // Wrong mixed-case checksum is rejected
        assert!(!is_valid_checksum_address(
            "0x5AAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        ));
    }

    #[test]
    fn is_valid_address_format() {
        assert!(is_valid_address(
            "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        ));
        assert!(!is_valid_address(
            "5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        )); // no 0x
        assert!(!is_valid_address("0x1234")); // too short
        assert!(!is_valid_address(
            "0xZZAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        )); // non-hex
    }

    #[test]
    fn parse_address_enforces_checksum() {
        let s = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed";
        let addr = parse_address(s).unwrap();
        assert_eq!(to_checksum_address(&addr), s);

        // Mixed-case with a flipped checksum bit → error
        assert!(parse_address("0x5AAeb6053F3E94C9b9A09f33669435E7Ef1BeAed").is_err());
        // Malformed → error
        assert!(parse_address("0xnothex").is_err());
        // All-lowercase round-trips back to the checksummed form
        let lower = parse_address("0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed").unwrap();
        assert_eq!(to_checksum_address(&lower), s);
    }

    #[test]
    fn keccak256_known_vector() {
        // keccak256("") = c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470
        let h = keccak256(b"");
        assert_eq!(
            hex::encode(h),
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
        );
    }

    // ── recover_eth_address ───────────────────────────────────────────────────

    #[test]
    fn recover_known_vector_roundtrip() {
        // A real secp256k1 sign → recover roundtrip: derive the address from a
        // fixed key, sign an EIP-191 hash, and assert recovery returns the same
        // address for both legacy (v=27/28) and EIP-155 (v=0/1) encodings.
        use k256::ecdsa::SigningKey;

        let sk_bytes = [
            0x4cu8, 0x0b, 0x3a, 0x1f, 0x9e, 0x77, 0x21, 0x55, 0x88, 0x90, 0xab, 0xcd, 0xef, 0x01,
            0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef, 0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54, 0x32,
            0x10, 0x11, 0x22, 0x33,
        ];
        let sk = SigningKey::from_bytes((&sk_bytes).into()).expect("valid key");
        let vk = sk.verifying_key();
        let point = vk.to_encoded_point(false);
        let mut expected = [0u8; 20];
        expected.copy_from_slice(&Keccak256::digest(&point.as_bytes()[1..])[12..]);

        let hash = personal_sign_hash(b"kotoba eip-191 vector");
        let (sig, rec_id) = sk.sign_prehash_recoverable(&hash).expect("sign");

        // Legacy v = rec_id + 27
        let mut legacy = sig.to_bytes().to_vec();
        legacy.push(u8::from(rec_id) + 27);
        assert_eq!(recover_eth_address(&hash, &legacy).unwrap(), expected);

        // EIP-155 raw parity v = rec_id
        let mut raw = sig.to_bytes().to_vec();
        raw.push(u8::from(rec_id));
        assert_eq!(recover_eth_address(&hash, &raw).unwrap(), expected);

        // Sanity: the checksummed form of the recovered address is stable.
        assert!(is_valid_checksum_address(&to_checksum_address(&expected)));
    }

    #[test]
    fn recover_rejects_wrong_length_sig() {
        let hash = [0u8; 32];
        let sig = [0u8; 64]; // 64 bytes, not 65
        let result = recover_eth_address(&hash, &sig);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("65"), "error should mention 65 bytes: {msg}");
    }

    // ── EthError display ──────────────────────────────────────────────────────

    #[test]
    fn eth_error_display_sig() {
        let e = EthError::Sig("bad sig".to_string());
        assert!(e.to_string().contains("bad sig"));
    }

    #[test]
    fn eth_error_display_did() {
        let e = EthError::Did("bad did".to_string());
        assert!(e.to_string().contains("bad did"));
    }

    // ── roundtrip: parse DID → encode back ───────────────────────────────────

    #[test]
    fn roundtrip_address_via_erc725_did() {
        let original = [0x11u8; 20];
        let did = eth_address_to_erc725_did(&original);
        let parsed = parse_eth_address_from_did(&did).unwrap();
        assert_eq!(original, parsed);
    }
}
