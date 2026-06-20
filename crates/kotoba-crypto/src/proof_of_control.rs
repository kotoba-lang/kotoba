//! proof_of_control — self-issued, non-extractable actor keys + a zero-knowledge proof of control.
//!
//! The actor-identity model the organism always intended, made real:
//!
//! * Each actor **issues its own key** ([`ActorKey::issue`]). The secret scalar is generated
//!   locally and held **opaquely** — no method on this type ever returns it, and it is zeroized
//!   on drop. It is *non-extractable through this API*: even the holder cannot pull the raw key
//!   out. (A hardware backend — Secure Enclave / TPM — slots in behind the same surface for true
//!   never-in-RAM non-extractability; this software type is the portable interface and the
//!   default. We make no claim of hardware isolation here, only that the *interface* never
//!   reveals the secret.)
//! * **No one else — and no server (no-server-key) — ever sees the secret.** Only the public
//!   [`ActorIdentity`] commitment is shared (a 32-byte ristretto point, serialisable as the
//!   actor's `did:key` payload).
//! * **Control is proven in zero knowledge.** [`ActorKey::prove_control`] produces a
//!   non-interactive Schnorr proof of knowledge of the discrete log of the identity point
//!   (Fiat–Shamir over ristretto255), bound to a caller-supplied `context` for domain
//!   separation. The verifier ([`ControlProof::verify`]) learns *only* that the prover controls
//!   the key — never the key itself.
//!
//! This is a textbook Schnorr Σ-protocol (honest-verifier zero-knowledge, special-sound),
//! made non-interactive via Fiat–Shamir. It proves *control*, it never extracts the key:
//! the secret is revealed to no one, ever — including its own holder, through this surface.

use curve25519_dalek::{
    ristretto::{CompressedRistretto, RistrettoPoint},
    scalar::Scalar,
};
use multibase::Base;
use rand_core::{CryptoRng, RngCore};
use sha2::{Digest, Sha512};
use zeroize::{Zeroize, ZeroizeOnDrop};

/// Domain-separation tag for the Fiat–Shamir challenge (versioned).
const CHALLENGE_DOMAIN: &[u8] = b"kotoba.actor.proof-of-control.schnorr.v1";
/// Domain-separation tag for the hedged synthetic nonce (versioned).
const NONCE_DOMAIN: &[u8] = b"kotoba.actor.proof-of-control.nonce.v1";

/// An actor's public identity: the commitment `P = x·G` to its secret `x`.
/// Carries no secret; safe to publish (e.g. as the actor's `did:key`).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ActorIdentity(RistrettoPoint);

impl ActorIdentity {
    /// 32-byte compressed encoding (the published identity / `did:key` payload).
    pub fn to_bytes(&self) -> [u8; 32] {
        self.0.compress().to_bytes()
    }
    /// Parse a published identity. `None` if the bytes are not a valid ristretto point.
    pub fn from_bytes(bytes: &[u8; 32]) -> Option<Self> {
        CompressedRistretto::from_slice(bytes)
            .ok()?
            .decompress()
            .map(ActorIdentity)
    }

    /// Canonical multibase (base58btc, `z…`) string — the form to store in a datom or surface in
    /// a DID document, mirroring the project's `did:key` convention. NOTE: this encodes the raw
    /// ristretto255 point; it is the kotoba actor-identity form, NOT a W3C `did:key` (ristretto255
    /// has no registered did:key multicodec — when one lands, a `did:key` variant can wrap this).
    pub fn to_multibase(&self) -> String {
        multibase::encode(Base::Base58Btc, self.to_bytes())
    }
    /// Parse the multibase form. `None` on bad multibase, wrong length, or an invalid point.
    pub fn from_multibase(s: &str) -> Option<Self> {
        let (_, bytes) = multibase::decode(s).ok()?;
        let arr: [u8; 32] = bytes.try_into().ok()?;
        Self::from_bytes(&arr)
    }
}

