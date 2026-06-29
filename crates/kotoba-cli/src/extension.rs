//! `kotoba extension` — Clojure/EDN package lifecycle through the kotoba CLI.
//!
//! This is the compatibility bridge for portable `.cljc` packages that still use
//! `deps.edn` and `clojure.test`. The operator-facing command is `kotoba`; the
//! execution host is selected by the extension manifest. Today `:clj/deps` runs
//! through the Clojure CLI so existing test suites keep working while kotoba-clj
//! grows enough JVM/Clojure compatibility to take over more of the surface.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{anyhow, bail, Context, Result};
use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use clap::Subcommand;
use kotoba_core::cid::KotobaCid;
use kotoba_edn::{EdnValue, Keyword};

const MANIFEST: &str = "kotoba.extension.edn";

#[derive(Subcommand)]
pub enum ExtensionCmd {
    /// Run the extension's test alias through the kotoba CLI.
    Test {
        /// Extension directory. Defaults to the current directory.
        #[arg(default_value = ".")]
        path: PathBuf,
        /// Override the manifest's test alias.
        #[arg(long)]
        alias: Option<String>,
        /// Extra arguments passed after `--` to the Clojure CLI.
        #[arg(last = true)]
        args: Vec<String>,
    },

    /// Run an extension main namespace/function.
    Run {
        /// Extension directory. Defaults to the current directory.
        #[arg(default_value = ".")]
        path: PathBuf,
        /// Main namespace passed to `clojure -M -m`.
        #[arg(long)]
        main: Option<String>,
        /// Extra arguments passed to the extension main.
        #[arg(last = true)]
        args: Vec<String>,
    },

    /// Evaluate the extension gate. Currently this is an alias for `test`.
    Eval {
        /// Extension directory. Defaults to the current directory.
        #[arg(default_value = ".")]
        path: PathBuf,
        /// Override the manifest's test alias.
        #[arg(long)]
        alias: Option<String>,
    },

    /// Validate and package an extension artifact.
    Build {
        /// Extension directory. Defaults to the current directory.
        #[arg(default_value = ".")]
        path: PathBuf,
        /// Write the artifact to this path.
        #[arg(short, long)]
        out: Option<PathBuf>,
        /// Skip the test gate before emitting the artifact.
        #[arg(long)]
        skip_test: bool,
    },

    /// Build and deploy the extension artifact to a running kotoba node.
    Deploy {
        /// Extension directory. Defaults to the current directory.
        #[arg(default_value = ".")]
        path: PathBuf,
        /// Write the artifact to this path before deploying.
        #[arg(short, long)]
        out: Option<PathBuf>,
        /// Do not POST to block.put; only print the artifact CID.
        #[arg(long)]
        dry_run: bool,
        /// Skip the test gate before emitting the artifact.
        #[arg(long)]
        skip_test: bool,
    },

    /// Print the resolved extension manifest.
    Info {
        /// Extension directory. Defaults to the current directory.
        #[arg(default_value = ".")]
        path: PathBuf,
    },
}

#[derive(Debug, Clone)]
struct Extension {
    name: String,
    kind: String,
    host: String,
    paths: Vec<String>,
    test_paths: Vec<String>,
    test_alias: String,
    main: Option<String>,
    artifact: Option<String>,
    manifest_path: Option<PathBuf>,
}

pub async fn run(cmd: ExtensionCmd, url: &str, token: &Option<String>) -> Result<()> {
    match cmd {
        ExtensionCmd::Test { path, alias, args } => {
            let ext = load_or_infer(&path)?;
            run_test(&path, &ext, alias.as_deref(), &args)
        }
        ExtensionCmd::Eval { path, alias } => {
            let ext = load_or_infer(&path)?;
            run_test(&path, &ext, alias.as_deref(), &[])
        }
        ExtensionCmd::Run { path, main, args } => {
            let ext = load_or_infer(&path)?;
            run_main(&path, &ext, main.as_deref(), &args)
        }
        ExtensionCmd::Build {
            path,
            out,
            skip_test,
        } => {
            let ext = load_or_infer(&path)?;
            let (artifact, cid) = build_artifact(&path, &ext, out, skip_test)?;
            println!("artifact: {}", artifact.display());
            println!("cid: {cid}");
            Ok(())
        }
        ExtensionCmd::Deploy {
            path,
            out,
            dry_run,
            skip_test,
        } => {
            let ext = load_or_infer(&path)?;
            let (artifact, cid) = build_artifact(&path, &ext, out, skip_test)?;
            println!("artifact: {}", artifact.display());
            println!("cid: {cid}");
            if dry_run {
                println!("dry-run: not published");
                return Ok(());
            }
            let bytes = std::fs::read(&artifact)
                .with_context(|| format!("read artifact {}", artifact.display()))?;
            let published = put_block(url, token, &bytes).await?;
            println!("published: {published}");
            Ok(())
        }
        ExtensionCmd::Info { path } => {
            let ext = load_or_infer(&path)?;
            println!("{}", extension_edn(&path, &ext, None)?);
            Ok(())
        }
    }
}

