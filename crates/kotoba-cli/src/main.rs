//! kotoba CLI — serve, block, quad, health subcommands.
//!
//! Configuration via env vars (same as the server):
//!   KOTOBA_URL   — server base URL for client subcommands (default: http://localhost:8080)
//!   KOTOBA_TOKEN — Bearer token for authenticated requests (block put, quad put/retract)
//!
//! Server env vars (serve subcommand):
//!   KOTOBA_PORT, KOTOBA_NO_SWARM, KOTOBA_IPFS_ENDPOINT, etc.

use anyhow::{Context, Result};
use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use clap::{CommandFactory, Parser, Subcommand};
use std::path::{Path, PathBuf};
use std::process::Command;
use tracing_subscriber::EnvFilter;

mod extension;
mod mesh;
mod shell;
mod word;

// ── NSIDs (mirror kotoba-server::xrpc constants) ─────────────────────────────
const NSID_BLOCK_PUT: &str = "com.etzhayyim.apps.kotoba.block.put";
const NSID_BLOCK_GET: &str = "com.etzhayyim.apps.kotoba.block.get";
const NSID_QUAD_CREATE: &str = "com.etzhayyim.apps.kotoba.quad.create";
const NSID_QUAD_RETRACT: &str = "com.etzhayyim.apps.kotoba.quad.retract";
const NSID_GRAPH_QUERY: &str = "com.etzhayyim.apps.kotoba.graph.query";
const DEFAULT_WASM_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");

// ── CLI definition ────────────────────────────────────────────────────────────

#[derive(Parser)]
#[command(name = "kotoba", about = "Kotoba knowledge-graph node CLI", version)]
struct Cli {
    /// Compile and run one inline Kotoba expression as `main`.
    #[arg(short = 'e', long = "eval")]
    eval: Option<String>,

    /// With -e/--eval, also write the compiled core wasm module to this path.
    #[arg(long = "wasm-out", requires = "eval")]
    wasm_out: Option<std::path::PathBuf>,

    /// Server base URL (overrides KOTOBA_URL)
    #[arg(
        long,
        env = "KOTOBA_URL",
        global = true,
        default_value = "http://localhost:8080"
    )]
    url: String,

    /// Bearer token for authenticated requests (overrides KOTOBA_TOKEN)
    #[arg(long, env = "KOTOBA_TOKEN", global = true)]
    token: Option<String>,

    #[command(subcommand)]
    cmd: Option<Cmd>,
}

#[derive(Subcommand)]
enum Cmd {
    /// Start the kotoba server
    Serve,

    /// t-of-N key custody operations (ADR-sealed-cold-tier R3): deal a block
    /// key into custodian shares, recombine grants, generate custodian keys.
    #[command(subcommand)]
    Key(KeyCmd),

    /// Raw block operations
    #[command(subcommand)]
    Block(BlockCmd),

    /// Named-graph quad operations
    #[command(subcommand)]
    Quad(QuadCmd),

    /// kotoba words — agent-callable units (list/invoke/manifest/lexicons/MCP)
    #[command(subcommand)]
    Word(word::WordCmd),

    /// KOTOBA Mesh — compile a WASM component (Kotoba default) to a CID.
    #[command(subcommand)]
    Component(mesh::ComponentCmd),

    /// Kotoba language → Wasm compiler tools.
    #[command(subcommand)]
    Wasm(WasmCmd),

    /// KOTOBA Mesh — resolve & deploy an EDN app manifest.
    #[command(subcommand)]
    App(mesh::AppCmd),

    /// KOTOBA Mesh — lattice participation status.
    #[command(subcommand)]
    Lattice(mesh::LatticeCmd),

    /// Kotoba extensions — evaluate, run, build, and deploy Kotoba/EDN packages.
    #[command(subcommand)]
    Extension(extension::ExtensionCmd),

    /// kotoba-shell — Tauri-shaped CLJS/safe Kotoba app shell planning.
    #[command(subcommand)]
    Shell(shell::ShellCmd),

    /// Run a Kotoba source file like `deno run`.
    Run(RunCmd),

    /// Check Kotoba source without emitting an artifact.
    Check(CheckCmd),

    /// Database operations: transact, query, quad, commit, status.
    #[command(subcommand)]
    Db(DbCmd),

    /// Git operations through kotoba's smart-HTTP repository endpoint.
    #[command(subcommand)]
    Git(GitCmd),

    /// kotoba-rad sovereign repository identity helpers.
    #[command(subcommand)]
    Rad(RadCmd),

    /// Deploy an app manifest to the Kotoba mesh.
    Deploy(DeployCmd),

    /// SPARQL query (SELECT / DESCRIBE / CONSTRUCT / ASK) over the running
    /// server's direct-SPARQL endpoint.  Auto-detects the form from the
    /// query.  Goes to POST /xrpc/com.etzhayyim.apps.kotoba.graph.sparql which
    /// runs over IPFS-backed cold storage (DistributedBlockStore / Kubo HTTP).
    Sparql {
        /// SPARQL query string (max 64 KiB).
        query: String,
        /// Maximum quads returned (default 10000)
        #[arg(long, default_value = "10000")]
        limit: usize,
        /// CACAO chain (base64 DAG-CBOR) for private graphs
        #[arg(long, env = "KOTOBA_CACAO_B64")]
        cacao: Option<String>,
        /// Target named graph CID (multibase). Defaults to the kg-graph.
        #[arg(long)]
        graph: Option<String>,
        /// DESCRIBE only: traverse N hops along QuadObject::Cid edges from
        /// matched seeds (multi-pop subgraph expansion).  Capped at 16 server-side.
        #[arg(long, default_value = "0")]
        max_hops: usize,
    },

    /// Datomic Datalog query (`[:find … :where …]`) over the running server's
    /// distributed Datom graph. POST /xrpc/com.etzhayyim.apps.kotoba.datomic.q.
    /// With --emit-cid the response also carries content-addressed provenance
    /// (query_spec_cid / query_job_cid / result_cid) — the resultCid is fetchable
    /// via `block.get` for Public graphs.
    Q {
        /// Datomic Datalog query EDN, e.g. `[:find ?e :where [?e :a ?v]]`.
        query: String,
        /// Target graph CID (multibase) — required for datomic.q.
        #[arg(long)]
        graph: String,
        /// Emit content-addressed provenance CIDs alongside the rows.
        #[arg(long)]
        emit_cid: bool,
        /// Optional as-of transaction CID (reproducible time-travel read).
        #[arg(long)]
        as_of: Option<String>,
        /// CACAO chain (base64 DAG-CBOR) for private graphs.
        #[arg(long, env = "KOTOBA_CACAO_B64")]
        cacao: Option<String>,
    },

    /// Cypher MATCH/RETURN over the running server (same endpoint, lang=cypher).
    Cypher {
        query: String,
        #[arg(long, default_value = "1000")]
        limit: usize,
        #[arg(long, env = "KOTOBA_CACAO_B64")]
        cacao: Option<String>,
    },

    /// Cross-modal search: a text query retrieves matching assets across ALL
    /// modalities (image / video / audio / document) from one shared embedding
    /// space.  GET /xrpc/com.etzhayyim.apps.kotoba.media.search.  Uses operator auth
    /// (built from the local `kotoba init` identity).
    MediaSearch {
        /// Free-text query (max 8 KiB).
        query: String,
        /// Maximum results (default 10, server cap 100).
        #[arg(long, default_value = "10")]
        top_k: usize,
        /// Restrict to one modality: text|image|audio|video|document.
        #[arg(long)]
        modality: Option<String>,
    },

    /// Ingest one media file (image / video / audio / book / PDF) into the
    /// shared search space.  POST /xrpc/com.etzhayyim.apps.kotoba.media.ingest.
    /// MIME is inferred from the file extension; the caption (if given) is the
    /// strongest cross-modal bridge to text queries.
    MediaIngest {
        /// Path to the asset file.
        path: String,
        /// Caption / OCR / transcript text describing the asset.
        #[arg(long)]
        caption: Option<String>,
        /// Display title (defaults to the file name).
        #[arg(long)]
        title: Option<String>,
        /// Page index for paginated documents (books / PDFs).
        #[arg(long, default_value = "0")]
        page: i64,
    },

    /// Show multimodal index status: asset count, embeddings, IVF centroids,
    /// and a per-modality breakdown.  GET /xrpc/com.etzhayyim.apps.kotoba.media.status.
    MediaStatus,

    /// Ping the server's /health endpoint
    Health,

    /// Initialise device-local identity (Ed25519 + X25519 + DID) and persist to
    /// macOS Keychain (or ~/.etzhayyim/kotoba.env on Linux/other).  Subsequent
    /// `kotoba serve` invocations will load these automatically and the DID
    /// remains stable across restarts.
    Init {
        /// Overwrite any existing device-local identity.
        #[arg(long)]
        force: bool,
        /// Print the resulting DID + hex material to stdout.
        #[arg(long)]
        show: bool,
    },

    /// Print the local deployment-config summary (env-driven): identity
    /// source, IPFS endpoint, peer list, default visibility, hot-cache size.
    Whoami,

    /// Check whether `etzhayyim/kotoba` main branch is newer than this
    /// binary's build commit.  Hits GitHub's REST API once and caches the
    /// result for 24 h in `~/.etzhayyim/kotoba-update.json`.
    UpdateCheck {
        /// Re-fetch even if the cache is fresh.
        #[arg(long)]
        force: bool,
    },

    /// Seal the running server's hot Arrangement into 4 ProllyTrees +
    /// checkpoint via POST /xrpc/com.etzhayyim.apps.kotobase.kg.commit.
    /// Required by the operator to make ingested writes survive crash +
    /// restart.  Sends an operator JWT — by default constructs one from
    /// the local Keychain identity so the operator-auth check passes.
    Commit {
        /// Optional author DID for the commit metadata.
        #[arg(long)]
        author: Option<String>,
    },

    /// End-to-end smoke: ingest a sample entity via kg.ingest, then run
    /// SELECT / ASK / DESCRIBE / CONSTRUCT through the direct-SPARQL endpoint.
    /// Useful for verifying that `kotoba serve` is wired up against the
    /// expected IPFS + CACAO + graph stack.
    Demo {
        /// Bearer token used for the Authenticated tier (kg graph default).
        /// If absent, falls back to `KOTOBA_TOKEN` or "demo-token".
        #[arg(long, env = "KOTOBA_DEMO_TOKEN")]
        token: Option<String>,
    },

    /// Derive a `did:key:z…` from a 32-byte hex Ed25519 seed.  Useful for
    /// pre-computing the DID a `kotoba serve` will boot with when
    /// KOTOBA_AGENT_ED25519_HEX is set to the same seed.
    DidDerive {
        /// 64 hex chars (32-byte seed).
        seed: String,
    },

    /// Build a real-signed CACAO authorising `datom:read` (or another cap) on a
    /// graph CID, signed by the supplied Ed25519 seed.  Output is DAG-CBOR
    /// base64-standard — paste into `cacaoB64` field of the SPARQL request.
    CacaoSign {
        /// 32-byte hex Ed25519 seed of the signer.
        seed: String,
        /// Graph CID multibase to scope the CACAO to.
        #[arg(long)]
        graph: String,
        /// Capability granted (e.g. `datom:read`, `datom:write`).
        #[arg(long, default_value = "datom:read")]
        capability: String,
        /// Audience.  Defaults to the issuer DID (the server enforces
        /// aud == operator_did on Private graphs).
        #[arg(long)]
        aud: Option<String>,
        /// CACAO nonce (anti-replay).  Default `kotoba-cli-nonce`.
        #[arg(long, default_value = "kotoba-cli-nonce")]
        nonce: String,
        /// If true, prefix the graph as `private/<did>` (matches the server's
        /// Private-visibility check).  When the server runs with
        /// KOTOBA_DEFAULT_VISIBILITY=private this is required.
        #[arg(long)]
        private: bool,
    },

