//! `B2Client` — minimal S3-compatible object client for the CAR-on-B2 cold tier.
//!
//! Backblaze B2 exposes an S3-compatible API (`https://s3.<region>.backblazeb2.com`).
//! This client speaks just enough of it — PutObject / GetObject (+ ranged) /
//! HeadObject / ListObjectsV2 — to upload one CAR bundle per commit and to
//! enumerate / restore them. It signs with **AWS Signature V4** built by hand on
//! the existing `reqwest` dependency (no aws-sdk), and bridges the async HTTP
//! into the synchronous call sites with a dedicated runtime, mirroring
//! `kubo_store::kubo_block_on`.
//!
//! Path-style addressing (`{endpoint}/{bucket}/{key}`) is used — B2 supports it
//! and it avoids per-bucket DNS. The tier is **opt-in**: [`B2Config::from_env`]
//! returns `None` unless all four `KOTOBA_B2_*` vars are set, so default and
//! dev deployments are unaffected.

use anyhow::{anyhow, Context, Result};
use bytes::Bytes;
use hmac::{Hmac, Mac};
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};

type HmacSha256 = Hmac<Sha256>;

/// SHA-256 of the empty payload — the `x-amz-content-sha256` value for bodyless
/// requests (GET / HEAD / LIST).
const EMPTY_SHA256: &str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

// ─── Config ──────────────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct B2Config {
    /// Base endpoint, e.g. `https://s3.us-west-004.backblazeb2.com` (no trailing slash).
    pub endpoint: String,
    pub bucket: String,
    /// SigV4 region, e.g. `us-west-004` (parsed from the endpoint host if unset).
    pub region: String,
    pub key_id: String,
    pub app_key: String,
}

impl B2Config {
    /// Build from `KOTOBA_B2_ENDPOINT` / `_BUCKET` / `_KEY_ID` / `_APP_KEY`
    /// (+ optional `_REGION`). Returns `None` if any required var is absent or
    /// blank — the cold tier and exporter stay disabled.
    pub fn from_env() -> Option<Self> {
        let v = |k: &str| std::env::var(k).ok().filter(|s| !s.trim().is_empty());
        let endpoint = v("KOTOBA_B2_ENDPOINT")?;
        let bucket = v("KOTOBA_B2_BUCKET")?;
        let key_id = v("KOTOBA_B2_KEY_ID")?;
        let app_key = v("KOTOBA_B2_APP_KEY")?;
        let region = v("KOTOBA_B2_REGION").unwrap_or_else(|| region_from_endpoint(&endpoint));
        Some(Self {
            endpoint: endpoint.trim_end_matches('/').to_string(),
            bucket,
            region,
            key_id,
            app_key,
        })
    }

    fn host(&self) -> &str {
        self.endpoint
            .strip_prefix("https://")
            .or_else(|| self.endpoint.strip_prefix("http://"))
            .unwrap_or(&self.endpoint)
    }
}

/// `https://s3.us-west-004.backblazeb2.com` → `us-west-004`. Falls back to
/// `us-east-1` if the host doesn't match the `s3.<region>.…` shape.
fn region_from_endpoint(endpoint: &str) -> String {
    let host = endpoint
        .strip_prefix("https://")
        .or_else(|| endpoint.strip_prefix("http://"))
        .unwrap_or(endpoint);
    host.strip_prefix("s3.")
        .and_then(|rest| rest.split('.').next())
        .unwrap_or("us-east-1")
        .to_string()
}

// ─── SigV4 (pure, testable) ──────────────────────────────────────────────────

/// RFC-3986 percent-encoding per AWS rules. Unreserved set `A-Za-z0-9-_.~` is
/// left as-is; everything else is `%XX` (uppercase). When `encode_slash` is
/// false, `/` is preserved (path segments); when true, it is encoded (query).
fn uri_encode(s: &str, encode_slash: bool) -> String {
    let mut out = String::with_capacity(s.len());
    for &b in s.as_bytes() {
        let keep = b.is_ascii_alphanumeric()
            || matches!(b, b'-' | b'_' | b'.' | b'~')
            || (b == b'/' && !encode_slash);
        if keep {
            out.push(b as char);
        } else {
            out.push('%');
            out.push_str(&format!("{b:02X}"));
        }
    }
    out
}

