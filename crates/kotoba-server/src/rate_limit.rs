//! Lightweight per-client token-bucket rate limiter (enterprise edge hardening, b).
//!
//! A single caller must not be able to exhaust the node, and a breached edge
//! (CF Worker) must not be able to amplify into the origin. This bounds the
//! request rate per client without pulling in a new dependency — it reuses the
//! `DashMap` already vendored for the nonce store and keys on the
//! Cloudflare-injected `CF-Connecting-IP` (falling back to `x-kotoba-client-ip`,
//! then the first `x-forwarded-for` hop, then a shared global bucket for
//! direct / un-proxied access).
//!
//! Disabled unless `KOTOBA_RATE_LIMIT_RPS` is set, so the default deployment is
//! behaviourally unchanged. Knobs:
//!   * `KOTOBA_RATE_LIMIT_RPS`   — sustained requests/sec/client (enables it).
//!   * `KOTOBA_RATE_LIMIT_BURST` — bucket depth (default = `max(rps, 1)`).
//!
//! The bucket map is capped at `MAX_BUCKETS` distinct keys; once full, unseen
//! keys share the global bucket so a spoofed-`x-forwarded-for` flood (only
//! possible on direct, un-proxied access) cannot grow memory without bound.

use std::sync::Arc;
use std::time::Instant;

use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::Response,
};
use dashmap::DashMap;

/// Shared bucket for callers we can't (or won't) distinguish by IP.
const GLOBAL_KEY: &str = "@global";
/// Upper bound on distinct per-client buckets (memory cap).
const MAX_BUCKETS: usize = 100_000;

/// A token bucket: `tokens` refills at `rps` up to `burst`.
struct Bucket {
    tokens: f64,
    last: Instant,
}

pub struct RateLimiter {
    rps: f64,
    burst: f64,
    buckets: DashMap<String, Bucket>,
}

impl RateLimiter {
    /// Build from the environment. Returns `None` (disabled) unless
    /// `KOTOBA_RATE_LIMIT_RPS` parses to a finite, positive number.
    pub fn from_env() -> Option<Arc<Self>> {
        let rps: f64 = std::env::var("KOTOBA_RATE_LIMIT_RPS")
            .ok()?
            .trim()
            .parse()
            .ok()?;
        if !(rps.is_finite() && rps > 0.0) {
            return None;
        }
        let burst = std::env::var("KOTOBA_RATE_LIMIT_BURST")
            .ok()
            .and_then(|v| v.trim().parse::<f64>().ok())
            .filter(|b| b.is_finite() && *b > 0.0)
            .unwrap_or_else(|| rps.max(1.0));
        tracing::info!(rps, burst, "rate limiter enabled");
        Some(Arc::new(Self {
            rps,
            burst,
            buckets: DashMap::new(),
        }))
    }

    #[cfg(test)]
    pub fn new(rps: f64, burst: f64) -> Arc<Self> {
        Arc::new(Self {
            rps,
            burst,
            buckets: DashMap::new(),
        })
    }

    /// Consume one token for `key`. Returns `true` if allowed.
    fn check(&self, key: &str) -> bool {
        self.check_at(key, Instant::now())
    }

    /// Testable core: `now` injected so the refill maths can be exercised
    /// deterministically.
    fn check_at(&self, key: &str, now: Instant) -> bool {
        // Bound memory: an unseen key past the cap shares the global bucket.
        let effective: &str =
            if self.buckets.len() >= MAX_BUCKETS && !self.buckets.contains_key(key) {
                GLOBAL_KEY
            } else {
                key
            };
        let mut bucket = self.buckets.entry(effective.to_string()).or_insert(Bucket {
            tokens: self.burst,
            last: now,
        });
        let elapsed = now.saturating_duration_since(bucket.last).as_secs_f64();
        bucket.tokens = (bucket.tokens + elapsed * self.rps).min(self.burst);
        bucket.last = now;
        if bucket.tokens >= 1.0 {
            bucket.tokens -= 1.0;
            true
        } else {
            false
        }
    }
}

/// Derive the rate-limit key from trusted forwarding headers, else a shared
/// global bucket. `CF-Connecting-IP` is set by Cloudflare and is the canonical
/// client identity for a Worker-fronted deployment.
fn client_key(req: &Request) -> String {
    let h = req.headers();
    for name in ["cf-connecting-ip", "x-kotoba-client-ip", "x-forwarded-for"] {
        if let Some(v) = h.get(name).and_then(|v| v.to_str().ok()) {
            // `x-forwarded-for` may be a comma list; the first hop is the client.
            if let Some(first) = v.split(',').next() {
                let ip = first.trim();
                if !ip.is_empty() {
                    return ip.to_string();
                }
            }
        }
    }
    GLOBAL_KEY.to_string()
}

/// Axum middleware: reject with `429 Too Many Requests` when the caller's
/// bucket is empty.
pub async fn rate_limit_middleware(
    State(limiter): State<Arc<RateLimiter>>,
    req: Request,
    next: Next,
) -> Result<Response, (StatusCode, String)> {
    let key = client_key(&req);
    if limiter.check(&key) {
        Ok(next.run(req).await)
    } else {
        Err((
            StatusCode::TOO_MANY_REQUESTS,
            "rate limit exceeded".to_string(),
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[test]
    fn burst_then_throttle_then_refill() {
        let rl = RateLimiter::new(1.0, 3.0);
        let t0 = Instant::now();
        // Burst of 3 succeeds.
        assert!(rl.check_at("1.2.3.4", t0));
        assert!(rl.check_at("1.2.3.4", t0));
        assert!(rl.check_at("1.2.3.4", t0));
        // 4th in the same instant is throttled.
        assert!(!rl.check_at("1.2.3.4", t0));
        // After 1s, exactly one token refilled.
        let t1 = t0 + Duration::from_secs(1);
        assert!(rl.check_at("1.2.3.4", t1));
        assert!(!rl.check_at("1.2.3.4", t1));
    }

    #[test]
    fn buckets_are_per_key() {
        let rl = RateLimiter::new(1.0, 1.0);
        let t0 = Instant::now();
        assert!(rl.check_at("a", t0));
        assert!(!rl.check_at("a", t0));
        // A different client has its own bucket.
        assert!(rl.check_at("b", t0));
    }

    #[test]
    fn disabled_without_env() {
        // Ensure the var is unset for this assertion.
        std::env::remove_var("KOTOBA_RATE_LIMIT_RPS");
        assert!(RateLimiter::from_env().is_none());
    }
}