    /// HTTP-level loadtest for the direct-SPARQL endpoint.  Issues `iters`
    /// POSTs of the same query (sequential or concurrent) and reports
    /// p50/p95/p99/mean in milliseconds plus aggregate QPS.
    Bench {
        /// SPARQL query to repeat.
        #[arg(default_value = r#"SELECT * WHERE { ?s <kg/claim/role> ?o }"#)]
        query: String,
        /// Total iterations (default 100).
        #[arg(long, default_value = "100")]
        iters: usize,
        /// Concurrent in-flight clients (default 1 = sequential).
        #[arg(long, short = 'c', default_value = "1")]
        concurrency: usize,
        /// Bearer token (defaults to a fresh JWT-shaped demo token).
        #[arg(long, env = "KOTOBA_DEMO_TOKEN")]
        token: Option<String>,
        /// CACAO chain (DAG-CBOR base64).  When set, every request includes
        /// `cacaoB64` — required for Private-visibility graphs.  Note: CAIP-74
        /// anti-replay nonce is single-use, so this works for one request only.
        /// Use `--cacao-seed` instead for sustained CACAO loadtests.
        #[arg(long, env = "KOTOBA_CACAO_B64")]
        cacao: Option<String>,
        /// 32-byte hex Ed25519 seed — when set, a fresh CACAO is signed for
        /// each request with a unique nonce.  Required for any sustained
        /// (`--iters > 1`) CACAO-gated bench.
        #[arg(long)]
        cacao_seed: Option<String>,
        /// Graph scope baked into the per-request CACAO.  With
        /// `--cacao-private` the scope is rewritten to `private/<did>` to
        /// match the server's Private-visibility check.
        #[arg(long, default_value = "foo")]
        cacao_graph: String,
        /// Treat the graph as Private (rewrite scope to `private/<did>`).
        #[arg(long)]
        cacao_private: bool,
        /// DESCRIBE only: N-hop multi-pop subgraph expansion depth.
        #[arg(long, default_value = "0")]
        max_hops: usize,
    },
}

#[derive(Subcommand)]
enum BlockCmd {
    /// Store bytes and return the CID.
    /// Provide data inline as hex, or use --file to read from disk.
    Put {
        /// Hex-encoded bytes (mutually exclusive with --file)
        data_hex: Option<String>,
        /// Path to file to read (mutually exclusive with inline hex)
        #[arg(long, short)]
        file: Option<std::path::PathBuf>,
    },
    /// Retrieve a block by CID (multibase)
    Get {
        cid: String,
        /// Write raw bytes to this path instead of printing base64
        #[arg(long, short)]
        out: Option<std::path::PathBuf>,
    },
}

#[derive(Subcommand)]
enum WasmCmd {
    /// Compile a Kotoba source file into a kotoba:kais Wasm component.
    Build {
        /// Kotoba source file.
        cell: PathBuf,
        /// Output Wasm path. Defaults to replacing the Kotoba-family extension with .wasm.
        #[arg(short = 'o')]
        out: Option<PathBuf>,
        /// WIT directory for component wrapping.
        #[arg(long)]
        wit: Option<PathBuf>,
        /// Extra source root for namespace resolution.
        #[arg(short = 'S', long = "source-path")]
        source_path: Vec<PathBuf>,
    },
    /// Compile a capability-confined Kotoba source file into a core Wasm module.
    SafeBuild {
        /// Kotoba source file.
        cell: PathBuf,
        /// Deny-by-default capability policy.
        #[arg(long)]
        policy: PathBuf,
        /// Output Wasm path. Defaults to replacing the Kotoba-family extension with .wasm.
        #[arg(short = 'o')]
        out: Option<PathBuf>,
        /// Compatibility alias; safe-build is selfhost-first by default.
        #[arg(long)]
        selfhost_gate: bool,
        /// Reader conditional target.
        #[arg(long, default_value = "kotoba")]
        reader_target: String,
        /// Extra source root for namespace resolution.
        #[arg(short = 'S', long = "source-path")]
        source_path: Vec<PathBuf>,
    },
    /// Synthesize the minimal least-privilege policy for a Kotoba source file.
    SafePolicy {
        /// Kotoba source file.
        cell: PathBuf,
        /// Write policy EDN to this path instead of stdout.
        #[arg(short = 'o')]
        out: Option<PathBuf>,
        /// Compatibility alias; safe-policy is selfhost-first by default.
        #[arg(long)]
        selfhost_gate: bool,
        /// Reader conditional target.
        #[arg(long, default_value = "kotoba")]
        reader_target: String,
        /// Extra source root for namespace resolution.
        #[arg(short = 'S', long = "source-path")]
        source_path: Vec<PathBuf>,
    },
    /// Inspect self-hosted analyzer input/output for a Kotoba source file.
    SelfhostInspect {
        /// Kotoba source file.
        cell: PathBuf,
        /// Optional policy to include admission results.
        #[arg(long)]
        policy: Option<PathBuf>,
        /// Reader conditional target.
        #[arg(long, default_value = "kotoba")]
        reader_target: String,
        /// Extra source root for namespace resolution.
        #[arg(short = 'S', long = "source-path")]
        source_path: Vec<PathBuf>,
        /// Print the analyzer request as CBOR hex.
        #[arg(long)]
        request_hex: bool,
        /// Print JSON output.
        #[arg(long)]
        json: bool,
    },
}

#[derive(clap::Args)]
struct RunCmd {
    /// Kotoba source file.
    cell: PathBuf,
    /// Exported function to call.
    #[arg(long, default_value = "main")]
    func: String,
    /// i64 arguments passed to the exported function.
    args: Vec<i64>,
    /// Extra source root for namespace resolution.
    #[arg(short = 'S', long = "source-path")]
    source_path: Vec<PathBuf>,
}

#[derive(clap::Args)]
struct CheckCmd {
    /// Kotoba source file.
    cell: PathBuf,
    /// Optional deny-by-default policy. When omitted, check emits a minimal policy.
    #[arg(long)]
    policy: Option<PathBuf>,
    /// Reader conditional target.
    #[arg(long, default_value = "kotoba")]
    reader_target: String,
    /// Extra source root for namespace resolution.
    #[arg(short = 'S', long = "source-path")]
    source_path: Vec<PathBuf>,
}

#[derive(Subcommand)]
enum DbCmd {
    /// Show node health for the database endpoint.
    Status,
    /// Transact Datomic EDN into a named graph.
    Transact {
        /// Target graph CID / name.
        #[arg(long)]
        graph: String,
        /// EDN transaction string. If omitted, stdin is read.
        tx_edn: Option<String>,
        /// Read transaction EDN from a file.
        #[arg(long, short)]
        file: Option<PathBuf>,
        /// CACAO chain (DAG-CBOR base64) for private/write-scoped graphs.
        #[arg(long, env = "KOTOBA_CACAO_B64")]
        cacao: Option<String>,
    },
    /// Datomic Datalog query.
    Q {
        query: String,
        #[arg(long)]
        graph: String,
        #[arg(long)]
        emit_cid: bool,
        #[arg(long)]
        as_of: Option<String>,
        #[arg(long, env = "KOTOBA_CACAO_B64")]
        cacao: Option<String>,
    },
    /// SPARQL query.
    Sparql {
        query: String,
        #[arg(long, default_value = "10000")]
        limit: usize,
        #[arg(long, env = "KOTOBA_CACAO_B64")]
        cacao: Option<String>,
        #[arg(long)]
        graph: Option<String>,
        #[arg(long, default_value = "0")]
        max_hops: usize,
    },
    /// Cypher query.
    Cypher {
        query: String,
        #[arg(long, default_value = "1000")]
        limit: usize,
        #[arg(long, env = "KOTOBA_CACAO_B64")]
        cacao: Option<String>,
    },
    /// Assert one quad.
    Put {
        graph: String,
        subject: String,
        predicate: String,
        object: String,
    },
    /// Retract one quad.
    Retract {
        graph: String,
        subject: String,
        predicate: String,
        object: String,
    },
    /// SPO pattern query over a named graph.
    Query {
        #[arg(long)]
        graph: String,
        #[arg(long, short)]
        subject: Option<String>,
        #[arg(long, short)]
        predicate: Option<String>,
        #[arg(long, default_value = "100")]
        limit: u64,
    },
    /// Seal the hot database into durable ProllyTree checkpoints.
    Commit {
        #[arg(long)]
        author: Option<String>,
    },
}

#[derive(Subcommand)]
enum GitCmd {
    /// Print the smart-HTTP URL for a kotoba repo.
    Url { repo: String },
    /// Clone a kotoba smart-HTTP repo using the real git CLI.
    Clone { repo: String, dir: Option<PathBuf> },
    /// Add or update a git remote pointing at a kotoba repo.
    Remote {
        repo: String,
        #[arg(long, default_value = "kotoba")]
        name: String,
    },
    /// Push using the real git CLI. Defaults to `kotoba HEAD:refs/heads/main`.
    Push {
        #[arg(long, default_value = "kotoba")]
        remote: String,
        #[arg(default_value = "HEAD:refs/heads/main")]
        refspec: String,
    },
    /// Fetch using the real git CLI.
    Fetch {
        #[arg(long, default_value = "kotoba")]
        remote: String,
    },
    /// Run `git status` in the current worktree.
    Status,
}

#[derive(Subcommand)]
enum RadCmd {
    /// Show the local kotoba-rad journal configuration.
    Status,
    /// Print the currently documented R1 CLI shape.
    Plan,
}

#[derive(clap::Args)]
struct DeployCmd {
    /// Path to `kotoba.app.edn`.
    manifest: PathBuf,
    /// Path to the kotoba-node WIT dir.
    #[arg(
        long,
        env = "KOTOBA_WIT_DIR",
        default_value = "crates/kotoba-runtime/wit"
    )]
    wit_dir: String,
    /// Publish to a running node instead of dry-running.
    #[arg(long)]
    publish: bool,
}

#[derive(Subcommand)]
enum QuadCmd {
    /// Assert a quad: `<graph-cid> <subject> <predicate> <object>`
    Put {
        graph: String,
        subject: String,
        predicate: String,
        object: String,
    },
    /// Retract a quad: `<graph-cid> <subject> <predicate> <object>`
    Retract {
        graph: String,
        subject: String,
        predicate: String,
        object: String,
    },
    /// SPO pattern query over a named graph
    Query {
        /// Named graph CID (multibase)
        #[arg(long)]
        graph: String,
        /// Subject filter (multibase CID or raw string)
        #[arg(long, short)]
        subject: Option<String>,
        /// Predicate filter (exact string)
        #[arg(long, short)]
        predicate: Option<String>,
        /// Maximum results (1–1000, default 100)
        #[arg(long, default_value = "100")]
        limit: u64,
    },
}

#[derive(Subcommand)]
enum KeyCmd {
    /// Generate an X25519 custodian/requester keypair (hex). The PUBLIC key is
    /// what an operator deals shares to; keep the secret offline.
    GenKey,

    /// Split a 32-byte block key into t-of-N custodian shares, offline. Each
    /// `--custodian DID:PUBKEY_HEX` gets one HPKE-wrapped share; any `t` of them
    /// recombine. Prints the share JSONs (deposit each to its custodian via
    /// `key.depositShare`).
    Deal {
        /// Block key as 64 hex chars (KOTOBA_BLOCK_KEY).
        #[arg(long, env = "KOTOBA_BLOCK_KEY")]
        key_hex: String,
        /// Recombination threshold (2..=N).
        #[arg(long)]
        threshold: u8,
        /// Custodian as `DID:X25519_PUBKEY_HEX`, repeatable.
        #[arg(long = "custodian", required = true)]
        custodians: Vec<String>,
        /// Rotation epoch (R3c); bump when re-dealing to a changed set.
        #[arg(long, default_value = "0")]
        epoch: u64,
    },

    /// Recombine `threshold` granted shares (as returned by `key.requestShare`)
    /// back into the block key, offline. `--grant` is a path to a grant JSON,
    /// repeatable; `--requester-sk-hex` is the X25519 secret the shares were
    /// re-wrapped to.
    Combine {
        /// Path to a grant JSON file, repeatable (need >= threshold).
        #[arg(long = "grant", required = true)]
        grants: Vec<std::path::PathBuf>,
        /// Requester X25519 secret (64 hex chars).
        #[arg(long, env = "KOTOBA_REQUESTER_SK")]
        requester_sk_hex: String,
        /// Threshold the deal used.
        #[arg(long)]
        threshold: u8,
    },
}

