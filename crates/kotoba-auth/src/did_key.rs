use thiserror::Error;

const ED25519_CODEC: [u8; 2] = [0xed, 0x01];

#[derive(Debug, Error)]
pub enum DidKeyError {
    #[error("not a did:key DID: {0}")]
    NotDidKey(String),
    #[error("multibase decode error: {0}")]
    MultibaseDecode(String),
    #[error("missing Ed25519 multicodec prefix [0xed, 0x01]")]
    MissingCodecPrefix,
    #[error("invalid key length: expected 32, got {0}")]
    InvalidKeyLength(usize),
}

/// Extract the raw 32-byte Ed25519 public key from a `did:key` DID.
///
/// Accepts BOTH encodings kotoba emits for the same key:
///   - W3C standard `did:key:z6Mk…` — multibase(base58btc) of `[0xed,0x01]||pubkey`.
///   - kotoba-wasm `did:key:z<64-hex>` — `'z'` followed by `hex(pubkey32)`, no
///     multicodec (`WriteCrypto::did`; agent identities and `KOTOBA_OPERATOR_DID`
///     use this form). This form previously failed to parse, so an operator/agent
///     DID minted by the wasm path could not be verified against a CACAO produced
///     by `kotoba cacao-sign` (standard form) — see kyber-plm `live/LIVE.md`.
///     Accepting both unifies the two encodings for the same key.
pub fn parse_ed25519_did_key(did: &str) -> Result<[u8; 32], DidKeyError> {
    let key_str = did
        .strip_prefix("did:key:")
        .ok_or_else(|| DidKeyError::NotDidKey(did.to_string()))?;

    // kotoba-wasm hex form: 'z' + exactly 64 hex chars = the raw 32-byte pubkey.
    // Checked before multibase: an ed25519 base58btc did:key is ~47 chars and
    // carries the 0xed01 multicodec, so a 64-char hex body is unambiguous.
    if let Some(hex_body) = key_str.strip_prefix('z') {
        if hex_body.len() == 64 && hex_body.bytes().all(|b| b.is_ascii_hexdigit()) {
            let mut arr = [0u8; 32];
            for (i, chunk) in hex_body.as_bytes().chunks(2).enumerate() {
                let s = std::str::from_utf8(chunk).expect("ascii hex chunk");
                arr[i] = u8::from_str_radix(s, 16)
                    .map_err(|e| DidKeyError::MultibaseDecode(e.to_string()))?;
            }
            return Ok(arr);
        }
    }

    let (_, bytes) =
        multibase::decode(key_str).map_err(|e| DidKeyError::MultibaseDecode(e.to_string()))?;

    if bytes.len() < 2 || bytes[0] != ED25519_CODEC[0] || bytes[1] != ED25519_CODEC[1] {
        return Err(DidKeyError::MissingCodecPrefix);
    }

    let key_bytes = &bytes[2..];
    let len = key_bytes.len();
    if len != 32 {
        return Err(DidKeyError::InvalidKeyLength(len));
    }

    let mut arr = [0u8; 32];
    arr.copy_from_slice(key_bytes);
    Ok(arr)
}

/// kotoba-wasm hex-form encoder: `did:key:z<hex(pubkey32)>`. The non-standard
/// form used by agent identities; kept so callers can produce a DID that matches
/// `KOTOBA_AGENT_DID` / `KOTOBA_OPERATOR_DID`.
pub fn ed25519_pubkey_to_did_key_hex(pubkey: &[u8; 32]) -> String {
    let hex: String = pubkey.iter().map(|b| format!("{b:02x}")).collect();
    format!("did:key:z{hex}")
}

/// Canonicalise any accepted `did:key` form (standard or kotoba-wasm hex) to the
/// W3C standard `did:key:z6Mk…`. Use this to compare DIDs by identity rather than
/// by surface string, so `aud == operator_did` / `iss == owner` checks succeed
/// regardless of which encoding each side used.
pub fn to_canonical_did_key(did: &str) -> Result<String, DidKeyError> {
    Ok(ed25519_pubkey_to_did_key(&parse_ed25519_did_key(did)?))
}

/// True if two `did:key` DIDs denote the same Ed25519 key, across encodings.
pub fn did_keys_equal(a: &str, b: &str) -> bool {
    match (parse_ed25519_did_key(a), parse_ed25519_did_key(b)) {
        (Ok(x), Ok(y)) => x == y,
        _ => a == b,
    }
}