pub fn run_clojure_alias_shorthand(args: &[String]) -> Result<()> {
    let first = args
        .first()
        .ok_or_else(|| anyhow!("missing -M/-X alias argument"))?;
    let alias = first
        .strip_prefix("-M:")
        .or_else(|| first.strip_prefix("-X:"))
        .or_else(|| first.strip_prefix("-M"))
        .or_else(|| first.strip_prefix("-X"))
        .filter(|s| !s.is_empty())
        .unwrap_or("test");
    let extra = args.iter().skip(1).cloned().collect::<Vec<_>>();
    let cwd = std::env::current_dir().context("current dir")?;
    let ext = load_or_infer(&cwd)?;
    run_test(&cwd, &ext, Some(alias), &extra)
}

fn load_or_infer(path: &Path) -> Result<Extension> {
    let root = path
        .canonicalize()
        .with_context(|| format!("resolve {}", path.display()))?;
    let manifest = root.join(MANIFEST);
    if manifest.exists() {
        let src = std::fs::read_to_string(&manifest)
            .with_context(|| format!("read {}", manifest.display()))?;
        let mut ext =
            parse_manifest(&src).map_err(|e| anyhow!("parse {}: {e}", manifest.display()))?;
        ext.manifest_path = Some(manifest);
        return Ok(ext);
    }

    let name = root
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("extension")
        .to_string();
    Ok(Extension {
        name,
        kind: "clj/library".into(),
        host: "clj/deps".into(),
        paths: vec!["src".into()],
        test_paths: vec!["test".into()],
        test_alias: "test".into(),
        main: None,
        artifact: None,
        manifest_path: None,
    })
}

fn parse_manifest(src: &str) -> Result<Extension> {
    let value = kotoba_edn::parse(src)?;
    let map = value
        .as_map()
        .ok_or_else(|| anyhow!("extension manifest must be an EDN map"))?;
    let name = get_str(map, "kotoba.extension/name")
        .ok_or_else(|| anyhow!("missing :kotoba.extension/name"))?;
    Ok(Extension {
        name,
        kind: get_str(map, "kotoba.extension/type").unwrap_or_else(|| "clj/library".into()),
        host: get_str(map, "kotoba.extension/host").unwrap_or_else(|| "clj/deps".into()),
        paths: get_strs(map, "kotoba.extension/paths").unwrap_or_else(|| vec!["src".into()]),
        test_paths: get_strs(map, "kotoba.extension/test-paths")
            .unwrap_or_else(|| vec!["test".into()]),
        test_alias: get_str(map, "kotoba.extension/test-alias").unwrap_or_else(|| "test".into()),
        main: get_str(map, "kotoba.extension/main"),
        artifact: get_nested_str(map, "kotoba.extension/build", "artifact"),
        manifest_path: None,
    })
}

fn run_test(root: &Path, ext: &Extension, alias: Option<&str>, args: &[String]) -> Result<()> {
    ensure_host(ext)?;
    let alias = alias.unwrap_or(&ext.test_alias);
    let mut cmd = Command::new("clojure");
    cmd.current_dir(root).arg(format!("-M:{alias}")).args(args);
    run_command(cmd, &format!("test {}", ext.name))
}

fn run_main(root: &Path, ext: &Extension, main: Option<&str>, args: &[String]) -> Result<()> {
    ensure_host(ext)?;
    let main = main.or(ext.main.as_deref()).ok_or_else(|| {
        anyhow!("no main namespace configured; pass --main or set :kotoba.extension/main")
    })?;
    let mut cmd = Command::new("clojure");
    cmd.current_dir(root)
        .arg("-M")
        .arg("-m")
        .arg(main)
        .args(args);
    run_command(cmd, &format!("run {}", ext.name))
}

fn run_command(mut cmd: Command, label: &str) -> Result<()> {
    eprintln!("[kotoba extension] {label}: {:?}", cmd);
    let status = cmd.status().with_context(|| format!("spawn {label}"))?;
    if !status.success() {
        bail!("{label} failed with {status}");
    }
    Ok(())
}

fn build_artifact(
    root: &Path,
    ext: &Extension,
    out: Option<PathBuf>,
    skip_test: bool,
) -> Result<(PathBuf, String)> {
    if !skip_test {
        run_test(root, ext, None, &[])?;
    }
    let out = out.unwrap_or_else(|| {
        ext.artifact
            .as_ref()
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(format!("target/kotoba/{}-extension.edn", ext.name)))
    });
    let out = if out.is_absolute() {
        out
    } else {
        root.join(out)
    };
    if let Some(parent) = out.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    let artifact = extension_edn(root, ext, Some(&out))?;
    std::fs::write(&out, artifact.as_bytes())
        .with_context(|| format!("write {}", out.display()))?;
    let cid = KotobaCid::from_bytes(artifact.as_bytes()).to_multibase();
    Ok((out, cid))
}

