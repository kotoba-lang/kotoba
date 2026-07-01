use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn temp_dir(name: &str) -> PathBuf {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!(
        "kotoba-cli-test-{}-{name}-{nonce}",
        std::process::id()
    ));
    fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn kotoba_eval_runs_inline_kotoba_expression() {
    let output = Command::new(env!("CARGO_BIN_EXE_kotoba"))
        .arg("-e")
        .arg("(+ 1 2)")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "3");
}

#[test]
fn kotoba_wasm_build_compiles_kotoba_source_file() {
    let dir = temp_dir("wasm-build");
    let cell = dir.join("cell.kotoba");
    let out = dir.join("cell.wasm");
    fs::write(&cell, r#"(defn run [ctx] ctx)"#).unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba"))
        .arg("wasm")
        .arg("build")
        .arg(&cell)
        .arg("-S")
        .arg(&dir)
        .arg("-o")
        .arg(&out)
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("[wasm build]"));
    assert!(!stderr.contains("kotoba-clj"));
    let wasm = fs::read(&out).unwrap();
    assert!(wasm.starts_with(b"\0asm"));

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn kotoba_wasm_safe_policy_synthesizes_policy_for_kotoba_source() {
    let dir = temp_dir("safe-policy");
    let cell = dir.join("cell.kotoba");
    fs::write(&cell, r#"(defn run [] (kqe-assert! "graphA" "s" "p" "v"))"#).unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba"))
        .arg("wasm")
        .arg("safe-policy")
        .arg(&cell)
        .arg("-S")
        .arg(&dir)
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains(":graph-write"));
    assert!(stdout.contains("\"graphA\""));
    assert!(!stdout.contains("kotoba-clj"));

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn kotoba_wasm_safe_policy_prefers_kotoba_namespace_over_clj_compat() {
    let dir = temp_dir("namespace-priority");
    let src = dir.join("src");
    let demo = src.join("demo");
    fs::create_dir_all(&demo).unwrap();
    let cell = dir.join("cell.kotoba");
    fs::write(
        &cell,
        r#"(ns demo.main (:require [demo.util :as u]))
(defn run [] (u/write))"#,
    )
    .unwrap();
    fs::write(
        demo.join("util.kotoba"),
        r#"(ns demo.util)
(defn write [] (kqe-assert! "graphKotoba" "s" "p" "v"))"#,
    )
    .unwrap();
    fs::write(
        demo.join("util.clj"),
        r#"(ns demo.util)
(defn write [] (kqe-assert! "graphClj" "s" "p" "v"))"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba"))
        .arg("wasm")
        .arg("safe-policy")
        .arg(&cell)
        .arg("-S")
        .arg(&src)
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("\"graphKotoba\""));
    assert!(!stdout.contains("graphClj"));

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn kotoba_wasm_selfhost_inspect_reports_kotoba_analyzer_json() {
    let dir = temp_dir("selfhost-inspect");
    let cell = dir.join("cell.kotoba");
    fs::write(&cell, r#"(defn run [] (kqe-assert! "graphA" "s" "p" "v"))"#).unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba"))
        .arg("wasm")
        .arg("selfhost-inspect")
        .arg(&cell)
        .arg("-S")
        .arg(&dir)
        .arg("--json")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains(r#""abi": "kotoba.selfhost.safe-analyzer.v1""#));
    assert!(stdout.contains(r#""readerTarget": "kotoba""#));
    assert!(stdout.contains(r#""functions": 1"#));
    assert!(stdout.contains(r#""name": "run""#));
    assert!(stdout.contains(r#""graph-write""#));
    assert!(!stdout.contains("kotoba-clj"));

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn kotoba_wasm_safe_build_reports_kotoba_admission_gate() {
    let dir = temp_dir("safe-build");
    let cell = dir.join("cell.kotoba");
    let policy = dir.join("policy.edn");
    let out = dir.join("cell.wasm");
    fs::write(&cell, r#"(defn run [] (kqe-assert! "graphA" "s" "p" "v"))"#).unwrap();
    fs::write(
        &policy,
        r#"{:imports {:graph-read [] :graph-write ["graphA"] :infer [] :auth false :egress [] :secrets [] :clock false :random false}
            :limits {:memory-pages 4 :fuel 1000000 :max-call-depth 128 :max-output-bytes 65536}}"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba"))
        .arg("wasm")
        .arg("safe-build")
        .arg(&cell)
        .arg("--policy")
        .arg(&policy)
        .arg("-S")
        .arg(&dir)
        .arg("-o")
        .arg(&out)
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("admission gate: selfhost/kotoba"));
    assert!(!stderr.contains("admission gate: selfhost/kotoba-clj"));
    assert!(stderr.contains("capability surface: kotoba:kais/kqe@0.1.0"));
    assert!(out.exists());

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn kotoba_wasm_safe_build_rejects_package_lock_over_policy() {
    let dir = temp_dir("safe-build-package-lock");
    let cell = dir.join("cell.kotoba");
    let policy = dir.join("policy.edn");
    let lock = dir.join("kotoba.lock.edn");
    let out = dir.join("cell.wasm");
    fs::write(&cell, r#"(defn run [x] (+ x 1))"#).unwrap();
    fs::write(
        &policy,
        r#"{:imports {:graph-read ["graphA"] :graph-write [] :infer [] :auth false :egress [] :secrets [] :clock false :random false}
            :limits {:memory-pages 4 :fuel 1000000 :max-call-depth 128 :max-output-bytes 65536}}"#,
    )
    .unwrap();
    fs::write(
        &lock,
        r#"{:kotoba.lock/version 1
            :deps
            [{:dep/name "kotoba-lang/json"
              :dep/version "0.1.0"
              :dep/repo-rid "bafyrepojson111111111111111111111111111111111111111111111111"
              :dep/ref "refs/tags/v0.1.0"
              :dep/commit "0123456789abcdef0123456789abcdef01234567"
              :dep/tree-cid "bafytreejson111111111111111111111111111111111111111111111111"
              :dep/manifest-cid "bafymanifestjson111111111111111111111111111111111111111111"
              :dep/signers ["did:key:z6Mkpkgjson"]
              :dep/capabilities [:graph-write]}]}"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba"))
        .arg("wasm")
        .arg("safe-build")
        .arg(&cell)
        .arg("--policy")
        .arg(&policy)
        .arg("--package-lock")
        .arg(&lock)
        .arg("-S")
        .arg(&dir)
        .arg("-o")
        .arg(&out)
        .output()
        .unwrap();

    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("dependency capability grant exceeds caller policy"));
    assert!(stderr.contains(":graph-write"));
    assert!(!out.exists());

    let _ = fs::remove_dir_all(dir);
}
