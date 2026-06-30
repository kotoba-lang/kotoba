//! `kotoba component` / `kotoba app` / `kotoba lattice` — KOTOBA Mesh CLI (M3).
//!
//! - `component build <file>` — compile a component source to a WASM component
//!   and print its content-address (CID). `.kotoba` is the canonical Kotoba
//!   source extension; `.clj` / `.cljc` / `.cljs` remain compatibility inputs.
//!   Kotoba compiles to the `kotoba-node` world.
//! - `app deploy <manifest.edn>` — parse the EDN manifest, compile every
//!   component's `src` to a CID, and print the resolved content-addressed
//!   desired state (the input the lattice reconciler converges on).
//! - `lattice ps` — show lattice participation status.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use anyhow::{anyhow, bail, Context, Result};
use clap::Subcommand;
use kotoba_core::cid::KotobaCid;
use kotoba_lattice::{AppManifest, Lang};

/// Default location of the `kotoba-node` WIT package (override with
/// `--wit-dir` or `KOTOBA_WIT_DIR`).
fn default_wit_dir() -> String {
    std::env::var("KOTOBA_WIT_DIR").unwrap_or_else(|_| "crates/kotoba-runtime/wit".to_string())
}

/// Canonical content-address of a compiled component (CIDv1 dag-cbor sha2-256,
/// IPFS-compatible) — the same scheme kotoba uses for program CIDs.
fn component_cid(wasm: &[u8]) -> String {
    KotobaCid::from_bytes(wasm).to_multibase()
}

#[derive(Subcommand)]
pub enum ComponentCmd {
    /// Compile a component source file to a WASM component and print its CID.
    Build {
        /// Source file (`.kotoba` canonical; `.clj`/`.cljc`/`.cljs` compatibility).
        file: PathBuf,
        /// Path to the kotoba-node WIT dir.
        #[arg(long, env = "KOTOBA_WIT_DIR", default_value_t = default_wit_dir())]
        wit_dir: String,
        /// Write the compiled `.wasm` to this path.
        #[arg(short, long)]
        out: Option<PathBuf>,
    },
}

#[derive(Subcommand)]
pub enum AppCmd {
    /// Parse an EDN manifest, compile its components, print the resolved plan,
    /// and (with `--publish`) announce its triggers/routes to a running node.
    Deploy {
        /// Path to `kotoba.app.edn`.
        manifest: PathBuf,
        /// Path to the kotoba-node WIT dir.
        #[arg(long, env = "KOTOBA_WIT_DIR", default_value_t = default_wit_dir())]
        wit_dir: String,
        /// Publish the app's PutTriggers/PutRoutes to a running node's lattice
        /// (via the `mesh.deploy` endpoint). Without this, deploy is a dry-run.
        #[arg(long)]
        publish: bool,
        /// Server base URL for `--publish`.
        #[arg(long, env = "KOTOBA_URL", default_value = "http://localhost:8080")]
        url: String,
    },
}

#[derive(Subcommand)]
pub enum LatticeCmd {
    /// Show lattice participation status for the local node.
    Ps,
}

/// Compile a single source file to component bytes, dispatching on language.
/// Returns `(wasm_bytes, lang)`.
fn compile_source(file: &Path, wit_dir: &str) -> Result<(Vec<u8>, Lang)> {
    let path = file.to_string_lossy();
    let lang = Lang::from_ext(&path);
    let src =
        std::fs::read_to_string(file).with_context(|| format!("read component source {}", path))?;

    let wasm = match lang {
        // Mesh build path (M7): exports `run`, plus `on-http` when the guest
        // defines `(defn on-http [req] …)` — targeting the `kotoba-component`
        // world. Run-only guests fall back to the `kotoba-node` world, so
        // existing components are unaffected. The Kotoba prelude (dynamic
        // vector/map containers + CBOR encode/decode + kqe accessors) is
        // prepended so guests can use those helpers — mirrors the compiler's
        // own build CLI; direct host-import builtins (kqe-assert!/kqe-query)
        // work with or without it.
        Lang::Kotoba => {
            let with_prelude = format!("{}\n{}", kotoba_clj::prelude(), src);
            kotoba_clj::component::compile_kais_mesh_component_str(&with_prelude, wit_dir)
                .map_err(|e| anyhow!("Kotoba compile {}: {e:?}", path))?
        }
        other => bail!(
            "language {:?} not wired into `kotoba component build` yet — \
             Kotoba (.kotoba canonical, .clj/.cljc/.cljs compatibility) is the default; build {:?} components with their \
             native toolchain and reference the resulting CID in the manifest",
            other,
            other
        ),
    };
    Ok((wasm, lang))
}