fn extension_edn(root: &Path, ext: &Extension, artifact_path: Option<&Path>) -> Result<String> {
    let git_rev = git_output(root, &["rev-parse", "HEAD"]).unwrap_or_else(|| "unknown".into());
    let status = git_output(root, &["status", "--short"]).unwrap_or_default();
    let files = collect_files(root, &ext.paths, &ext.test_paths)?;
    let artifact = artifact_path
        .map(|p| p.display().to_string())
        .unwrap_or_else(|| ext.artifact.clone().unwrap_or_default());
    Ok(format!(
        "{{:kotoba.extension/name {:?}\n\
          :kotoba.extension/type :{}\n\
          :kotoba.extension/host :{}\n\
          :kotoba.extension/paths {:?}\n\
          :kotoba.extension/test-paths {:?}\n\
          :kotoba.extension/test-alias :{}\n\
          :kotoba.extension/main {}\n\
          :kotoba.extension/git-rev {:?}\n\
          :kotoba.extension/git-dirty? {}\n\
          :kotoba.extension/files {:?}\n\
          :kotoba.extension/artifact {:?}}}\n",
        ext.name,
        ext.kind,
        ext.host,
        ext.paths,
        ext.test_paths,
        ext.test_alias,
        ext.main
            .as_ref()
            .map(|s| format!("{s:?}"))
            .unwrap_or_else(|| "nil".into()),
        git_rev.trim(),
        !status.trim().is_empty(),
        files,
        artifact
    ))
}

fn collect_files(root: &Path, paths: &[String], test_paths: &[String]) -> Result<Vec<String>> {
    let mut roots = paths.to_vec();
    roots.extend(test_paths.iter().cloned());
    let mut files = Vec::new();
    for rel in roots {
        let dir = root.join(&rel);
        if !dir.exists() {
            continue;
        }
        collect_files_rec(root, &dir, &mut files)?;
    }
    files.sort();
    Ok(files)
}

fn collect_files_rec(root: &Path, dir: &Path, files: &mut Vec<String>) -> Result<()> {
    for entry in std::fs::read_dir(dir).with_context(|| format!("read dir {}", dir.display()))? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            collect_files_rec(root, &path, files)?;
        } else if is_clj_file(&path) {
            let rel = path.strip_prefix(root).unwrap_or(&path);
            files.push(rel.display().to_string());
        }
    }
    Ok(())
}

fn is_clj_file(path: &Path) -> bool {
    matches!(
        path.extension().and_then(|s| s.to_str()),
        Some("clj" | "cljc" | "cljs" | "edn" | "kotoba")
    )
}

async fn put_block(url: &str, token: &Option<String>, bytes: &[u8]) -> Result<String> {
    let mut headers = reqwest::header::HeaderMap::new();
    if let Some(tok) = token {
        let val = reqwest::header::HeaderValue::from_str(&format!("Bearer {tok}"))
            .context("invalid token value")?;
        headers.insert(reqwest::header::AUTHORIZATION, val);
    }
    let client = reqwest::Client::builder()
        .default_headers(headers)
        .build()
        .context("building HTTP client")?;
    let endpoint = format!(
        "{}/xrpc/com.etzhayyim.apps.kotoba.block.put",
        url.trim_end_matches('/')
    );
    let resp = client
        .post(&endpoint)
        .json(&serde_json::json!({ "data_b64": B64.encode(bytes) }))
        .send()
        .await
        .with_context(|| format!("POST {endpoint}"))?;
    let status = resp.status();
    let json: serde_json::Value = resp.json().await.unwrap_or_default();
    if !status.is_success() {
        bail!("deploy failed ({status}): {json}");
    }
    Ok(json["cid"].as_str().unwrap_or("(no cid)").to_string())
}

fn ensure_host(ext: &Extension) -> Result<()> {
    if ext.host == "clj/deps" {
        Ok(())
    } else {
        bail!(
            "extension host :{} is not implemented by kotoba extension yet",
            ext.host
        )
    }
}

fn git_output(root: &Path, args: &[&str]) -> Option<String> {
    let out = Command::new("git")
        .current_dir(root)
        .args(args)
        .output()
        .ok()?;
    out.status
        .success()
        .then(|| String::from_utf8_lossy(&out.stdout).trim().to_string())
}

fn get_str(map: &BTreeMap<EdnValue, EdnValue>, key: &str) -> Option<String> {
    map.get(&EdnValue::Keyword(Keyword::parse(key)))
        .and_then(as_str)
}

fn get_strs(map: &BTreeMap<EdnValue, EdnValue>, key: &str) -> Option<Vec<String>> {
    map.get(&EdnValue::Keyword(Keyword::parse(key)))
        .and_then(|v| v.as_seq())
        .map(|items| items.iter().filter_map(as_str).collect())
}

fn get_nested_str(map: &BTreeMap<EdnValue, EdnValue>, key: &str, child: &str) -> Option<String> {
    let nested = map
        .get(&EdnValue::Keyword(Keyword::parse(key)))
        .and_then(|v| v.as_map())?;
    get_str(nested, child)
}

fn as_str(v: &EdnValue) -> Option<String> {
    match v {
        EdnValue::String(s) => Some(s.clone()),
        EdnValue::Keyword(k) => Some(k.to_qualified()),
        EdnValue::Symbol(s) => Some(s.to_qualified()),
        _ => None,
    }
}