// ── Entry point ───────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("warn")),
        )
        .init();

    let raw_args: Vec<String> = std::env::args().collect();
    if raw_args
        .get(1)
        .is_some_and(|arg| arg.starts_with("-M") || arg.starts_with("-X"))
    {
        return extension::run_clojure_alias_shorthand(&raw_args[1..]);
    }

    let cli = Cli::parse();

    if let Some(expr) = cli.eval.as_deref() {
        run_inline_eval(expr, cli.wasm_out.as_deref())?;
        return Ok(());
    }

    let Some(cmd) = cli.cmd else {
        Cli::command().print_help()?;
        println!();
        return Ok(());
    };

    match cmd {
        Cmd::Serve => {
            // Fire-and-forget update-check before booting the server.  Cached
            // 24 h to avoid hitting GitHub on every restart.  Result is printed
            // to stderr so it doesn't interfere with structured logging.
            if let Some(msg) = check_for_update(false).await {
                eprintln!("{msg}");
            }
            kotoba_server::run().await?;
        }

        Cmd::Word(cmd) => {
            word::run(cmd).await?;
        }

        Cmd::Component(cmd) => mesh::run_component(cmd)?,
        Cmd::Wasm(cmd) => run_wasm_cmd(cmd)?,
        Cmd::App(cmd) => mesh::run_app(cmd).await?,
        Cmd::Lattice(cmd) => mesh::run_lattice(cmd)?,
        Cmd::Extension(cmd) => extension::run(cmd, &cli.url, &cli.token).await?,
        Cmd::Shell(cmd) => shell::run(cmd)?,
        Cmd::Run(cmd) => run_source_cmd(cmd)?,
        Cmd::Check(cmd) => run_check_cmd(cmd)?,
        Cmd::Db(cmd) => run_db_cmd(cmd, &cli.url, &cli.token).await?,
        Cmd::Git(cmd) => run_git_cmd(cmd, &cli.url)?,
        Cmd::Rad(cmd) => run_rad_cmd(cmd)?,
        Cmd::Deploy(cmd) => {
            mesh::run_app(mesh::AppCmd::Deploy {
                manifest: cmd.manifest,
                wit_dir: cmd.wit_dir,
                publish: cmd.publish,
                url: cli.url.clone(),
            })
            .await?
        }

        Cmd::Key(key_cmd) => run_key_cmd(key_cmd)?,

        Cmd::Sparql {
            query,
            limit,
            cacao,
            graph,
            max_hops,
        } => {
            run_sparql(&cli.url, &cli.token, &query, limit, cacao, graph, max_hops).await?;
        }

        Cmd::Q {
            query,
            graph,
            emit_cid,
            as_of,
            cacao,
        } => {
            run_datomic_q(&cli.url, &cli.token, &query, &graph, emit_cid, as_of, cacao).await?;
        }

        Cmd::Cypher {
            query,
            limit,
            cacao,
        } => {
            run_kg_query(&cli.url, &cli.token, "cypher", &query, limit, cacao).await?;
        }

        Cmd::MediaSearch {
            query,
            top_k,
            modality,
        } => {
            run_media_search(&cli.url, &query, top_k, modality).await?;
        }

        Cmd::MediaIngest {
            path,
            caption,
            title,
            page,
        } => {
            run_media_ingest(&cli.url, &path, caption, title, page).await?;
        }

        Cmd::MediaStatus => {
            run_media_status(&cli.url).await?;
        }

        Cmd::Init { force, show } => {
            // Refuse to overwrite an existing identity unless --force.
            if !force {
                if let Some(existing) = kotoba_vault::AgentIdentity::from_keychain() {
                    anyhow::bail!(
                        "device-local identity already exists (DID={}). \
                         Use --force to overwrite.",
                        existing.did
                    );
                }
            }
            let id = kotoba_vault::AgentIdentity::generate_persistent();
            id.persist_to_keychain().context("persisting identity")?;
            println!("Persisted identity to macOS Keychain (or ~/.etzhayyim/kotoba.env).");
            println!("DID: {}", id.did);
            if show {
                println!(
                    "KOTOBA_AGENT_ED25519_HEX={}",
                    hex::encode(id.signing_key.to_bytes())
                );
                println!(
                    "KOTOBA_AGENT_X25519_HEX={}",
                    hex::encode(id.dh_secret.to_bytes())
                );
                println!("KOTOBA_AGENT_DID={}", id.did);
            }
        }

        Cmd::Demo { token } => {
            let tok = token
                .or_else(|| cli.token.clone())
                .unwrap_or_else(|| "demo-token".into());
            run_demo(&cli.url, &tok).await?;
        }

        Cmd::DidDerive { seed } => {
            use ed25519_dalek::SigningKey;
            let bytes = hex::decode(seed.trim()).context("seed must be hex")?;
            if bytes.len() != 32 {
                anyhow::bail!("seed must decode to exactly 32 bytes, got {}", bytes.len());
            }
            let mut arr = [0u8; 32];
            arr.copy_from_slice(&bytes);
            let sk = SigningKey::from_bytes(&arr);
            let did =
                kotoba_auth::did_key::ed25519_pubkey_to_did_key(sk.verifying_key().as_bytes());
            println!("{did}");
        }

        Cmd::CacaoSign {
            seed,
            graph,
            capability,
            aud,
            nonce,
            private,
        } => {
            use base64::{
                engine::general_purpose::{STANDARD as B64, URL_SAFE_NO_PAD},
                Engine,
            };
            use ed25519_dalek::{Signer, SigningKey};
            use kotoba_auth::did_key::ed25519_pubkey_to_did_key;
            use kotoba_auth::{Cacao, CacaoHeader, CacaoPayload, CacaoSig};

            let bytes = hex::decode(seed.trim()).context("seed must be hex")?;
            if bytes.len() != 32 {
                anyhow::bail!("seed must decode to exactly 32 bytes");
            }
            let mut arr = [0u8; 32];
            arr.copy_from_slice(&bytes);
            let sk = SigningKey::from_bytes(&arr);
            let did = ed25519_pubkey_to_did_key(sk.verifying_key().as_bytes());

            // The Private-visibility check uses the synthetic graph scope
            // "private/<owner_did>" rather than the raw CID multibase, so the
            // CACAO must carry that scope to be accepted by the server.
            let graph_scope = if private {
                format!("private/{did}")
            } else {
                graph
            };

            let aud_resolved = aud.unwrap_or_else(|| did.clone());
            let mut cacao = Cacao {
                h: CacaoHeader {
                    t: "caip122".into(),
                },
                p: CacaoPayload {
                    iss: did.clone(),
                    aud: aud_resolved,
                    issued_at: "2026-05-26T00:00:00Z".into(),
                    expiry: Some("2099-01-01T00:00:00Z".into()),
                    nonce,
                    domain: "kotoba.cli".into(),
                    statement: None,
                    version: "1".into(),
                    resources: vec![
                        format!("kotoba://graph/{graph_scope}"),
                        format!("kotoba://can/{capability}"),
                    ],
                },
                s: CacaoSig {
                    t: "EdDSA".into(),
                    s: String::new(),
                },
            };
            let msg = cacao.siwe_message();
            let sig: ed25519_dalek::Signature = sk.sign(msg.as_bytes());
            cacao.s.s = URL_SAFE_NO_PAD.encode(sig.to_bytes());

            let mut cbor = Vec::new();
            ciborium::into_writer(&cacao, &mut cbor).context("cbor encode")?;
            println!("{}", B64.encode(&cbor));
        }

        Cmd::Bench {
            query,
            iters,
            concurrency,
            token,
            cacao,
            cacao_seed,
            cacao_graph,
            cacao_private,
            max_hops,
        } => {
            let tok = token
                .or_else(|| cli.token.clone())
                .unwrap_or_else(|| "demo-token".into());
            run_bench(
                &cli.url,
                &tok,
                &query,
                iters,
                concurrency,
                cacao,
                cacao_seed,
                cacao_graph,
                cacao_private,
                max_hops,
            )
            .await?;
        }

        Cmd::Commit { author } => {
            run_commit(&cli.url, author).await?;
        }

        Cmd::UpdateCheck { force } => {
            let local_sha = BUILD_COMMIT;
            println!("local build commit : {local_sha}");
            match check_for_update(force).await {
                Some(msg) => println!("{msg}"),
                None => println!("you are up to date."),
            }
        }

        Cmd::Whoami => {
            // Resolve identity (keychain → env → ephemeral)
            let id = kotoba_vault::AgentIdentity::from_env();
            let source = if id.ephemeral {
                "ephemeral (no keychain, no env)"
            } else if kotoba_vault::AgentIdentity::from_keychain().is_some() {
                "keychain"
            } else {
                "env"
            };
            let ipfs_off = std::env::var("KOTOBA_IPFS")
                .map(|v| {
                    v.eq_ignore_ascii_case("off") || v == "0" || v.eq_ignore_ascii_case("false")
                })
                .unwrap_or(false);
            let ipfs_endpoint = std::env::var("KOTOBA_IPFS_ENDPOINT")
                .unwrap_or_else(|_| "http://localhost:5001 (default)".into());
            let peers = std::env::var("KOTOBA_PEERS").unwrap_or_default();
            let default_vis = std::env::var("KOTOBA_DEFAULT_VISIBILITY")
                .unwrap_or_else(|_| "private (default)".into());
            let hot_mib = std::env::var("KOTOBA_HOT_CACHE_BYTES")
                .or_else(|_| std::env::var("KOTOBA_STORAGE_BUDGET_BYTES"))
                .ok()
                .and_then(|s| s.parse::<usize>().ok())
                .map(|b| b / (1024 * 1024))
                .unwrap_or(256);
            println!("identity source       : {source}");
            println!("DID                   : {}", id.did);
            println!("ephemeral             : {}", id.ephemeral);
            println!(
                "IPFS cold tier        : {}",
                if ipfs_off {
                    "OFF (KOTOBA_IPFS=off)"
                } else {
                    "ON"
                }
            );
            println!("KOTOBA_IPFS_ENDPOINT  : {ipfs_endpoint}");
            println!(
                "KOTOBA_PEERS          : {}",
                if peers.trim().is_empty() {
                    "(none — single-node)".into()
                } else {
                    peers.split_whitespace().collect::<Vec<_>>().join(", ")
                }
            );
            println!("default visibility    : {default_vis}");
            println!("hot cache             : {hot_mib} MiB");
        }

        Cmd::Health => {
            let url = format!("{}/health", cli.url.trim_end_matches('/'));
            let resp = reqwest::get(&url).await.context("GET /health failed")?;
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            println!("{status}  {body}");
            if !status.is_success() {
                std::process::exit(1);
            }
        }

        Cmd::Block(block_cmd) => {
            let client = build_client(&cli.token)?;
            match block_cmd {
                BlockCmd::Put { data_hex, file } => {
                    let bytes = match (data_hex, file) {
                        (Some(hex), None) => hex::decode(hex.trim()).context("invalid hex data")?,
                        (None, Some(path)) => std::fs::read(&path)
                            .with_context(|| format!("reading {}", path.display()))?,
                        (Some(_), Some(_)) => anyhow::bail!("specify data_hex OR --file, not both"),
                        (None, None) => {
                            // Read stdin
                            use std::io::Read;
                            let mut buf = Vec::new();
                            std::io::stdin().read_to_end(&mut buf)?;
                            buf
                        }
                    };

                    let data_b64 = B64.encode(&bytes);
                    let url = format!("{}/xrpc/{}", cli.url.trim_end_matches('/'), NSID_BLOCK_PUT);
                    let resp = client
                        .post(&url)
                        .json(&serde_json::json!({ "data_b64": data_b64 }))
                        .send()
                        .await
                        .context("POST block.put failed")?;
                    check_status(&resp)?;
                    let json: serde_json::Value = resp.json().await?;
                    println!("{}", json["cid"].as_str().unwrap_or("(no cid)"));
                }

                BlockCmd::Get { cid, out } => {
                    let url = format!(
                        "{}/xrpc/{}?cid={}",
                        cli.url.trim_end_matches('/'),
                        NSID_BLOCK_GET,
                        urlencoding::encode(&cid)
                    );
                    let resp = client
                        .get(&url)
                        .send()
                        .await
                        .context("GET block.get failed")?;
                    check_status(&resp)?;
                    let json: serde_json::Value = resp.json().await?;
                    let data_b64 = json["data_b64"].as_str().unwrap_or("");
                    let bytes = B64.decode(data_b64).context("invalid base64 in response")?;

                    if let Some(path) = out {
                        std::fs::write(&path, &bytes)
                            .with_context(|| format!("writing {}", path.display()))?;
                        eprintln!("wrote {} bytes to {}", bytes.len(), path.display());
                    } else {
                        print!("{}", B64.encode(&bytes));
                    }
                }
            }
        }

        Cmd::Quad(quad_cmd) => {
            let client = build_client(&cli.token)?;
            match quad_cmd {
                QuadCmd::Put {
                    graph,
                    subject,
                    predicate,
                    object,
                } => {
                    let url = format!(
                        "{}/xrpc/{}",
                        cli.url.trim_end_matches('/'),
                        NSID_QUAD_CREATE
                    );
                    let resp = client
                        .post(&url)
                        .json(&serde_json::json!({
                            "graph":     graph,
                            "subject":   subject,
                            "predicate": predicate,
                            "object":    object,
                        }))
                        .send()
                        .await
                        .context("POST quad.create failed")?;
                    check_status(&resp)?;
                    let json: serde_json::Value = resp.json().await?;
                    println!("{}", serde_json::to_string_pretty(&json)?);
                }

                QuadCmd::Retract {
                    graph,
                    subject,
                    predicate,
                    object,
                } => {
                    let url = format!(
                        "{}/xrpc/{}",
                        cli.url.trim_end_matches('/'),
                        NSID_QUAD_RETRACT
                    );
                    let resp = client
                        .post(&url)
                        .json(&serde_json::json!({
                            "graph":     graph,
                            "subject":   subject,
                            "predicate": predicate,
                            "object":    object,
                        }))
                        .send()
                        .await
                        .context("POST quad.retract failed")?;
                    check_status(&resp)?;
                    let json: serde_json::Value = resp.json().await?;
                    println!("{}", serde_json::to_string_pretty(&json)?);
                }

                QuadCmd::Query {
                    graph,
                    subject,
                    predicate,
                    limit,
                } => {
                    let mut url = format!(
                        "{}/xrpc/{}?graph={}&limit={}",
                        cli.url.trim_end_matches('/'),
                        NSID_GRAPH_QUERY,
                        urlencoding::encode(&graph),
                        limit,
                    );
                    if let Some(s) = &subject {
                        url.push_str(&format!("&subject={}", urlencoding::encode(s)));
                    }
                    if let Some(p) = &predicate {
                        url.push_str(&format!("&predicate={}", urlencoding::encode(p)));
                    }
                    let resp = client
                        .get(&url)
                        .send()
                        .await
                        .context("GET graph.query failed")?;
                    check_status(&resp)?;
                    let json: serde_json::Value = resp.json().await?;
                    println!("{}", serde_json::to_string_pretty(&json)?);
                }
            }
        }
    }

    Ok(())
}

