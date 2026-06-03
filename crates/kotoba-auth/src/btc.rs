//! secp256k1 public-key → Bitcoin address derivation and message-signature
//! verification, plus the chain-agnostic BIP-122 / CAIP identifier surface.
//!
//! This is the Bitcoin sibling of [`crate::eth`]. It mirrors that module's
//! posture exactly:
//!
//! Boundary note: everything here is **read + verify**. No transaction is built
//! or signed, no key is generated, no UTXO is spent, no DID/on-chain state is
//! originated — that is etzhayyim-exclusive per the operating-entity boundary
//! (ADR-2605231525 No-Server-Key). A member's self-custody wallet does the
//! signing/sending; kotoba only proves address ownership and observes facts.
//!
//! The submodules depend only on `k256` + `sha2` + `ripemd` + `bs58` + `hex`
//! (no `kotoba-datomic`/`kotoba-core` coupling) so the BTC codec stays portable
//! — it can be lifted into a standalone `kotoba-btc` crate or a wasm guest later
//! without churn.
//!
//! Scope (honest R0):
//! - address derivation + validation: P2PKH (Base58Check), P2WPKH (bech32),
//!   P2TR (bech32m) — see [`address`].
//! - CAIP-2/10/19 over the `bip122` namespace — see [`caip`].
//! - signature verification: the **legacy "Bitcoin Signed Message"** scheme
//!   (Bitcoin Core `signmessage`/`verifymessage`, Electrum legacy) which uses a
//!   65-byte recoverable ECDSA signature — see [`verify_message`]. Full BIP-322
//!   (`simple`/`full`, witness-/script-based) is **deferred** (it needs virtual
//!   transaction construction + Script execution); a `bip322` placeholder
//!   documents the boundary.

pub mod address;
pub mod bip322;
pub mod caip;

use k256::ecdsa::{RecoveryId, Signature, VerifyingKey};
use ripemd::Ripemd160;
use sha2::{Digest, Sha256};
use thiserror::Error;

pub use address::{AddressKind, BtcAddress, BtcNetwork};

