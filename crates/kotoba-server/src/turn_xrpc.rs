//! `turn.credential` XRPC — operator-gated ICE-server config for browser WebRTC peers.
//!
//! P2 of the kotoba-net WebRTC plan (root ADR-2606271800). A browser joining the Live
//! plane over WebRTC asks here for an `RTCPeerConnection({ iceServers })` config that
//! carries a short-lived TURN credential, minted by `kotoba_turn::ice` with the same
//! ephemeral scheme the relay (the kotoba-turn UDP listener) verifies — so what the
//! tab receives is exactly what the relay accepts. The shared secret
//! (`KOTOBA_TURN_SECRET`) never leaves the server; only `(username, credential)` go out.

use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use axum::extract::{Query, State};
use axum::http::{HeaderMap, StatusCode};
use axum::Json;
use serde::Deserialize;

use crate::server::KotobaState;

pub const NSID_TURN_CREDENTIAL: &str = "com.etzhayyim.apps.kotoba.turn.credential";

#[derive(Debug, Deserialize)]
pub struct TurnCredentialQuery {
    /// The room/channel the credential is scoped to (default "default").
    pub room: Option<String>,
    /// The player/seat id within the room (default 0).
    pub player: Option<u32>,
    /// Requested TTL in seconds (default 300, cap 86_400).
    pub ttl: Option<u64>,
}

/// Parse a comma-separated env var into a list of non-empty URLs.
fn env_urls(key: &str) -> Vec<String> {
    std::env::var(key)
        .ok()
        .map(|s| {
            s.split(',')
                .map(|u| u.trim().to_string())
                .filter(|u| !u.is_empty())
                .collect()
        })
        .unwrap_or_default()
}

/// GET /xrpc/com.etzhayyim.apps.kotoba.turn.credential
///
/// Operator-gated (the same Bearer/CACAO operator check the audit XRPCs use). Returns
/// `{ iceServers, ttl, expiresAt }`. STUN URLs come from `KOTOBA_STUN_URLS`, TURN URLs
/// from `KOTOBA_TURN_URLS` (comma lists); the credential is keyed by `KOTOBA_TURN_SECRET`.
pub async fn turn_credential(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<TurnCredentialQuery>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;

    let secret = std::env::var("KOTOBA_TURN_SECRET").map_err(|_| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "KOTOBA_TURN_SECRET not configured".to_string(),
        )
    })?;

    let room = q.room.as_deref().unwrap_or("default");
    let player = q.player.unwrap_or(0);
    let ttl = q.ttl.unwrap_or(300).min(86_400);
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);

    let stun = env_urls("KOTOBA_STUN_URLS");
    let turn = env_urls("KOTOBA_TURN_URLS");
    let stun_refs: Vec<&str> = stun.iter().map(String::as_str).collect();
    let turn_refs: Vec<&str> = turn.iter().map(String::as_str).collect();

    let cfg = kotoba_turn::ice::ice_config(&secret, &stun_refs, &turn_refs, room, player, ttl, now);

    let ice_servers: Vec<serde_json::Value> = cfg
        .ice_servers
        .iter()
        .map(|s| {
            let mut o = serde_json::Map::new();
            o.insert("urls".into(), serde_json::Value::from(s.urls.clone()));
            if let Some(u) = &s.username {
                o.insert("username".into(), u.clone().into());
            }
            if let Some(c) = &s.credential {
                o.insert("credential".into(), c.clone().into());
            }
            serde_json::Value::Object(o)
        })
        .collect();

    Ok(Json(serde_json::json!({
        "iceServers": ice_servers,
        "ttl": cfg.expires_at.saturating_sub(now),
        "expiresAt": cfg.expires_at,
    })))
}
