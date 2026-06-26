//! `kotoba-clj` — generic command-line tool for the Clojure→WASM cell toolchain.
//!
//! Domain-agnostic: it knows nothing about ISCO/APQC or any actor. It exposes
//! the two engine capabilities an actor needs to build + smoke-test a cell:
//!
//!   kotoba-clj build <cell.clj> [-o out.wasm] [--wit <dir>]
//!       Compile a kotoba-clj source file (prelude auto-prepended) into a
//!       `kotoba:kais` WASM Component.
//!
//!   kotoba-clj run <component.wasm> [--ctx <json>] [--ctx-file <path>]
//!                  [--snapshot <json>] [--snapshot-file <path>]
//!                  [--gas <n>] [--agent <did>] [--echo-llm]
//!       Instantiate the Component on WasmExecutor and invoke run(ctx). ctx is
//!       a JSON value encoded to CBOR; snapshot is a JSON array of
//!       {graph,subject,predicate,object} Datom quads (object CBOR-encoded).
//!       Prints the output_cbor as hex and, when decodable, as a CBOR value.
//!
//! Build/install: `cargo build -p kotoba-clj --features cli` (or `--release`).

use std::collections::HashMap;
use std::sync::Arc;

use anyhow::{anyhow, bail, Context, Result};
use kotoba_runtime::host::WitQuad;
use kotoba_runtime::WasmExecutor;

use crate::component::compile_kais_component_str;
use crate::prelude;

const DEFAULT_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
const DEFAULT_GAS: u64 = 10_000_000;

/// One-line summary of the `build`/`run` subcommands, surfaced by `src/main.rs`
/// in the binary's `--help` output.
pub const SUBCOMMAND_USAGE: &str = "\
     kotoba-clj build <cell.clj> [-o <out.wasm>] [--wit <dir>]\n  \
     kotoba-clj safe-build <cell.clj> --policy <policy.edn> [-o <out.wasm>]\n  \
     kotoba-clj safe-policy <cell.clj> [-o <policy.edn>]\n  \
     kotoba-clj run <component.wasm> [--ctx <json> | --ctx-file <path>] \
     [--snapshot <json> | --snapshot-file <path>] [--gas <n>] [--agent <did>] [--echo-llm]";

/// Dispatch the `kotoba-clj <subcommand> …` interface.
///
/// `subcommand` is the already-matched `build`|`run` token and `argv` is the
/// process arguments that follow it; `src/main.rs` routes here when the first
/// argument is a recognised subcommand, otherwise it runs the legacy file
/// runner.
pub fn run(subcommand: &str, argv: &[String]) -> Result<()> {
    match subcommand {
        "build" => cmd_build(argv),
        "safe-build" => cmd_safe_build(argv),
        "safe-policy" => cmd_safe_policy(argv),
        "run" => cmd_run(argv),
        other => {
            bail!("unknown subcommand '{other}' (expected: build | safe-build | safe-policy | run)")
        }
    }
}

/// Pull `--flag value` out of args; returns the value if present.
fn flag<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    args.iter()
        .position(|a| a == name)
        .and_then(|i| args.get(i + 1))
        .map(String::as_str)
}

fn has_flag(args: &[String], name: &str) -> bool {
    args.iter().any(|a| a == name)
}

/// First arg that is not a flag and not a flag-value.
fn positional(args: &[String]) -> Option<&str> {
    let mut skip_next = false;
    for (i, a) in args.iter().enumerate() {
        if skip_next {
            skip_next = false;
            continue;
        }
        if a.starts_with('-') {
            // flags that take a value
            if matches!(
                a.as_str(),
                "-o" | "--wit"
                    | "--ctx"
                    | "--ctx-file"
                    | "--snapshot"
                    | "--snapshot-file"
                    | "--gas"
                    | "--agent"
                    | "--policy"
            ) {
                skip_next = true;
            }
            continue;
        }
        let _ = i;
        return Some(a);
    }
    None
}

fn cmd_build(args: &[String]) -> Result<()> {
    let cell = positional(args).ok_or_else(|| anyhow!("build: missing <cell.clj>"))?;
    let wit = flag(args, "--wit").unwrap_or(DEFAULT_WIT_DIR);
    let out = flag(args, "-o")
        .map(str::to_string)
        .unwrap_or_else(|| cell.trim_end_matches(".clj").to_string() + ".wasm");

    let body = std::fs::read_to_string(cell).with_context(|| format!("read {cell}"))?;
    let src = format!("{}\n{}", prelude(), body);
    let wasm =
        compile_kais_component_str(&src, wit).map_err(|e| anyhow!("compile {cell}: {e:?}"))?;
    std::fs::write(&out, &wasm).with_context(|| format!("write {out}"))?;
    eprintln!("[build] {cell} -> {out} ({} bytes)", wasm.len());
    Ok(())
}

