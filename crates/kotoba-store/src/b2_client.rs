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
const MAX_B2_ENDPOINT_LEN: usize = 2048;
const MAX_B2_BUCKET_LEN: usize = 128;
const MAX_B2_REGION_LEN: usize = 64;
const MAX_B2_KEY_ID_LEN: usize = 256;
const MAX_B2_APP_KEY_LEN: usize = 512;
const MAX_B2_OBJECT_KEY_LEN: usize = 1024;
const MAX_B2_LIST_PREFIX_LEN: usize = 1024;
const MAX_B2_LIST_RESPONSE_BYTES: usize = 8 * 1024 * 1024;
const MAX_B2_CONTINUATION_TOKEN_LEN: usize = 2048;
const MAX_B2_LIST_PAGES: usize = 1_000_000;

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
        normalize_config(endpoint, bucket, region, key_id, app_key).ok()
    }

    fn host(&self) -> &str {
        self.endpoint
            .strip_prefix("https://")
            .or_else(|| self.endpoint.strip_prefix("http://"))
            .unwrap_or(&self.endpoint)
    }
}

fn normalize_config(
    endpoint: String,
    bucket: String,
    region: String,
    key_id: String,
    app_key: String,
) -> Result<B2Config> {
    Ok(B2Config {
        endpoint: normalize_endpoint(&endpoint)?,
        bucket: validate_plain_component("bucket", bucket, MAX_B2_BUCKET_LEN)?,
        region: validate_plain_component("region", region, MAX_B2_REGION_LEN)?,
        key_id: validate_plain_component("key_id", key_id, MAX_B2_KEY_ID_LEN)?,
        app_key: validate_plain_component("app_key", app_key, MAX_B2_APP_KEY_LEN)?,
    })
}

fn normalize_endpoint(endpoint: &str) -> Result<String> {
    let endpoint = endpoint.trim();
    anyhow::ensure!(!endpoint.is_empty(), "b2 endpoint must be non-empty");
    anyhow::ensure!(
        endpoint.len() <= MAX_B2_ENDPOINT_LEN,
        "b2 endpoint too long: {} > {MAX_B2_ENDPOINT_LEN}",
        endpoint.len()
    );
    anyhow::ensure!(
        !has_control(endpoint),
        "b2 endpoint must not contain control characters"
    );
    let parsed = reqwest::Url::parse(endpoint).context("invalid b2 endpoint URL")?;
    anyhow::ensure!(
        matches!(parsed.scheme(), "https" | "http"),
        "b2 endpoint scheme must be http or https"
    );
    anyhow::ensure!(
        parsed.username().is_empty() && parsed.password().is_none(),
        "b2 endpoint must not contain userinfo"
    );
    anyhow::ensure!(
        parsed.host_str().is_some(),
        "b2 endpoint must include a host"
    );
    anyhow::ensure!(
        matches!(parsed.path(), "" | "/")
            && parsed.query().is_none()
            && parsed.fragment().is_none(),
        "b2 endpoint must not include path, query, or fragment"
    );
    let mut normalized = parsed;
    normalized.set_path("");
    normalized.set_query(None);
    normalized.set_fragment(None);
    Ok(normalized.as_str().trim_end_matches('/').to_string())
}

fn validate_plain_component(name: &str, value: String, max_len: usize) -> Result<String> {
    let value = value.trim().to_string();
    anyhow::ensure!(!value.is_empty(), "b2 {name} must be non-empty");
    anyhow::ensure!(
        value.len() <= max_len,
        "b2 {name} too long: {} > {max_len}",
        value.len()
    );
    anyhow::ensure!(
        !has_control(&value),
        "b2 {name} must not contain control characters"
    );
    Ok(value)
}

fn validate_object_key(key: &str) -> Result<()> {
    anyhow::ensure!(!key.is_empty(), "b2 object key must be non-empty");
    validate_pathish_component("object key", key, MAX_B2_OBJECT_KEY_LEN)
}

fn validate_list_prefix(prefix: &str) -> Result<()> {
    validate_pathish_component("list prefix", prefix, MAX_B2_LIST_PREFIX_LEN)
}

fn validate_continuation_token(token: &str) -> Result<()> {
    anyhow::ensure!(!token.is_empty(), "b2 continuation token must be non-empty");
    anyhow::ensure!(
        token.len() <= MAX_B2_CONTINUATION_TOKEN_LEN,
        "b2 continuation token too long: {} > {MAX_B2_CONTINUATION_TOKEN_LEN}",
        token.len()
    );
    anyhow::ensure!(
        !has_control(token),
        "b2 continuation token must not contain control characters"
    );
    Ok(())
}