#[derive(Debug, Error)]
pub enum BtcError {
    #[error("invalid signature bytes: {0}")]
    Sig(String),
    #[error("invalid DID format: {0}")]
    Did(String),
    #[error("invalid address: {0}")]
    Addr(String),
    #[error("hex decode: {0}")]
    Hex(#[from] hex::FromHexError),
}

/// Single SHA-256.
pub fn sha256(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

/// Double SHA-256 — the Bitcoin "Hash256" primitive (checksums, txids, message
/// digests).
pub fn hash256(bytes: &[u8]) -> [u8; 32] {
    sha256(&sha256(bytes))
}

/// `HASH160 = RIPEMD160(SHA256(bytes))` — the 20-byte witness/pubkey-hash
/// primitive used by P2PKH and P2WPKH.
pub fn hash160(bytes: &[u8]) -> [u8; 20] {
    let sha = Sha256::digest(bytes);
    Ripemd160::digest(sha).into()
}

/// The magic prefix for legacy Bitcoin Signed Messages.
const MSG_MAGIC: &[u8] = b"\x18Bitcoin Signed Message:\n";

/// Compute the digest a legacy Bitcoin Signed Message signs:
///   `Hash256(varstr("\x18Bitcoin Signed Message:\n") || varstr(message))`
///
/// The magic itself is length-prefixed (`0x18` = 24 = its own byte length), and
/// the message is prefixed with a Bitcoin `CompactSize` varint of its length.
/// This mirrors [`crate::eth::personal_sign_hash`] for the EVM side.
pub fn signed_message_hash(message: &[u8]) -> [u8; 32] {
    let mut buf = Vec::with_capacity(MSG_MAGIC.len() + 9 + message.len());
    buf.extend_from_slice(MSG_MAGIC);
    write_compact_size(&mut buf, message.len() as u64);
    buf.extend_from_slice(message);
    hash256(&buf)
}

/// Append a Bitcoin `CompactSize` (varint) length prefix.
fn write_compact_size(buf: &mut Vec<u8>, n: u64) {
    match n {
        0..=0xfc => buf.push(n as u8),
        0xfd..=0xffff => {
            buf.push(0xfd);
            buf.extend_from_slice(&(n as u16).to_le_bytes());
        }
        0x1_0000..=0xffff_ffff => {
            buf.push(0xfe);
            buf.extend_from_slice(&(n as u32).to_le_bytes());
        }
        _ => {
            buf.push(0xff);
            buf.extend_from_slice(&n.to_le_bytes());
        }
    }
}

/// Recover the 33-byte **compressed** secp256k1 public key from a legacy
/// Bitcoin Signed Message signature.
///
/// `sig` is 65 bytes: `header(1) || r(32) || s(32)`. The header encodes both the
/// recovery id and the compression flag, per Bitcoin's `signmessage`:
///   27..=30  → uncompressed key, recid = header-27
///   31..=34  → compressed   key, recid = header-31
///
/// kotoba always returns the **compressed** SEC1 encoding (modern wallets sign
/// for compressed-key addresses); the compression bit only tells us which
/// address form the signer intended.
pub fn recover_pubkey_from_message(
    message: &[u8],
    sig: &[u8],
) -> Result<([u8; 33], bool), BtcError> {
    if sig.len() != 65 {
        return Err(BtcError::Sig(format!(
            "expected 65 bytes, got {}",
            sig.len()
        )));
    }
    let header = sig[0];
    if !(27..=34).contains(&header) {
        return Err(BtcError::Sig(format!("bad header byte: {header}")));
    }
    let compressed = header >= 31;
    let recid = if compressed { header - 31 } else { header - 27 };
    let rec_id = RecoveryId::try_from(recid).map_err(|e| BtcError::Sig(e.to_string()))?;
    let signature = Signature::from_slice(&sig[1..]).map_err(|e| BtcError::Sig(e.to_string()))?;
    let digest = signed_message_hash(message);
    let vk = VerifyingKey::recover_from_prehash(&digest, &signature, rec_id)
        .map_err(|e| BtcError::Sig(e.to_string()))?;
    let point = vk.to_encoded_point(true); // compressed SEC1
    let mut out = [0u8; 33];
    out.copy_from_slice(point.as_bytes());
    Ok((out, compressed))
}

/// Verify a legacy Bitcoin Signed Message against an expected address.
///
/// Recovers the signer's public key, derives the address of the **same kind**
/// as `expected`, and compares. Supports P2PKH and P2WPKH (the two HASH160
/// address kinds a recoverable-ECDSA `signmessage` can target). For P2TR /
/// script addresses, full BIP-322 is required — see [`bip322`].
pub fn verify_message(message: &[u8], sig: &[u8], expected: &BtcAddress) -> Result<bool, BtcError> {
    let (pubkey, _compressed) = recover_pubkey_from_message(message, sig)?;
    let h160 = hash160(&pubkey);
    match expected.kind {
        AddressKind::P2pkh | AddressKind::P2wpkh => Ok(expected.payload == h160),
        other => Err(BtcError::Sig(format!(
            "legacy signmessage cannot target {other:?}; full BIP-322 required"
        ))),
    }
}

/// Parse the BIP-122 chain reference and on-chain payload from a `did:pkh` DID.
///
/// Accepts `did:pkh:bip122:<genesis-hash-prefix>:<address>` (CAIP-10 over the
/// `bip122` namespace, the registered Bitcoin form). Returns the parsed,
/// network-validated [`BtcAddress`] alongside the chain reference string.
///
/// Reference: <https://github.com/ChainAgnostic/namespaces/blob/main/bip122/caip10.md>
pub fn parse_btc_address_from_did(iss: &str) -> Result<(String, BtcAddress), BtcError> {
    let parts: Vec<&str> = iss.split(':').collect();
    // did : pkh : bip122 : <ref> : <address>
    if parts.len() != 5 || parts[0] != "did" || parts[1] != "pkh" || parts[2] != caip::BIP122 {
        return Err(BtcError::Did(format!("not a did:pkh:bip122 DID: {iss}")));
    }
    let reference = parts[3].to_string();
    let addr = BtcAddress::parse(parts[4]).map_err(|e| BtcError::Did(e.to_string()))?;
    Ok((reference, addr))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash160_known_vector() {
        // HASH160 of the empty string = RIPEMD160(SHA256("")).
        let h = hash160(b"");
        assert_eq!(hex::encode(h), "b472a266d0bd89c13706a4132ccfb16f7c3b9fcb");
    }

    #[test]
    fn signed_message_hash_is_deterministic() {
        assert_eq!(signed_message_hash(b"hello"), signed_message_hash(b"hello"));
        assert_ne!(signed_message_hash(b"hello"), signed_message_hash(b"world"));
    }

    #[test]
    fn compact_size_boundaries() {
        let mut b = Vec::new();
        write_compact_size(&mut b, 0xfc);
        assert_eq!(b, vec![0xfc]);
        b.clear();
        write_compact_size(&mut b, 0xfd);
        assert_eq!(b, vec![0xfd, 0xfd, 0x00]);
        b.clear();
        write_compact_size(&mut b, 0x1_0000);
        assert_eq!(b, vec![0xfe, 0x00, 0x00, 0x01, 0x00]);
    }

    #[test]
    fn recover_rejects_wrong_length() {
        assert!(recover_pubkey_from_message(b"x", &[0u8; 64]).is_err());
    }

    #[test]
    fn recover_rejects_bad_header() {
        let mut sig = [0u8; 65];
        sig[0] = 26; // below the valid 27..=34 range
        assert!(recover_pubkey_from_message(b"x", &sig).is_err());
    }

    #[test]
    fn parse_did_pkh_bip122_mainnet_p2pkh() {
        // Satoshi's genesis coinbase address, mainnet genesis hash prefix.
        let did =
            "did:pkh:bip122:000000000019d6689c085ae165831e93:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa";
        let (reference, addr) = parse_btc_address_from_did(did).unwrap();
        assert_eq!(reference, "000000000019d6689c085ae165831e93");
        assert_eq!(addr.kind, AddressKind::P2pkh);
        assert_eq!(addr.network, BtcNetwork::Mainnet);
    }

    #[test]
    fn parse_did_rejects_eip155() {
        let did = "did:pkh:eip155:1:0xabcdef1234567890abcdef1234567890abcdef12";
        assert!(parse_btc_address_from_did(did).is_err());
    }

    #[test]
    fn sign_recover_verify_roundtrip_p2pkh_and_p2wpkh() {
        use k256::ecdsa::SigningKey;

        // Deterministic key (NOT a real funded key — test only).
        let sk = SigningKey::from_bytes(&[0x42u8; 32].into()).unwrap();
        let vk = sk.verifying_key();
        let pubkey_compressed = vk.to_encoded_point(true);
        let h160 = hash160(pubkey_compressed.as_bytes());

        let msg = b"etzhayyim membership: prove this BTC address";
        let digest = signed_message_hash(msg);
        let (signature, recid) = sk.sign_prehash_recoverable(&digest).unwrap();

        // Legacy header for a compressed key = 31 + recovery_id.
        let mut sig = Vec::with_capacity(65);
        sig.push(31 + recid.to_byte());
        sig.extend_from_slice(&signature.to_bytes());

        // Recovery returns the same compressed pubkey.
        let (recovered, compressed) = recover_pubkey_from_message(msg, &sig).unwrap();
        assert!(compressed);
        assert_eq!(&recovered[..], pubkey_compressed.as_bytes());

        // Verify against both HASH160 address kinds derived from that key.
        let p2pkh = BtcAddress {
            network: BtcNetwork::Mainnet,
            kind: AddressKind::P2pkh,
            payload: h160.to_vec(),
            witness_version: None,
        };
        let p2wpkh = BtcAddress {
            network: BtcNetwork::Mainnet,
            kind: AddressKind::P2wpkh,
            payload: h160.to_vec(),
            witness_version: Some(0),
        };
        assert!(verify_message(msg, &sig, &p2pkh).unwrap());
        assert!(verify_message(msg, &sig, &p2wpkh).unwrap());

        // A different message must NOT verify.
        assert!(!verify_message(b"tampered", &sig, &p2pkh).unwrap());
    }

    #[test]
    fn verify_message_rejects_taproot_target() {
        // A P2TR address cannot be verified via legacy signmessage.
        let addr =
            BtcAddress::parse("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0")
                .unwrap();
        assert_eq!(addr.kind, AddressKind::P2tr);
        let sig = [31u8; 65];
        assert!(verify_message(b"hi", &sig, &addr).is_err());
    }
}
