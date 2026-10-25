//! cc-phase3: Common Crawl WAT → Parquet (Shannon-optimal single path)
//!
//! Parquet output:
//!   {output}/batch_{id:06}_pages.parquet   → vertex_page schema (per-page DID)
//!   {output}/batch_{id:06}_links.parquet   → edge_links_to schema
//!   {output}/batch_{id:06}_dlinks.parquet  → edge_links_to_domain schema
//!
//! Per-page DID (W3C did:web, path-isomorphic):
//!   URL  https://example.com/foo/bar
//!   DID  did:web:site.etzhayyim.com:example-com:foo:bar
//!   rkey example-com:foo:bar (= vertex_id)
//!
//! Features:
//! - rayon parallel WAT file processing
//! - Per-rkey dedup (URL path slug keyed)
//! - Authority domain filter (103 domains)
//! - Topic classification (14 heuristics)
//! - ZSTD-compressed Parquet output

use std::collections::{HashMap, HashSet};
use std::fs::{self, File};
use std::io::{BufRead, BufReader, BufWriter, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use ahash::AHashMap;
use arrow::array::{Int64Array, StringArray};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use clap::Parser;
// crossbeam-channel reserved for future bounded writer
use flate2::read::MultiGzDecoder;
use parquet::arrow::ArrowWriter;
use parquet::basic::Compression;
use parquet::file::properties::WriterProperties;
use rayon::prelude::*;
use sha2::{Digest, Sha256};

/// cc-phase3: WAT → DID Sql graph generator (Rust)
#[derive(Parser)]
#[command(name = "cc-phase3")]
struct Args {
    /// Source directory containing *.warc.wat.gz files
    #[arg(long, default_value = "/Volumes/251220/CC/2603/wat-full")]
    source: PathBuf,

    /// Output directory for batch_*.sql files
    #[arg(long, default_value = "/Volumes/251220/CC/2603/graph-rs")]
    output: PathBuf,

    /// Pages per Sql batch file
    #[arg(long, default_value_t = 10_000)]
    batch_size: usize,

    /// Number of parallel WAT file workers
    #[arg(long, default_value_t = 8)]
    workers: usize,

    /// Authority domain filter file (one domain per line)
    #[arg(long)]
    domains_file: Option<PathBuf>,

    /// Skip resume, start fresh
    #[arg(long)]
    no_resume: bool,

    /// Crawl ID tag
    #[arg(long, default_value = "CC-MAIN-2026-12")]
    crawl_id: String,
}

// ── Topic classification (14 heuristics + Wikipedia/OSM/Wikidata) ──

/// Classify domain+title into topic slug via TLD + keyword heuristics.
fn classify_topic(domain: &str, title: &str) -> &'static str {
    let dl = domain.to_ascii_lowercase();
    let tl = title.to_ascii_lowercase();

    // Wikipedia/Wikimedia → reference
    if dl.contains("wikipedia.org")
        || dl.contains("wikimedia.org")
        || dl.contains("wikidata.org")
        || dl.contains("wiktionary.org")
    {
        return "reference";
    }
    // OpenStreetMap → infrastructure
    if dl.contains("openstreetmap.org") {
        return "infrastructure";
    }

    static RULES: &[(&str, &[&str], &[&str])] = &[
        (
            "government",
            &[".gov", ".go.jp", ".gc.ca", ".gov.uk", ".gov.au", ".europa.eu"],
            &["government", "ministry"],
        ),
        ("legal", &[".courts"], &["court", "law", "legal"]),
        (
            "academic",
            &[".edu", ".ac.jp", ".ac.uk"],
            &["university", "research", "journal"],
        ),
        (
            "science",
            &[],
            &["science", "biology", "physics", "chemistry", "genome", "ncbi", "pubmed"],
        ),
        (
            "technology",
            &[".io", ".dev"],
            &["github", "stackoverflow", "developer", "api", "sdk"],
        ),
        (
            "news_media",
            &[],
            &["news", "times", "post", "herald"],
        ),
        (
            "health",
            &[],
            &["health", "medical", "hospital", "pharma", "who.int"],
        ),
        (
            "commerce",
            &[".shop", ".store"],
            &["shop", "buy", "price", "amazon", "ebay"],
        ),
        (
            "finance",
            &[".bank"],
            &["bank", "finance", "invest", "stock", "insurance"],
        ),
        (
            "security",
            &[],
            &["security", "cve", "malware", "threat", "vulnerability", "cyber"],
        ),
        (
            "culture",
            &[".museum"],
            &["museum", "art", "culture", "heritage"],
        ),
        (
            "education",
            &[],
            &["learn", "course", "tutorial", "education"],
        ),
        (
            "infrastructure",
            &[],
            &["transport", "railway", "energy", "telecom"],
        ),
        ("jp_classics", &[".aozora.gr.jp"], &[]),
    ];

    for &(slug, tlds, keywords) in RULES {
        for &tld in tlds {
            if dl.ends_with(tld) || dl.contains(tld) {
                return slug;
            }
        }
        for &kw in keywords {
            if dl.contains(kw) || tl.contains(kw) {
                return slug;
            }
        }
    }
    ""
}

// ── WAT record parsing ──

/// Parsed page metadata from a WAT JSON envelope.
#[derive(Debug)]
struct PageRecord {
    url: String,
    domain: String,
    title: String,
    description: String,
    language: String,
    content_type: String,
    status_code: String,
    ip_address: String,
    content_hash: String,
    og_image: String,
    robots: String,
    crawled_at: String,
    outlinks: Vec<OutLink>,
    outlink_count: usize,
}