/// A self-issued actor key. Holds the secret scalar **opaquely**: no accessor returns it,
/// and it is zeroized on drop. Only [`ActorKey::identity`] (public) and
/// [`ActorKey::prove_control`] (zero-knowledge) are exposed — there is, by construction, no
/// `export`/`to_bytes`/`as_scalar` on this type.
#[derive(ZeroizeOnDrop)]
pub struct ActorKey {
    secret: Scalar,
}

impl ActorKey {
    /// Issue a fresh actor key. The secret is generated locally and never leaves this value.
    pub fn issue<R: RngCore + CryptoRng>(rng: &mut R) -> Self {
        ActorKey {
            secret: Scalar::random(rng),
        }
    }

    /// The public identity — the ONLY thing safe to share.
    pub fn identity(&self) -> ActorIdentity {
        ActorIdentity(RistrettoPoint::mul_base(&self.secret))
    }

    /// Hedged synthetic Schnorr nonce `k = H(NONCE_DOMAIN ‖ x ‖ rng32 ‖ len(ctx) ‖ ctx) mod ℓ`.
    /// Internal-only: it reads the secret bytes WITHOUT exposing them outside the type. The rng
    /// hedge keeps it randomized per call when the RNG works; the secret+context binding keeps it
    /// unique (never reused across contexts) even if the RNG is broken — closing the nonce-reuse
    /// key-leak hole that a pure `Scalar::random` would open under RNG failure.
    fn synthetic_nonce<R: RngCore + CryptoRng>(&self, context: &[u8], rng: &mut R) -> Scalar {
        let mut hedge = [0u8; 32];
        rng.fill_bytes(&mut hedge);
        let mut h = Sha512::new();
        h.update(NONCE_DOMAIN);
        h.update(self.secret.as_bytes());
        h.update(hedge);
        h.update((context.len() as u64).to_le_bytes());
        h.update(context);
        let mut wide = [0u8; 64];
        wide.copy_from_slice(&h.finalize());
        let k = Scalar::from_bytes_mod_order_wide(&wide);
        wide.zeroize();
        hedge.zeroize();
        k
    }

    /// Produce a non-interactive zero-knowledge proof that this key controls [`Self::identity`],
    /// bound to `context` (domain-separated — a proof minted for one purpose cannot be replayed
    /// for another). Reveals nothing about the secret.
    pub fn prove_control<R: RngCore + CryptoRng>(
        &self,
        context: &[u8],
        rng: &mut R,
    ) -> ControlProof {
        // Schnorr: pick nonce k, commit T = k·G, challenge c = H(P, T, ctx), response s = k + c·x.
        // The nonce is HEDGED-SYNTHETIC, not pure-RNG: k = H(domain ‖ x ‖ rng ‖ ctx). With a good
        // RNG it is random per call; with a BROKEN rng (e.g. all-zero) it is still unique per
        // (secret, context) and never repeats across distinct contexts — so a failed RNG cannot
        // cause the nonce reuse that would leak the key. (RFC 6979 / Ed25519-style synthetic nonce.)
        let mut k = self.synthetic_nonce(context, rng);
        let commit = RistrettoPoint::mul_base(&k);
        let p = RistrettoPoint::mul_base(&self.secret);
        let c = challenge(&p, &commit, context);
        let s = k + c * self.secret;
        k.zeroize(); // the nonce is as sensitive as the key (k + leaking c reveals x)
        ControlProof {
            commit: commit.compress(),
            response: s,
        }
    }
}

/// A Schnorr zero-knowledge proof of control. Carries no secret; safe to transmit and store.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ControlProof {
    commit: CompressedRistretto,
    response: Scalar,
}

impl ControlProof {
    /// Verify that the proof demonstrates control of `identity`, under the same `context`.
    pub fn verify(&self, identity: &ActorIdentity, context: &[u8]) -> bool {
        let Some(commit) = self.commit.decompress() else {
            return false;
        };
        let c = challenge(&identity.0, &commit, context);
        // s·G == T + c·P   ⇔   the prover knows x with P = x·G
        RistrettoPoint::mul_base(&self.response) == commit + identity.0 * c
    }