fn validate_next_list_token(previous: Option<&str>, next: Option<&str>) -> Result<()> {
    if let Some(token) = next {
        validate_continuation_token(token)?;
        anyhow::ensure!(
            previous != Some(token),
            "b2 LIST continuation token did not advance"
        );
    }
    Ok(())
}

fn validate_pathish_component(name: &str, value: &str, max_len: usize) -> Result<()> {
    anyhow::ensure!(
        value.len() <= max_len,
        "b2 {name} too long: {} > {max_len}",
        value.len()
    );
    anyhow::ensure!(
        !has_control(value),
        "b2 {name} must not contain control characters"
    );
    anyhow::ensure!(!value.starts_with('/'), "b2 {name} must be relative");
    Ok(())
}

fn has_control(value: &str) -> bool {
    value.bytes().any(|b| b.is_ascii_control())
}

fn parse_list_objects_body(body: &str) -> Result<(Vec<String>, Option<String>)> {
    anyhow::ensure!(
        body.len() <= MAX_B2_LIST_RESPONSE_BYTES,
        "b2 LIST response too large: {} > {MAX_B2_LIST_RESPONSE_BYTES}",
        body.len()
    );
    let keys = extract_xml_tag_texts(body, "Key")?;
    for key in &keys {
        validate_object_key(key).with_context(|| format!("invalid b2 LIST object key: {key:?}"))?;
    }
    let truncated = extract_xml_tag_texts(body, "IsTruncated")?
        .into_iter()
        .any(|s| s.trim().eq_ignore_ascii_case("true"));
    let token = if truncated {
        let mut tokens = extract_xml_tag_texts(body, "NextContinuationToken")?;
        anyhow::ensure!(
            !tokens.is_empty(),
            "b2 LIST response is truncated but has no NextContinuationToken"
        );
        let token = tokens.remove(0);
        validate_continuation_token(&token)?;
        Some(token)
    } else {
        None
    };
    Ok((keys, token))
}

fn extract_xml_tag_texts(body: &str, tag: &str) -> Result<Vec<String>> {
    let open = format!("<{tag}>");
    let close = format!("</{tag}>");
    let mut values = Vec::new();
    let mut rest = body;
    while let Some(start) = rest.find(&open) {
        let after_open = &rest[start + open.len()..];
        let Some(end) = after_open.find(&close) else {
            anyhow::bail!("b2 LIST response has unterminated <{tag}> element");
        };
        values.push(decode_xml_text(&after_open[..end])?);
        rest = &after_open[end + close.len()..];
    }
    Ok(values)
}

