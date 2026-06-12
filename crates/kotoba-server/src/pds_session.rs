//! PDS session auth on kotoba-server (ADR-2606015000 — PDS refactor onto kotoba).
//!
//! The legacy TS PDS worker delegated session checks to the auth Worker. As the
//! PDS is refactored to run ON kotoba-server (the substrate already serves the
//! AT Protocol XRPC surface), session verification moves here as a Rust
//! Proof-of-Possession check: the client signs a compact EdDSA JWS with its
//! ARK-derived session key (ADR-2606014000/2606014500 C-3) and kotoba-server
//! VERIFIES it against the issuer DID's Ed25519 key — resolved trustlessly for
//! `did:key`, or from the DID document (ERC725 mirror) for `did:web`/`did:plc`.
//! No server-held signing key; read-only verification.

use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use kotoba_auth::resolver::DidDocumentResolver;
use serde_json::Value;

#[derive(Debug, Clone)]
pub struct PopVerdict {
    pub valid: bool,
    pub did: Option<String>,
    pub reason: String,
    pub claims: Option<Value>,
}

fn fail(reason: impl Into<String>) -> PopVerdict {
    PopVerdict {
        valid: false,
        did: None,
        reason: reason.into(),
        claims: None,
    }
}

/// Verify a compact EdDSA JWS session PoP (`b64url(header).b64url(payload).b64url(sig)`)
/// by resolving the issuer DID to its Ed25519 key and checking the signature.
///
/// `now_secs` is injected (no wall-clock here) so verification is deterministic
/// and testable. A DID that does not resolve, or whose document has no Ed25519
/// method, is reported unverified — never falsely vouched.
pub fn verify_session_pop(
    token: &str,
    resolver: &dyn DidDocumentResolver,
    now_secs: u64,
) -> PopVerdict {
    // No audience requirement (backwards-compatible default).
    verify_session_pop_with_audience(token, resolver, now_secs, None)
}