fn run_inline_eval(expr: &str, wasm_out: Option<&Path>) -> Result<()> {
    let wasm = kotoba_clj::compile_expr_with_prelude(expr)
        .map_err(|err| anyhow::anyhow!("compile inline Kotoba expression: {err}"))?;
    if let Some(path) = wasm_out {
        std::fs::write(path, &wasm).with_context(|| format!("write {}", path.display()))?;
    }
    let value = kotoba_clj::run::run(&wasm, "main", &[])
        .map_err(|err| anyhow::anyhow!("run inline Kotoba expression: {err}"))?;
    println!("{value}");
    Ok(())
}

fn run_source_cmd(cmd: RunCmd) -> Result<()> {
    let body = load_kotoba_source(
        &cmd.cell,
        kotoba_clj::ReaderTarget::Kotoba,
        &cmd.source_path,
    )?;
    let src = format!("{}\n{}", kotoba_clj::prelude(), body);
    let wasm = kotoba_clj::compile_str(&src)
        .map_err(|err| anyhow::anyhow!("compile {}: {err}", cmd.cell.display()))?;
    let value = kotoba_clj::run::run(&wasm, &cmd.func, &cmd.args)
        .map_err(|err| anyhow::anyhow!("run {}#{}: {err}", cmd.cell.display(), cmd.func))?;
    println!("{value}");
    Ok(())
}

fn run_check_cmd(cmd: CheckCmd) -> Result<()> {
    let target = parse_reader_target(&cmd.reader_target)?;
    let body = load_kotoba_source(&cmd.cell, target, &cmd.source_path)?;
    let analyzer = kotoba_clj::selfhost::Analyzer::new()
        .map_err(|err| anyhow::anyhow!("selfhost analyzer: {err}"))?;
    if let Some(policy_path) = cmd.policy {
        let policy = read_policy(&policy_path)?;
        let gate = analyzer
            .check_compile_gate_with_reader_target(&body, target, &policy)
            .map_err(|err| anyhow::anyhow!("check {}: {err}", cmd.cell.display()))?;
        if !gate.subset.ok {
            anyhow::bail!("subset denied: {}", join_set(&gate.subset.denials));
        }
        if !gate.types.ok {
            anyhow::bail!("type denied: {}", join_set(&gate.types.denials));
        }
        if !gate.effects.ok {
            anyhow::bail!(
                "effect denied: {} violation(s)",
                gate.effects.violations.len()
            );
        }
        if !gate.policy.ok {
            anyhow::bail!(
                "policy denied: caps={} targets={}",
                join_set(&gate.policy.denials),
                join_set(&gate.policy.target_denials)
            );
        }
        println!("ok: {}", cmd.cell.display());
    } else {
        let policy = analyzer
            .minimal_policy_with_reader_target(&body, target)
            .map_err(|err| anyhow::anyhow!("analyze {}: {err}", cmd.cell.display()))?;
        println!("ok: {}", cmd.cell.display());
        println!("{}", policy.to_edn());
    }
    Ok(())
}

async fn run_db_cmd(cmd: DbCmd, base_url: &str, token: &Option<String>) -> Result<()> {
    match cmd {
        DbCmd::Status => {
            let url = format!("{}/health", base_url.trim_end_matches('/'));
            let resp = reqwest::get(&url).await.context("GET /health failed")?;
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            println!("{status}  {body}");
            if !status.is_success() {
                std::process::exit(1);
            }
        }
        DbCmd::Transact {
            graph,
            tx_edn,
            file,
            cacao,
        } => {
            let tx_edn = read_inline_file_or_stdin(tx_edn, file, "tx_edn")?;
            run_datomic_transact(base_url, token, &graph, &tx_edn, cacao).await?;
        }
        DbCmd::Q {
            query,
            graph,
            emit_cid,
            as_of,
            cacao,
        } => run_datomic_q(base_url, token, &query, &graph, emit_cid, as_of, cacao).await?,
        DbCmd::Sparql {
            query,
            limit,
            cacao,
            graph,
            max_hops,
        } => run_sparql(base_url, token, &query, limit, cacao, graph, max_hops).await?,
        DbCmd::Cypher {
            query,
            limit,
            cacao,
        } => run_kg_query(base_url, token, "cypher", &query, limit, cacao).await?,
        DbCmd::Put {
            graph,
            subject,
            predicate,
            object,
        } => run_quad_put(base_url, token, &graph, &subject, &predicate, &object).await?,
        DbCmd::Retract {
            graph,
            subject,
            predicate,
            object,
        } => run_quad_retract(base_url, token, &graph, &subject, &predicate, &object).await?,
        DbCmd::Query {
            graph,
            subject,
            predicate,
            limit,
        } => {
            run_quad_query(
                base_url,
                token,
                &graph,
                subject.as_deref(),
                predicate.as_deref(),
                limit,
            )
            .await?
        }
        DbCmd::Commit { author } => run_commit(base_url, author).await?,
    }
    Ok(())
}

fn run_git_cmd(cmd: GitCmd, base_url: &str) -> Result<()> {
    match cmd {
        GitCmd::Url { repo } => {
            println!("{}", kotoba_git_url(base_url, &repo));
        }
        GitCmd::Clone { repo, dir } => {
            let url = kotoba_git_url(base_url, &repo);
            let mut git = Command::new("git");
            git.arg("clone").arg(url);
            if let Some(dir) = dir {
                git.arg(dir);
            }
            run_process(git, "git clone")?;
        }
        GitCmd::Remote { repo, name } => {
            let url = kotoba_git_url(base_url, &repo);
            let exists = Command::new("git")
                .args(["remote", "get-url", &name])
                .output()
                .map(|out| out.status.success())
                .unwrap_or(false);
            let mut git = Command::new("git");
            if exists {
                git.args(["remote", "set-url", &name, &url]);
            } else {
                git.args(["remote", "add", &name, &url]);
            }
            run_process(git, "git remote")?;
            println!("{name}\t{url}");
        }
        GitCmd::Push { remote, refspec } => {
            let mut git = Command::new("git");
            git.args(["push", &remote, &refspec]);
            run_process(git, "git push")?;
        }
        GitCmd::Fetch { remote } => {
            let mut git = Command::new("git");
            git.args(["fetch", &remote]);
            run_process(git, "git fetch")?;
        }
        GitCmd::Status => {
            let mut git = Command::new("git");
            git.arg("status");
            run_process(git, "git status")?;
        }
    }
    Ok(())
}

fn run_rad_cmd(cmd: RadCmd) -> Result<()> {
    match cmd {
        RadCmd::Status => {
            let dir = std::env::var("KOTOBA_RAD_JOURNAL_DIR").unwrap_or_default();
            if dir.trim().is_empty() {
                println!("KOTOBA_RAD_JOURNAL_DIR: (unset)");
                println!("registered identities : 0");
                return Ok(());
            }
            let journal_count = std::fs::read_dir(&dir)
                .map(|entries| {
                    entries
                        .flatten()
                        .filter(|entry| {
                            entry
                                .path()
                                .to_string_lossy()
                                .ends_with(".identity.journal.edn")
                        })
                        .count()
                })
                .unwrap_or(0);
            println!("KOTOBA_RAD_JOURNAL_DIR: {dir}");
            println!("identity journals     : {journal_count}");
        }
        RadCmd::Plan => {
            println!("planned kotoba-rad CLI:");
            println!("  kotoba rad init --name <owner/repo> --private");
            println!("  kotoba rad import .git --actor <did>");
            println!("  kotoba rad refs");
            println!("  kotoba rad push --to <peer> --ref refs/heads/main");
            println!("  kotoba rad grant add <did>");
            println!("  kotoba rad verify --rid <cid>");
            println!();
            println!("implemented now:");
            println!("  kotoba git url|remote|clone|fetch|push|status");
            println!("  server-side rad delegate gating via KOTOBA_RAD_JOURNAL_DIR");
        }
    }
    Ok(())
}

fn run_wasm_cmd(cmd: WasmCmd) -> Result<()> {
    match cmd {
        WasmCmd::Build {
            cell,
            out,
            wit,
            source_path,
        } => {
            let wit = wit
                .map(|path| path.to_string_lossy().into_owned())
                .unwrap_or_else(|| DEFAULT_WASM_WIT_DIR.to_string());
            let out = out.unwrap_or_else(|| default_wasm_out(&cell));
            let body = load_kotoba_source(&cell, kotoba_clj::ReaderTarget::Kotoba, &source_path)?;
            let src = format!("{}\n{}", kotoba_clj::prelude(), body);
            let wasm = kotoba_clj::component::compile_kais_component_str(&src, &wit)
                .map_err(|err| anyhow::anyhow!("compile {}: {err}", cell.display()))?;
            std::fs::write(&out, &wasm).with_context(|| format!("write {}", out.display()))?;
            eprintln!(
                "[wasm build] {} -> {} ({} bytes)",
                cell.display(),
                out.display(),
                wasm.len()
            );
            Ok(())
        }
        WasmCmd::SafeBuild {
            cell,
            policy,
            out,
            selfhost_gate: _,
            reader_target,
            source_path,
        } => {
            let target = parse_reader_target(&reader_target)?;
            let out = out.unwrap_or_else(|| default_wasm_out(&cell));
            let policy = read_policy(&policy)?;
            let body = load_kotoba_source(&cell, target, &source_path)?;
            let wasm = kotoba_clj::compile_safe_kotoba_with_prelude_and_reader_target(
                &body, target, &policy,
            )
            .map_err(|err| anyhow::anyhow!("safe-build {} rejected: {err}", cell.display()))?;
            std::fs::write(&out, &wasm).with_context(|| format!("write {}", out.display()))?;
            print_safe_build_evidence(&cell, &body, target, &policy, &wasm);
            Ok(())
        }
        WasmCmd::SafePolicy {
            cell,
            out,
            selfhost_gate: _,
            reader_target,
            source_path,
        } => {
            let target = parse_reader_target(&reader_target)?;
            let body = load_kotoba_source(&cell, target, &source_path)?;
            let policy = kotoba_clj::minimal_policy_with_reader_target(&body, target)
                .map_err(|err| anyhow::anyhow!("analyze {}: {err}", cell.display()))?;
            let edn = policy.to_edn();
            if let Some(out) = out {
                std::fs::write(&out, &edn).with_context(|| format!("write {}", out.display()))?;
                eprintln!(
                    "[wasm safe-policy] {} -> {} (minimal least-privilege policy)",
                    cell.display(),
                    out.display()
                );
            } else {
                println!("{edn}");
            }
            Ok(())
        }
        WasmCmd::SelfhostInspect {
            cell,
            policy,
            reader_target,
            source_path,
            request_hex,
            json,
        } => {
            let target = parse_reader_target(&reader_target)?;
            let body = load_kotoba_source(&cell, target, &source_path)?;
            let request = kotoba_clj::selfhost::AnalyzerRequest::from_source_with_reader_target(
                &body, target,
            )
            .map_err(|err| {
                anyhow::anyhow!("build analyzer request for {}: {err}", cell.display())
            })?;
            let request_cbor_hex = if request_hex {
                Some(
                    request
                        .to_cbor()
                        .map(hex::encode)
                        .map_err(|err| anyhow::anyhow!("serialize analyzer request: {err}"))?,
                )
            } else {
                None
            };
            let analyzer = kotoba_clj::selfhost::Analyzer::new()
                .map_err(|err| anyhow::anyhow!("selfhost analyzer: {err}"))?;
            let summaries = analyzer
                .analyze_program_all_with_reader_target(&body, target)
                .map_err(|err| anyhow::anyhow!("run analyzer for {}: {err}", cell.display()))?;
            let type_check = analyzer
                .check_types_with_reader_target(&body, target)
                .map_err(|err| anyhow::anyhow!("check types for {}: {err}", cell.display()))?;
            let admission = match policy {
                Some(policy_path) => {
                    let policy = read_policy(&policy_path)?;
                    Some(
                        analyzer
                            .check_admission_with_reader_target(&body, target, &policy)
                            .map_err(|err| {
                                anyhow::anyhow!("check admission for {}: {err}", cell.display())
                            })?,
                    )
                }
                None => None,
            };
            if json {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&selfhost_inspect_json(
                        request.abi(),
                        target,
                        request.function_count(),
                        &summaries,
                        &type_check,
                        admission.as_ref(),
                        request_cbor_hex.as_deref(),
                    ))?
                );
            } else {
                println!("abi: {}", request.abi());
                println!("reader-target: {}", target.as_str());
                println!("functions: {}", request.function_count());
                for (name, summary) in &summaries {
                    println!(
                        "{name}: effects={{{}}} caps={{{}}} targets={{{}}}",
                        join_set(&summary.effects),
                        join_set(&summary.caps),
                        join_set(&summary.targets)
                    );
                }
                println!(
                    "types: {}",
                    if type_check.ok {
                        "ok".to_string()
                    } else {
                        format!("denied {{{}}}", join_set(&type_check.denials))
                    }
                );
                if let Some(admission) = &admission {
                    println!(
                        "admission: effects={} policy={}",
                        admission.effects.ok, admission.policy.ok
                    );
                }
                if let Some(hex) = request_cbor_hex {
                    println!("request-cbor-hex: {hex}");
                }
            }
            Ok(())
        }
    }
}