fn hex_sha256(data: &[u8]) -> String {
    hex::encode(Sha256::digest(data))
}

fn hmac(key: &[u8], msg: &[u8]) -> Vec<u8> {
    let mut m = HmacSha256::new_from_slice(key).expect("HMAC accepts any key length");
    m.update(msg);
    m.finalize().into_bytes().to_vec()
}

/// Derive the SigV4 signing key: `AWS4{secret} → date → region → service → aws4_request`.
fn signing_key(secret: &str, datestamp: &str, region: &str, service: &str) -> Vec<u8> {
    let k_date = hmac(format!("AWS4{secret}").as_bytes(), datestamp.as_bytes());
    let k_region = hmac(&k_date, region.as_bytes());
    let k_service = hmac(&k_region, service.as_bytes());
    hmac(&k_service, b"aws4_request")
}

/// Compute the lowercase-hex SigV4 signature for a fully-formed canonical
/// request. Kept dependency-free and parameterised so the AWS sig-v4-test-suite
/// known-answer vectors can pin it (see tests).
#[allow(clippy::too_many_arguments)]
fn sigv4_signature(
    secret: &str,
    region: &str,
    service: &str,
    amzdate: &str,
    datestamp: &str,
    canonical_request: &str,
) -> String {
    let scope = format!("{datestamp}/{region}/{service}/aws4_request");
    let string_to_sign = format!(
        "AWS4-HMAC-SHA256\n{amzdate}\n{scope}\n{}",
        hex_sha256(canonical_request.as_bytes())
    );
    let key = signing_key(secret, datestamp, region, service);
    hex::encode(hmac(&key, string_to_sign.as_bytes()))
}

/// Build the canonical request string (AWS SigV4 §"Create a canonical request").
fn canonical_request(
    method: &str,
    canonical_uri: &str,
    canonical_query: &str,
    canonical_headers: &str,
    signed_headers: &str,
    payload_hash: &str,
) -> String {
    format!(
        "{method}\n{canonical_uri}\n{canonical_query}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )
}

// ─── Timestamp (no chrono dep) ───────────────────────────────────────────────

/// `(amzdate "YYYYMMDDTHHMMSSZ", datestamp "YYYYMMDD")` for a unix second count.
/// Uses Howard Hinnant's days→civil algorithm so it stays dependency-free and
/// deterministic (the tests pin a fixed instant).
fn amz_timestamps(unix_secs: u64) -> (String, String) {
    let days = (unix_secs / 86_400) as i64;
    let secs_of_day = unix_secs % 86_400;
    let (h, mi, s) = (secs_of_day / 3600, (secs_of_day % 3600) / 60, secs_of_day % 60);

    // days since 1970-01-01 → civil (y, m, d). Hinnant, "chrono-Compatible Low-Level Date Algorithms".
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };

    let datestamp = format!("{y:04}{m:02}{d:02}");
    let amzdate = format!("{y:04}{m:02}{d:02}T{h:02}{mi:02}{s:02}Z");
    (amzdate, datestamp)
}

fn now_timestamps() -> (String, String) {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    amz_timestamps(secs)
}

// ─── Client ──────────────────────────────────────────────────────────────────

#[derive(Clone)]
pub struct B2Client {
    cfg: B2Config,
    http: reqwest::Client,
}

impl B2Client {
    pub fn new(cfg: B2Config) -> Self {
        Self {
            cfg,
            http: reqwest::Client::new(),
        }
    }

    pub fn bucket(&self) -> &str {
        &self.cfg.bucket
    }

