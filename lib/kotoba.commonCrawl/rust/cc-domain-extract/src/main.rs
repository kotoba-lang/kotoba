//! Extract all unique domains from Common Crawl Sql batch files.
//!
//! Scans `batch_*.sql` files in parallel (rayon), extracts
//! `MERGE (d:DomainDID {did: "...", domain: "...", slug: "..."})` lines,
//! aggregates page counts per domain, and outputs gzipped JSONL.
//!
//! ~200-500 files/s on SSD (vs Python ~11 files/s).

use ahash::AHashMap;
use clap::Parser;
use flate2::write::GzEncoder;
use flate2::Compression;
use rayon::prelude::*;
use serde::Serialize;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

#[derive(Parser)]
#[command(name = "cc-domain-extract", about = "Extract unique domains from CC Sql batches")]
struct Args {
    /// Graph directory containing batch_*.sql files
    #[arg(short, long, default_value = "/Volumes/251220/CC/2603/graph")]
    graph_dir: PathBuf,

    /// Output JSONL.gz path
    #[arg(short, long, default_value = "/tmp/cc-all-domains.jsonl.gz")]
    output: PathBuf,

    /// Number of rayon threads (0 = auto)
    #[arg(short, long, default_value_t = 0)]
    threads: usize,
}

#[derive(Debug, Clone, Serialize)]
struct DomainInfo {
    did: String,
    domain: String,
    slug: String,
    #[serde(rename = "pageCount")]
    page_count: u64,
}

/// Parse one line for DomainDID MERGE pattern.
/// Returns (did, domain, slug) if matched.
fn parse_domain_line(line: &str) -> Option<(&str, &str, &str)> {
    // Pattern: MERGE (d:DomainDID {did: "X"}) ON CREATE SET d.domain = "Y", d.slug = "Z"
    let marker = r#"MERGE (d:DomainDID {did: ""#;
    let pos = line.find(marker)?;
    let rest = &line[pos + marker.len()..];
    let did_end = rest.find('"')?;
    let did = &rest[..did_end];

    let dom_marker = r#"d.domain = ""#;
    let dom_pos = rest.find(dom_marker)? + dom_marker.len();
    let dom_rest = &rest[dom_pos..];
    let dom_end = dom_rest.find('"')?;
    let domain = &dom_rest[..dom_end];

    let slug_marker = r#"d.slug = ""#;
    let slug_pos = rest.find(slug_marker)? + slug_marker.len();
    let slug_rest = &rest[slug_pos..];
    let slug_end = slug_rest.find('"')?;
    let slug = &slug_rest[..slug_end];

    Some((did, domain, slug))
}

/// Extract domains from a single Sql file.
fn extract_from_file(path: &Path) -> AHashMap<String, DomainInfo> {
    let mut domains = AHashMap::new();
    let file = match fs::File::open(path) {
        Ok(f) => f,
        Err(_) => return domains,
    };
    let reader = BufReader::with_capacity(256 * 1024, file);

    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => continue,
        };
        if !line.contains("DomainDID") {
            continue;
        }
        if let Some((did, domain, slug)) = parse_domain_line(&line) {
            domains
                .entry(domain.to_string())
                .and_modify(|d: &mut DomainInfo| d.page_count += 1)
                .or_insert_with(|| DomainInfo {
                    did: did.to_string(),
                    domain: domain.to_string(),
                    slug: slug.to_string(),
                    page_count: 1,
                });
        }
    }
    domains
}

fn main() {
    let args = Args::parse();

    if args.threads > 0 {
        rayon::ThreadPoolBuilder::new()
            .num_threads(args.threads)
            .build_global()
            .unwrap();
    }

    let t0 = Instant::now();

    // Collect batch files
    let mut files: Vec<PathBuf> = fs::read_dir(&args.graph_dir)
        .expect("cannot read graph dir")
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| {
            p.file_name()
                .map(|n| n.to_string_lossy().starts_with("batch_") && n.to_string_lossy().ends_with(".sql"))
                .unwrap_or(false)
        })
        .collect();
    files.sort();

    let total_files = files.len();
    eprintln!("Scanning {} Sql files...", total_files);

    let progress = AtomicUsize::new(0);

    // Parallel extraction
    let per_file_results: Vec<AHashMap<String, DomainInfo>> = files
        .par_iter()
        .map(|f| {
            let result = extract_from_file(f);
            let done = progress.fetch_add(1, Ordering::Relaxed) + 1;
            if done % 5000 == 0 {
                eprintln!("  [{}/{}] ({:.0}s)", done, total_files, t0.elapsed().as_secs_f64());
            }
            result
        })
        .collect();

    // Merge
    eprintln!("Merging...");
    let mut all_domains: AHashMap<String, DomainInfo> = AHashMap::new();
    for file_domains in per_file_results {
        for (domain, info) in file_domains {
            all_domains
                .entry(domain)
                .and_modify(|d| d.page_count += info.page_count)
                .or_insert(info);
        }
    }

    let elapsed = t0.elapsed().as_secs_f64();
    eprintln!(
        "\n{} unique domains from {} files in {:.1}s ({:.0} files/s)",
        all_domains.len(),
        total_files,
        elapsed,
        total_files as f64 / elapsed,
    );

    // Sort by page_count desc
    let mut sorted: Vec<&DomainInfo> = all_domains.values().collect();
    sorted.sort_by(|a, b| b.page_count.cmp(&a.page_count));

    // Top 10
    eprintln!("\nTop 10:");
    for d in sorted.iter().take(10) {
        eprintln!("  {:40} {:>10} pages", d.domain, d.page_count);
    }

    // Write JSONL.gz
    let out_file = fs::File::create(&args.output).expect("cannot create output");
    let mut gz = GzEncoder::new(out_file, Compression::fast());
    for d in &sorted {
        serde_json::to_writer(&mut gz, d).unwrap();
        gz.write_all(b"\n").unwrap();
    }
    gz.finish().unwrap();

    let out_size = fs::metadata(&args.output).map(|m| m.len()).unwrap_or(0);
    eprintln!(
        "Saved: {} ({:.1} MB, {} domains)",
        args.output.display(),
        out_size as f64 / 1024.0 / 1024.0,
        sorted.len(),
    );
}