fn parse_reader_target(target: &str) -> Result<kotoba_clj::ReaderTarget> {
    kotoba_clj::ReaderTarget::parse(target)
        .ok_or_else(|| anyhow::anyhow!("unsupported reader target: {target}"))
}

fn read_policy(path: &Path) -> Result<kotoba_clj::Policy> {
    let src = std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    kotoba_clj::Policy::parse_edn(&src)
        .map_err(|err| anyhow::anyhow!("parse policy {}: {err}", path.display()))
}

fn load_kotoba_source(
    cell: &Path,
    target: kotoba_clj::ReaderTarget,
    source_paths: &[PathBuf],
) -> Result<String> {
    kotoba_clj::compat::load_file_graph_with_source_paths(cell, target, source_paths)
        .map_err(|err| anyhow::anyhow!("load {}: {err}", cell.display()))
}

fn default_wasm_out(cell: &Path) -> PathBuf {
    let path = cell.to_string_lossy();
    for ext in [".kotoba", ".clj", ".cljc", ".cljs"] {
        if let Some(stem) = path.strip_suffix(ext) {
            return PathBuf::from(format!("{stem}.wasm"));
        }
    }
    PathBuf::from(format!("{path}.wasm"))
}

fn print_safe_build_evidence(
    cell: &Path,
    body: &str,
    target: kotoba_clj::ReaderTarget,
    policy: &kotoba_clj::Policy,
    wasm: &[u8],
) {
    let ifaces = kotoba_clj::embedded_capability_ifaces(wasm);
    let surface = if ifaces.is_empty() {
        "none (pure)".to_string()
    } else {
        ifaces.join(", ")
    };
    eprintln!(
        "[wasm safe-build] {} ({} bytes)",
        cell.display(),
        wasm.len()
    );
    eprintln!("[wasm safe-build] admission gate: selfhost/kotoba");
    eprintln!("[wasm safe-build] reader target: {}", target.as_str());
    eprintln!("[wasm safe-build] capability surface: {surface}");

    let unused = kotoba_clj::unused_grants_with_reader_target(body, target, policy)
        .map_err(|err| err.to_string());
    if let Ok(unused) = unused {
        for finding in &unused {
            eprintln!("[wasm safe-build] warning: over-grant - {finding}");
        }
    }

    if let Ok(effects) = kotoba_clj::infer_effects_with_reader_target(body, target) {
        let mut rows: Vec<String> = effects
            .iter()
            .filter(|(_, effects)| !effects.is_empty())
            .map(|(function, effects)| format!("{function}={{{}}}", join_set(effects)))
            .collect();
        rows.sort();
        let report = if rows.is_empty() {
            "all pure".to_string()
        } else {
            rows.join(" ")
        };
        eprintln!("[wasm safe-build] inferred effects: {report}");
    }
}

fn join_set(values: &std::collections::BTreeSet<String>) -> String {
    values.iter().cloned().collect::<Vec<_>>().join(",")
}

fn set_vec(values: &std::collections::BTreeSet<String>) -> Vec<String> {
    values.iter().cloned().collect()
}

fn selfhost_inspect_json(
    abi: &str,
    target: kotoba_clj::ReaderTarget,
    function_count: usize,
    summaries: &std::collections::BTreeMap<String, kotoba_clj::selfhost::FunctionSummary>,
    type_check: &kotoba_clj::selfhost::TypeCheck,
    admission: Option<&kotoba_clj::selfhost::AdmissionCheck>,
    request_cbor_hex: Option<&str>,
) -> serde_json::Value {
    let functions: Vec<serde_json::Value> = summaries
        .iter()
        .map(|(name, summary)| {
            serde_json::json!({
                "name": name,
                "effects": set_vec(&summary.effects),
                "caps": set_vec(&summary.caps),
                "targets": set_vec(&summary.targets),
            })
        })
        .collect();
    serde_json::json!({
        "abi": abi,
        "readerTarget": target.as_str(),
        "request": {
            "functions": function_count,
            "cborHex": request_cbor_hex,
        },
        "functions": functions,
        "types": {
            "ok": type_check.ok,
            "denials": set_vec(&type_check.denials),
        },
        "admission": admission.map(admission_json),
    })
}

fn admission_json(admission: &kotoba_clj::selfhost::AdmissionCheck) -> serde_json::Value {
    serde_json::json!({
        "effects": {
            "ok": admission.effects.ok,
            "violations": admission.effects.violations.iter().map(|violation| {
                serde_json::json!({
                    "name": violation.name,
                    "used": set_vec(&violation.used),
                    "declared": set_vec(&violation.declared),
                    "missing": set_vec(&violation.missing),
                    "unknown": set_vec(&violation.unknown),
                })
            }).collect::<Vec<_>>(),
        },
        "policy": {
            "ok": admission.policy.ok,
            "used": set_vec(&admission.policy.used),
            "granted": set_vec(&admission.policy.granted),
            "denials": set_vec(&admission.policy.denials),
            "targetDenials": set_vec(&admission.policy.target_denials),
        },
    })
}

// ── Helpers ───────────────────────────────────────────────────────────────────

fn build_client(token: &Option<String>) -> Result<reqwest::Client> {
    let mut headers = reqwest::header::HeaderMap::new();
    if let Some(tok) = token {
        let val = reqwest::header::HeaderValue::from_str(&format!("Bearer {tok}"))
            .context("invalid token value")?;
        headers.insert(reqwest::header::AUTHORIZATION, val);
    }
    reqwest::Client::builder()
        .default_headers(headers)
        .build()
        .context("building HTTP client")
}

fn check_status(resp: &reqwest::Response) -> Result<()> {
    let status = resp.status();
    if !status.is_success() {
        anyhow::bail!("server returned {status}");
    }
    Ok(())
}

fn read_inline_file_or_stdin(
    inline: Option<String>,
    file: Option<PathBuf>,
    label: &str,
) -> Result<String> {
    match (inline, file) {
        (Some(src), None) => Ok(src),
        (None, Some(path)) => {
            std::fs::read_to_string(&path).with_context(|| format!("read {}", path.display()))
        }
        (Some(_), Some(_)) => anyhow::bail!("specify {label} OR --file, not both"),
        (None, None) => {
            use std::io::Read;
            let mut src = String::new();
            std::io::stdin()
                .read_to_string(&mut src)
                .with_context(|| format!("read {label} from stdin"))?;
            Ok(src)
        }
    }
}

async fn run_datomic_transact(
    base_url: &str,
    token: &Option<String>,
    graph: &str,
    tx_edn: &str,
    cacao: Option<String>,
) -> Result<()> {
    let client = build_client(token)?;
    let endpoint = format!(
        "{}/xrpc/com.etzhayyim.apps.kotoba.datomic.transact",
        base_url.trim_end_matches('/')
    );
    let resp = client
        .post(&endpoint)
        .json(&serde_json::json!({
            "graph": graph,
            "tx_edn": tx_edn,
            "cacaoB64": cacao,
        }))
        .send()
        .await
        .with_context(|| format!("POST {endpoint}"))?;
    check_status(&resp)?;
    let json: serde_json::Value = resp.json().await?;
    println!("{}", serde_json::to_string_pretty(&json)?);
    Ok(())
}

async fn run_quad_put(
    base_url: &str,
    token: &Option<String>,
    graph: &str,
    subject: &str,
    predicate: &str,
    object: &str,
) -> Result<()> {
    let client = build_client(token)?;
    let url = format!(
        "{}/xrpc/{}",
        base_url.trim_end_matches('/'),
        NSID_QUAD_CREATE
    );
    let resp = client
        .post(&url)
        .json(&serde_json::json!({
            "graph": graph,
            "subject": subject,
            "predicate": predicate,
            "object": object,
        }))
        .send()
        .await
        .context("POST quad.create failed")?;
    check_status(&resp)?;
    let json: serde_json::Value = resp.json().await?;
    println!("{}", serde_json::to_string_pretty(&json)?);
    Ok(())
}

async fn run_quad_retract(
    base_url: &str,
    token: &Option<String>,
    graph: &str,
    subject: &str,
    predicate: &str,
    object: &str,
) -> Result<()> {
    let client = build_client(token)?;
    let url = format!(
        "{}/xrpc/{}",
        base_url.trim_end_matches('/'),
        NSID_QUAD_RETRACT
    );
    let resp = client
        .post(&url)
        .json(&serde_json::json!({
            "graph": graph,
            "subject": subject,
            "predicate": predicate,
            "object": object,
        }))
        .send()
        .await
        .context("POST quad.retract failed")?;
    check_status(&resp)?;
    let json: serde_json::Value = resp.json().await?;
    println!("{}", serde_json::to_string_pretty(&json)?);
    Ok(())
}

async fn run_quad_query(
    base_url: &str,
    token: &Option<String>,
    graph: &str,
    subject: Option<&str>,
    predicate: Option<&str>,
    limit: u64,
) -> Result<()> {
    let client = build_client(token)?;
    let mut url = format!(
        "{}/xrpc/{}?graph={}&limit={}",
        base_url.trim_end_matches('/'),
        NSID_GRAPH_QUERY,
        urlencoding::encode(graph),
        limit,
    );
    if let Some(s) = subject {
        url.push_str(&format!("&subject={}", urlencoding::encode(s)));
    }
    if let Some(p) = predicate {
        url.push_str(&format!("&predicate={}", urlencoding::encode(p)));
    }
    let resp = client
        .get(&url)
        .send()
        .await
        .context("GET graph.query failed")?;
    check_status(&resp)?;
    let json: serde_json::Value = resp.json().await?;
    println!("{}", serde_json::to_string_pretty(&json)?);
    Ok(())
}

fn kotoba_git_url(base_url: &str, repo: &str) -> String {
    format!(
        "{}/git/{}",
        base_url.trim_end_matches('/'),
        repo.trim_matches('/')
    )
}

fn run_process(mut cmd: Command, label: &str) -> Result<()> {
    eprintln!("[kotoba] {label}: {:?}", cmd);
    let status = cmd.status().with_context(|| format!("spawn {label}"))?;
    if !status.success() {
        anyhow::bail!("{label} failed with {status}");
    }
    Ok(())
}

/// A signer that produces a fresh DAG-CBOR base64 CACAO with a caller-chosen
/// nonce on every call.  Used by `kotoba bench --cacao-seed` to sustain a
/// CACAO-gated loadtest beyond iter 1 (CAIP-74 nonce is single-use).
struct CacaoSigner {
    sk: ed25519_dalek::SigningKey,
    did: String,
    graph_scope: String,
}