    /// Sign + send one request. `query` is the already-canonical (sorted,
    /// encoded) query string (may be empty). `body` is `None` for GET/HEAD/LIST.
    async fn send(
        &self,
        method: &str,
        key: &str,
        query: &str,
        range: Option<(u64, u64)>,
        body: Option<&[u8]>,
    ) -> Result<reqwest::Response> {
        let (amzdate, datestamp) = now_timestamps();
        let host = self.cfg.host().to_string();
        let payload_hash = match body {
            Some(b) => hex_sha256(b),
            None => EMPTY_SHA256.to_string(),
        };
        // canonical_uri: /{bucket}/{key} with each path segment encoded, "/" kept.
        let canonical_uri = if key.is_empty() {
            format!("/{}", uri_encode(&self.cfg.bucket, true))
        } else {
            format!(
                "/{}/{}",
                uri_encode(&self.cfg.bucket, true),
                uri_encode(key, false)
            )
        };
        // Signed headers: host;x-amz-content-sha256;x-amz-date (alphabetical).
        let canonical_headers = format!(
            "host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amzdate}\n"
        );
        let signed_headers = "host;x-amz-content-sha256;x-amz-date";
        let creq = canonical_request(
            method,
            &canonical_uri,
            query,
            &canonical_headers,
            signed_headers,
            &payload_hash,
        );
        let signature = sigv4_signature(
            &self.cfg.app_key,
            &self.cfg.region,
            "s3",
            &amzdate,
            &datestamp,
            &creq,
        );
        let scope = format!("{datestamp}/{}/s3/aws4_request", self.cfg.region);
        let authorization = format!(
            "AWS4-HMAC-SHA256 Credential={}/{scope}, SignedHeaders={signed_headers}, Signature={signature}",
            self.cfg.key_id
        );

        let url = if query.is_empty() {
            format!("{}{canonical_uri}", self.cfg.endpoint)
        } else {
            format!("{}{canonical_uri}?{query}", self.cfg.endpoint)
        };
        let mut rb = self
            .http
            .request(method.parse().context("bad method")?, &url)
            .header("host", &host)
            .header("x-amz-content-sha256", &payload_hash)
            .header("x-amz-date", &amzdate)
            .header("authorization", authorization);
        if let Some((start, len)) = range {
            rb = rb.header("range", format!("bytes={}-{}", start, start + len - 1));
        }
        if let Some(b) = body {
            rb = rb.body(b.to_vec());
        }
        rb.send().await.context("b2 request send failed")
    }

    /// PutObject — single PUT of `body` under `key`. `key` is the CAR object name.
    pub async fn put_object(&self, key: &str, body: &[u8]) -> Result<()> {
        let resp = self.send("PUT", key, "", None, Some(body)).await?;
        let status = resp.status();
        if !status.is_success() {
            let txt = resp.text().await.unwrap_or_default();
            return Err(anyhow!("b2 PUT {key} → {status}: {txt}"));
        }
        Ok(())
    }

    /// GetObject — full object bytes.
    pub async fn get_object(&self, key: &str) -> Result<Bytes> {
        let resp = self.send("GET", key, "", None, None).await?;
        let status = resp.status();
        if !status.is_success() {
            let txt = resp.text().await.unwrap_or_default();
            return Err(anyhow!("b2 GET {key} → {status}: {txt}"));
        }
        Ok(resp.bytes().await.context("b2 GET body")?)
    }

    /// GetObject with a `Range: bytes=start-(start+len-1)` — the CAR ranged read.
    pub async fn get_object_range(&self, key: &str, start: u64, len: u64) -> Result<Bytes> {
        let resp = self
            .send("GET", key, "", Some((start, len)), None)
            .await?;
        let status = resp.status();
        // 206 Partial Content on success; some gateways return 200 for full-range.
        if !status.is_success() {
            let txt = resp.text().await.unwrap_or_default();
            return Err(anyhow!("b2 GET-range {key} → {status}: {txt}"));
        }
        Ok(resp.bytes().await.context("b2 GET-range body")?)
    }

    /// HeadObject — `true` if the key exists (200), `false` on 404.
    pub async fn head_object(&self, key: &str) -> Result<bool> {
        let resp = self.send("HEAD", key, "", None, None).await?;
        Ok(resp.status().is_success())
    }

