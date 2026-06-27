//! ICE-server configuration for browser WebRTC peers (P2 of the kotoba-net WebRTC
//! plan, root ADR-2606271800).
//!
//! A browser that wants to join the Live plane as a WebRTC peer needs an
//! `RTCPeerConnection({ iceServers })` config: the STUN/TURN URLs plus a short-lived
//! TURN credential. This module mints that config from the same ephemeral-credential
//! scheme the relay verifies ([`crate::mint`]) — so the credential handed to the
//! browser is exactly what the UDP listener ([`crate::listener`]) accepts. The shared
//! secret stays server-side; only the derived `(username, credential)` reach the tab.
//!
//! `kotoba-server` exposes this over an operator-gated XRPC
//! (`com.etzhayyim.apps.kotoba.turn.credential`); this crate keeps the logic pure and
//! dependency-free so it stays a leaf and is unit-testable without a server.

use crate::mint;

/// One entry of an `RTCConfiguration.iceServers` array.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct IceServer {
    /// e.g. `stun:stun.l.google.com:19302` or `turn:relay.example:3478?transport=udp`.
    pub urls: Vec<String>,
    /// Present only for TURN servers (the minted ephemeral username).
    pub username: Option<String>,
    /// Present only for TURN servers (the minted credential).
    pub credential: Option<String>,
}

/// A full ICE config to hand a browser, plus the raw credential + its absolute
/// expiry so the caller can also surface a refresh deadline.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct IceConfig {
    pub ice_servers: Vec<IceServer>,
    /// The minted TURN username (`<expiry>:<room>:<player>`).
    pub username: String,
    /// The minted TURN credential (base64 HMAC).
    pub credential: String,
    /// Absolute expiry, unix seconds (= `now + ttl`).
    pub expires_at: u64,
}

/// Build an ICE config for `(room, player)`, valid for `ttl_secs` from `now`.
///
/// `stun_urls` are passed through credential-free; `turn_urls` all carry the one
/// minted ephemeral credential (coturn `use-auth-secret` issues a single
/// username/credential pair that authorizes every TURN URL). `secret` is the relay's
/// shared secret and must never be sent to the browser.
pub fn ice_config(
    secret: &str,
    stun_urls: &[&str],
    turn_urls: &[&str],
    room: &str,
    player: u32,
    ttl_secs: u64,
    now: u64,
) -> IceConfig {
    let expires_at = now.saturating_add(ttl_secs);
    let cred = mint(secret, room, player, expires_at);

    let mut ice_servers = Vec::new();
    if !stun_urls.is_empty() {
        ice_servers.push(IceServer {
            urls: stun_urls.iter().map(|s| s.to_string()).collect(),
            username: None,
            credential: None,
        });
    }
    if !turn_urls.is_empty() {
        ice_servers.push(IceServer {
            urls: turn_urls.iter().map(|s| s.to_string()).collect(),
            username: Some(cred.username.clone()),
            credential: Some(cred.credential.clone()),
        });
    }

    IceConfig {
        ice_servers,
        username: cred.username,
        credential: cred.credential,
        expires_at,
    }
}

/// Serialize an [`IceConfig`] to the JSON shape browsers expect
/// (`{ "iceServers": [...], "ttl": N, "expiresAt": N }`), hand-rolled so the crate
/// stays dependency-free. Strings are JSON-escaped (URLs/usernames are simple, but
/// be correct anyway).
pub fn to_json(cfg: &IceConfig, now: u64) -> String {
    fn esc(s: &str) -> String {
        let mut o = String::with_capacity(s.len() + 2);
        for c in s.chars() {
            match c {
                '"' => o.push_str("\\\""),
                '\\' => o.push_str("\\\\"),
                '\n' => o.push_str("\\n"),
                '\r' => o.push_str("\\r"),
                '\t' => o.push_str("\\t"),
                c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)),
                c => o.push(c),
            }
        }
        o
    }
    fn arr(urls: &[String]) -> String {
        let items: Vec<String> = urls.iter().map(|u| format!("\"{}\"", esc(u))).collect();
        format!("[{}]", items.join(","))
    }
    let servers: Vec<String> = cfg
        .ice_servers
        .iter()
        .map(|s| {
            let mut fields = vec![format!("\"urls\":{}", arr(&s.urls))];
            if let Some(u) = &s.username {
                fields.push(format!("\"username\":\"{}\"", esc(u)));
            }
            if let Some(c) = &s.credential {
                fields.push(format!("\"credential\":\"{}\"", esc(c)));
            }
            format!("{{{}}}", fields.join(","))
        })
        .collect();
    format!(
        "{{\"iceServers\":[{}],\"ttl\":{},\"expiresAt\":{}}}",
        servers.join(","),
        cfg.expires_at.saturating_sub(now),
        cfg.expires_at
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::verify;

    const SECRET: &str = "s3cret";

    #[test]
    fn config_mints_a_relay_verifiable_credential() {
        let cfg = ice_config(
            SECRET,
            &["stun:stun.l.google.com:19302"],
            &["turn:relay.kotoba:3478?transport=udp"],
            "room-1",
            7,
            300,
            1_700_000_000,
        );
        assert_eq!(cfg.expires_at, 1_700_000_300);
        assert_eq!(cfg.username, "1700000300:room-1:7");
        // the credential the browser receives is exactly what the relay verifies
        let scope = verify(SECRET, &cfg.username, &cfg.credential, 1_700_000_000).unwrap();
        assert_eq!(scope.room, "room-1");
        assert_eq!(scope.player, 7);
    }

    #[test]
    fn stun_is_credential_free_turn_carries_the_credential() {
        let cfg = ice_config(SECRET, &["stun:s:1"], &["turn:t:2"], "r", 1, 60, 0);
        assert_eq!(cfg.ice_servers.len(), 2);
        let stun = &cfg.ice_servers[0];
        assert_eq!(stun.urls, vec!["stun:s:1"]);
        assert!(stun.username.is_none() && stun.credential.is_none());
        let turn = &cfg.ice_servers[1];
        assert_eq!(turn.username.as_deref(), Some("60:r:1"));
        assert_eq!(turn.credential.as_deref(), Some(cfg.credential.as_str()));
    }

    #[test]
    fn omits_empty_server_lists() {
        let only_turn = ice_config(SECRET, &[], &["turn:t:2"], "r", 1, 60, 0);
        assert_eq!(only_turn.ice_servers.len(), 1);
        assert!(only_turn.ice_servers[0].username.is_some());

        let neither = ice_config(SECRET, &[], &[], "r", 1, 60, 0);
        assert!(neither.ice_servers.is_empty());
        // a credential is still minted (callers may want it even with no URLs)
        assert_eq!(neither.username, "60:r:1");
    }

    #[test]
    fn json_has_expected_shape() {
        let cfg = ice_config(SECRET, &["stun:s:1"], &["turn:t:2"], "r", 1, 300, 1000);
        let json = to_json(&cfg, 1000);
        assert!(json.contains("\"iceServers\":["));
        assert!(json.contains("\"urls\":[\"stun:s:1\"]"));
        assert!(json.contains("\"urls\":[\"turn:t:2\"]"));
        assert!(json.contains(&format!("\"username\":\"{}\"", cfg.username)));
        assert!(json.contains("\"ttl\":300"));
        assert!(json.contains("\"expiresAt\":1300"));
        // STUN entry must not leak a username/credential
        let stun_obj = &json[json.find("stun:s:1").unwrap()..json.find("turn:t:2").unwrap()];
        assert!(!stun_obj.contains("username"));
    }
}