impl CacaoSigner {
    fn from_seed_hex(seed: &str, graph: &str, private: bool) -> Result<Self> {
        use ed25519_dalek::SigningKey;
        let bytes = hex::decode(seed.trim()).context("cacao seed must be hex")?;
        if bytes.len() != 32 {
            anyhow::bail!("cacao seed must decode to 32 bytes");
        }
        let mut arr = [0u8; 32];
        arr.copy_from_slice(&bytes);
        let sk = SigningKey::from_bytes(&arr);
        let did = kotoba_auth::did_key::ed25519_pubkey_to_did_key(sk.verifying_key().as_bytes());
        let graph_scope = if private {
            format!("private/{did}")
        } else {
            graph.to_string()
        };
        Ok(Self {
            sk,
            did,
            graph_scope,
        })
    }

    fn sign_with_nonce(&self, nonce: &str) -> String {
        use base64::{
            engine::general_purpose::{STANDARD as B64, URL_SAFE_NO_PAD},
            Engine,
        };
        use ed25519_dalek::Signer;
        use kotoba_auth::{Cacao, CacaoHeader, CacaoPayload, CacaoSig};
        let mut cacao = Cacao {
            h: CacaoHeader {
                t: "caip122".into(),
            },
            p: CacaoPayload {
                iss: self.did.clone(),
                aud: self.did.clone(),
                issued_at: "2026-05-26T00:00:00Z".into(),
                expiry: Some("2099-01-01T00:00:00Z".into()),
                nonce: nonce.to_string(),
                domain: "kotoba.bench".into(),
                statement: None,
                version: "1".into(),
                resources: vec![
                    format!("kotoba://graph/{}", self.graph_scope),
                    "kotoba://can/datom:read".into(),
                ],
            },
            s: CacaoSig {
                t: "EdDSA".into(),
                s: String::new(),
            },
        };
        let msg = cacao.siwe_message();
        let sig: ed25519_dalek::Signature = self.sk.sign(msg.as_bytes());
        cacao.s.s = URL_SAFE_NO_PAD.encode(sig.to_bytes());
        let mut cbor = Vec::new();
        ciborium::into_writer(&cacao, &mut cbor).expect("cbor encode");
        B64.encode(&cbor)
    }
}

