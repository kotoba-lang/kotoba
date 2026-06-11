//! TURN relay — ephemeral-credential authentication core.
//!
//! Implements the coturn `use-auth-secret` scheme (the de-facto WebRTC standard,
//! RFC-7635 flavored) used by `kotoba` real-media calls. A short-lived credential
//! is an expiry-prefixed, room/player-scoped username signed with a shared secret:
//!
//! ```text
//! username   = "<expiry_unix>:<room>:<player>"
//! credential = base64( HMAC_SHA1( RT_TURN_SECRET, username ) )
//! ```
//!
//! This is the SAME wire format the browser SDK mints in
//! `@etzhayyim/kami-engine-sdk/call` (`mintTurnCredential` / `verifyTurnCredential`);
//! the RFC 2202 test vector below pins both implementations to identical bytes, so
//! a credential minted in the control plane verifies here and vice versa.
//!
//! v0 scope: the auth core only. STUN/TURN message codec, allocations, and the
//! UDP/TCP/TLS listeners are deferred to a later phase (see `docs/ADR-turn-relay.md`).

pub mod allocation;
pub mod channel;
pub mod server;
pub mod stun;

use base64::Engine as _;
use hmac::{Hmac, Mac};
use sha1::Sha1;

type HmacSha1 = Hmac<Sha1>;

const B64: base64::engine::general_purpose::GeneralPurpose = base64::engine::general_purpose::STANDARD;

/// HMAC-SHA1 of `message` under `secret`, base64 (standard alphabet, padded).
pub fn hmac_sha1_base64(secret: &str, message: &str) -> String {
    let mut mac = HmacSha1::new_from_slice(secret.as_bytes()).expect("HMAC accepts any key length");
    mac.update(message.as_bytes());
    B64.encode(mac.finalize().into_bytes())
}

/// A minted TURN credential, ready to hand to a client's `iceServers`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Credential {
    pub username: String,
    pub credential: String,
    /// Absolute expiry, unix seconds.
    pub expires_at: u64,
}

/// Mint a credential valid until `expires_at` (unix seconds). Server-side only —
/// `secret` must never reach a browser.
pub fn mint(secret: &str, room: &str, player: u32, expires_at: u64) -> Credential {
    let username = format!("{expires_at}:{room}:{player}");
    let credential = hmac_sha1_base64(secret, &username);
    Credential { username, credential, expires_at }
}

/// The room/player a verified credential authorizes.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Scope {
    pub room: String,
    pub player: u32,
    pub expires_at: u64,
}

/// Why a credential was rejected. Mirrors the SDK's `VerifyTurnResult.reason`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum AuthError {
    #[error("malformed username")]
    Malformed,
    #[error("bad expiry")]
    BadExpiry,
    #[error("expired")]
    Expired,
    #[error("bad signature")]
    BadSignature,
}

/// Verify a credential exactly as the relay's `Allocate` handler must: structure,
/// expiry, then a constant-time HMAC check. `now` is unix seconds.
pub fn verify(secret: &str, username: &str, credential: &str, now: u64) -> Result<Scope, AuthError> {
    let parts: Vec<&str> = username.split(':').collect();
    if parts.len() != 3 {
        return Err(AuthError::Malformed);
    }
    let expires_at: u64 = parts[0].parse().map_err(|_| AuthError::BadExpiry)?;
    let player: u32 = parts[2].parse().map_err(|_| AuthError::Malformed)?;
    if expires_at < now {
        return Err(AuthError::Expired);
    }
    // Constant-time: decode the presented MAC and let `verify_slice` compare.
    let presented = B64.decode(credential).map_err(|_| AuthError::BadSignature)?;
    let mut mac = HmacSha1::new_from_slice(secret.as_bytes()).map_err(|_| AuthError::BadSignature)?;
    mac.update(username.as_bytes());
    mac.verify_slice(&presented).map_err(|_| AuthError::BadSignature)?;
    Ok(Scope { room: parts[1].to_string(), player, expires_at })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hmac_matches_rfc2202_and_the_js_sdk() {
        // RFC 2202 §3 case 2: key="Jefe", data="what do ya want for nothing?".
        // Identical base64 to the SDK's turn.test.ts — pins cross-impl interop.
        assert_eq!(
            hmac_sha1_base64("Jefe", "what do ya want for nothing?"),
            "7/zfauXrL6LSdBbV8YTfnCWafHk=",
        );
    }

    #[test]
    fn mint_then_verify_recovers_scope() {
        let c = mint("k", "room-1", 7, 1_700_000_600);
        assert_eq!(c.username, "1700000600:room-1:7");
        let scope = verify("k", &c.username, &c.credential, 1_700_000_000).unwrap();
        assert_eq!(scope, Scope { room: "room-1".into(), player: 7, expires_at: 1_700_000_600 });
    }

    #[test]
    fn rejects_expired() {
        let c = mint("k", "r", 1, 1_700_000_060);
        assert_eq!(verify("k", &c.username, &c.credential, 1_700_000_061), Err(AuthError::Expired));
    }

    #[test]
    fn rejects_tampered_and_wrong_secret() {
        let c = mint("k", "r", 1, 1_700_000_600);
        let tampered = format!("{}A", c.credential);
        assert_eq!(verify("k", &c.username, &tampered, 1_700_000_000), Err(AuthError::BadSignature));
        assert_eq!(verify("WRONG", &c.username, &c.credential, 1_700_000_000), Err(AuthError::BadSignature));
    }

    #[test]
    fn rejects_malformed_username() {
        assert_eq!(verify("k", "no-colons", "x", 0), Err(AuthError::Malformed));
        assert_eq!(verify("k", "1700000600:r", "x", 0), Err(AuthError::Malformed));
    }
}