/// Build a `did:key:z6Mk...` DID from a raw 32-byte Ed25519 public key.
pub fn ed25519_pubkey_to_did_key(pubkey: &[u8; 32]) -> String {
    let mut payload = Vec::with_capacity(34);
    payload.extend_from_slice(&ED25519_CODEC);
    payload.extend_from_slice(pubkey);
    let encoded = multibase::encode(multibase::Base::Base58Btc, &payload);
    format!("did:key:{encoded}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::SigningKey;

    fn test_keypair() -> SigningKey {
        SigningKey::from_bytes(&[7u8; 32])
    }

    #[test]
    fn roundtrip_pubkey_to_did_key_and_back() {
        let sk = test_keypair();
        let pk = sk.verifying_key();
        let did = ed25519_pubkey_to_did_key(pk.as_bytes());
        assert!(
            did.starts_with("did:key:z6Mk"),
            "DID should start with did:key:z6Mk, got: {did}"
        );
        let recovered = parse_ed25519_did_key(&did).unwrap();
        assert_eq!(&recovered, pk.as_bytes());
    }

    #[test]
    fn parse_non_did_key_errors() {
        assert!(parse_ed25519_did_key("did:pkh:eip155:1:0xabc").is_err());
    }

    #[test]
    fn parse_wrong_codec_errors() {
        // Build a payload with secp256k1 codec [0xe7, 0x01] instead of ed25519
        let mut payload = vec![0xe7u8, 0x01];
        payload.extend_from_slice(&[0u8; 32]);
        let encoded = multibase::encode(multibase::Base::Base58Btc, &payload);
        let did = format!("did:key:{encoded}");
        let err = parse_ed25519_did_key(&did).unwrap_err();
        assert!(matches!(err, DidKeyError::MissingCodecPrefix));
    }

    #[test]
    fn parse_invalid_key_length_errors() {
        // Build a payload with correct ed25519 codec but wrong key length (16 bytes instead of 32)
        let mut payload = vec![0xedu8, 0x01];
        payload.extend_from_slice(&[0u8; 16]);
        let encoded = multibase::encode(multibase::Base::Base58Btc, &payload);
        let did = format!("did:key:{encoded}");
        let err = parse_ed25519_did_key(&did).unwrap_err();
        assert!(matches!(err, DidKeyError::InvalidKeyLength(16)));
    }

    #[test]
    fn roundtrip_is_inverse() {
        // pubkey → DID → pubkey should be lossless
        let pubkey = [0xABu8; 32];
        let did = ed25519_pubkey_to_did_key(&pubkey);
        let recovered = parse_ed25519_did_key(&did).unwrap();
        assert_eq!(recovered, pubkey);
    }

    #[test]
    fn error_display_messages() {
        let e1 = DidKeyError::NotDidKey("did:pkh:foo".to_string());
        assert!(e1.to_string().contains("not a did:key"));

        let e2 = DidKeyError::MissingCodecPrefix;
        assert!(e2.to_string().contains("Ed25519"));

        let e3 = DidKeyError::InvalidKeyLength(16);
        assert!(e3.to_string().contains("16"));

        let e4 = DidKeyError::MultibaseDecode("bad base".to_string());
        assert!(e4.to_string().contains("bad base"));
    }

    #[test]
    fn did_key_starts_with_z6mk() {
        let sk = test_keypair();
        let pk = sk.verifying_key();
        let did = ed25519_pubkey_to_did_key(pk.as_bytes());
        // z6Mk is the multibase base58btc prefix for ed25519 keys
        assert!(
            did.starts_with("did:key:z6Mk"),
            "expected did:key:z6Mk prefix, got: {did}"
        );
    }

    #[test]
    fn parses_kotoba_wasm_hex_form() {
        // 'z' + hex(pubkey32), no multicodec — the agent/operator identity form.
        let pubkey = [0xABu8; 32];
        let hex_did = ed25519_pubkey_to_did_key_hex(&pubkey);
        assert!(hex_did.starts_with("did:key:z"));
        assert_eq!(hex_did.len(), "did:key:z".len() + 64);
        assert_eq!(parse_ed25519_did_key(&hex_did).unwrap(), pubkey);
    }

    #[test]
    fn hex_and_standard_forms_decode_to_same_key() {
        let sk = test_keypair();
        let pk = *sk.verifying_key().as_bytes();
        let std_did = ed25519_pubkey_to_did_key(&pk);
        let hex_did = ed25519_pubkey_to_did_key_hex(&pk);
        assert_ne!(std_did, hex_did, "two distinct surface encodings");
        assert_eq!(parse_ed25519_did_key(&std_did).unwrap(), pk);
        assert_eq!(parse_ed25519_did_key(&hex_did).unwrap(), pk);
        // …and canonicalisation collapses them to one identity.
        assert_eq!(to_canonical_did_key(&hex_did).unwrap(), std_did);
        assert_eq!(to_canonical_did_key(&std_did).unwrap(), std_did);
        assert!(did_keys_equal(&hex_did, &std_did));
    }

    #[test]
    fn known_operator_did_hex_form_round_trips() {
        // The production KOTOBA_OPERATOR_DID is stored in hex form; it must parse
        // and canonicalise to its standard form (and back via the hex encoder).
        let op = "did:key:z35dec6b49a374eec5711a4f3ccaf66b944ecae6773766e62d71c86ff8e3b5a37";
        let pk = parse_ed25519_did_key(op).expect("hex operator DID must parse");
        assert_eq!(ed25519_pubkey_to_did_key_hex(&pk), op);
        assert_eq!(to_canonical_did_key(op).unwrap(), ed25519_pubkey_to_did_key(&pk));
    }

    #[test]
    fn hex_form_with_bad_length_falls_through_to_multibase_err() {
        // 'z' + 63 hex chars is neither the hex form (needs 64) nor valid base58btc.
        let did = format!("did:key:z{}", "a".repeat(63));
        assert!(parse_ed25519_did_key(&did).is_err());
    }
}