/// Outgoing link with anchor text.
#[derive(Debug)]
struct OutLink {
    url: String,
    anchor_text: String,
}

/// Extract hostname from URL.
fn extract_domain(url: &str) -> Option<String> {
    // Fast path: find "://" then next "/" or end
    let after_scheme = url.find("://").map(|i| i + 3)?;
    let rest = &url[after_scheme..];
    let host_end = rest.find('/').unwrap_or(rest.len());
    let host_port = &rest[..host_end];
    // Strip port
    let host = if let Some(colon) = host_port.rfind(':') {
        // Check it's not IPv6
        if host_port.contains('[') {
            host_port
        } else {
            &host_port[..colon]
        }
    } else {
        host_port
    };
    if host.is_empty() {
        return None;
    }
    Some(host.to_ascii_lowercase())
}

/// Parse WAT JSON envelope → PageRecord.
fn parse_wat_record(content: &[u8]) -> Option<PageRecord> {
    let text = std::str::from_utf8(content)
        .ok()
        .or_else(|| Some(std::str::from_utf8(&content[..content.len().min(1_000_000)]).unwrap_or("")))?;

    let json_start = text.find('{')?;
    let data: serde_json::Value = serde_json::from_str(&text[json_start..]).ok()?;

    let envelope = data.get("Envelope")?;
    let target_uri = envelope
        .pointer("/WARC-Header-Metadata/WARC-Target-URI")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    if target_uri.is_empty() || !target_uri.starts_with("http") {
        return None;
    }

    let domain = extract_domain(target_uri)?;

    let payload = envelope.pointer("/Payload-Metadata/HTTP-Response-Metadata");
    let html_meta = payload.and_then(|p| p.get("HTML-Metadata"));
    let headers = payload
        .and_then(|p| p.get("Headers"))
        .and_then(|h| h.as_object());

    let title = html_meta
        .and_then(|h| h.pointer("/Head/Title"))
        .and_then(|v| v.as_str())
        .unwrap_or("");

    // WARC headers
    let warc_header = envelope.get("WARC-Header-Metadata");
    let ip_address = warc_header
        .and_then(|h| h.get("WARC-IP-Address"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let content_hash = warc_header
        .and_then(|h| h.get("WARC-Payload-Digest"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let crawled_at = warc_header
        .and_then(|h| h.get("WARC-Date"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    // OG description + language + og:image + robots from metas
    let mut og_desc = String::new();
    let mut language = String::new();
    let mut og_image = String::new();
    let mut robots = String::new();
    if let Some(metas) = html_meta.and_then(|h| h.pointer("/Head/Metas")).and_then(|v| v.as_array())
    {
        for m in metas {
            if let Some(obj) = m.as_object() {
                let prop = obj.get("property").and_then(|v| v.as_str()).unwrap_or("");
                let name = obj
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_ascii_lowercase();
                let content_val = obj.get("content").and_then(|v| v.as_str()).unwrap_or("");

                if prop == "og:description" && og_desc.is_empty() {
                    og_desc = content_val.chars().take(500).collect();
                }
                if prop == "og:image" && og_image.is_empty() {
                    og_image = content_val.chars().take(2048).collect();
                }
                if matches!(name.as_str(), "language" | "lang" | "content-language")
                    && language.is_empty()
                {
                    language = content_val.chars().take(10).collect();
                }
                if name == "robots" && robots.is_empty() {
                    robots = content_val.chars().take(256).collect();
                }
            }
        }
    }
    if language.is_empty() {
        if let Some(hdrs) = headers {
            language = hdrs
                .get("Content-Language")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .chars()
                .take(10)
                .collect();
        }
    }

    let content_type = headers
        .and_then(|h| h.get("Content-Type"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .chars()
        .take(100)
        .collect::<String>();

    let status_code = headers
        .and_then(|h| h.get("HTTP-Status-Code"))
        .map(|v| match v {
            serde_json::Value::Number(n) => n.to_string(),
            serde_json::Value::String(s) => s.clone(),
            _ => String::new(),
        })
        .unwrap_or_default();

    // Outlinks with anchor text (max 500)
    let mut outlinks = Vec::new();
    if let Some(links) = html_meta.and_then(|h| h.get("Links")).and_then(|v| v.as_array()) {
        for lnk in links.iter().take(500) {
            if let Some(href) = lnk.get("url").and_then(|v| v.as_str()) {
                if href.starts_with("http") {
                    let anchor = lnk.get("text").and_then(|v| v.as_str()).unwrap_or("");
                    outlinks.push(OutLink {
                        url: href.to_string(),
                        anchor_text: anchor.chars().take(256).collect(),
                    });
                }
            }
        }
    }
    let outlink_count = outlinks.len();

    Some(PageRecord {
        url: target_uri.chars().take(2000).collect(),
        domain,
        title: title.chars().take(500).collect(),
        description: og_desc,
        language,
        content_type,
        status_code,
        ip_address,
        content_hash,
        og_image,
        robots,
        crawled_at,
        outlinks,
        outlink_count,
    })
}

// ── Page DID derivation (URL path-isomorphic) ──

/// Domain → slug (dots and underscores to hyphens).
fn domain_to_slug(domain: &str) -> String {
    domain.replace('.', "-").replace('_', "-")
}

/// Percent-encode a single path segment for did:web safety.
/// Preserves [A-Za-z0-9._-]; everything else → `%XX`.
fn encode_segment(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'.' | b'_' => out.push(b as char),
            _ => out.push_str(&format!("%{:02X}", b)),
        }
    }
    out
}

/// SHA-256 truncated hex (16 chars) — fallback when DID exceeds length cap.
fn url_hash(url: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(url.as_bytes());
    hex::encode(&hasher.finalize()[..8])
}

/// Maximum total page DID length before SHA-256 fallback kicks in.
const PAGE_DID_MAX_LEN: usize = 2048;
const DID_PREFIX: &str = "did:web:site.etzhayyim.com:";

/// Build (rkey, page_did) from URL using directory path → DID path isomorphism.
///
/// `https://example.com/foo/bar/page.html` →
///   rkey = `example-com:foo:bar:page.html`
///   did  = `did:web:site.etzhayyim.com:example-com:foo:bar:page.html`
///
/// Root path (`/`) → `{slug}:_root`. Query / fragment stripped. Long URLs fall
/// back to `{slug}:_h:{16hex}` to stay under PAGE_DID_MAX_LEN.
fn page_did_from_url(url: &str) -> Option<(String, String)> {
    let domain = extract_domain(url)?;
    let domain_slug = domain_to_slug(&domain);

    let after_scheme = url.find("://").map(|i| i + 3)?;
    let rest = &url[after_scheme..];
    let path_start = rest.find('/').unwrap_or(rest.len());
    let raw_path = &rest[path_start..];
    let path_end = raw_path
        .find(|c| c == '?' || c == '#')
        .unwrap_or(raw_path.len());
    let path = &raw_path[..path_end];

    let segments: Vec<String> = path
        .split('/')
        .filter(|s| !s.is_empty())
        .map(encode_segment)
        .collect();

    let rkey = if segments.is_empty() {
        format!("{domain_slug}:_root")
    } else {
        format!("{domain_slug}:{}", segments.join(":"))
    };

    let mut did = format!("{DID_PREFIX}{rkey}");
    if did.len() > PAGE_DID_MAX_LEN {
        let fallback_rkey = format!("{domain_slug}:_h:{}", url_hash(url));
        did = format!("{DID_PREFIX}{fallback_rkey}");
        return Some((fallback_rkey, did));
    }
    Some((rkey, did))
}

/// Domain DID — `did:web:site.etzhayyim.com:{domain-slug}`.
fn domain_did_from_slug(domain_slug: &str) -> String {
    format!("{DID_PREFIX}{domain_slug}")
}

// ── Parquet generation (Shannon-optimal: WAT → Parquet direct) ──

fn parquet_props() -> WriterProperties {
    WriterProperties::builder()
        .set_compression(Compression::ZSTD(Default::default()))
        .build()
}

/// Write pages batch as vertex_page Parquet.
///
/// Each page row carries its own DID actor (`owner_did`) derived from the URL
/// directory path: `did:web:site.etzhayyim.com:{domain-slug}:{path-segments}`.
/// `rkey` / `vertex_id` use the same path slug (domain-slug:seg1:seg2…).
fn write_pages_parquet(
    pages: &[PageRecord],
    crawl_id: &str,
    path: &Path,
) -> usize {
    let mut seen: HashSet<String> = HashSet::new();
    let mut rkeys = Vec::new();
    let mut urls = Vec::new();
    let mut domains = Vec::new();
    let mut titles = Vec::new();
    let mut descriptions = Vec::new();
    let mut languages = Vec::new();
    let mut content_types = Vec::new();
    let mut outlink_counts = Vec::new();
    let mut crawls = Vec::new();
    let mut owner_dids = Vec::new();

    let mut status_codes = Vec::new();
    let mut ip_addresses = Vec::new();
    let mut content_hashes = Vec::new();
    let mut og_images = Vec::new();
    let mut robots_vals = Vec::new();
    let mut crawled_ats = Vec::new();

    for page in pages {
        if page.url.is_empty() || page.domain.is_empty() {
            continue;
        }
        let Some((rkey, page_did)) = page_did_from_url(&page.url) else {
            continue;
        };
        if !seen.insert(rkey.clone()) {
            continue;
        }
        rkeys.push(rkey);
        owner_dids.push(Some(page_did));
        urls.push(page.url.chars().take(2048).collect::<String>());
        domains.push(page.domain.clone());
        titles.push(if page.title.is_empty() { None } else { Some(page.title.chars().take(1024).collect::<String>()) });
        descriptions.push(if page.description.is_empty() { None } else { Some(page.description.clone()) });
        languages.push(if page.language.is_empty() { None } else { Some(page.language.clone()) });
        content_types.push(if page.content_type.is_empty() { None } else { Some(page.content_type.clone()) });
        status_codes.push(if page.status_code.is_empty() { None } else { Some(page.status_code.clone()) });
        outlink_counts.push(page.outlink_count as i64);
        crawls.push(crawl_id.to_string());
        ip_addresses.push(if page.ip_address.is_empty() { None } else { Some(page.ip_address.clone()) });
        og_images.push(if page.og_image.is_empty() { None } else { Some(page.og_image.clone()) });
        robots_vals.push(if page.robots.is_empty() { None } else { Some(page.robots.clone()) });
        content_hashes.push(if page.content_hash.is_empty() { None } else { Some(page.content_hash.clone()) });
        crawled_ats.push(if page.crawled_at.is_empty() { None } else { Some(page.crawled_at.clone()) });
    }

    let n = rkeys.len();
    if n == 0 { return 0; }

    let nulls: Vec<Option<String>> = vec![None; n];
    let zeros: Vec<i64> = vec![0; n];
    let null_i64: Vec<Option<i64>> = vec![None; n];

    // Column order matches vertex_page CREATE TABLE (rkey first, then vertex_id at end)
    let schema = Arc::new(Schema::new(vec![
        Field::new("rkey", DataType::Utf8, true),
        Field::new("url", DataType::Utf8, true),
        Field::new("domain", DataType::Utf8, true),
        Field::new("title", DataType::Utf8, true),
        Field::new("description", DataType::Utf8, true),
        Field::new("language", DataType::Utf8, true),
        Field::new("content_type", DataType::Utf8, true),
        Field::new("status_code", DataType::Utf8, true),
        Field::new("outlink_count", DataType::Int64, true),
        Field::new("crawl", DataType::Utf8, true),
        Field::new("ip_address", DataType::Utf8, true),
        Field::new("og_image", DataType::Utf8, true),
        Field::new("robots", DataType::Utf8, true),
        Field::new("content_hash", DataType::Utf8, true),
        Field::new("previous_content_hash", DataType::Utf8, true),
        Field::new("version", DataType::Int64, true),
        Field::new("crawled_at", DataType::Utf8, true),
        Field::new("vertex_id", DataType::Utf8, false),
        Field::new("_seq", DataType::Int64, true),
        Field::new("created_date", DataType::Date32, true),
        Field::new("sensitivity_ord", DataType::Int64, true),
        Field::new("owner_did", DataType::Utf8, true),
    ]));

    let batch = RecordBatch::try_new(schema.clone(), vec![
        Arc::new(StringArray::from(rkeys.clone())),
        Arc::new(StringArray::from(urls)),
        Arc::new(StringArray::from(domains)),
        Arc::new(StringArray::from(titles)),
        Arc::new(StringArray::from(descriptions)),
        Arc::new(StringArray::from(languages)),
        Arc::new(StringArray::from(content_types)),
        Arc::new(StringArray::from(status_codes)),
        Arc::new(Int64Array::from(outlink_counts)),
        Arc::new(StringArray::from(crawls)),
        Arc::new(StringArray::from(ip_addresses)),
        Arc::new(StringArray::from(og_images)),
        Arc::new(StringArray::from(robots_vals)),
        Arc::new(StringArray::from(content_hashes)),
        Arc::new(StringArray::from(nulls.clone())),       // previous_content_hash
        Arc::new(Int64Array::from(null_i64)),             // version
        Arc::new(StringArray::from(crawled_ats)),
        Arc::new(StringArray::from(rkeys)),               // vertex_id = rkey
        Arc::new(Int64Array::from(zeros.clone())),        // _seq
        Arc::new(arrow::array::Date32Array::from(vec![None::<i32>; n])), // created_date
        Arc::new(Int64Array::from(zeros)),                // sensitivity_ord
        Arc::new(StringArray::from(owner_dids)),          // owner_did = per-page DID
    ]).expect("RecordBatch creation failed");

    let file = File::create(path).expect("Cannot create parquet file");
    let mut writer = ArrowWriter::try_new(file, schema, Some(parquet_props())).expect("ArrowWriter creation failed");
    writer.write(&batch).expect("Parquet write failed");
    writer.close().expect("Parquet close failed");
    n
}

/// Write links batch as edge_links_to Parquet.
///
/// src_vid / dst_vid are URL-path slugs (matches vertex_page.rkey).
/// owner_did = src page DID actor.
fn write_links_parquet(
    pages: &[PageRecord],
    path: &Path,
) -> usize {
    let mut seen_rkeys: HashSet<String> = HashSet::new();
    let mut labels = Vec::new();
    let mut anchor_texts = Vec::new();
    let mut edge_ids = Vec::new();
    let mut src_vids = Vec::new();
    let mut dst_vids = Vec::new();
    let mut owner_dids = Vec::new();

    for page in pages {
        if page.url.is_empty() || page.domain.is_empty() { continue; }
        let Some((src_rkey, src_did)) = page_did_from_url(&page.url) else { continue; };
        if !seen_rkeys.insert(src_rkey.clone()) { continue; }

        for outlink in page.outlinks.iter().take(50) {
            if let Some(out_domain) = extract_domain(&outlink.url) {
                if out_domain != page.domain {
                    let Some((dst_rkey, _)) = page_did_from_url(&outlink.url) else { continue; };
                    labels.push("LinksTo".to_string());
                    anchor_texts.push(if outlink.anchor_text.is_empty() { None } else { Some(outlink.anchor_text.clone()) });
                    edge_ids.push(format!("{src_rkey}->links->{dst_rkey}"));
                    src_vids.push(src_rkey.clone());
                    dst_vids.push(dst_rkey);
                    owner_dids.push(Some(src_did.clone()));
                }
            }
        }
    }

    let n = labels.len();
    if n == 0 { return 0; }

    let zeros: Vec<i64> = vec![0; n];

    let schema = Arc::new(Schema::new(vec![
        Field::new("label", DataType::Utf8, true),
        Field::new("anchor_text", DataType::Utf8, true),
        Field::new("edge_id", DataType::Utf8, false),
        Field::new("src_vid", DataType::Utf8, true),
        Field::new("dst_vid", DataType::Utf8, true),
        Field::new("_seq", DataType::Int64, true),
        Field::new("created_date", DataType::Date32, true),
        Field::new("sensitivity_ord", DataType::Int64, true),
        Field::new("owner_did", DataType::Utf8, true),
    ]));

    let batch = RecordBatch::try_new(schema.clone(), vec![
        Arc::new(StringArray::from(labels)),
        Arc::new(StringArray::from(anchor_texts)),
        Arc::new(StringArray::from(edge_ids)),
        Arc::new(StringArray::from(src_vids)),
        Arc::new(StringArray::from(dst_vids)),
        Arc::new(Int64Array::from(zeros.clone())),
        Arc::new(arrow::array::Date32Array::from(vec![None::<i32>; n])), // created_date
        Arc::new(Int64Array::from(zeros)),
        Arc::new(StringArray::from(owner_dids)),                         // owner_did = src page DID
    ]).expect("RecordBatch creation failed");

    let file = File::create(path).expect("Cannot create parquet file");
    let mut writer = ArrowWriter::try_new(file, schema, Some(parquet_props())).expect("ArrowWriter creation failed");
    writer.write(&batch).expect("Parquet write failed");
    writer.close().expect("Parquet close failed");
    n
}

/// Write domain-level link aggregation as edge_links_to_domain Parquet.
///
/// owner_did = src domain DID (`did:web:site.etzhayyim.com:{src-slug}`).
fn write_dlinks_parquet(
    pages: &[PageRecord],
    path: &Path,
) -> usize {
    let mut seen_rkeys: HashSet<String> = HashSet::new();
    let mut domain_links: HashMap<(String, String), i64> = HashMap::new();

    for page in pages {
        if page.url.is_empty() || page.domain.is_empty() { continue; }
        let Some((rkey, _)) = page_did_from_url(&page.url) else { continue; };
        if !seen_rkeys.insert(rkey) { continue; }

        for outlink in page.outlinks.iter().take(50) {
            if let Some(out_domain) = extract_domain(&outlink.url) {
                if out_domain != page.domain {
                    *domain_links.entry((page.domain.clone(), out_domain)).or_insert(0) += 1;
                }
            }
        }
    }

    let n = domain_links.len();
    if n == 0 { return 0; }

    let mut labels = Vec::with_capacity(n);
    let mut counts = Vec::with_capacity(n);
    let mut edge_ids = Vec::with_capacity(n);
    let mut src_vids = Vec::with_capacity(n);
    let mut dst_vids = Vec::with_capacity(n);
    let mut owner_dids = Vec::with_capacity(n);

    for ((src, dst), count) in &domain_links {
        labels.push("LinksToDomain".to_string());
        counts.push(*count);
        edge_ids.push(format!("{src}->dlinks->{dst}"));
        src_vids.push(src.clone());
        dst_vids.push(dst.clone());
        owner_dids.push(Some(domain_did_from_slug(&domain_to_slug(src))));
    }

    let zeros: Vec<i64> = vec![0; n];

    let schema = Arc::new(Schema::new(vec![
        Field::new("label", DataType::Utf8, true),
        Field::new("count", DataType::Int64, true),
        Field::new("edge_id", DataType::Utf8, false),
        Field::new("src_vid", DataType::Utf8, true),
        Field::new("dst_vid", DataType::Utf8, true),
        Field::new("_seq", DataType::Int64, true),
        Field::new("created_date", DataType::Date32, true),
        Field::new("sensitivity_ord", DataType::Int64, true),
        Field::new("owner_did", DataType::Utf8, true),
    ]));

    let batch = RecordBatch::try_new(schema.clone(), vec![
        Arc::new(StringArray::from(labels)),
        Arc::new(Int64Array::from(counts)),
        Arc::new(StringArray::from(edge_ids)),
        Arc::new(StringArray::from(src_vids)),
        Arc::new(StringArray::from(dst_vids)),
        Arc::new(Int64Array::from(zeros.clone())),
        Arc::new(arrow::array::Date32Array::from(vec![None::<i32>; n])), // created_date
        Arc::new(Int64Array::from(zeros)),
        Arc::new(StringArray::from(owner_dids)),                         // owner_did = src domain DID
    ]).expect("RecordBatch creation failed");

    let file = File::create(path).expect("Cannot create parquet file");
    let mut writer = ArrowWriter::try_new(file, schema, Some(parquet_props())).expect("ArrowWriter creation failed");
    writer.write(&batch).expect("Parquet write failed");
    writer.close().expect("Parquet close failed");
    n
}

// ── WARC/WAT streaming parser ──

/// Parse a single gzipped WAT file, returning parsed page records.
///
/// WARC format: header block (lines ending with \r\n\r\n) + content block.
/// WAT records have `WARC-Type: metadata` and JSON content.
fn parse_wat_file(path: &Path, authority_domains: Option<&HashSet<String>>) -> Vec<PageRecord> {
    let file = match File::open(path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("ERROR: Cannot open {}: {e}", path.display());
            return Vec::new();
        }
    };

    let gz = MultiGzDecoder::new(BufReader::with_capacity(256 * 1024, file));
    let mut reader = BufReader::with_capacity(256 * 1024, gz);
    let mut pages = Vec::new();

    // WARC parser with Content-Length skip for non-metadata records.
    // WAT files contain warcinfo, request, response, and metadata records.
    // Only metadata records contain the JSON we need (~10% of bytes).
    // Non-metadata records are skipped via Content-Length → read_exact into /dev/null.
    let mut line_buf = String::new();
    let mut skip_buf = vec![0u8; 64 * 1024]; // reusable skip buffer

    loop {
        // ── Read WARC record header ──
        let mut warc_type = String::new();
        let mut content_length: usize = 0;
        let mut found_warc = false;

        loop {
            line_buf.clear();
            match reader.read_line(&mut line_buf) {
                Ok(0) => return pages, // EOF
                Err(_) => return pages,
                Ok(_) => {}
            }

            let trimmed = line_buf.trim();

            if trimmed.starts_with("WARC/1.0") {
                found_warc = true;
                warc_type.clear();
                content_length = 0;
                continue;
            }

            if !found_warc {
                continue; // skip lines before first WARC record
            }

            if trimmed.is_empty() {
                break; // end of headers → content follows
            }

            if let Some(val) = trimmed.strip_prefix("WARC-Type: ") {
                warc_type = val.trim().to_string();
            }
            if let Some(val) = trimmed.strip_prefix("Content-Length: ") {
                content_length = val.trim().parse().unwrap_or(0);
            }
        }

        if !found_warc {
            break;
        }

        // ── Process or skip content ──
        if warc_type == "metadata" && content_length > 0 {
            // Read metadata content for JSON parsing
            let mut content_buf = vec![0u8; content_length];
            if reader.read_exact(&mut content_buf).is_ok() {
                if let Some(page) = parse_wat_record(&content_buf) {
                    let dominated = if let Some(auth) = authority_domains {
                        auth.iter().any(|d| page.domain.ends_with(d.as_str()))
                    } else {
                        true
                    };
                    if dominated {
                        pages.push(page);
                    }
                }
            }
        } else if content_length > 0 {
            // Skip non-metadata content via read_exact (no line-by-line parsing)
            let mut remaining = content_length;
            while remaining > 0 {
                let to_read = remaining.min(skip_buf.len());
                match reader.read_exact(&mut skip_buf[..to_read]) {
                    Ok(_) => remaining -= to_read,
                    Err(_) => break,
                }
            }
        }

        // Skip trailing blank lines after content (WARC records end with \r\n\r\n)
        loop {
            line_buf.clear();
            match reader.read_line(&mut line_buf) {
                Ok(0) => break,
                Err(_) => break,
                Ok(_) => {
                    if !line_buf.trim().is_empty() {
                        // Non-blank line = start of next WARC record, but we already consumed it.
                        // This shouldn't happen if Content-Length is accurate.
                        break;
                    }
                    // Blank line — continue skipping
                }
            }
        }
    }

    pages
}

// ── State / Checkpoint ──

#[derive(serde::Serialize, serde::Deserialize, Default)]
struct State {
    files_done: Vec<String>,
    batch_id: u64,
    total_pages: u64,
    total_domains: u64,
}

fn load_state(path: &Path) -> State {
    if path.exists() {
        let data = fs::read_to_string(path).unwrap_or_default();
        serde_json::from_str(&data).unwrap_or_default()
    } else {
        State::default()
    }
}

fn save_state(path: &Path, state: &State) {
    if let Ok(json) = serde_json::to_string(state) {
        let _ = fs::write(path, json);
    }
}

// ── Main ──

fn main() {
    let args = Args::parse();

    // Setup
    fs::create_dir_all(&args.output).expect("Cannot create output directory");
    let state_file = args.output.join(".phase3_rs_state.json");
    let mut state = if !args.no_resume {
        load_state(&state_file)
    } else {
        State::default()
    };
    let files_done: HashSet<String> = state.files_done.iter().cloned().collect();

    // Load authority domains if specified
    let authority_domains: Option<HashSet<String>> = args.domains_file.as_ref().map(|path| {
        let content = fs::read_to_string(path).expect("Cannot read domains file");
        content
            .lines()
            .map(|l| l.trim().to_string())
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .collect()
    });

    // Discover WAT files (parallel, uses rayon default pool)
    let scan_start = std::time::Instant::now();
    eprintln!("Scanning WAT files under {}…", args.source.display());
    let mut wat_files: Vec<PathBuf> = Vec::new();
    collect_wat_files(&args.source, &mut wat_files);
    wat_files.sort();
    eprintln!(
        "Scanned {} WAT files in {:.1}s",
        wat_files.len(),
        scan_start.elapsed().as_secs_f64()
    );
    let remaining: Vec<PathBuf> = wat_files
        .into_iter()
        .filter(|f| {
            f.file_name()
                .map(|n| !files_done.contains(n.to_str().unwrap_or("")))
                .unwrap_or(false)
        })
        .collect();

    let total_files = remaining.len();
    eprintln!(
        "cc-phase3 (Rust): {} WAT files remaining, resume batch_id={}",
        total_files, state.batch_id
    );

    // Shutdown signal
    let shutdown = Arc::new(AtomicBool::new(false));
    let shutdown_clone = shutdown.clone();
    ctrlc_handler(shutdown_clone);

    // Counters
    let total_pages = Arc::new(AtomicU64::new(state.total_pages));
    let batch_id = Arc::new(AtomicU64::new(state.batch_id));

    // Domain topic cache (shared, append-only)
    let domain_topics: Arc<Mutex<AHashMap<String, &'static str>>> =
        Arc::new(Mutex::new(AHashMap::new()));

    // Domain stats (for final summary)
    let domain_stats: Arc<Mutex<HashMap<String, u64>>> = Arc::new(Mutex::new(HashMap::new()));
    let domain_titles: Arc<Mutex<HashMap<String, Vec<String>>>> =
        Arc::new(Mutex::new(HashMap::new()));

    // Configure rayon thread pool
    rayon::ThreadPoolBuilder::new()
        .num_threads(args.workers)
        .build_global()
        .ok();

    // Process WAT files in parallel, collect pages, write batches
    let output_dir = args.output.clone();
    let crawl_id = args.crawl_id.clone();

    // ── Chunked parallel pipeline ──
    // Process WAT files in chunks of workers*2 to bound memory.
    // Within each chunk: parse + Parquet write fully parallel (no sequential bottleneck).
    let done_count = Arc::new(AtomicU64::new(0));
    let chunk_size = args.workers * 2;

    for chunk in remaining.chunks(chunk_size) {
        if shutdown.load(Ordering::Relaxed) {
            eprintln!("Shutdown requested...");
            break;
        }

        // Fully parallel within chunk: parse WAT + write Parquet + update stats
        chunk.par_iter().for_each(|path| {
        if shutdown.load(Ordering::Relaxed) {
            return;
        }

        let fname = path.file_name().unwrap_or_default().to_str().unwrap_or("").to_string();
        let pages = parse_wat_file(path, authority_domains.as_ref());
        let page_count = pages.len() as u64;
        total_pages.fetch_add(page_count, Ordering::Relaxed);

        // Update domain stats (short lock)
        {
            let mut stats = domain_stats.lock().unwrap();
            let mut titles = domain_titles.lock().unwrap();
            let mut topics = domain_topics.lock().unwrap();
            for page in &pages {
                *stats.entry(page.domain.clone()).or_insert(0) += 1;
                if !topics.contains_key(page.domain.as_str()) {
                    let topic = classify_topic(&page.domain, &page.title);
                    if !topic.is_empty() {
                        topics.insert(page.domain.clone(), topic);
                    }
                }
                let title_list = titles.entry(page.domain.clone()).or_default();
                if title_list.len() < 5 && !page.title.is_empty() {
                    title_list.push(page.title.chars().take(100).collect());
                }
            }
        }

        if !pages.is_empty() {
            let bid = batch_id.fetch_add(1, Ordering::Relaxed);
            let np = write_pages_parquet(&pages, &crawl_id, &output_dir.join(format!("batch_{bid:06}_pages.parquet")));
            let nl = write_links_parquet(&pages, &output_dir.join(format!("batch_{bid:06}_links.parquet")));
            let nd = write_dlinks_parquet(&pages, &output_dir.join(format!("batch_{bid:06}_dlinks.parquet")));
            let dc = done_count.fetch_add(1, Ordering::Relaxed) + 1;
            if dc % 50 == 0 {
                let tp = total_pages.load(Ordering::Relaxed);
                let ds = domain_stats.lock().unwrap().len();
                eprintln!("  [{dc}/{total_files}] pages={tp}, domains={ds}, batch={bid}: {np} pages, {nl} links, {nd} dlinks");
            }
        }
        let _ = fname; // tracked via done_count; state.files_done updated after chunk
        });

        // Record processed filenames
        for path in chunk {
            if let Some(fname) = path.file_name().and_then(|n| n.to_str()) {
                state.files_done.push(fname.to_string());
            }
        }

        // Checkpoint after each chunk
        let dc = done_count.load(Ordering::Relaxed);
        state.batch_id = batch_id.load(Ordering::Relaxed);
        state.total_pages = total_pages.load(Ordering::Relaxed);
        state.total_domains = domain_stats.lock().unwrap().len() as u64;
        save_state(&state_file, &state);
        eprintln!(
            "Checkpoint: {dc}/{total_files} files, pages={}, domains={}, batches={}",
            state.total_pages, state.total_domains, state.batch_id,
        );
    }

    // Final state save
    state.batch_id = batch_id.load(Ordering::Relaxed);
    state.total_pages = total_pages.load(Ordering::Relaxed);
    state.total_domains = domain_stats.lock().unwrap().len() as u64;
    save_state(&state_file, &state);

    // Write domain JSONL for Phase 4
    write_domain_jsonl(&args.output, &domain_stats, &domain_titles, &domain_topics);

    // Write stats summary
    write_stats_summary(
        &args.output,
        &crawl_id,
        &state,
        &domain_stats,
        &domain_topics,
    );

    eprintln!(
        "Done: {} pages, {} domains, {} batches",
        state.total_pages, state.total_domains, state.batch_id
    );
}

/// Recursively collect *.warc.wat.gz files using `DirEntry::file_type()`
/// (avoids an extra `stat()` call per entry) + rayon for parallel subdir scan.
///
/// On slow external volumes (USB / network mounts) sequential `is_dir()`
/// + recursion can take hours for tens of thousands of files. This version
/// fans out subdir enumeration across the rayon pool so disk-queue depth is
/// utilized.
fn collect_wat_files(dir: &Path, out: &mut Vec<PathBuf>) {
    let (dirs, files) = scan_dir_shallow(dir);
    out.extend(files);

    if dirs.is_empty() {
        return;
    }

    // Parallel recursion over subdirs. Each worker returns its own Vec,
    // then we merge.
    let nested: Vec<Vec<PathBuf>> = dirs
        .par_iter()
        .map(|d| {
            let mut acc = Vec::new();
            collect_wat_files(d, &mut acc);
            acc
        })
        .collect();
    for v in nested {
        out.extend(v);
    }
}

/// Read one directory, splitting entries into (subdirs, matching files).
/// Uses `DirEntry::file_type()` which is cheaper than `Path::is_dir()` on
/// most platforms (no extra stat on Linux; avoids re-open on macOS).
fn scan_dir_shallow(dir: &Path) -> (Vec<PathBuf>, Vec<PathBuf>) {
    let mut dirs = Vec::new();
    let mut files = Vec::new();
    let Ok(entries) = fs::read_dir(dir) else {
        return (dirs, files);
    };
    for entry in entries.flatten() {
        let ft = match entry.file_type() {
            Ok(t) => t,
            Err(_) => continue,
        };
        if ft.is_dir() {
            dirs.push(entry.path());
        } else if ft.is_file() {
            let path = entry.path();
            if path
                .file_name()
                .and_then(|n| n.to_str())
                .map(|n| n.ends_with(".warc.wat.gz"))
                .unwrap_or(false)
            {
                files.push(path);
            }
        }
    }
    (dirs, files)
}

/// Write domains_for_classification.jsonl.gz.
fn write_domain_jsonl(
    output_dir: &Path,
    domain_stats: &Arc<Mutex<HashMap<String, u64>>>,
    domain_titles: &Arc<Mutex<HashMap<String, Vec<String>>>>,
    domain_topics: &Arc<Mutex<AHashMap<String, &'static str>>>,
) {
    let stats = domain_stats.lock().unwrap();
    let titles = domain_titles.lock().unwrap();
    let topics = domain_topics.lock().unwrap();

    let mut entries: Vec<(&String, &u64)> = stats.iter().collect();
    entries.sort_by(|a, b| b.1.cmp(a.1));

    let path = output_dir.join("domains_for_classification.jsonl.gz");
    let file = File::create(&path).expect("Cannot create domain JSONL");
    let gz = flate2::write::GzEncoder::new(BufWriter::new(file), flate2::Compression::default());
    let mut writer = BufWriter::new(gz);

    for (domain, &count) in &entries {
        if domain.is_empty() {
            continue;
        }
        let rec = serde_json::json!({
            "domain": domain,
            "pageCount": count,
            "sampleTitles": titles.get(*domain).cloned().unwrap_or_default(),
            "topic": topics.get(domain.as_str()).copied().unwrap_or(""),
        });
        let _ = writeln!(writer, "{}", rec);
    }
}

/// Write link_graph_stats.json.
fn write_stats_summary(
    output_dir: &Path,
    crawl_id: &str,
    state: &State,
    domain_stats: &Arc<Mutex<HashMap<String, u64>>>,
    domain_topics: &Arc<Mutex<AHashMap<String, &'static str>>>,
) {
    let stats = domain_stats.lock().unwrap();
    let topics = domain_topics.lock().unwrap();

    let mut entries: Vec<(&String, &u64)> = stats.iter().collect();
    entries.sort_by(|a, b| b.1.cmp(a.1));

    let top_domains: Vec<(&str, u64)> = entries
        .iter()
        .take(200)
        .map(|(d, &c)| (d.as_str(), c))
        .collect();

    let mut topic_dist: HashMap<&str, usize> = HashMap::new();
    for &topic in topics.values() {
        *topic_dist.entry(topic).or_insert(0) += 1;
    }
    let mut topic_entries: Vec<(&&str, &usize)> = topic_dist.iter().collect();
    topic_entries.sort_by(|a, b| b.1.cmp(a.1));

    let summary = serde_json::json!({
        "crawl": crawl_id,
        "generator": "cc-phase3 (Rust)",
        "totalPages": state.total_pages,
        "uniqueDomains": state.total_domains,
        "sqlBatches": state.batch_id,
        "topicDistribution": topic_entries.iter().map(|(t, c)| (t, c)).collect::<Vec<_>>(),
        "topDomains": top_domains,
    });

    let path = output_dir.join("link_graph_stats.json");
    let file = File::create(&path).expect("Cannot create stats JSON");
    serde_json::to_writer_pretty(BufWriter::new(file), &summary).ok();
}

/// Register Ctrl+C / SIGTERM handler.
fn ctrlc_handler(shutdown: Arc<AtomicBool>) {
    // Register signal handlers (set static flag on signal)
    unsafe {
        libc::signal(libc::SIGINT, handle_sig as *const () as libc::sighandler_t);
        libc::signal(libc::SIGTERM, handle_sig as *const () as libc::sighandler_t);
    }

    // Bridge the static flag to the Arc (poll in background thread)
    std::thread::spawn(move || {
        while !SHUTDOWN_FLAG.load(Ordering::Relaxed) {
            std::thread::sleep(std::time::Duration::from_millis(200));
        }
        shutdown.store(true, Ordering::Relaxed);
        eprintln!("Signal received, shutting down gracefully...");
    });
}

static SHUTDOWN_FLAG: AtomicBool = AtomicBool::new(false);

extern "C" fn handle_sig(_: libc::c_int) {
    SHUTDOWN_FLAG.store(true, Ordering::SeqCst);
}