pub fn run_component(cmd: ComponentCmd) -> Result<()> {
    match cmd {
        ComponentCmd::Build { file, wit_dir, out } => {
            let (wasm, lang) = compile_source(&file, &wit_dir)?;
            let cid = component_cid(&wasm);
            eprintln!(
                "built {} ({:?}) → {} bytes",
                file.display(),
                lang,
                wasm.len()
            );
            if let Some(out) = out {
                std::fs::write(&out, &wasm).with_context(|| format!("write {}", out.display()))?;
                eprintln!("wrote {}", out.display());
            }
            // CID on stdout so it can be piped/captured
            println!("{cid}");
            Ok(())
        }
    }
}

pub async fn run_app(cmd: AppCmd) -> Result<()> {
    match cmd {
        AppCmd::Deploy {
            manifest,
            wit_dir,
            publish,
            url,
        } => {
            let src = std::fs::read_to_string(&manifest)
                .with_context(|| format!("read manifest {}", manifest.display()))?;
            let app = AppManifest::from_edn(&src)
                .map_err(|e| anyhow!("parse manifest {}: {e}", manifest.display()))?;
            let base = manifest.parent().unwrap_or_else(|| Path::new("."));

            println!(
                "app {} v{}",
                app.name,
                app.version.as_deref().unwrap_or("?")
            );
            println!(
                "placement: spread={:?} require={:?}",
                app.placement.spread, app.placement.require
            );
            println!("components ({}):", app.components.len());

            let mut resolved: BTreeMap<String, u32> = BTreeMap::new();
            let mut resolved_by_name: BTreeMap<String, String> = BTreeMap::new();
            for c in &app.components {
                // resolve the artifact CID: explicit :cid wins, else compile :src
                let cid = if let Some(cid) = &c.cid {
                    cid.clone()
                } else if let Some(src_file) = &c.src {
                    let path = base.join(src_file);
                    let (wasm, _) = compile_source(&path, &wit_dir)
                        .with_context(|| format!("compile component {}", c.name))?;
                    component_cid(&wasm)
                } else {
                    bail!("component {} has neither :cid nor :src", c.name);
                };
                let triggers: Vec<&str> = c.triggers.iter().map(|t| t.kind.as_str()).collect();
                println!(
                    "  • {:<10} lang={:?} scale={} cid={} requires={:?} triggers={:?}",
                    c.name, c.lang, c.scale, cid, c.requires, triggers
                );
                resolved.insert(cid.clone(), c.scale);
                resolved_by_name.insert(c.name.clone(), cid);
            }

            println!(
                "\nresolved desired state (content-addressed):\n  {:?}",
                resolved
            );

            // Control-graph datoms — the durable wadm SSOT (ADR §7/§14, M4).
            // Ingest these into the control graph; every node's reconciler reads
            // them (or receives them live via a PutApp lattice message).
            let datoms = kotoba_lattice::control::app_to_quads(&app, &resolved_by_name);
            println!("\ncontrol-graph datoms ({}):", datoms.len());
            for q in &datoms {
                println!("  ({}  {}  {})", q.subject, q.predicate, q.object);
            }
            println!(
                "\nThese datoms are the desired state the lattice reconciler converges on.\n\
                 Bring up nodes (`kotoba serve`, KOTOBA_NODE_ROLES=compute) — each\n\
                 advertises a Heartbeat, bids on auctions, and places (executes) the\n\
                 components it wins via the WASM host."
            );

            // Lattice control messages (M16): PutTriggers (datom-Δ) + PutRoutes
            // (KSE topic / cron / HTTP route), resolved to compiled CIDs.
            let msgs = kotoba_lattice::deploy_messages(&app, &resolved_by_name);
            println!("\nlattice control messages ({}):", msgs.len());
            for (topic, m) in &msgs {
                let kind = match m {
                    kotoba_lattice::LatticeMessage::PutTriggers { triggers, .. } => {
                        format!("PutTriggers ({} datom-Δ)", triggers.len())
                    }
                    kotoba_lattice::LatticeMessage::PutRoutes { routes, .. } => format!(
                        "PutRoutes (kse={} cron={} http={})",
                        routes.kse.len(),
                        routes.cron.len(),
                        routes.http.len()
                    ),
                    _ => "?".into(),
                };
                println!("  → {topic}  {kind}");
            }

            if publish {
                // Serialize the RESOLVED messages (compiled CIDs included) as
                // CBOR Vec<(topic, lattice_msg_cbor)> so :src components deploy
                // with their real artifact CID (R0).
                let mut wire: Vec<(String, Vec<u8>)> = Vec::with_capacity(msgs.len());
                for (topic, m) in &msgs {
                    let cbor = m
                        .to_cbor()
                        .map_err(|e| anyhow!("encode lattice msg: {e}"))?;
                    wire.push((topic.to_string(), cbor));
                }
                let mut body = Vec::new();
                ciborium::into_writer(&wire, &mut body)
                    .map_err(|e| anyhow!("cbor encode deploy body: {e}"))?;
                let endpoint = format!(
                    "{}/xrpc/com.etzhayyim.apps.kotoba.mesh.deploy",
                    url.trim_end_matches('/')
                );
                let resp = reqwest::Client::new()
                    .post(&endpoint)
                    .header("content-type", "application/cbor")
                    .body(body)
                    .send()
                    .await
                    .with_context(|| format!("POST {endpoint}"))?;
                let status = resp.status();
                let text = resp.text().await.unwrap_or_default();
                if status.is_success() {
                    println!("\npublished → {endpoint}\n  {text}");
                } else {
                    bail!("publish failed ({status}): {text}");
                }
            } else {
                println!(
                    "\n(dry-run — re-run with `--publish` to announce these to a running node's lattice)"
                );
            }
            Ok(())
        }
    }
}