/// `kotoba-clj safe-build <cell.clj> --policy <p.edn> [-o out.wasm]`
///
/// Compile a cell against a deny-by-default capability [`Policy`] (loaded from
/// `--policy`). Emits the **core** wasm module produced by
/// [`crate::compile_safe_clj_with_prelude`]: a module whose import section is a
/// subset of the policy's grants. The build *fails* if the cell uses a
/// capability the policy does not grant or a form outside the safe subset.
///
/// Prints the module's audited capability surface — the `kotoba:kais`
/// interfaces actually embedded — as confinement evidence.
fn cmd_safe_build(args: &[String]) -> Result<()> {
    let cell = positional(args).ok_or_else(|| anyhow!("safe-build: missing <cell.clj>"))?;
    let policy_path = flag(args, "--policy")
        .ok_or_else(|| anyhow!("safe-build: missing --policy <policy.edn>"))?;
    let out = flag(args, "-o")
        .map(str::to_string)
        .unwrap_or_else(|| cell.trim_end_matches(".clj").to_string() + ".wasm");

    let policy_src =
        std::fs::read_to_string(policy_path).with_context(|| format!("read {policy_path}"))?;
    let policy = crate::Policy::parse_edn(&policy_src)
        .map_err(|e| anyhow!("parse policy {policy_path}: {e}"))?;

    let body = std::fs::read_to_string(cell).with_context(|| format!("read {cell}"))?;
    let wasm = crate::compile_safe_clj_with_prelude(&body, &policy)
        .map_err(|e| anyhow!("safe-build {cell} rejected: {e}"))?;

    std::fs::write(&out, &wasm).with_context(|| format!("write {out}"))?;

    let ifaces = crate::embedded_capability_ifaces(&wasm);
    let surface = if ifaces.is_empty() {
        "none (pure)".to_string()
    } else {
        ifaces.join(", ")
    };
    eprintln!("[safe-build] {cell} -> {out} ({} bytes)", wasm.len());
    eprintln!("[safe-build] capability surface: {surface}");

    // Least-privilege lint: warn if the policy grants more than the cell uses.
    if let Ok(unused) = crate::unused_grants(&body, &policy) {
        for finding in &unused {
            eprintln!("[safe-build] warning: over-grant — {finding}");
        }
    }

    // Source-level effect inference: report what each function actually does.
    if let Ok(effects) = crate::infer_effects(&body) {
        let mut rows: Vec<String> = effects
            .iter()
            .filter(|(_, e)| !e.is_empty())
            .map(|(f, e)| {
                let set = e.iter().cloned().collect::<Vec<_>>().join(",");
                format!("{f}={{{set}}}")
            })
            .collect();
        rows.sort();
        let report = if rows.is_empty() {
            "all pure".to_string()
        } else {
            rows.join(" ")
        };
        eprintln!("[safe-build] inferred effects: {report}");
    }
    Ok(())
}

/// `kotoba-clj safe-policy <cell.clj> [-o policy.edn]`
///
/// Synthesize and print the **minimal least-privilege policy** a cell needs
/// (the inverse of `safe-build`): grants exactly the resources the code targets
/// and nothing more. Pipe it into a `policy.edn`, review, tighten, then feed it
/// back to `safe-build`.
fn cmd_safe_policy(args: &[String]) -> Result<()> {
    let cell = positional(args).ok_or_else(|| anyhow!("safe-policy: missing <cell.clj>"))?;
    let body = std::fs::read_to_string(cell).with_context(|| format!("read {cell}"))?;
    let policy =
        crate::minimal_policy(&body).map_err(|e| anyhow!("analyze {cell}: {e}"))?;
    let edn = policy.to_edn();
    match flag(args, "-o") {
        Some(out) => {
            std::fs::write(out, &edn).with_context(|| format!("write {out}"))?;
            eprintln!("[safe-policy] {cell} -> {out} (minimal least-privilege policy)");
        }
        None => println!("{edn}"),
    }
    Ok(())
}

