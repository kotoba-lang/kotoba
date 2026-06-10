//! `kotoba word` — word registry subcommands over the built-in example root.
//!
//! Words are authored as typed Rust closures (the SSOT); these subcommands
//! exercise the derived artifacts: direct invocation, the extracted manifest
//! (lockfile pattern: `manifest` writes it, `diff` is the CI gate), the
//! ATProto lexicon projection, and the MCP stdio projection.

use std::path::PathBuf;
use std::sync::Arc;

use anyhow::{Context, Result};
use clap::Subcommand;
use kotoba_word::projection::{lexicon, mcp};
use kotoba_word::{examples, Manifest};

#[derive(Subcommand)]
pub enum WordCmd {
    /// List registered words with caps and executor provenance
    List,

    /// Invoke a word: `kotoba word invoke <nsid> --input '<json>'`
    Invoke {
        /// Full NSID (e.g. com.etzhayyim.apps.kotoba.word.math.add)
        nsid: String,
        /// JSON input object
        #[arg(long, short, default_value = "{}")]
        input: String,
    },

    /// Extract the word manifest (interchange SSOT) to stdout or a file
    Manifest {
        /// Write to this path instead of stdout
        #[arg(long, short)]
        out: Option<PathBuf>,
    },

    /// Diff the live registry against a committed manifest (CI gate).
    /// Exit codes: 0 = no change, 1 = additive change, 2 = BREAKING change.
    Diff {
        /// Path to the committed manifest JSON
        path: PathBuf,
    },

    /// Generate ATProto lexicon documents, one file per word
    Lexicons {
        /// Output directory (repo convention: lexicons/)
        #[arg(long, short, default_value = "lexicons")]
        out_dir: PathBuf,
    },

    /// Serve the root as an MCP server over stdio (newline-delimited JSON-RPC)
    Mcp,
}

pub async fn run(cmd: WordCmd) -> Result<()> {
    let root = examples::example_root().map_err(|e| anyhow::anyhow!(e.to_string()))?;

    match cmd {
        WordCmd::List => {
            for w in root.words() {
                let caps = if w.caps.is_empty() {
                    "-".to_string()
                } else {
                    w.caps
                        .iter()
                        .map(|c| c.to_string())
                        .collect::<Vec<_>>()
                        .join(",")
                };
                println!(
                    "{}\t[{:?}:{}]\tcaps={}\t{}",
                    w.nsid, w.executor.kind, w.executor.reference, caps, w.description
                );
            }
        }

        WordCmd::Invoke { nsid, input } => {
            let input: serde_json::Value =
                serde_json::from_str(&input).context("parse --input as JSON")?;
            match root.invoke(&nsid, input).await {
                Ok(out) => println!("{}", serde_json::to_string_pretty(&out)?),
                Err(e) => {
                    eprintln!("error: {e}");
                    std::process::exit(1);
                }
            }
        }

        WordCmd::Manifest { out } => {
            let json = root.manifest().to_canonical_json();
            match out {
                Some(path) => {
                    std::fs::write(&path, format!("{json}\n"))?;
                    eprintln!("wrote {}", path.display());
                }
                None => println!("{json}"),
            }
        }

        WordCmd::Diff { path } => {
            let committed = Manifest::from_json(
                &std::fs::read_to_string(&path)
                    .with_context(|| format!("read {}", path.display()))?,
            )?;
            let live = root.manifest();
            let diff = committed.diff(&live);
            if diff.is_empty() {
                println!("manifest up to date ({} words)", live.words.len());
            } else {
                println!("{}", diff.summary());
                std::process::exit(if diff.is_breaking() { 2 } else { 1 });
            }
        }

        WordCmd::Lexicons { out_dir } => {
            let written = lexicon::write_lexicons(&root.manifest(), &out_dir)?;
            for p in &written {
                println!("{}", p.display());
            }
            eprintln!("{} lexicon docs written", written.len());
        }

        WordCmd::Mcp => {
            eprintln!(
                "kotoba-word MCP server (root {}) on stdio — attach an agent",
                root.nsid_root()
            );
            mcp::serve_stdio(Arc::new(root)).await?;
        }
    }

    Ok(())
}