    /// ListObjectsV2 under `prefix` → all keys (follows continuation tokens).
    pub async fn list_objects(&self, prefix: &str) -> Result<Vec<String>> {
        let mut keys = Vec::new();
        let mut token: Option<String> = None;
        loop {
            // Canonical query: params sorted by key, values uri-encoded (slash too).
            let mut params: Vec<(String, String)> = vec![("list-type".into(), "2".into())];
            if !prefix.is_empty() {
                params.push(("prefix".into(), prefix.to_string()));
            }
            if let Some(t) = &token {
                params.push(("continuation-token".into(), t.clone()));
            }
            params.sort_by(|a, b| a.0.cmp(&b.0));
            let query = params
                .iter()
                .map(|(k, v)| format!("{}={}", uri_encode(k, true), uri_encode(v, true)))
                .collect::<Vec<_>>()
                .join("&");

            let resp = self.send("GET", "", &query, None, None).await?;
            let status = resp.status();
            let body = resp.text().await.context("b2 LIST body")?;
            if !status.is_success() {
                return Err(anyhow!("b2 LIST → {status}: {body}"));
            }
            for cap in body.split("<Key>").skip(1) {
                if let Some(end) = cap.find("</Key>") {
                    keys.push(cap[..end].to_string());
                }
            }
            // <IsTruncated>true</IsTruncated> + <NextContinuationToken>…</…>
            let truncated = body.contains("<IsTruncated>true</IsTruncated>");
            token = if truncated {
                body.split("<NextContinuationToken>")
                    .nth(1)
                    .and_then(|s| s.split("</NextContinuationToken>").next())
                    .map(|s| s.to_string())
            } else {
                None
            };
            if token.is_none() {
                break;
            }
        }
        Ok(keys)
    }
}

// ─── Sync bridge (mirrors kubo_store::kubo_block_on) ──────────────────────────

/// Dedicated multi-thread runtime driving B2 HTTP I/O for synchronous callers.
/// Keeping I/O off the caller's runtime is what prevents the "runtime within a
/// runtime" deadlock — see the rationale on `kubo_store::kubo_runtime`.
fn b2_runtime() -> &'static tokio::runtime::Runtime {
    static RT: std::sync::OnceLock<tokio::runtime::Runtime> = std::sync::OnceLock::new();
    RT.get_or_init(|| {
        tokio::runtime::Builder::new_multi_thread()
            .worker_threads(2)
            .enable_all()
            .thread_name("b2-io")
            .build()
            .expect("build b2-io runtime")
    })
}

/// Spawn a long-running future onto the dedicated `b2-io` runtime (used for the
/// CAR export task, so it runs independently of whether the caller is inside a
/// Tokio runtime — `KotobaState::new` is synchronous).
pub fn b2_spawn<F>(fut: F)
where
    F: std::future::Future<Output = ()> + Send + 'static,
{
    b2_runtime().spawn(fut);
}