    /// 64-byte wire encoding (commit ‖ response).
    pub fn to_bytes(&self) -> [u8; 64] {
        let mut out = [0u8; 64];
        out[..32].copy_from_slice(self.commit.as_bytes());
        out[32..].copy_from_slice(self.response.as_bytes());
        out
    }
    /// Parse a wire-encoded proof. `None` on malformed bytes (non-canonical scalar / bad point).
    pub fn from_bytes(bytes: &[u8; 64]) -> Option<Self> {
        let commit = CompressedRistretto::from_slice(&bytes[..32]).ok()?;
        let mut sb = [0u8; 32];
        sb.copy_from_slice(&bytes[32..]);
        let response = Option::from(Scalar::from_canonical_bytes(sb))?;
        Some(ControlProof { commit, response })
    }

    /// Canonical multibase (base58btc, `z…`) string form, for transport/storage in the kotoba
    /// ecosystem (datoms, JSON, DID-document proof values).
    pub fn to_multibase(&self) -> String {
        multibase::encode(Base::Base58Btc, self.to_bytes())
    }
    /// Parse the multibase form. `None` on bad multibase, wrong length, or malformed proof.
    pub fn from_multibase(s: &str) -> Option<Self> {
        let (_, bytes) = multibase::decode(s).ok()?;
        let arr: [u8; 64] = bytes.try_into().ok()?;
        Self::from_bytes(&arr)
    }
}

