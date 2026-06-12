//! Server request-handling core — the pure decision layer the UDP/TCP listeners
//! sit on top of. No sockets here: a listener reads a datagram, calls
//! [`classify_datagram`] to route it, and for STUN requests calls
//! [`authenticate`] before mutating the [`crate::allocation::AllocationTable`].
//!
//! Keeping this logic socket-free makes the security-critical path — credential
//! verification and STUN/ChannelData demux — fully unit-testable.

use crate::channel;
use crate::stun;
use crate::Scope;

/// What an inbound datagram is, decided from its first byte (RFC 8656 §12.4:
/// STUN messages are 0x00–0x3F, ChannelData frames 0x40–0x7F).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Datagram {
    Stun,
    ChannelData,
    Unknown,
}

/// Route a datagram without fully parsing it.
pub fn classify_datagram(buf: &[u8]) -> Datagram {
    match buf.first() {
        Some(&b) if channel::is_channel_data(b) => Datagram::ChannelData,
        Some(&b) if b <= 0x3F => Datagram::Stun,
        _ => Datagram::Unknown,
    }
}

/// The TURN method of a STUN request message type.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TurnMethod {
    Allocate,
    Refresh,
    CreatePermission,
    ChannelBind,
    Binding,
    Other,
}

pub fn method_of(typ: u16) -> TurnMethod {
    match typ {
        stun::ALLOCATE_REQUEST => TurnMethod::Allocate,
        stun::REFRESH_REQUEST => TurnMethod::Refresh,
        stun::CREATE_PERMISSION_REQUEST => TurnMethod::CreatePermission,
        stun::CHANNEL_BIND_REQUEST => TurnMethod::ChannelBind,
        stun::BINDING_REQUEST => TurnMethod::Binding,
        _ => TurnMethod::Other,
    }
}

/// Why a request failed authentication — maps to a STUN error response code.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AuthReject {
    /// 401 — no/invalid USERNAME or MESSAGE-INTEGRITY.
    Unauthorized,
    /// 438 — the credential's embedded expiry has passed.
    Stale,
}

impl AuthReject {
    pub fn error_code(self) -> u16 {
        match self {
            AuthReject::Unauthorized => 401,
            AuthReject::Stale => 438,
        }
    }
}

/// Authenticate a STUN request under the ephemeral-credential scheme: recompute
/// the credential from USERNAME + the shared secret, verify MESSAGE-INTEGRITY
/// against it, then check the embedded expiry. Returns the authorized scope.
pub fn authenticate(msg: &[u8], secret: &str, now: u64) -> Result<Scope, AuthReject> {
    if msg.len() < 20 {
        return Err(AuthReject::Unauthorized);
    }
    let attrs = stun::attributes(&msg[20..]).map_err(|_| AuthReject::Unauthorized)?;

    let username = attrs
        .iter()
        .find(|(t, _)| *t == stun::ATTR_USERNAME)
        .and_then(|(_, v)| std::str::from_utf8(v).ok())
        .ok_or(AuthReject::Unauthorized)?;
    if !attrs
        .iter()
        .any(|(t, _)| *t == stun::ATTR_MESSAGE_INTEGRITY)
    {
        return Err(AuthReject::Unauthorized);
    }

    // The MI key is the credential the client was issued = HMAC(secret, username).
    let credential = crate::hmac_sha1_base64(secret, username);
    stun::verify_message_integrity(msg, credential.as_bytes())
        .map_err(|_| AuthReject::Unauthorized)?;

    // Signature proven; now enforce the embedded expiry/scope.
    match crate::verify(secret, username, &credential, now) {
        Ok(scope) => Ok(scope),
        Err(crate::AuthError::Expired) => Err(AuthReject::Stale),
        Err(_) => Err(AuthReject::Unauthorized),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mint;
    use crate::stun::Header;

    #[test]
    fn classify_routes_by_first_byte() {
        assert_eq!(classify_datagram(&[0x00, 0x01]), Datagram::Stun); // Binding request
        assert_eq!(classify_datagram(&[0x01, 0x03]), Datagram::Stun); // Allocate response high byte
        assert_eq!(classify_datagram(&[0x40, 0x01]), Datagram::ChannelData);
        assert_eq!(classify_datagram(&[0x7F]), Datagram::ChannelData);
        assert_eq!(classify_datagram(&[0x80]), Datagram::Unknown);
        assert_eq!(classify_datagram(&[]), Datagram::Unknown);
    }

    #[test]
    fn method_classification() {
        assert_eq!(method_of(stun::ALLOCATE_REQUEST), TurnMethod::Allocate);
        assert_eq!(method_of(stun::REFRESH_REQUEST), TurnMethod::Refresh);
        assert_eq!(
            method_of(stun::CREATE_PERMISSION_REQUEST),
            TurnMethod::CreatePermission
        );
        assert_eq!(
            method_of(stun::CHANNEL_BIND_REQUEST),
            TurnMethod::ChannelBind
        );
        assert_eq!(method_of(0x00FF), TurnMethod::Other);
    }

    /// Build an Allocate request authenticated with `mint`ed credentials.
    fn authed_allocate(secret: &str, room: &str, player: u32, expires_at: u64) -> Vec<u8> {
        let cred = mint(secret, room, player, expires_at);
        let mut msg = Header {
            typ: stun::ALLOCATE_REQUEST,
            length: 0,
            txid: [7; 12],
        }
        .encode()
        .to_vec();
        // USERNAME attribute (padded to 4 bytes).
        let u = cred.username.as_bytes();
        msg.extend_from_slice(&stun::ATTR_USERNAME.to_be_bytes());
        msg.extend_from_slice(&(u.len() as u16).to_be_bytes());
        msg.extend_from_slice(u);
        while !(msg.len() - 20).is_multiple_of(4) {
            msg.push(0);
        }
        let attr_len = (msg.len() - 20) as u16;
        msg[2..4].copy_from_slice(&attr_len.to_be_bytes());
        // MI keyed by the credential, exactly as the client computes it.
        stun::append_message_integrity(&mut msg, cred.credential.as_bytes());
        msg
    }

    #[test]
    fn authenticate_accepts_valid_credentials() {
        let msg = authed_allocate("s3cret", "room-1", 7, 1_700_000_600);
        let scope = authenticate(&msg, "s3cret", 1_700_000_000).unwrap();
        assert_eq!(
            scope,
            Scope {
                room: "room-1".into(),
                player: 7,
                expires_at: 1_700_000_600
            }
        );
    }

    #[test]
    fn authenticate_rejects_wrong_secret_and_missing_integrity() {
        let msg = authed_allocate("s3cret", "r", 1, 1_700_000_600);
        assert_eq!(
            authenticate(&msg, "WRONG", 1_700_000_000),
            Err(AuthReject::Unauthorized)
        );

        // A request with no attributes at all → no USERNAME → unauthorized.
        let bare = Header {
            typ: stun::ALLOCATE_REQUEST,
            length: 0,
            txid: [0; 12],
        }
        .encode()
        .to_vec();
        assert_eq!(
            authenticate(&bare, "s3cret", 0),
            Err(AuthReject::Unauthorized)
        );
    }

    #[test]
    fn authenticate_flags_expired_credentials_as_stale() {
        let msg = authed_allocate("s3cret", "r", 1, 1_700_000_060);
        assert_eq!(
            authenticate(&msg, "s3cret", 1_700_000_061),
            Err(AuthReject::Stale)
        );
        assert_eq!(AuthReject::Stale.error_code(), 438);
        assert_eq!(AuthReject::Unauthorized.error_code(), 401);
    }
}