pub fn run_lattice(cmd: LatticeCmd) -> Result<()> {
    match cmd {
        LatticeCmd::Ps => {
            // The fleet view lives inside the running node's swarm actor
            // (kotoba-server net_actor). A read-only XRPC projection of it is
            // the next increment; for now report local participation config.
            let roles = std::env::var("KOTOBA_NODE_ROLES").unwrap_or_else(|_| "pin,compute".into());
            let labels = std::env::var("KOTOBA_NODE_LABELS").unwrap_or_default();
            println!("lattice participation (local config):");
            println!("  roles  : {roles}");
            println!(
                "  labels : {}",
                if labels.is_empty() { "(none)" } else { &labels }
            );
            println!(
                "\nA running `kotoba serve` node subscribes to the lattice topics,\n\
                 publishes Heartbeats, and auto-bids on auctions over gossipsub.\n\
                 (Cross-node fleet listing via XRPC is the next increment.)"
            );
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn component_cid_is_deterministic_and_canonical() {
        let a = component_cid(b"\0asm hello");
        // deterministic
        assert_eq!(a, component_cid(b"\0asm hello"));
        // distinct inputs → distinct CIDs
        assert_ne!(a, component_cid(b"\0asm world"));
        // canonical kotoba CID (matches KotobaCid scheme) + round-trips + IPFS-compatible
        let kc = KotobaCid::from_bytes(b"\0asm hello");
        assert_eq!(a, kc.to_multibase());
        let parsed = KotobaCid::from_multibase(&a).expect("parse back");
        assert!(parsed.is_ipfs_compatible());
    }

    #[test]
    fn compile_source_bails_on_non_kotoba_language() {
        // a .py source dispatches to Python and bails (only Kotoba is wired)
        let p = std::env::temp_dir().join("kotoba_mesh_cli_test.py");
        std::fs::write(&p, b"print('hi')").unwrap();
        let r = compile_source(&p, "crates/kotoba-runtime/wit");
        let _ = std::fs::remove_file(&p);
        let err = r.unwrap_err().to_string();
        assert!(
            err.contains("Python") || err.contains("not wired"),
            "got: {err}"
        );
    }

    #[test]
    fn non_kotoba_language_error_names_kotoba_canonical_and_clj_family_compat() {
        let p = std::env::temp_dir().join("kotoba_mesh_cli_test.rs");
        std::fs::write(&p, b"fn main() {}").unwrap();
        let r = compile_source(&p, "crates/kotoba-runtime/wit");
        let _ = std::fs::remove_file(&p);
        let err = r.unwrap_err().to_string();

        assert!(err.contains(".kotoba canonical"), "got: {err}");
        assert!(err.contains(".clj/.cljc/.cljs compatibility"), "got: {err}");
        assert!(!err.contains("Clojure default"), "got: {err}");
    }

    #[test]
    fn compile_source_reports_missing_file() {
        let r = compile_source(
            Path::new("/no/such/reply.kotoba"),
            "crates/kotoba-runtime/wit",
        );
        assert!(r.is_err(), "missing source must error, not panic");
    }
}