/// As [`verify_session_pop`], but additionally binds the token to an audience when
/// `expected_aud` is `Some`. A PoP minted for one service can otherwise be replayed
/// to another within its `exp` window; passing the verifying service's identifier
/// closes that cross-service replay. When `Some(want)`, a verified token must carry
/// `aud == want` — a missing or mismatched `aud` is rejected. `None` preserves the
/// original (audience-agnostic) behaviour, so the policy is the caller's to choose.
pub fn verify_session_pop_with_audience(
    token: &str,
    resolver: &dyn DidDocumentResolver,
    now_secs: u64,
    expected_aud: Option<&str>,
) -> PopVerdict {
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return fail("malformed token (expected 3 JWS segments)");
    }
    let (h, p, s) = (parts[0], parts[1], parts[2]);

    let header: Value = match B64U
        .decode(h)
        .ok()
        .and_then(|b| serde_json::from_slice(&b).ok())
    {
        Some(v) => v,
        None => return fail("bad header encoding"),
    };
    let payload: Value = match B64U
        .decode(p)
        .ok()
        .and_then(|b| serde_json::from_slice(&b).ok())
    {
        Some(v) => v,
        None => return fail("bad payload encoding"),
    };

    if header.get("alg").and_then(Value::as_str) != Some("EdDSA") {
        return fail("unsupported alg (expected EdDSA)");
    }
    let did = match payload.get("iss").and_then(Value::as_str) {
        Some(d) if !d.is_empty() => d.to_string(),
        _ => return fail("missing iss"),
    };
    if let Some(exp) = payload.get("exp").and_then(Value::as_u64) {
        if exp < now_secs {
            return PopVerdict {
                valid: false,
                did: Some(did),
                reason: "expired".into(),
                claims: None,
            };
        }
    }

    let pubkey = match resolver.resolve(&did) {
        Ok(doc) => match doc.ed25519_public_key() {
            Some(k) => k,
            None => {
                return PopVerdict {
                    valid: false,
                    did: Some(did),
                    reason: "DID document has no Ed25519 verification method".into(),
                    claims: None,
                }
            }
        },
        Err(e) => {
            return PopVerdict {
                valid: false,
                did: Some(did),
                reason: format!("DID resolution failed: {e}"),
                claims: None,
            }
        }
    };

    let sig_bytes = match B64U.decode(s) {
        Ok(b) => b,
        Err(_) => {
            return PopVerdict {
                valid: false,
                did: Some(did),
                reason: "bad signature encoding".into(),
                claims: None,
            }
        }
    };
    let sig_arr: [u8; 64] = match sig_bytes.as_slice().try_into() {
        Ok(a) => a,
        Err(_) => {
            return PopVerdict {
                valid: false,
                did: Some(did),
                reason: "signature not 64 bytes".into(),
                claims: None,
            }
        }
    };
    let vk = match VerifyingKey::from_bytes(&pubkey) {
        Ok(k) => k,
        Err(_) => {
            return PopVerdict {
                valid: false,
                did: Some(did),
                reason: "bad Ed25519 public key".into(),
                claims: None,
            }
        }
    };
    let signing_input = format!("{h}.{p}");
    match vk.verify(signing_input.as_bytes(), &Signature::from_bytes(&sig_arr)) {
        Ok(()) => {
            // Signature is valid; enforce audience binding if the caller requires it.
            if let Some(want) = expected_aud {
                match payload.get("aud").and_then(Value::as_str) {
                    Some(a) if a == want => {}
                    Some(_) => {
                        return PopVerdict {
                            valid: false,
                            did: Some(did),
                            reason: "audience mismatch".into(),
                            claims: None,
                        }
                    }
                    None => {
                        return PopVerdict {
                            valid: false,
                            did: Some(did),
                            reason: "missing aud (audience binding required)".into(),
                            claims: None,
                        }
                    }
                }
            }
            PopVerdict {
                valid: true,
                did: Some(did),
                reason: "ok".into(),
                claims: Some(payload),
            }
        }
        Err(_) => PopVerdict {
            valid: false,
            did: Some(did),
            reason: "signature invalid".into(),
            claims: None,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*; // base64 Engine + B64U already in scope from the module
    use ed25519_dalek::{Signer, SigningKey};
    use kotoba_auth::resolver::{CompositeDidResolver, DidKeyResolver, InMemoryDidResolver};

    fn didkey_resolver() -> CompositeDidResolver {
        CompositeDidResolver::new().with_method(DidKeyResolver)
    }

    /// Build a signed PoP token for a did:key issuer.
    fn make_pop(seed: u8, exp: u64) -> (String, String) {
        let sk = SigningKey::from_bytes(&[seed; 32]);
        let did = kotoba_auth::did_key::ed25519_pubkey_to_did_key(&sk.verifying_key().to_bytes());
        let header = B64U.encode(
            serde_json::to_vec(&serde_json::json!({ "alg": "EdDSA", "typ": "pop+jwt" })).unwrap(),
        );
        let payload = B64U.encode(
            serde_json::to_vec(
                &serde_json::json!({ "iss": did, "sub": did, "iat": 1_750_000_000u64, "exp": exp }),
            )
            .unwrap(),
        );
        let signing_input = format!("{header}.{payload}");
        let sig = sk.sign(signing_input.as_bytes());
        (
            format!("{signing_input}.{}", B64U.encode(sig.to_bytes())),
            did,
        )
    }

    /// Build a signed PoP carrying an `aud` claim (or none when `aud` is `None`).
    fn make_pop_with_aud(seed: u8, exp: u64, aud: Option<&str>) -> (String, String) {
        let sk = SigningKey::from_bytes(&[seed; 32]);
        let did = kotoba_auth::did_key::ed25519_pubkey_to_did_key(&sk.verifying_key().to_bytes());
        let header =
            B64U.encode(serde_json::to_vec(&serde_json::json!({ "alg": "EdDSA" })).unwrap());
        let mut claims = serde_json::json!({ "iss": did, "exp": exp });
        if let Some(a) = aud {
            claims["aud"] = serde_json::json!(a);
        }
        let payload = B64U.encode(serde_json::to_vec(&claims).unwrap());
        let signing_input = format!("{header}.{payload}");
        let sig = sk.sign(signing_input.as_bytes());
        (
            format!("{signing_input}.{}", B64U.encode(sig.to_bytes())),
            did,
        )
    }

    #[test]
    fn audience_binding_accepts_matching_rejects_mismatch_and_missing() {
        let now = 1_750_000_100;
        let exp = 1_750_003_600;
        let r = didkey_resolver();

        // Matching aud → valid.
        let (tok, _) = make_pop_with_aud(7, exp, Some("did:web:srv-a"));
        assert!(verify_session_pop_with_audience(&tok, &r, now, Some("did:web:srv-a")).valid);

        // Mismatched aud → rejected (the cross-service-replay case: a token minted
        // for srv-b presented to srv-a).
        let (tok_b, _) = make_pop_with_aud(7, exp, Some("did:web:srv-b"));
        let v = verify_session_pop_with_audience(&tok_b, &r, now, Some("did:web:srv-a"));
        assert!(!v.valid);
        assert_eq!(v.reason, "audience mismatch");

        // No aud at all, but the verifier requires one → rejected.
        let (tok_none, _) = make_pop_with_aud(7, exp, None);
        let v2 = verify_session_pop_with_audience(&tok_none, &r, now, Some("did:web:srv-a"));
        assert!(!v2.valid);
        assert_eq!(v2.reason, "missing aud (audience binding required)");
    }

    #[test]
    fn no_audience_requirement_ignores_aud_claim_backward_compatible() {
        // Default path (expected_aud = None): an `aud` claim is neither required nor
        // checked, so existing audience-agnostic callers are unaffected.
        let now = 1_750_000_100;
        let (tok, _) = make_pop_with_aud(7, 1_750_003_600, Some("did:web:whatever"));
        assert!(verify_session_pop(&tok, &didkey_resolver(), now).valid);
        // And a token with no aud still verifies under the no-requirement path.
        let (tok_none, _) = make_pop_with_aud(7, 1_750_003_600, None);
        assert!(verify_session_pop(&tok_none, &didkey_resolver(), now).valid);
    }

    #[test]
    fn didkey_pop_verifies_trustlessly() {
        let (token, did) = make_pop(7, 1_750_003_600);
        let v = verify_session_pop(&token, &didkey_resolver(), 1_750_000_100);
        assert!(v.valid, "reason={}", v.reason);
        assert_eq!(v.did.as_deref(), Some(did.as_str()));
    }

    #[test]
    fn tampered_payload_rejected() {
        let (token, _) = make_pop(7, 1_750_003_600);
        let mut parts: Vec<&str> = token.split('.').collect();
        // swap payload for a different one (re-encode iss with extra claim)
        let bad_payload = B64U.encode(b"{\"iss\":\"did:key:zEvil\",\"exp\":9999999999}");
        parts[1] = &bad_payload;
        let bad = parts.join(".");
        assert!(!verify_session_pop(&bad, &didkey_resolver(), 1_750_000_100).valid);
    }

    #[test]
    fn expired_token_rejected() {
        let (token, _) = make_pop(7, 1_750_000_000); // exp in the past relative to now
        let v = verify_session_pop(&token, &didkey_resolver(), 1_750_999_999);
        assert!(!v.valid);
        assert_eq!(v.reason, "expired");
    }

    #[test]
    fn didweb_verifies_against_resolved_doc() {
        use kotoba_auth::did_document::{DidDocument, VerificationMethod, ED25519_KEY_TYPE_2020};
        let sk = SigningKey::from_bytes(&[9u8; 32]);
        let did = "did:web:etzhayyim.com:actor:alice";
        // sign a PoP for the did:web issuer with sk
        let header =
            B64U.encode(serde_json::to_vec(&serde_json::json!({ "alg": "EdDSA" })).unwrap());
        let payload = B64U.encode(
            serde_json::to_vec(&serde_json::json!({ "iss": did, "exp": 1_750_003_600u64 }))
                .unwrap(),
        );
        let signing_input = format!("{header}.{payload}");
        let sig = sk.sign(signing_input.as_bytes());
        let token = format!("{signing_input}.{}", B64U.encode(sig.to_bytes()));

        let mut doc = DidDocument::empty(did);
        doc.verification_method.push(VerificationMethod {
            id: format!("{did}#session-key"),
            key_type: ED25519_KEY_TYPE_2020.to_string(),
            controller: did.to_string(),
            public_key_multibase: multibase::encode(
                multibase::Base::Base58Btc,
                sk.verifying_key().as_bytes(),
            ),
        });
        let resolver = InMemoryDidResolver::new();
        resolver.insert(did, doc);

        let v = verify_session_pop(&token, &resolver, 1_750_000_100);
        assert!(v.valid, "reason={}", v.reason);
    }

    #[test]
    fn unresolvable_did_not_vouched() {
        let (token, _) = make_pop(7, 1_750_003_600);
        // empty resolver → did:key method unavailable → resolution fails
        let v = verify_session_pop(&token, &CompositeDidResolver::new(), 1_750_000_100);
        assert!(!v.valid);
        assert!(
            v.reason.contains("resolution failed"),
            "reason={}",
            v.reason
        );
    }

    // ── error-path coverage ───────────────────────────────────────────────────

    #[test]
    fn malformed_token_segments_rejected() {
        for bad in ["", "only-one", "two.parts", "a.b.c.d"] {
            let v = verify_session_pop(bad, &didkey_resolver(), 1_750_000_100);
            assert!(!v.valid, "{bad:?} should be rejected");
            assert!(
                v.reason.contains("malformed")
                    || v.reason.contains("encoding")
                    || v.reason.contains("alg")
            );
        }
    }

    #[test]
    fn bad_base64_header_rejected() {
        let v = verify_session_pop("!!!.@@@.###", &didkey_resolver(), 1_750_000_100);
        assert!(!v.valid);
        assert!(v.reason.contains("header"), "reason={}", v.reason);
    }

    #[test]
    fn non_eddsa_alg_rejected() {
        let header = B64U.encode(b"{\"alg\":\"HS256\"}");
        let payload = B64U.encode(b"{\"iss\":\"did:key:z6MkX\"}");
        let token = format!("{header}.{payload}.{}", B64U.encode([0u8; 64]));
        let v = verify_session_pop(&token, &didkey_resolver(), 1_750_000_100);
        assert!(!v.valid);
        assert!(v.reason.contains("alg"), "reason={}", v.reason);
    }

    #[test]
    fn missing_iss_rejected() {
        let header = B64U.encode(b"{\"alg\":\"EdDSA\"}");
        let payload = B64U.encode(b"{\"exp\":9999999999}");
        let token = format!("{header}.{payload}.{}", B64U.encode([0u8; 64]));
        let v = verify_session_pop(&token, &didkey_resolver(), 1_750_000_100);
        assert!(!v.valid);
        assert!(v.reason.contains("iss"), "reason={}", v.reason);
    }

    #[test]
    fn signature_wrong_length_rejected() {
        let (token, _) = make_pop(7, 1_750_003_600);
        let mut parts: Vec<&str> = token.split('.').collect();
        let short_sig = B64U.encode([0u8; 32]); // not 64 bytes
        parts[2] = &short_sig;
        let v = verify_session_pop(&parts.join("."), &didkey_resolver(), 1_750_000_100);
        assert!(!v.valid);
        assert!(
            v.reason.contains("64 bytes") || v.reason.contains("invalid"),
            "reason={}",
            v.reason
        );
    }

    #[test]
    fn pop_valid_signature_by_wrong_key_rejected() {
        // Impersonation / key-confusion: a token claims a VICTIM's did:key as `iss`
        // but is signed by a DIFFERENT key with a perfectly valid Ed25519 signature.
        // verify resolves the victim DID to the victim's key and checks against it,
        // so the structurally-valid-but-wrong-signer signature must fail. Distinct
        // from `tampered_payload_rejected`, which swaps to an *invalid* issuer that
        // fails at resolution rather than at the signature check.
        let victim_sk = SigningKey::from_bytes(&[7u8; 32]);
        let victim_did =
            kotoba_auth::did_key::ed25519_pubkey_to_did_key(&victim_sk.verifying_key().to_bytes());
        let attacker_sk = SigningKey::from_bytes(&[8u8; 32]); // not the victim's key
        let header =
            B64U.encode(serde_json::to_vec(&serde_json::json!({ "alg": "EdDSA" })).unwrap());
        let payload = B64U.encode(
            serde_json::to_vec(&serde_json::json!({ "iss": victim_did, "exp": 1_750_003_600u64 }))
                .unwrap(),
        );
        let signing_input = format!("{header}.{payload}");
        let sig = attacker_sk.sign(signing_input.as_bytes()); // valid sig, wrong signer
        let token = format!("{signing_input}.{}", B64U.encode(sig.to_bytes()));

        let v = verify_session_pop(&token, &didkey_resolver(), 1_750_000_100);
        assert!(!v.valid, "a PoP signed by a non-DID key must not verify");
        assert_eq!(
            v.did.as_deref(),
            Some(victim_did.as_str()),
            "iss still extracted"
        );
        assert_eq!(v.reason, "signature invalid");
    }

    #[test]
    fn tampered_header_rejected() {
        // The signing input is `header.payload`, so the header is integrity-protected
        // by the signature. Mutating it after signing — even to a still-EdDSA header
        // that passes the alg gate — must invalidate the signature. Complements
        // `tampered_payload_rejected` (the other half of the signing input).
        let (token, _) = make_pop(7, 1_750_003_600);
        let mut parts: Vec<&str> = token.split('.').collect();
        // Still alg=EdDSA (so it passes the alg check and reaches signature verify),
        // but a different byte sequence than what was signed.
        let new_header = B64U.encode(b"{\"alg\":\"EdDSA\",\"extra\":\"x\"}");
        parts[0] = &new_header;
        let v = verify_session_pop(&parts.join("."), &didkey_resolver(), 1_750_000_100);
        assert!(!v.valid, "tampered header must be rejected");
        assert_eq!(v.reason, "signature invalid");
    }

    #[test]
    fn doc_without_ed25519_method_not_vouched() {
        use kotoba_auth::did_document::DidDocument;
        let did = "did:web:etzhayyim.com:actor:nokeys";
        let header = B64U.encode(b"{\"alg\":\"EdDSA\"}");
        let payload = B64U.encode(format!("{{\"iss\":\"{did}\",\"exp\":9999999999}}").as_bytes());
        let token = format!("{header}.{payload}.{}", B64U.encode([0u8; 64]));
        let resolver = InMemoryDidResolver::new();
        resolver.insert(did, DidDocument::empty(did)); // no verification method
        let v = verify_session_pop(&token, &resolver, 1_750_000_100);
        assert!(!v.valid);
        assert!(v.reason.contains("no Ed25519"), "reason={}", v.reason);
    }
}