/// Fiat–Shamir challenge: `c = H(domain ‖ P ‖ T ‖ len(ctx) ‖ ctx) mod ℓ`.
fn challenge(p: &RistrettoPoint, commit: &RistrettoPoint, context: &[u8]) -> Scalar {
    let mut h = Sha512::new();
    h.update(CHALLENGE_DOMAIN);
    h.update(p.compress().as_bytes());
    h.update(commit.compress().as_bytes());
    h.update((context.len() as u64).to_le_bytes());
    h.update(context);
    let mut wide = [0u8; 64];
    wide.copy_from_slice(&h.finalize());
    Scalar::from_bytes_mod_order_wide(&wide)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand_core::OsRng;

    /// An adversarial RNG that always yields zeros — models a catastrophic RNG failure.
    /// With a pure `Scalar::random` nonce this would force k = 0 (and leak the key); the hedged
    /// synthetic nonce must stay safe under it.
    struct ZeroRng;
    impl RngCore for ZeroRng {
        fn next_u32(&mut self) -> u32 {
            0
        }
        fn next_u64(&mut self) -> u64 {
            0
        }
        fn fill_bytes(&mut self, dest: &mut [u8]) {
            dest.iter_mut().for_each(|b| *b = 0);
        }
        fn try_fill_bytes(&mut self, dest: &mut [u8]) -> Result<(), rand_core::Error> {
            self.fill_bytes(dest);
            Ok(())
        }
    }
    impl CryptoRng for ZeroRng {}

    #[test]
    fn hedged_nonce_survives_broken_rng() {
        // Even with an all-zero RNG, the secret+context-derived nonce yields a valid proof.
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let proof = key.prove_control(b"ctx", &mut ZeroRng);
        assert!(proof.verify(&id, b"ctx"));
    }

    #[test]
    fn broken_rng_distinct_contexts_distinct_commits() {
        // The key safety property: under a broken RNG, different contexts must still use
        // DIFFERENT nonces (different commits) — otherwise same-k-different-challenge leaks x.
        let key = ActorKey::issue(&mut OsRng);
        let p1 = key.prove_control(b"login", &mut ZeroRng).to_bytes();
        let p2 = key.prove_control(b"transfer", &mut ZeroRng).to_bytes();
        assert_ne!(p1[..32], p2[..32]); // commits differ
    }

    #[test]
    fn broken_rng_same_context_is_deterministic_and_safe() {
        // Same key + same context + broken RNG → identical proof (one statement, one nonce → no
        // two distinct proofs ever share a nonce, so no key-leak hazard). Still verifies.
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let p1 = key.prove_control(b"ctx", &mut ZeroRng);
        let p2 = key.prove_control(b"ctx", &mut ZeroRng);
        assert_eq!(p1.to_bytes(), p2.to_bytes());
        assert!(p1.verify(&id, b"ctx"));
    }

    #[test]
    fn issue_prove_verify_roundtrip() {
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let proof = key.prove_control(b"login", &mut OsRng);
        assert!(proof.verify(&id, b"login"));
    }

    #[test]
    fn wrong_context_fails() {
        // domain separation: a proof for "login" must not verify for "transfer".
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let proof = key.prove_control(b"login", &mut OsRng);
        assert!(!proof.verify(&id, b"transfer"));
    }

    #[test]
    fn wrong_identity_fails() {
        let key = ActorKey::issue(&mut OsRng);
        let other = ActorKey::issue(&mut OsRng);
        let proof = key.prove_control(b"ctx", &mut OsRng);
        assert!(!proof.verify(&other.identity(), b"ctx"));
    }

    #[test]
    fn tampered_proof_fails() {
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let proof = key.prove_control(b"ctx", &mut OsRng);
        let mut b = proof.to_bytes();
        b[40] ^= 0x01; // flip a bit in the response scalar
        match ControlProof::from_bytes(&b) {
            Some(t) => assert!(!t.verify(&id, b"ctx")),
            None => { /* non-canonical scalar → already rejected at parse, also a pass */ }
        }
    }

    #[test]
    fn proof_is_randomized_but_both_verify() {
        // zero-knowledge: each proof uses a fresh nonce, so two proofs differ byte-for-byte,
        // yet both verify — the verifier learns nothing that distinguishes them.
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let p1 = key.prove_control(b"ctx", &mut OsRng);
        let p2 = key.prove_control(b"ctx", &mut OsRng);
        assert_ne!(p1.to_bytes(), p2.to_bytes());
        assert!(p1.verify(&id, b"ctx"));
        assert!(p2.verify(&id, b"ctx"));
    }

    #[test]
    fn identity_serialization_roundtrip() {
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let b = id.to_bytes();
        assert_eq!(ActorIdentity::from_bytes(&b), Some(id));
    }

    #[test]
    fn identity_multibase_roundtrip() {
        let id = ActorKey::issue(&mut OsRng).identity();
        let s = id.to_multibase();
        assert!(s.starts_with('z')); // base58btc multibase prefix
        assert_eq!(ActorIdentity::from_multibase(&s), Some(id));
        assert!(ActorIdentity::from_multibase("not-multibase").is_none());
        assert!(ActorIdentity::from_multibase("z11111").is_none()); // valid mb, wrong length
    }

    #[test]
    fn proof_multibase_roundtrip() {
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let proof = key.prove_control(b"ctx", &mut OsRng);
        let s = proof.to_multibase();
        assert!(s.starts_with('z'));
        let parsed = ControlProof::from_multibase(&s).unwrap();
        assert!(parsed.verify(&id, b"ctx"));
        assert!(ControlProof::from_multibase("znope").is_none());
    }

    #[test]
    fn proof_serialization_roundtrip() {
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let proof = key.prove_control(b"ctx", &mut OsRng);
        let parsed = ControlProof::from_bytes(&proof.to_bytes()).unwrap();
        assert!(parsed.verify(&id, b"ctx"));
    }

    #[test]
    fn empty_and_long_context_supported() {
        let key = ActorKey::issue(&mut OsRng);
        let id = key.identity();
        let long = vec![0xABu8; 4096];
        for ctx in [b"".as_slice(), long.as_slice()] {
            let proof = key.prove_control(ctx, &mut OsRng);
            assert!(proof.verify(&id, ctx));
        }
    }
}