fn cmd_run(args: &[String]) -> Result<()> {
    let wasm_path = positional(args).ok_or_else(|| anyhow!("run: missing <component.wasm>"))?;
    let wasm = std::fs::read(wasm_path).with_context(|| format!("read {wasm_path}"))?;

    let ctx_json = match (flag(args, "--ctx"), flag(args, "--ctx-file")) {
        (Some(s), _) => s.to_string(),
        (None, Some(p)) => std::fs::read_to_string(p).with_context(|| format!("read {p}"))?,
        (None, None) => "{}".to_string(),
    };
    let ctx_cbor = json_str_to_cbor(&ctx_json).context("encode ctx")?;

    let snapshot_json = match (flag(args, "--snapshot"), flag(args, "--snapshot-file")) {
        (Some(s), _) => Some(s.to_string()),
        (None, Some(p)) => Some(std::fs::read_to_string(p).with_context(|| format!("read {p}"))?),
        (None, None) => None,
    };
    let snapshot = match snapshot_json {
        Some(s) => parse_snapshot(&s).context("parse snapshot")?,
        None => Vec::new(),
    };

    let gas: u64 = flag(args, "--gas")
        .map(|s| s.parse())
        .transpose()
        .context("--gas")?
        .unwrap_or(DEFAULT_GAS);
    let agent = flag(args, "--agent").unwrap_or("did:web:etzhayyim.com");

    let exec = if has_flag(args, "--echo-llm") {
        let engine = Arc::new(|prompt: &str, _max: usize| Ok(format!("echo:{prompt}")));
        WasmExecutor::with_inference(gas, engine).map_err(|e| anyhow!("executor: {e:?}"))?
    } else {
        WasmExecutor::new(gas).map_err(|e| anyhow!("executor: {e:?}"))?
    };

    let result = exec
        .execute(
            "kotoba-clj-cli",
            &wasm,
            agent,
            ctx_cbor,
            snapshot,
            HashMap::new(),
        )
        .map_err(|e| anyhow!("execute: {e:?}"))?;

    let out = result.output_cbor;
    println!("output.hex: {}", hex(&out));
    match ciborium::from_reader::<ciborium::Value, _>(out.as_slice()) {
        Ok(v) => println!("output.cbor: {v:?}"),
        Err(_) => println!("output.utf8: {}", String::from_utf8_lossy(&out)),
    }
    println!("gas_used: {}", result.gas_used);
    if !result.assert_quads.is_empty() {
        println!("asserted: {} quad(s)", result.assert_quads.len());
    }
    Ok(())
}

fn json_str_to_cbor(s: &str) -> Result<Vec<u8>> {
    let v: serde_json::Value = serde_json::from_str(s)?;
    let c = json_to_cbor(&v);
    let mut buf = Vec::new();
    ciborium::into_writer(&c, &mut buf)?;
    Ok(buf)
}

fn json_to_cbor(v: &serde_json::Value) -> ciborium::Value {
    use ciborium::Value as C;
    use serde_json::Value as J;
    match v {
        J::Null => C::Null,
        J::Bool(b) => C::Bool(*b),
        J::Number(n) => {
            if let Some(u) = n.as_u64() {
                C::Integer(u.into())
            } else if let Some(i) = n.as_i64() {
                C::Integer(i.into())
            } else {
                C::Float(n.as_f64().unwrap_or(0.0))
            }
        }
        J::String(s) => C::Text(s.clone()),
        J::Array(a) => C::Array(a.iter().map(json_to_cbor).collect()),
        J::Object(o) => C::Map(
            o.iter()
                .map(|(k, val)| (C::Text(k.clone()), json_to_cbor(val)))
                .collect(),
        ),
    }
}

fn parse_snapshot(s: &str) -> Result<Vec<WitQuad>> {
    let rows: Vec<serde_json::Value> = serde_json::from_str(s)?;
    let mut out = Vec::with_capacity(rows.len());
    for (i, r) in rows.iter().enumerate() {
        let get = |k: &str| -> Result<String> {
            r.get(k)
                .and_then(|v| v.as_str())
                .map(str::to_string)
                .ok_or_else(|| anyhow!("snapshot[{i}]: missing string field '{k}'"))
        };
        let object = r
            .get("object")
            .ok_or_else(|| anyhow!("snapshot[{i}]: missing 'object'"))?;
        let mut object_cbor = Vec::new();
        ciborium::into_writer(&json_to_cbor(object), &mut object_cbor)?;
        out.push(WitQuad {
            graph: get("graph")?,
            subject: get("subject")?,
            predicate: get("predicate")?,
            object_cbor,
        });
    }
    Ok(out)
}

fn hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{b:02x}"));
    }
    s
}
