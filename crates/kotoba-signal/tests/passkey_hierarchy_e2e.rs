//! End-to-end walk of the passkey-rooted secrecy hierarchy (ADR-2606014000).
//!
//! Exercises every layer in one flow:
//!   L0 WebAuthn PRF (simulated 32-byte output)
//!   L1 Account Root Key — wrap per-passkey + Shamir guardian recovery
//!   L2 purpose keys — k_storage / k_signal / k_session
//!   L3 at-rest PII — VaultKeyedCrypto(from_ark) + context-bound blob
//!   L5 user↔user — Signal identity bound to DID, record key wrapped over the ratchet
//!
//! This is the executable spec for the wiring that production code will follow.

use kotoba_crypto::agent_crypto::{AgentCrypto, VaultKeyedCrypto};
use kotoba_crypto::key_tree::{
    self, derive_session_seed, derive_signal_seed, generate_ark, unwrap_ark, wrap_ark,
};
use kotoba_signal::identity::IdentityKeyPair;
use kotoba_signal::prekey::{PreKey, PreKeyBundle, SignedPreKey};
use kotoba_signal::session::Session;
use kotoba_signal::{unwrap_record_key, wrap_record_key, SignalBinding};

const ACCOUNT_DID: &str = "did:web:etzhayyim.com:actor:alice";

#[tokio::test]
async fn full_passkey_hierarchy_l0_to_l5() {
    // ── L0/L1: enrollment — generate ARK, wrap it under device-1's passkey PRF ──
    let prf_device_1 = b"webauthn-prf-output-device-1....";
    let ark = generate_ark();
    let wrapped = wrap_ark(prf_device_1, &ark, ACCOUNT_DID).unwrap();

    // A later session on device 1 recovers ARK from the public wrapped blob.
    let ark = unwrap_ark(prf_device_1, &wrapped, ACCOUNT_DID).unwrap();

    // ── L2/L3: at-rest PII — storage engine sourced from ARK, blob bound to slot ──
    let storage = VaultKeyedCrypto::from_ark(&ark);
    let intake_slot = b"kotoba://datom/bafyManimaniIntake-42";
    let body = b"From: doctor@example.com\nSubject: results\n\n<private>";
    let sealed = storage.encrypt_blob_bound(intake_slot, body).await.unwrap();
    // Right slot opens; a swapped slot must fail (the D2 binding).
    let opened = storage
        .decrypt_blob_bound(intake_slot, &sealed)
        .await
        .unwrap();
    assert_eq!(opened.as_slice(), body);
    assert!(
        storage
            .decrypt_blob_bound(b"kotoba://datom/other", &sealed)
            .await
            .is_err(),
        "a blob bound to one intake slot must not open under another"
    );

    // ── L2/L5: Signal identity derived from ARK, bound to the DID ──
    // Deterministic seed proves the same Signal identity is recoverable on any
    // device that can recover ARK (we only assert determinism of the seed here).
    let signal_seed_a = derive_signal_seed(&ark);
    let signal_seed_b = derive_signal_seed(&ark);
    assert_eq!(
        signal_seed_a, signal_seed_b,
        "Signal seed is ARK-deterministic"
    );
    assert_ne!(
        signal_seed_a,
        derive_session_seed(&ark),
        "signal and session seeds must be distinct purposes"
    );

    // Alice publishes a DID↔Signal binding signed by her DID key; Bob verifies it.
    use ed25519_dalek::SigningKey;
    let alice_did_key = SigningKey::from_bytes(&[3u8; 32]);
    let alice_signal = IdentityKeyPair::generate();
    let binding = SignalBinding::from_identity(
        ACCOUNT_DID,
        &alice_signal.public_key(),
        4242,
        "2026-06-01T00:00:00Z",
    );
    let binding_sig = binding.sign(&alice_did_key);
    assert!(
        binding.verify(&binding_sig, &alice_did_key.verifying_key().to_bytes()),
        "Bob must accept Alice's DID-signed Signal binding"
    );

    // ── L5: establish a Signal session and wrap a record key over the ratchet ──
    let bob_ik = IdentityKeyPair::generate();
    let bob_spk = SignedPreKey::generate(1, &bob_ik);
    let bob_opk = PreKey::generate(100);
    let bundle = PreKeyBundle {
        did: "did:web:etzhayyim.com:actor:bob".into(),
        device_id: "dev-1".into(),
        identity_key: bob_ik.public_key(),
        signed_prekey: bob_spk.public_bytes().to_vec(),
        signed_prekey_id: bob_spk.id,
        signed_prekey_sig: bob_spk.signature.clone(),
        one_time_prekey: Some(bob_opk.public_bytes().to_vec()),
        one_time_prekey_id: Some(bob_opk.id),
    };
    // Bob's binding matches the bundle he advertises (substitution guard).
    let bob_binding = SignalBinding::from_identity(
        "did:web:etzhayyim.com:actor:bob",
        &bob_ik.public_key(),
        7,
        "t",
    );
    assert!(bob_binding.matches_bundle(&bundle));

    let (mut alice_sess, ep) = Session::initiate(&alice_signal, &bundle).unwrap();
    let ep: [u8; 32] = ep.try_into().unwrap();
    let mut bob_sess = Session::accept(
        &bob_ik,
        &bob_spk,
        Some(&bob_opk),
        &alice_signal.public_key(),
        &ep,
        ACCOUNT_DID,
        "dev-a",
    )
    .unwrap();

    // The symmetric record key that protects a shared encrypted record is wrapped
    // under the established session — keyWrap with forward secrecy.
    let record_key = [0x77u8; 32];
    let kw = wrap_record_key(&mut alice_sess, &record_key).unwrap();
    let unwrapped = unwrap_record_key(&mut bob_sess, &kw).unwrap();
    assert_eq!(
        unwrapped, record_key,
        "Bob recovers the record key via the Signal wrap transport"
    );
}

#[tokio::test]
async fn guardian_recovery_then_resume_storage() {
    // Device lost: recover ARK from a 2-of-3 guardian quorum, then prove the
    // recovered ARK still opens previously-sealed at-rest PII.
    let ark = generate_ark();
    let storage = VaultKeyedCrypto::from_ark(&ark);
    let slot = b"kotoba://datom/bafyRecoveryTest";
    let sealed = storage
        .encrypt_blob_bound(slot, b"survives recovery")
        .await
        .unwrap();

    let shares = key_tree::recovery::split(&ark, 2, 3);
    let quorum = vec![shares[0].clone(), shares[2].clone()];
    let recovered_ark = key_tree::recovery::combine(&quorum).unwrap();
    assert_eq!(recovered_ark.as_slice(), ark.as_slice());

    let storage2 = VaultKeyedCrypto::from_ark(&recovered_ark);
    let opened = storage2.decrypt_blob_bound(slot, &sealed).await.unwrap();
    assert_eq!(opened.as_slice(), b"survives recovery");
}