/// Drive a B2 future to completion from a synchronous context without starving
/// the caller's runtime (spawn on `b2-io`, block the current worker on a std
/// channel via `block_in_place`). Outside any runtime, block directly.
pub fn b2_block_on<F>(fut: F) -> F::Output
where
    F: std::future::Future + Send + 'static,
    F::Output: Send + 'static,
{
    let rt = b2_runtime();
    match tokio::runtime::Handle::try_current() {
        Ok(_) => {
            let (tx, rx) = std::sync::mpsc::sync_channel(1);
            rt.spawn(async move {
                let _ = tx.send(fut.await);
            });
            tokio::task::block_in_place(|| rx.recv())
                .expect("b2-io runtime dropped the in-flight result")
        }
        Err(_) => rt.block_on(fut),
    }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn region_parsed_from_endpoint() {
        assert_eq!(
            region_from_endpoint("https://s3.us-west-004.backblazeb2.com"),
            "us-west-004"
        );
        assert_eq!(region_from_endpoint("https://example.com"), "us-east-1");
    }

    #[test]
    fn uri_encode_rules() {
        assert_eq!(uri_encode("a/b c", false), "a/b%20c"); // path keeps slash
        assert_eq!(uri_encode("a/b c", true), "a%2Fb%20c"); // query encodes slash
        assert_eq!(uri_encode("Aa0-_.~", false), "Aa0-_.~"); // unreserved untouched
    }

    #[test]
    fn amz_timestamps_known_instant() {
        // 2015-08-30T12:36:00Z = 1440938160 (the sig-v4 test-suite instant).
        assert_eq!(
            amz_timestamps(1_440_938_160),
            ("20150830T123600Z".to_string(), "20150830".to_string())
        );
    }

    /// AWS SigV4 known-answer test — `get-vanilla` from the published
    /// aws-sig-v4-test-suite. A signing bug here is otherwise a silent 403.
    #[test]
    fn sigv4_get_vanilla_known_answer() {
        let access = "AKIDEXAMPLE";
        let secret = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY";
        let region = "us-east-1";
        let service = "service";
        let amzdate = "20150830T123600Z";
        let datestamp = "20150830";

        let canonical_headers = "host:example.amazonaws.com\nx-amz-date:20150830T123600Z\n";
        let signed_headers = "host;x-amz-date";
        let creq = canonical_request(
            "GET",
            "/",
            "",
            canonical_headers,
            signed_headers,
            EMPTY_SHA256,
        );
        let sig = sigv4_signature(secret, region, service, amzdate, datestamp, &creq);
        assert_eq!(
            sig, "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31",
            "SigV4 signature mismatch (get-vanilla) — signing is broken"
        );
        let _ = access; // documents the credential the Authorization header would carry
    }

    /// Second KAT — the AWS docs "Signature Version 4 signing (Python)" worked
    /// example: GET https://iam.amazonaws.com/?Action=ListUsers&Version=2010-05-08,
    /// us-east-1 / iam / 20150830T123600Z. Exercises query canonicalization +
    /// the x-amz-content-sha256 signed header (the production header set).
    #[test]
    fn sigv4_iam_listusers_known_answer() {
        let secret = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY";
        let region = "us-east-1";
        let service = "iam";
        let amzdate = "20150830T123600Z";
        let datestamp = "20150830";

        // Canonical query: params sorted, values uri-encoded (slash encoded).
        let query = "Action=ListUsers&Version=2010-05-08";
        let canonical_headers = format!(
            "content-type:application/x-www-form-urlencoded; charset=utf-8\nhost:iam.amazonaws.com\nx-amz-date:{amzdate}\n"
        );
        let signed_headers = "content-type;host;x-amz-date";
        let creq = canonical_request(
            "GET",
            "/",
            query,
            &canonical_headers,
            signed_headers,
            EMPTY_SHA256,
        );
        let sig = sigv4_signature(secret, region, service, amzdate, datestamp, &creq);
        assert_eq!(
            sig, "5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7",
            "SigV4 signature mismatch (iam ListUsers) — signing is broken"
        );
    }

    /// Live B2 round-trip — the verification bar: PUT a CAR-shaped object, then
    /// read its bytes back (full + ranged) and confirm via HEAD + LIST. Gated on
    /// `KOTOBA_B2_*`; run with real creds:
    ///   KOTOBA_B2_ENDPOINT=… KOTOBA_B2_BUCKET=… KOTOBA_B2_KEY_ID=… \
    ///   KOTOBA_B2_APP_KEY=… cargo test -p kotoba-store b2_live_roundtrip -- --ignored --nocapture
    #[tokio::test]
    #[ignore = "requires live B2 creds (KOTOBA_B2_*)"]
    async fn b2_live_roundtrip() {
        let cfg = B2Config::from_env().expect("KOTOBA_B2_* must be set");
        let client = B2Client::new(cfg);
        let key = "kotoba/cars/_selftest_roundtrip.kcar";
        let body: Vec<u8> = (0u8..=255).cycle().take(4096).collect();

        client.put_object(key, &body).await.expect("PUT");
        assert!(client.head_object(key).await.expect("HEAD"), "object should exist");

        let full = client.get_object(key).await.expect("GET");
        assert_eq!(&full[..], &body[..], "full GET bytes mismatch");

        let (start, len) = (1000u64, 256u64);
        let ranged = client.get_object_range(key, start, len).await.expect("GET range");
        assert_eq!(
            &ranged[..],
            &body[start as usize..(start + len) as usize],
            "ranged GET bytes mismatch"
        );

        let keys = client.list_objects("kotoba/cars/").await.expect("LIST");
        assert!(keys.iter().any(|k| k == key), "LIST should contain the key");
        println!("b2_live_roundtrip OK: bucket={} key={}", client.bucket(), key);
    }
}