fn decode_xml_text(text: &str) -> Result<String> {
    let mut out = String::with_capacity(text.len());
    let mut rest = text;
    while let Some(pos) = rest.find('&') {
        out.push_str(&rest[..pos]);
        rest = &rest[pos + 1..];
        let Some(end) = rest.find(';') else {
            anyhow::bail!("unterminated XML entity in b2 LIST response");
        };
        let entity = &rest[..end];
        if entity == "amp" {
            out.push('&');
        } else if entity == "lt" {
            out.push('<');
        } else if entity == "gt" {
            out.push('>');
        } else if entity == "quot" {
            out.push('"');
        } else if entity == "apos" {
            out.push('\'');
        } else if let Some(hex) = entity.strip_prefix("#x") {
            let code = u32::from_str_radix(hex, 16)
                .with_context(|| format!("invalid XML hex entity: &{entity};"))?;
            let ch =
                char::from_u32(code).ok_or_else(|| anyhow!("invalid XML codepoint: &{entity};"))?;
            out.push(ch);
        } else if let Some(dec) = entity.strip_prefix('#') {
            let code = dec
                .parse::<u32>()
                .with_context(|| format!("invalid XML decimal entity: &{entity};"))?;
            let ch =
                char::from_u32(code).ok_or_else(|| anyhow!("invalid XML codepoint: &{entity};"))?;
            out.push(ch);
        } else {
            anyhow::bail!("unknown XML entity in b2 LIST response: &{entity};");
        }
        rest = &rest[end + 1..];
    }
    out.push_str(rest);
    Ok(out)
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

fn range_header(start: u64, len: u64) -> Result<String> {
    anyhow::ensure!(len > 0, "b2 range length must be non-zero");
    let end = start
        .checked_add(len - 1)
        .ok_or_else(|| anyhow!("b2 range end overflows u64: start={start}, len={len}"))?;
    Ok(format!("bytes={start}-{end}"))
}

// ─── Timestamp (no chrono dep) ───────────────────────────────────────────────

/// `(amzdate "YYYYMMDDTHHMMSSZ", datestamp "YYYYMMDD")` for a unix second count.
/// Uses Howard Hinnant's days→civil algorithm so it stays dependency-free and
/// deterministic (the tests pin a fixed instant).
fn amz_timestamps(unix_secs: u64) -> (String, String) {
    let days = (unix_secs / 86_400) as i64;
    let secs_of_day = unix_secs % 86_400;
    let (h, mi, s) = (
        secs_of_day / 3600,
        (secs_of_day % 3600) / 60,
        secs_of_day % 60,
    );

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
        let canonical_headers =
            format!("host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amzdate}\n");
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
            rb = rb.header("range", range_header(start, len)?);
        }
        if let Some(b) = body {
            rb = rb.body(b.to_vec());
        }
        rb.send().await.context("b2 request send failed")
    }

    /// PutObject — single PUT of `body` under `key`. `key` is the CAR object name.
    pub async fn put_object(&self, key: &str, body: &[u8]) -> Result<()> {
        validate_object_key(key)?;
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
        validate_object_key(key)?;
        let resp = self.send("GET", key, "", None, None).await?;
        let status = resp.status();
        if !status.is_success() {
            let txt = resp.text().await.unwrap_or_default();
            return Err(anyhow!("b2 GET {key} → {status}: {txt}"));
        }
        resp.bytes().await.context("b2 GET body")
    }

    /// GetObject with a `Range: bytes=start-(start+len-1)` — the CAR ranged read.
    pub async fn get_object_range(&self, key: &str, start: u64, len: u64) -> Result<Bytes> {
        validate_object_key(key)?;
        let _ = range_header(start, len)?;
        let resp = self.send("GET", key, "", Some((start, len)), None).await?;
        let status = resp.status();
        // 206 Partial Content on success; some gateways return 200 for full-range.
        if !status.is_success() {
            let txt = resp.text().await.unwrap_or_default();
            return Err(anyhow!("b2 GET-range {key} → {status}: {txt}"));
        }
        resp.bytes().await.context("b2 GET-range body")
    }

    /// HeadObject — `true` if the key exists (200), `false` on 404.
    pub async fn head_object(&self, key: &str) -> Result<bool> {
        validate_object_key(key)?;
        let resp = self.send("HEAD", key, "", None, None).await?;
        Ok(resp.status().is_success())
    }

    /// ListObjectsV2 under `prefix` → all keys (follows continuation tokens).
    pub async fn list_objects(&self, prefix: &str) -> Result<Vec<String>> {
        validate_list_prefix(prefix)?;
        let mut keys = Vec::new();
        let mut token: Option<String> = None;
        let mut pages = 0usize;
        loop {
            pages += 1;
            anyhow::ensure!(
                pages <= MAX_B2_LIST_PAGES,
                "b2 LIST exceeded page limit {MAX_B2_LIST_PAGES}"
            );
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
            let body = resp.bytes().await.context("b2 LIST body")?;
            anyhow::ensure!(
                body.len() <= MAX_B2_LIST_RESPONSE_BYTES,
                "b2 LIST response too large: {} > {MAX_B2_LIST_RESPONSE_BYTES}",
                body.len()
            );
            let body = std::str::from_utf8(&body).context("b2 LIST body is not UTF-8")?;
            if !status.is_success() {
                return Err(anyhow!("b2 LIST → {status}: {body}"));
            }
            let (page_keys, next_token) = parse_list_objects_body(body)?;
            validate_next_list_token(token.as_deref(), next_token.as_deref())?;
            keys.extend(page_keys);
            token = next_token;
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
        Ok(handle) => {
            let (tx, rx) = std::sync::mpsc::sync_channel(1);
            rt.spawn(async move {
                let _ = tx.send(fut.await);
            });
            if matches!(
                handle.runtime_flavor(),
                tokio::runtime::RuntimeFlavor::MultiThread
            ) {
                tokio::task::block_in_place(|| rx.recv())
                    .expect("b2-io runtime dropped the in-flight result")
            } else {
                rx.recv()
                    .expect("b2-io runtime dropped the in-flight result")
            }
        }
        Err(_) => rt.block_on(fut),
    }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test(flavor = "current_thread")]
    async fn b2_block_on_works_inside_current_thread_runtime() {
        assert_eq!(b2_block_on(async { 7usize }), 7);
    }

    #[test]
    fn region_parsed_from_endpoint() {
        assert_eq!(
            region_from_endpoint("https://s3.us-west-004.backblazeb2.com"),
            "us-west-004"
        );
        assert_eq!(region_from_endpoint("https://example.com"), "us-east-1");
    }

    #[test]
    fn normalize_endpoint_accepts_http_https_and_strips_trailing_slash() {
        assert_eq!(
            normalize_endpoint("https://s3.us-west-004.backblazeb2.com/").unwrap(),
            "https://s3.us-west-004.backblazeb2.com"
        );
        assert_eq!(
            normalize_endpoint("http://localhost:9000").unwrap(),
            "http://localhost:9000"
        );
    }

    #[test]
    fn normalize_endpoint_rejects_ambiguous_or_header_unsafe_values() {
        for endpoint in [
            "ftp://s3.us-west-004.backblazeb2.com",
            "https://user:pass@s3.us-west-004.backblazeb2.com",
            "https://s3.us-west-004.backblazeb2.com/bucket",
            "https://s3.us-west-004.backblazeb2.com?x=1",
            "https://s3.us-west-004.backblazeb2.com#frag",
            "https://s3.us-west-004.backblazeb2.com\r\nx: y",
        ] {
            assert!(
                normalize_endpoint(endpoint).is_err(),
                "endpoint should be rejected: {endpoint:?}"
            );
        }
    }

    #[test]
    fn normalize_config_trims_and_rejects_control_characters_in_header_fields() {
        let cfg = normalize_config(
            " https://s3.us-west-004.backblazeb2.com/ ".to_string(),
            " bucket-name ".to_string(),
            " us-west-004 ".to_string(),
            " key-id ".to_string(),
            " app-key ".to_string(),
        )
        .unwrap();

        assert_eq!(cfg.endpoint, "https://s3.us-west-004.backblazeb2.com");
        assert_eq!(cfg.bucket, "bucket-name");
        assert_eq!(cfg.region, "us-west-004");
        assert_eq!(cfg.key_id, "key-id");
        assert_eq!(cfg.app_key, "app-key");

        assert!(
            normalize_config(
                "https://s3.us-west-004.backblazeb2.com".to_string(),
                "bucket".to_string(),
                "us-west-004\nx: y".to_string(),
                "key-id".to_string(),
                "app-key".to_string(),
            )
            .is_err(),
            "region is embedded in Authorization and must be header-safe"
        );
        assert!(
            normalize_config(
                "https://s3.us-west-004.backblazeb2.com".to_string(),
                "bucket".to_string(),
                "us-west-004".to_string(),
                "key-id\r\nx: y".to_string(),
                "app-key".to_string(),
            )
            .is_err(),
            "key_id is embedded in Authorization and must be header-safe"
        );
    }

    #[test]
    fn uri_encode_rules() {
        assert_eq!(uri_encode("a/b c", false), "a/b%20c"); // path keeps slash
        assert_eq!(uri_encode("a/b c", true), "a%2Fb%20c"); // query encodes slash
        assert_eq!(uri_encode("Aa0-_.~", false), "Aa0-_.~"); // unreserved untouched
    }

    #[test]
    fn object_key_validation_allows_relative_prefixes_but_rejects_unsafe_values() {
        validate_object_key("kotoba/cars/object.kcar").unwrap();
        assert!(validate_object_key("").is_err());
        assert!(validate_object_key("/absolute").is_err());
        assert!(validate_object_key("bad\nkey").is_err());
        assert!(validate_object_key(&"x".repeat(MAX_B2_OBJECT_KEY_LEN + 1)).is_err());
    }

    #[test]
    fn list_prefix_validation_allows_empty_prefix_but_rejects_unsafe_values() {
        validate_list_prefix("").unwrap();
        validate_list_prefix("kotoba/cars/").unwrap();
        assert!(validate_list_prefix("/absolute").is_err());
        assert!(validate_list_prefix("bad\rprefix").is_err());
        assert!(validate_list_prefix(&"x".repeat(MAX_B2_LIST_PREFIX_LEN + 1)).is_err());
    }

    #[test]
    fn parse_list_objects_body_decodes_keys_and_continuation_token() {
        let body = r#"
            <ListBucketResult>
              <Contents><Key>kotoba/cars/a&amp;b.kcar</Key></Contents>
              <Contents><Key>kotoba/cars/lt&#x2F;gt&#47;&lt;&gt;.kcar</Key></Contents>
              <IsTruncated>true</IsTruncated>
              <NextContinuationToken>tok&amp;en&#45;1</NextContinuationToken>
            </ListBucketResult>
        "#;

        let (keys, token) = parse_list_objects_body(body).unwrap();

        assert_eq!(
            keys,
            vec![
                "kotoba/cars/a&b.kcar".to_string(),
                "kotoba/cars/lt/gt/<>.kcar".to_string(),
            ]
        );
        assert_eq!(token.as_deref(), Some("tok&en-1"));
    }

    #[test]
    fn parse_list_objects_body_rejects_truncated_without_token() {
        let err = parse_list_objects_body(
            "<ListBucketResult><IsTruncated>true</IsTruncated></ListBucketResult>",
        )
        .unwrap_err();

        assert!(
            err.to_string().contains("NextContinuationToken"),
            "truncated LIST pages must not be treated as complete: {err}"
        );
    }

    #[test]
    fn parse_list_objects_body_rejects_invalid_returned_key() {
        let err = parse_list_objects_body(
            "<ListBucketResult><Contents><Key>/absolute</Key></Contents></ListBucketResult>",
        )
        .unwrap_err();

        assert!(
            err.to_string().contains("invalid b2 LIST object key"),
            "LIST keys are fed into signed object requests and must be validated: {err}"
        );
    }

    #[test]
    fn parse_list_objects_body_rejects_invalid_continuation_token() {
        let body = "<ListBucketResult><IsTruncated>true</IsTruncated><NextContinuationToken>bad&#10;token</NextContinuationToken></ListBucketResult>";

        let err = parse_list_objects_body(body).unwrap_err();

        assert!(
            err.to_string().contains("continuation token"),
            "continuation tokens become query params and must be bounded/header-safe: {err}"
        );
    }

    #[test]
    fn validate_next_list_token_rejects_non_advancing_or_invalid_token() {
        validate_next_list_token(None, None).unwrap();
        validate_next_list_token(None, Some("page-1")).unwrap();
        validate_next_list_token(Some("page-1"), Some("page-2")).unwrap();

        let same = validate_next_list_token(Some("page-1"), Some("page-1")).unwrap_err();
        assert!(
            same.to_string().contains("did not advance"),
            "same continuation token would loop forever: {same}"
        );

        let invalid = validate_next_list_token(Some("page-1"), Some("bad\ntoken")).unwrap_err();
        assert!(
            invalid.to_string().contains("continuation token"),
            "next token should still pass token validation: {invalid}"
        );
    }

    #[test]
    fn parse_list_objects_body_rejects_oversized_response() {
        let body = "x".repeat(MAX_B2_LIST_RESPONSE_BYTES + 1);

        let err = parse_list_objects_body(&body).unwrap_err();

        assert!(
            err.to_string().contains("LIST response too large"),
            "untrusted LIST responses must be bounded before parsing: {err}"
        );
    }

    #[test]
    fn decode_xml_text_rejects_unknown_or_unterminated_entities() {
        assert!(decode_xml_text("bad &bogus; entity").is_err());
        assert!(decode_xml_text("bad &amp entity").is_err());
    }

    #[test]
    fn range_header_rejects_zero_len() {
        let err = range_header(72, 0).unwrap_err();

        assert!(
            err.to_string().contains("non-zero"),
            "zero-length ranges must be handled before building an HTTP Range header: {err}"
        );
    }

    #[test]
    fn range_header_rejects_overflowing_end() {
        let err = range_header(u64::MAX, 2).unwrap_err();

        assert!(
            err.to_string().contains("overflows"),
            "range end arithmetic must not wrap: {err}"
        );
    }

    #[test]
    fn range_header_formats_inclusive_end() {
        assert_eq!(range_header(72, 4).unwrap(), "bytes=72-75");
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
        assert!(
            client.head_object(key).await.expect("HEAD"),
            "object should exist"
        );

        let full = client.get_object(key).await.expect("GET");
        assert_eq!(&full[..], &body[..], "full GET bytes mismatch");

        let (start, len) = (1000u64, 256u64);
        let ranged = client
            .get_object_range(key, start, len)
            .await
            .expect("GET range");
        assert_eq!(
            &ranged[..],
            &body[start as usize..(start + len) as usize],
            "ranged GET bytes mismatch"
        );

        let keys = client.list_objects("kotoba/cars/").await.expect("LIST");
        assert!(keys.iter().any(|k| k == key), "LIST should contain the key");
        println!(
            "b2_live_roundtrip OK: bucket={} key={}",
            client.bucket(),
            key
        );
    }
}