/// Build a non-expiring JWT-shaped token. The kotoba server's Authenticated
/// tier accepts any Bearer token whose `exp` claim is in the future — it does
/// NOT verify the signature (the upstream PDS / edge BFF is the trust
/// boundary).  This lets the demo run without an external identity service.
fn demo_token() -> String {
    use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
    let header = URL_SAFE_NO_PAD.encode(br#"{"alg":"HS256","typ":"JWT"}"#);
    let payload = URL_SAFE_NO_PAD.encode(br#"{"sub":"did:key:zKotobaDemo","exp":9999999999}"#);
    format!("{header}.{payload}.demosig")
}

/// HTTP SPARQL loadtest.  Issues `iters` POSTs of the same query with up to
/// `concurrency` in-flight clients; prints latency percentiles + aggregate QPS.
#[allow(clippy::too_many_arguments)]
async fn run_bench(
    base_url: &str,
    token_in: &str,
    query: &str,
    iters: usize,
    concurrency: usize,
    cacao: Option<String>,
    cacao_seed: Option<String>,
    cacao_graph: String,
    cacao_private: bool,
    max_hops: usize,
) -> Result<()> {
    use std::sync::Arc;
    use std::time::{Duration, Instant};

    let base = base_url.trim_end_matches('/');
    let client = reqwest::Client::new();
    let token: String = if token_in.contains('.') {
        token_in.to_string()
    } else {
        demo_token()
    };

    // Resolve the CACAO signer (when --cacao-seed given) so each worker can
    // forge a fresh CACAO with unique nonce per request — the only way to
    // sustain a CACAO-gated bench past iter 1.
    let signer: Option<CacaoSigner> = if let Some(seed) = &cacao_seed {
        Some(CacaoSigner::from_seed_hex(
            seed,
            &cacao_graph,
            cacao_private,
        )?)
    } else {
        None
    };

    let concurrency = concurrency.max(1);
    let mode = match (&cacao, &signer) {
        (_, Some(_)) => "CACAO-gated (fresh CACAO per request)",
        (Some(_), _) => "CACAO-gated (single CACAO — likely 1 request only)",
        (None, None) => "unauthed",
    };
    println!("→ benchmarking {iters} iters × concurrency {concurrency} ({mode}):");
    println!("    {query}");

    let url = Arc::new(format!(
        "{base}/xrpc/com.etzhayyim.apps.kotoba.graph.sparql"
    ));
    let token = Arc::new(token);
    let cacao_static = Arc::new(cacao);
    let signer = Arc::new(signer);
    let query = Arc::new(query.to_string());

    let wall_start = Instant::now();

    // Per-run nonce salt — ensures CACAO nonces from this bench run do not
    // collide with nonces from prior bench runs (the server's NonceStore
    // persists across requests but inside one server process).
    let run_salt = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();

    // Spawn `concurrency` workers; each consumes from a shared atomic counter
    // until `iters` requests have been dispatched.
    use std::sync::atomic::{AtomicUsize, Ordering};
    let next = Arc::new(AtomicUsize::new(0));
    let mut handles = Vec::with_capacity(concurrency);

    for worker_id in 0..concurrency {
        let client = client.clone();
        let url = Arc::clone(&url);
        let token = Arc::clone(&token);
        let next = Arc::clone(&next);
        let cacao_static = Arc::clone(&cacao_static);
        let signer = Arc::clone(&signer);
        let query = Arc::clone(&query);
        handles.push(tokio::spawn(async move {
            let mut local: Vec<Duration> = Vec::new();
            let mut last_count: u64 = 0;
            loop {
                let i = next.fetch_add(1, Ordering::Relaxed);
                if i >= iters {
                    break;
                }
                // Per-request CACAO when --cacao-seed is set.  Nonce must be
                // unique across requests so the server's NonceStore admits it.
                let cacao_field: Option<String> = match (&*signer, cacao_static.as_ref()) {
                    (Some(s), _) => {
                        Some(s.sign_with_nonce(&format!("kb-{run_salt}-{worker_id}-{i}")))
                    }
                    (None, Some(c)) => Some(c.clone()),
                    (None, None) => None,
                };
                let body = serde_json::json!({
                    "query":    &*query,
                    "limit":    100_000,
                    "cacaoB64": cacao_field,
                    "maxHops":  max_hops,
                });
                let t0 = Instant::now();
                let resp = match client
                    .post(url.as_str())
                    .header("Authorization", format!("Bearer {token}"))
                    .json(&body)
                    .send()
                    .await
                {
                    Ok(r) => r,
                    Err(_) => continue,
                };
                if !resp.status().is_success() {
                    continue;
                }
                let v: serde_json::Value = match resp.json().await {
                    Ok(v) => v,
                    Err(_) => continue,
                };
                local.push(t0.elapsed());
                last_count = v["count"].as_u64().unwrap_or(0);
            }
            (local, last_count)
        }));
    }

    let mut samples: Vec<Duration> = Vec::with_capacity(iters);
    let mut last_count: u64 = 0;
    for h in handles {
        let (mut local, n) = h.await.context("bench worker join")?;
        samples.append(&mut local);
        if n > 0 {
            last_count = n;
        }
    }
    let wall = wall_start.elapsed();
    if samples.is_empty() {
        anyhow::bail!("no successful samples — server may be unreachable");
    }
    samples.sort_unstable();

    let pct = |q: f64| -> u128 {
        let idx = ((samples.len() as f64 * q) as usize).min(samples.len() - 1);
        samples[idx].as_micros()
    };
    let mean: u128 =
        (samples.iter().map(|d| d.as_micros()).sum::<u128>()) / (samples.len() as u128);
    let qps = samples.len() as f64 / wall.as_secs_f64();

    println!("\nresults (concurrency = {concurrency}):");
    println!("  count per query : {last_count}");
    println!("  successful      : {} / {iters}", samples.len());
    println!("  p50             : {:.2} ms", pct(0.50) as f64 / 1000.0);
    println!("  p95             : {:.2} ms", pct(0.95) as f64 / 1000.0);
    println!("  p99             : {:.2} ms", pct(0.99) as f64 / 1000.0);
    println!("  mean            : {:.2} ms", mean as f64 / 1000.0);
    println!("  wall            : {:.2} s", wall.as_secs_f64());
    println!("  qps             : {:.1} req/s", qps);
    Ok(())
}

/// End-to-end smoke: ingest a sample entity then run all four SPARQL forms.
async fn run_demo(base_url: &str, token_in: &str) -> Result<()> {
    let base = base_url.trim_end_matches('/');
    let client = reqwest::Client::new();
    // If the caller passed a placeholder lacking JWT shape, upgrade to a
    // proper JWT-shaped token so the Bearer-auth gate accepts us.
    let token: String = if token_in.contains('.') {
        token_in.to_string()
    } else {
        demo_token()
    };
    let token = &token;

    let bearer =
        |req: reqwest::RequestBuilder| req.header("Authorization", format!("Bearer {token}"));

    // 1. ingest
    println!("→ ingest sample entity (kg.ingest)");
    let ingest_body = serde_json::json!({
        "id":         "kotoba-demo-001",
        "type":       "Person",
        "labelEn":    "Demo Subject",
        "confidence": "0.95",
        "license":    "CC0-1.0",
        "sourceId":   "kotoba-demo",
        "claims": [
            { "pred": "role",       "value": "admin" },
            { "pred": "occupation", "value": "engineer" }
        ],
        "relations": []
    });
    let resp = bearer(
        client
            .post(format!("{base}/xrpc/com.etzhayyim.apps.kotobase.kg.ingest"))
            .json(&ingest_body),
    )
    .send()
    .await
    .context("kg.ingest POST")?;
    check_status(&resp)?;
    let put: serde_json::Value = resp.json().await.context("ingest JSON")?;
    let subj_cid = put["subjectCid"]
        .as_str()
        .ok_or_else(|| anyhow::anyhow!("ingest response missing subjectCid: {put}"))?
        .to_string();
    println!("  ingested subjectCid: {subj_cid}");

    // 2. SELECT
    println!("→ SELECT * WHERE {{ ?s <kg/claim/role> ?o }}");
    let sel = sparql_req(
        &client,
        base,
        token.as_str(),
        r#"SELECT * WHERE { ?s <kg/claim/role> ?o }"#,
    )
    .await?;
    println!("  count={} (≥1 expected)", sel["count"]);

    // 3. ASK true
    println!("→ ASK {{ ?s <kg/claim/role> \"admin\" }}");
    let ask = sparql_req(
        &client,
        base,
        token.as_str(),
        r#"ASK { ?s <kg/claim/role> "admin" }"#,
    )
    .await?;
    println!("  result={}", ask["result"]);

    // 4. DESCRIBE the subject
    println!("→ DESCRIBE <cid:{subj_cid}>");
    let descr = sparql_req(
        &client,
        base,
        token.as_str(),
        &format!("DESCRIBE <cid:{subj_cid}>"),
    )
    .await?;
    println!("  count={} quads about the subject", descr["count"]);

    // 5. CONSTRUCT
    println!("→ CONSTRUCT {{ ?s <admin> \"yes\" }} WHERE {{ ?s <kg/claim/role> \"admin\" }}");
    let con = sparql_req(
        &client,
        base,
        token.as_str(),
        r#"CONSTRUCT { ?s <admin> "yes" } WHERE { ?s <kg/claim/role> "admin" }"#,
    )
    .await?;
    println!("  count={} constructed quads", con["count"]);

    println!("\n✓ demo complete — all four SPARQL forms executed against IPFS-backed cold path");
    Ok(())
}

async fn sparql_req(
    client: &reqwest::Client,
    base: &str,
    token: &str,
    query: &str,
) -> Result<serde_json::Value> {
    let resp = client
        .post(format!(
            "{base}/xrpc/com.etzhayyim.apps.kotoba.graph.sparql"
        ))
        .header("Authorization", format!("Bearer {token}"))
        .json(&serde_json::json!({ "query": query, "limit": 1000 }))
        .send()
        .await
        .context("kg.sparql POST")?;
    check_status(&resp)?;
    resp.json().await.context("sparql JSON")
}

/// POST a SPARQL query (any form) to the direct-SPARQL endpoint.
/// POST a Datomic Datalog query to the running server's `datomic.q` endpoint.
/// With `emit_cid`, the response carries content-addressed provenance CIDs
/// (query_spec_cid / query_job_cid / result_cid) — for Public graphs the result
/// envelope is fetchable via `kotoba block-get <result_cid>`.
async fn run_datomic_q(
    base_url: &str,
    token: &Option<String>,
    query_edn: &str,
    graph: &str,
    emit_cid: bool,
    as_of: Option<String>,
    cacao: Option<String>,
) -> Result<()> {
    let url = format!(
        "{}/xrpc/com.etzhayyim.apps.kotoba.datomic.q",
        base_url.trim_end_matches('/')
    );
    let client = build_client(token)?;
    // datomic.q uses snake_case field names (unlike the camelCase graph.sparql).
    let body = serde_json::json!({
        "graph":     graph,
        "query_edn": query_edn,
        "emit_cid":  emit_cid,
        "as_of":     as_of,
        "cacao_b64": cacao,
    });
    let resp = client
        .post(&url)
        .json(&body)
        .send()
        .await
        .context("POST kotoba.datomic.q failed")?;
    check_status(&resp)?;
    let v: serde_json::Value = resp.json().await.context("decode kotoba.datomic.q JSON")?;
    println!("{}", serde_json::to_string_pretty(&v)?);
    Ok(())
}

async fn run_sparql(
    base_url: &str,
    token: &Option<String>,
    query: &str,
    limit: usize,
    cacao: Option<String>,
    graph: Option<String>,
    max_hops: usize,
) -> Result<()> {
    let url = format!(
        "{}/xrpc/com.etzhayyim.apps.kotoba.graph.sparql",
        base_url.trim_end_matches('/')
    );
    let client = build_client(token)?;
    let body = serde_json::json!({
        "query":    query,
        "limit":    limit,
        "cacaoB64": cacao,
        "graph":    graph,
        "maxHops":  max_hops,
    });
    let resp = client
        .post(&url)
        .json(&body)
        .send()
        .await
        .context("POST kotoba.graph.sparql failed")?;
    check_status(&resp)?;
    let v: serde_json::Value = resp
        .json()
        .await
        .context("decode kotoba.graph.sparql JSON")?;
    println!("{}", serde_json::to_string_pretty(&v)?);
    Ok(())
}

/// POST a SPARQL/Cypher query to the running server's
/// `/xrpc/com.etzhayyim.apps.kotobase.kg.query` endpoint.  The server evaluates over
/// IPFS-backed cold storage (Kubo HTTP via KOTOBA_IPFS_ENDPOINT or a
/// DistributedBlockStore multi-peer setup).
async fn run_kg_query(
    base_url: &str,
    token: &Option<String>,
    lang: &str,
    query: &str,
    limit: usize,
    cacao: Option<String>,
) -> Result<()> {
    let url = format!(
        "{}/xrpc/com.etzhayyim.apps.kotobase.kg.query",
        base_url.trim_end_matches('/')
    );
    let client = build_client(token)?;
    let body = serde_json::json!({
        "lang":     lang,
        "query":    query,
        "limit":    limit,
        "cacaoB64": cacao,
    });
    let resp = client
        .post(&url)
        .json(&body)
        .send()
        .await
        .context("POST kg.query failed")?;
    check_status(&resp)?;
    let v: serde_json::Value = resp.json().await.context("decode kg.query JSON")?;
    println!("{}", serde_json::to_string_pretty(&v)?);
    Ok(())
}

/// Build an operator Bearer JWT from the local persisted identity.
///
/// Mirrors `run_commit`: the server's `require_operator_auth` accepts a JWT
/// whose `sub` claim equals the operator DID.  Requires `kotoba init` to have
/// run on this machine with the same identity `kotoba serve` uses.
fn operator_token() -> Result<String> {
    use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
    let id = kotoba_vault::AgentIdentity::from_env();
    if id.ephemeral {
        anyhow::bail!(
            "no persisted identity — media commands need a stable operator DID. \
             Run `kotoba init` first, then restart `kotoba serve`."
        );
    }
    let header = URL_SAFE_NO_PAD.encode(br#"{"alg":"HS256","typ":"JWT"}"#);
    let payload =
        URL_SAFE_NO_PAD.encode(format!(r#"{{"sub":"{}","exp":9999999999}}"#, id.did).as_bytes());
    Ok(format!("{header}.{payload}.kotoba-cli-media"))
}

/// GET media.search — cross-modal text→any-modality retrieval.
async fn run_media_search(
    base_url: &str,
    query: &str,
    top_k: usize,
    modality: Option<String>,
) -> Result<()> {
    let token = operator_token()?;
    let mut params: Vec<(&str, String)> =
        vec![("q", query.to_string()), ("topK", top_k.to_string())];
    if let Some(m) = &modality {
        params.push(("modality", m.clone()));
    }
    let url = format!(
        "{}/xrpc/com.etzhayyim.apps.kotoba.media.search",
        base_url.trim_end_matches('/')
    );
    let resp = reqwest::Client::new()
        .get(&url)
        .header("Authorization", format!("Bearer {token}"))
        .query(&params)
        .send()
        .await
        .context("GET media.search failed")?;
    check_status(&resp)?;
    let v: serde_json::Value = resp.json().await.context("decode media.search JSON")?;
    println!("{}", serde_json::to_string_pretty(&v)?);
    Ok(())
}

/// POST media.ingest — ingest a single file into the shared search space.
async fn run_media_ingest(
    base_url: &str,
    path: &str,
    caption: Option<String>,
    title: Option<String>,
    page: i64,
) -> Result<()> {
    let token = operator_token()?;
    let bytes = std::fs::read(path).with_context(|| format!("read {path}"))?;
    let mime = mime_for_path(path);
    let title = title.or_else(|| {
        std::path::Path::new(path)
            .file_name()
            .and_then(|n| n.to_str())
            .map(|s| s.to_string())
    });
    let item = serde_json::json!({
        "mime":    mime,
        "b64":     B64.encode(&bytes),
        "title":   title,
        "source":  path,
        "page":    page,
        "caption": caption,
    });
    let url = format!(
        "{}/xrpc/com.etzhayyim.apps.kotoba.media.ingest",
        base_url.trim_end_matches('/')
    );
    let resp = reqwest::Client::new()
        .post(&url)
        .header("Authorization", format!("Bearer {token}"))
        .json(&serde_json::json!({ "items": [item] }))
        .send()
        .await
        .context("POST media.ingest failed")?;
    check_status(&resp)?;
    let v: serde_json::Value = resp.json().await.context("decode media.ingest JSON")?;
    println!("{}", serde_json::to_string_pretty(&v)?);
    Ok(())
}

/// GET media.status — index summary + per-modality breakdown.
async fn run_media_status(base_url: &str) -> Result<()> {
    let token = operator_token()?;
    let url = format!(
        "{}/xrpc/com.etzhayyim.apps.kotoba.media.status",
        base_url.trim_end_matches('/')
    );
    let resp = reqwest::Client::new()
        .get(&url)
        .header("Authorization", format!("Bearer {token}"))
        .send()
        .await
        .context("GET media.status failed")?;
    check_status(&resp)?;
    let v: serde_json::Value = resp.json().await.context("decode media.status JSON")?;
    println!("{}", serde_json::to_string_pretty(&v)?);
    Ok(())
}

/// Map a file extension to a MIME type (best-effort; octet-stream fallback).
/// Mirrors `kotoba_ingest::media`'s server-side mapping so CLI and server agree.
fn mime_for_path(path: &str) -> String {
    let ext = std::path::Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    match ext.as_str() {
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "webp" => "image/webp",
        "bmp" => "image/bmp",
        "tif" | "tiff" => "image/tiff",
        "svg" => "image/svg+xml",
        "mp4" | "m4v" => "video/mp4",
        "webm" => "video/webm",
        "mov" => "video/quicktime",
        "mkv" => "video/x-matroska",
        "avi" => "video/x-msvideo",
        "mp3" => "audio/mpeg",
        "wav" => "audio/wav",
        "flac" => "audio/flac",
        "ogg" | "oga" => "audio/ogg",
        "m4a" => "audio/mp4",
        "pdf" => "application/pdf",
        "epub" => "application/epub+zip",
        "doc" => "application/msword",
        "docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt" | "md" => "text/plain",
        _ => "application/octet-stream",
    }
    .to_string()
}

/// POST kg.commit to seal pending writes into a ProllyTree commit + checkpoint.
///
/// Operator auth: server's `require_operator_auth` accepts a Bearer JWT whose
/// `sub` claim equals the operator DID.  We construct one from the local
/// Keychain identity, so this works as long as `kotoba init` ran on this
/// machine and `kotoba serve` is using the same identity.
async fn run_commit(base_url: &str, author: Option<String>) -> Result<()> {
    use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};

    let id = kotoba_vault::AgentIdentity::from_env();
    if id.ephemeral {
        anyhow::bail!(
            "no persisted identity — `kotoba commit` needs a stable operator DID. \
             Run `kotoba init` first, then restart `kotoba serve`."
        );
    }
    let header = URL_SAFE_NO_PAD.encode(br#"{"alg":"HS256","typ":"JWT"}"#);
    let payload =
        URL_SAFE_NO_PAD.encode(format!(r#"{{"sub":"{}","exp":9999999999}}"#, id.did).as_bytes());
    let token = format!("{header}.{payload}.kotoba-cli-commit");

    let body = serde_json::json!({ "author": author });
    let url = format!(
        "{}/xrpc/com.etzhayyim.apps.kotobase.kg.commit",
        base_url.trim_end_matches('/')
    );
    let resp = reqwest::Client::new()
        .post(&url)
        .header("Authorization", format!("Bearer {token}"))
        .json(&body)
        .send()
        .await
        .context("POST kg.commit failed")?;
    let status = resp.status();
    let body_text = resp.text().await.unwrap_or_default();
    if !status.is_success() {
        anyhow::bail!("server returned {status}: {body_text}");
    }
    let v: serde_json::Value = serde_json::from_str(&body_text).context("decode kg.commit JSON")?;
    println!(
        "commit CID  : {}",
        v["commitCid"].as_str().unwrap_or("<missing>")
    );
    println!("elapsed     : {} ms", v["elapsedMs"].as_u64().unwrap_or(0));
    Ok(())
}

// ── Update check (etzhayyim/kotoba) ───────────────────────────────────────────

/// Short SHA baked at build time by `build.rs`.  "unknown" outside a git tree
/// or when the build script did not run (e.g. cargo install from a tarball).
const BUILD_COMMIT: &str = match option_env!("KOTOBA_BUILD_COMMIT") {
    Some(s) => s,
    None => "unknown",
};

const UPDATE_CACHE_TTL_SECS: u64 = 24 * 3600;
const UPDATE_CHECK_URL: &str = "https://api.github.com/repos/etzhayyim/kotoba/commits/main";

#[derive(serde::Serialize, serde::Deserialize)]
struct UpdateCache {
    checked_at: u64, // unix seconds
    upstream_sha: String,
}

fn update_cache_path() -> Option<std::path::PathBuf> {
    let home = std::env::var_os("HOME")?;
    Some(
        std::path::PathBuf::from(home)
            .join(".etzhayyim")
            .join("kotoba-update.json"),
    )
}

fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn read_update_cache() -> Option<UpdateCache> {
    let path = update_cache_path()?;
    let raw = std::fs::read_to_string(&path).ok()?;
    serde_json::from_str(&raw).ok()
}

fn write_update_cache(c: &UpdateCache) -> Result<()> {
    let path = update_cache_path().ok_or_else(|| anyhow::anyhow!("no HOME"))?;
    if let Some(p) = path.parent() {
        std::fs::create_dir_all(p)?;
    }
    std::fs::write(&path, serde_json::to_vec(c)?)?;
    Ok(())
}

/// Return a short notice string when an upstream update is available.
/// `None` means up-to-date, no network failure, or fresh-enough cache that
/// matches the local commit.  Stays silent on any failure so the user is
/// never blocked by a flaky network.
async fn check_for_update(force: bool) -> Option<String> {
    if BUILD_COMMIT == "unknown" {
        return None;
    }

    if !force {
        if let Some(c) = read_update_cache() {
            if now_secs().saturating_sub(c.checked_at) < UPDATE_CACHE_TTL_SECS {
                return notify(&c.upstream_sha);
            }
        }
    }

    // One-shot GitHub fetch.  Short timeout so this never blocks startup.
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(3))
        .build()
        .ok()?;
    let resp = client
        .get(UPDATE_CHECK_URL)
        .header("User-Agent", format!("kotoba-cli/{BUILD_COMMIT}"))
        .header("Accept", "application/vnd.github+json")
        .send()
        .await
        .ok()?;
    if !resp.status().is_success() {
        return None;
    }
    let body: serde_json::Value = resp.json().await.ok()?;
    let upstream_full = body.get("sha")?.as_str()?.to_string();
    let upstream_sha = upstream_full.chars().take(12).collect::<String>();

    let _ = write_update_cache(&UpdateCache {
        checked_at: now_secs(),
        upstream_sha: upstream_sha.clone(),
    });

    notify(&upstream_sha)
}

fn notify(upstream_sha: &str) -> Option<String> {
    if upstream_sha == BUILD_COMMIT {
        return None;
    }
    Some(format!(
        "→ kotoba update available: upstream {upstream} ≠ local {local}\n  \
         brew upgrade etzhayyim/kotoba/kotoba   # or `brew reinstall --HEAD`\n  \
         see  https://github.com/etzhayyim/kotoba/commits/main",
        upstream = upstream_sha,
        local = BUILD_COMMIT,
    ))
}

// ── Key custody (R3) ─────────────────────────────────────────────────────────

fn parse_hex32(s: &str, what: &str) -> Result<[u8; 32]> {
    let b = hex::decode(s.trim()).with_context(|| format!("{what}: invalid hex"))?;
    b.try_into()
        .map_err(|v: Vec<u8>| anyhow::anyhow!("{what}: need 32 bytes, got {}", v.len()))
}

/// Parse `DID:PUBKEY_HEX` into (did, X25519 pubkey).
fn parse_custodian(spec: &str) -> Result<(String, x25519_dalek::PublicKey)> {
    // did:key:... contains colons, so split on the LAST colon.
    let (did, pk_hex) = spec
        .rsplit_once(':')
        .ok_or_else(|| anyhow::anyhow!("custodian must be DID:PUBKEY_HEX: {spec}"))?;
    let pk = parse_hex32(pk_hex, "custodian pubkey")?;
    Ok((did.to_string(), x25519_dalek::PublicKey::from(pk)))
}

fn run_key_cmd(cmd: KeyCmd) -> Result<()> {
    match cmd {
        KeyCmd::GenKey => {
            let sk = x25519_dalek::StaticSecret::random_from_rng(rand_core::OsRng);
            let pk = x25519_dalek::PublicKey::from(&sk);
            println!(
                "{}",
                serde_json::json!({
                    "x25519_secret_hex": hex::encode(sk.to_bytes()),
                    "x25519_pubkey_hex": hex::encode(pk.as_bytes()),
                })
            );
            Ok(())
        }

        KeyCmd::Deal {
            key_hex,
            threshold,
            custodians,
            epoch,
        } => {
            let key = parse_hex32(&key_hex, "key_hex")?;
            let parsed: Vec<(String, x25519_dalek::PublicKey)> = custodians
                .iter()
                .map(|c| parse_custodian(c))
                .collect::<Result<_>>()?;
            let shares = kotoba_custody::split_key_epoch(&key, threshold, &parsed, epoch)
                .map_err(|e| anyhow::anyhow!("split_key: {e}"))?;
            // One JSON object per line: { custodian, share } — feed each to
            // key.depositShare on that custodian.
            for (spec, share) in custodians.iter().zip(&shares) {
                let did = spec.rsplit_once(':').map(|(d, _)| d).unwrap_or(spec);
                println!(
                    "{}",
                    serde_json::json!({ "custodian": did, "share": share })
                );
            }
            eprintln!(
                "dealt {} shares (threshold {threshold}, epoch {epoch}); deposit each to its custodian via key.depositShare",
                shares.len()
            );
            Ok(())
        }

        KeyCmd::Combine {
            grants,
            requester_sk_hex,
            threshold,
        } => {
            let sk = x25519_dalek::StaticSecret::from(parse_hex32(
                &requester_sk_hex,
                "requester_sk_hex",
            )?);
            let mut parsed = Vec::with_capacity(grants.len());
            for path in &grants {
                let bytes = std::fs::read(path)
                    .with_context(|| format!("read grant {}", path.display()))?;
                let grant: kotoba_custody::GrantedShare = serde_json::from_slice(&bytes)
                    .with_context(|| format!("parse grant {}", path.display()))?;
                parsed.push(grant);
            }
            let key = kotoba_custody::combine_granted(threshold, &parsed, &sk)
                .map_err(|e| anyhow::anyhow!("combine: {e}"))?;
            println!("{}", hex::encode(*key));
            Ok(())
        }
    }
}

#[cfg(test)]
mod wasm_cli_tests {
    use super::*;

    #[test]
    fn wasm_build_accepts_source_paths() {
        let cli = Cli::try_parse_from([
            "kotoba",
            "wasm",
            "build",
            "-S",
            "src",
            "--source-path",
            "vendor",
            "app/main.kotoba",
            "-o",
            "target/app.wasm",
        ])
        .unwrap();

        let Some(Cmd::Wasm(WasmCmd::Build {
            cell,
            out,
            wit,
            source_path,
        })) = cli.cmd
        else {
            panic!("expected wasm build command");
        };

        assert_eq!(cell, PathBuf::from("app/main.kotoba"));
        assert_eq!(out, Some(PathBuf::from("target/app.wasm")));
        assert_eq!(wit, None);
        assert_eq!(
            source_path,
            vec![PathBuf::from("src"), PathBuf::from("vendor")]
        );
    }

    #[test]
    fn wasm_safe_build_accepts_source_paths() {
        let cli = Cli::try_parse_from([
            "kotoba",
            "wasm",
            "safe-build",
            "-S",
            "src",
            "cell.kotoba",
            "--policy",
            "policy.edn",
        ])
        .unwrap();

        let Some(Cmd::Wasm(WasmCmd::SafeBuild {
            cell,
            policy,
            source_path,
            ..
        })) = cli.cmd
        else {
            panic!("expected wasm safe-build command");
        };

        assert_eq!(cell, PathBuf::from("cell.kotoba"));
        assert_eq!(policy, PathBuf::from("policy.edn"));
        assert_eq!(source_path, vec![PathBuf::from("src")]);
    }

    #[test]
    fn wasm_safe_policy_defaults_to_kotoba_reader_target_and_accepts_source_paths() {
        let cli = Cli::try_parse_from([
            "kotoba",
            "wasm",
            "safe-policy",
            "-S",
            "src",
            "cell.kotoba",
            "-o",
            "policy.edn",
        ])
        .unwrap();

        let Some(Cmd::Wasm(WasmCmd::SafePolicy {
            cell,
            out,
            reader_target,
            source_path,
            ..
        })) = cli.cmd
        else {
            panic!("expected wasm safe-policy command");
        };

        assert_eq!(cell, PathBuf::from("cell.kotoba"));
        assert_eq!(out, Some(PathBuf::from("policy.edn")));
        assert_eq!(reader_target, "kotoba");
        assert_eq!(source_path, vec![PathBuf::from("src")]);
    }

    #[test]
    fn wasm_selfhost_inspect_defaults_to_kotoba_reader_target_and_accepts_source_paths() {
        let cli = Cli::try_parse_from([
            "kotoba",
            "wasm",
            "selfhost-inspect",
            "cell.kotoba",
            "--policy",
            "policy.edn",
            "--source-path",
            "src",
            "--json",
            "--request-hex",
        ])
        .unwrap();

        let Some(Cmd::Wasm(WasmCmd::SelfhostInspect {
            cell,
            policy,
            reader_target,
            source_path,
            request_hex,
            json,
        })) = cli.cmd
        else {
            panic!("expected wasm selfhost-inspect command");
        };

        assert_eq!(cell, PathBuf::from("cell.kotoba"));
        assert_eq!(policy, Some(PathBuf::from("policy.edn")));
        assert_eq!(reader_target, "kotoba");
        assert_eq!(source_path, vec![PathBuf::from("src")]);
        assert!(request_hex);
        assert!(json);
    }

    #[test]
    fn top_level_run_check_db_git_rad_and_deploy_parse() {
        let cli = Cli::try_parse_from(["kotoba", "run", "main.kotoba", "1", "2"]).unwrap();
        let Some(Cmd::Run(RunCmd {
            cell, func, args, ..
        })) = cli.cmd
        else {
            panic!("expected run command");
        };
        assert_eq!(cell, PathBuf::from("main.kotoba"));
        assert_eq!(func, "main");
        assert_eq!(args, vec![1, 2]);

        let cli =
            Cli::try_parse_from(["kotoba", "check", "main.kotoba", "--policy", "p.edn"]).unwrap();
        let Some(Cmd::Check(CheckCmd { cell, policy, .. })) = cli.cmd else {
            panic!("expected check command");
        };
        assert_eq!(cell, PathBuf::from("main.kotoba"));
        assert_eq!(policy, Some(PathBuf::from("p.edn")));

        let cli = Cli::try_parse_from([
            "kotoba",
            "db",
            "transact",
            "--graph",
            "g",
            "[[:db/add \"a\" :name \"A\"]]",
        ])
        .unwrap();
        let Some(Cmd::Db(DbCmd::Transact { graph, tx_edn, .. })) = cli.cmd else {
            panic!("expected db transact command");
        };
        assert_eq!(graph, "g");
        assert_eq!(tx_edn.as_deref(), Some("[[:db/add \"a\" :name \"A\"]]"));

        let cli =
            Cli::try_parse_from(["kotoba", "git", "remote", "demo", "--name", "origin"]).unwrap();
        let Some(Cmd::Git(GitCmd::Remote { repo, name })) = cli.cmd else {
            panic!("expected git remote command");
        };
        assert_eq!(repo, "demo");
        assert_eq!(name, "origin");

        let cli = Cli::try_parse_from(["kotoba", "rad", "status"]).unwrap();
        assert!(matches!(cli.cmd, Some(Cmd::Rad(RadCmd::Status))));

        let cli = Cli::try_parse_from(["kotoba", "deploy", "kotoba.app.edn", "--publish"]).unwrap();
        let Some(Cmd::Deploy(DeployCmd {
            manifest, publish, ..
        })) = cli.cmd
        else {
            panic!("expected deploy command");
        };
        assert_eq!(manifest, PathBuf::from("kotoba.app.edn"));
        assert!(publish);
    }
}

#[cfg(test)]
mod key_custody_cli_tests {
    use super::*;

    #[test]
    fn parse_custodian_handles_did_key_colons() {
        let pk_hex = hex::encode([7u8; 32]);
        let spec = format!("did:key:z6Mkabc:{pk_hex}");
        let (did, pk) = parse_custodian(&spec).unwrap();
        assert_eq!(did, "did:key:z6Mkabc");
        assert_eq!(pk.as_bytes(), &[7u8; 32]);
    }

    #[test]
    fn deal_then_combine_roundtrip_offline() {
        // Three custodian keypairs.
        let custs: Vec<(String, x25519_dalek::StaticSecret, x25519_dalek::PublicKey)> = (1u8..=3)
            .map(|i| {
                let sk = x25519_dalek::StaticSecret::from([i; 32]);
                let pk = x25519_dalek::PublicKey::from(&sk);
                (format!("did:key:zC{i}"), sk, pk)
            })
            .collect();
        let pubs: Vec<(String, x25519_dalek::PublicKey)> =
            custs.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let key = [0x5Au8; 32];
        let shares = kotoba_custody::split_key_epoch(&key, 2, &pubs, 0).unwrap();

        // Each custodian opens its share; a requester would normally get them
        // re-wrapped, but the CLI combine path takes GrantedShares. Simulate the
        // custodian handler re-wrapping to a requester key.
        let req_sk = x25519_dalek::StaticSecret::from([0x99u8; 32]);
        let req_pk = x25519_dalek::PublicKey::from(&req_sk);
        let grants: Vec<kotoba_custody::GrantedShare> = [0usize, 2]
            .iter()
            .map(|&i| {
                let opened = kotoba_custody::open_share(&shares[i], &custs[i].1).unwrap();
                let sealed = kotoba_crypto::hpke_seal(&req_pk, &opened.bytes).unwrap();
                kotoba_custody::GrantedShare {
                    custodian_did: shares[i].recipient_did.clone(),
                    index: shares[i].index,
                    threshold: shares[i].threshold,
                    epoch: shares[i].epoch,
                    deal_id: shares[i].deal_id.clone(),
                    graph_cid_mb: "bg".into(),
                    requester_x25519_pk: req_pk.as_bytes().to_vec(),
                    ts_unix: 1,
                    sealed_for_requester: sealed,
                    grant_sig: None,
                }
            })
            .collect();
        let recovered = kotoba_custody::combine_granted(2, &grants, &req_sk).unwrap();
        assert_eq!(
            *recovered, key,
            "CLI deal→grant→combine reconstructs the key"
        );
    }
}
