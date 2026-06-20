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
use rand_core::{CryptoRng, RngCore};
use sha2::{Digest, Sha512};
use zeroize::{Zeroize, ZeroizeOnDrop};

/// Domain-separation tag for the Fiat–Shamir challenge (versioned).
const CHALLENGE_DOMAIN: &[u8] = b"kotoba.actor.proof-of-control.schnorr.v1";

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

    /// Produce a non-interactive zero-knowledge proof that this key controls [`Self::identity`],
    /// bound to `context` (domain-separated — a proof minted for one purpose cannot be replayed
    /// for another). Reveals nothing about the secret.
    pub fn prove_control<R: RngCore + CryptoRng>(
        &self,
        context: &[u8],
        rng: &mut R,
    ) -> ControlProof {
        // Schnorr: pick nonce k, commit T = k·G, challenge c = H(P, T, ctx), response s = k + c·x.
        let mut k = Scalar::random(rng);
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
