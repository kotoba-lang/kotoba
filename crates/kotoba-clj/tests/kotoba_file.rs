use std::fs;
use std::process::Command;

#[test]
fn compiles_kotoba_file_with_shebang() {
    let path = temp_path("shebang.kotoba");
    fs::write(
        &path,
        "#!/usr/bin/env kotoba-clj\n(defn main [x] (clojure.core/inc x))\n",
    )
    .unwrap();

    let wasm = kotoba_clj::compile_file(&path).unwrap();
    let out = kotoba_clj::run::run(&wasm, "main", &[41]).unwrap();
    assert_eq!(out, 42);

    let _ = fs::remove_file(path);
}

#[test]
fn binary_runs_kotoba_file_main() {
    let path = temp_path("main.kotoba");
    fs::write(&path, "(defn main [a b] (+ a b))\n").unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&path)
        .arg("20")
        .arg("22")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn binary_runs_inline_expression() {
    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
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
fn binary_writes_inline_expression_wasm() {
    let out = temp_path("inline-expr.wasm");
    let _ = fs::remove_file(&out);

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("-e")
        .arg("(* 6 7)")
        .arg("--wasm-out")
        .arg(&out)
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");
    let wasm = fs::read(&out).unwrap();
    assert!(wasm.starts_with(b"\0asm"));

    let _ = fs::remove_file(out);
}

#[test]
fn binary_accepts_clj_extension_without_escape_hatch() {
    let path = temp_path("main.clj");
    fs::write(
        &path,
        "(ns demo.main (:require [clojure.core :as c]))\n(defn main [x] (inc x))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&path)
        .arg("41")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[cfg(feature = "cli")]
#[test]
fn binary_safe_build_reports_kotoba_selfhost_gate() {
    let dir = temp_dir("selfhost-safe-build");
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

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("safe-build")
        .arg(&cell)
        .arg("--policy")
        .arg(&policy)
        .arg("--selfhost-gate")
        .arg("--reader-target")
        .arg("kotoba")
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
    assert!(stderr.contains("capability surface: kotoba:kais/kqe@0.1.0"));
    assert!(out.exists());

    let _ = fs::remove_dir_all(dir);
}

#[cfg(feature = "cli")]
#[test]
fn binary_safe_build_selfhost_gate_rejects_ungranted_resource() {
    let dir = temp_dir("selfhost-safe-build-deny");
    let cell = dir.join("cell.kotoba");
    let policy = dir.join("policy.edn");
    fs::write(&cell, r#"(defn run [] (kqe-assert! "graphB" "s" "p" "v"))"#).unwrap();
    fs::write(
        &policy,
        r#"{:imports {:graph-read [] :graph-write ["graphA"] :infer [] :auth false :egress [] :secrets [] :clock false :random false}
            :limits {:memory-pages 4 :fuel 1000000 :max-call-depth 128 :max-output-bytes 65536}}"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("safe-build")
        .arg(&cell)
        .arg("--policy")
        .arg(&policy)
        .arg("--selfhost-gate")
        .arg("-S")
        .arg(&dir)
        .output()
        .unwrap();

    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("self-hosted capability confinement"));
    assert!(stderr.contains("graph-write:graphB"));

    let _ = fs::remove_dir_all(dir);
}

#[cfg(feature = "cli")]
#[test]
fn binary_safe_policy_uses_selfhost_gate() {
    let dir = temp_dir("selfhost-safe-policy");
    let cell = dir.join("cell.kotoba");
    let out = dir.join("policy.edn");
    fs::write(&cell, r#"(defn run [] (llm-infer "modelA" "prompt"))"#).unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("safe-policy")
        .arg(&cell)
        .arg("--selfhost-gate")
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
    let policy = fs::read_to_string(&out).unwrap();
    let policy = kotoba_clj::Policy::parse_edn(&policy).unwrap();
    assert_eq!(
        policy.infer,
        std::collections::BTreeSet::from(["modelA".to_string()])
    );

    let _ = fs::remove_dir_all(dir);
}

#[cfg(feature = "cli")]
#[test]
fn binary_safe_policy_selfhost_gate_honors_reader_target() {
    let dir = temp_dir("selfhost-safe-policy-reader-target");
    let cell = dir.join("cell.cljc");
    let out = dir.join("policy.edn");
    fs::write(
        &cell,
        r#"
#?(:cljs   (defn run [] (llm-infer "modelCljs" "prompt"))
   :clj    (defn run [] (llm-infer "modelClj" "prompt"))
   :kotoba (defn run [] (llm-infer "modelKotoba" "prompt")))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("safe-policy")
        .arg(&cell)
        .arg("--selfhost-gate")
        .arg("--reader-target")
        .arg("cljs")
        .arg("-o")
        .arg(&out)
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let policy = fs::read_to_string(&out).unwrap();
    let policy = kotoba_clj::Policy::parse_edn(&policy).unwrap();
    assert_eq!(
        policy.infer,
        std::collections::BTreeSet::from(["modelCljs".to_string()])
    );

    let _ = fs::remove_dir_all(dir);
}

#[cfg(feature = "cli")]
#[test]
fn binary_selfhost_inspect_prints_request_and_summary() {
    let dir = temp_dir("selfhost-inspect");
    let cell = dir.join("cell.cljc");
    fs::write(
        &cell,
        r#"
#?(:cljs (defn run [] (kqe-assert! "cljsGraph" "s" "p" "v"))
   :clj  (defn run [] (kqe-assert! "cljGraph" "s" "p" "v")))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("selfhost-inspect")
        .arg(&cell)
        .arg("--reader-target")
        .arg("cljs")
        .arg("--request-hex")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("abi: kotoba.selfhost.safe-analyzer.v1"));
    assert!(stdout.contains("request.functions: 1"));
    assert!(stdout.contains("request.cbor.hex: "));
    assert!(stdout.contains("function run effects={graph-write}"));
    assert!(stdout.contains("caps={graph-write}"));
    assert!(stdout.contains("targets={cljsGraph}"));
    assert!(stdout.contains("types.ok: true"));

    let _ = fs::remove_dir_all(dir);
}

#[cfg(feature = "cli")]
#[test]
fn binary_selfhost_inspect_reports_type_denials() {
    let dir = temp_dir("selfhost-inspect-types");
    let cell = dir.join("cell.kotoba");
    fs::write(&cell, r#"(defn run [] (byte-at "ab" 2))"#).unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("selfhost-inspect")
        .arg(&cell)
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("types.ok: false"));
    assert!(stdout.contains("types.denials: byte-at"));

    let _ = fs::remove_dir_all(dir);
}

#[cfg(feature = "cli")]
#[test]
fn binary_selfhost_inspect_can_emit_json() {
    let dir = temp_dir("selfhost-inspect-json");
    let cell = dir.join("cell.kotoba");
    let policy = dir.join("policy.edn");
    fs::write(&cell, r#"(defn run [] (llm-infer "modelA" "prompt"))"#).unwrap();
    fs::write(
        &policy,
        r#"{:imports {:graph-read [] :graph-write [] :infer ["modelA"] :auth false :egress [] :secrets [] :clock false :random false}
            :limits {:memory-pages 4 :fuel 1000000 :max-call-depth 128 :max-output-bytes 65536}}"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("selfhost-inspect")
        .arg(&cell)
        .arg("--policy")
        .arg(&policy)
        .arg("--request-hex")
        .arg("--json")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let value: serde_json::Value =
        serde_json::from_slice(&output.stdout).expect("selfhost-inspect json");
    assert_eq!(value["abi"], "kotoba.selfhost.safe-analyzer.v1");
    assert_eq!(value["readerTarget"], "kotoba");
    assert_eq!(value["request"]["functions"], 1);
    assert!(value["request"]["cborHex"]
        .as_str()
        .is_some_and(|s| !s.is_empty()));
    assert_eq!(value["functions"][0]["name"], "run");
    assert_eq!(value["functions"][0]["effects"][0], "infer");
    assert_eq!(value["functions"][0]["caps"][0], "infer");
    assert_eq!(value["functions"][0]["targets"][0], "modelA");
    assert_eq!(value["admission"]["effects"]["ok"], true);
    assert_eq!(value["admission"]["policy"]["ok"], true);
    assert_eq!(value["admission"]["policy"]["used"][0], "infer");
    assert_eq!(value["types"]["ok"], true);
    assert!(value["types"]["denials"]
        .as_array()
        .is_some_and(Vec::is_empty));

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn binary_accepts_quote_syntax_in_file() {
    let path = temp_path("quote.kotoba");
    fs::write(
        &path,
        "(ns demo.quote)\n(defn main [x] (+ x (str-len '(a b c))))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&path)
        .arg("35")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn binary_ignores_clojure_metadata_syntax() {
    let path = temp_path("metadata.kotoba");
    fs::write(
        &path,
        r#"
(ns demo.metadata)
^:private
(defn ^:export main "entry" [^long x ^String y]
  (+ x (str-len y)))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&path)
        .arg("40")
        .arg("2")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn binary_ignores_discard_reader_syntax() {
    let path = temp_path("discard.kotoba");
    fs::write(
        &path,
        r#"
(ns demo.discard)
#_ (defn main [x] (missing x))
#_ ^:private '(discarded data)
(defn main [x] (+ x 2))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&path)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn binary_accepts_threading_macros_in_file() {
    let path = temp_path("threading.kotoba");
    fs::write(
        &path,
        r#"
(ns demo.threading)
(defn main [x]
  (+ (-> x inc)
     (->> x (+ 1) (* 1))
     (cond-> 0 true (+ 0))
     (some-> 5 (+ 5))))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&path)
        .arg("15")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn binary_accepts_case_in_file() {
    let path = temp_path("case.kotoba");
    fs::write(
        &path,
        r#"
(ns demo.case)
(defn main [x]
  (case x
    1 10
    (2 3) 42
    7))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&path)
        .arg("3")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn cljc_reader_conditionals_select_kotoba_then_clj_fallback() {
    let path = temp_path("conditional.cljc");
    fs::write(
        &path,
        r#"
(ns demo.conditional)
#?(:cljs (defn ignored [x] x)
   :kotoba (defn main [x] (+ x 10))
   :clj (defn main [x] (+ x 1)))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&path)
        .arg("32")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn binary_accepts_vector_and_map_literals_in_file() {
    let path = temp_path("literals.kotoba");
    fs::write(
        &path,
        r#"
(ns demo.literals)
(defn main [x]
  (let [v [10 20 30]
        m {:offset x :values v}]
    (+ (get m :offset) (count (get m :values)) (last v))))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&path)
        .arg("9")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn reader_target_can_select_cljs_branch() {
    let path = temp_path("target.cljs");
    fs::write(
        &path,
        r#"
#?(:cljs (defn main [x] (+ x 2))
   :clj (defn main [x] (+ x 100)))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("--reader-target")
        .arg("cljs")
        .arg(&path)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn require_alias_loads_neighbor_namespace() {
    let dir = temp_dir("require-alias");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/util.kotoba"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :as u]))\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_as_alias_does_not_load_namespace() {
    let dir = temp_dir("require-as-alias");
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [missing.spec :as-alias spec]))\n(defn main [x] (+ x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn unused_platform_requires_do_not_load_files() {
    let path = temp_path("platform-requires.cljc");
    fs::write(
        &path,
        r#"
(ns demo.platform
  (:require [clojure.string :as str]
            [clojure.set :refer [union]]
            [cljs.core :as cljs]))
(defn main [x] (+ x 2))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("--reader-target")
        .arg("cljs")
        .arg(&path)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_file(path);
}

#[test]
fn reader_target_controls_required_namespace_extension_priority() {
    let dir = temp_dir("require-extension-priority");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/util.clj"),
        "(ns demo.util)\n(defn add [a b] (+ a b 1000))\n",
    )
    .unwrap();
    fs::write(
        dir.join("demo/util.cljs"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("main.cljs");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :as u]))\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("--reader-target")
        .arg("cljs")
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn kotoba_target_prefers_kotoba_required_namespace() {
    let dir = temp_dir("require-kotoba-priority");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/util.clj"),
        "(ns demo.util)\n(defn add [a b] (+ a b 1000))\n",
    )
    .unwrap();
    fs::write(
        dir.join("demo/util.kotoba"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :as u]))\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_loads_namespace_with_defonce_and_private_defn() {
    let dir = temp_dir("require-private-defn");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/util.kotoba"),
        r#"
(ns demo.util)
(defonce bonus "compile-time value" 1)
(defn- hidden
  ([x] (+ x bonus)))
(defn shadow-param [bonus] bonus)
(defn shadow-let [x] (let [bonus x] bonus))
(defn shadow-if-let [bonus] (if-let [bonus bonus] bonus 0))
(defn shadow-when-let [bonus] (when-let [bonus bonus] bonus))
(defn shadow-as-thread [bonus] (as-> bonus bonus (+ bonus 1)))
(defn add [a]
  (+ (hidden a)
     (shadow-param 80)
     (shadow-let 10)
     (shadow-if-let 5)
     (shadow-when-let 5)
     (shadow-as-thread 6)))
"#,
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :as u]))\n(defn main [x] (u/add x))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("--")
        .arg("-66")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_loads_namespace_wrapped_in_top_level_do() {
    let dir = temp_dir("require-top-level-do");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/util.kotoba"),
        r#"
(do
  (ns demo.util)
  (def offset 2)
  (defn add [x] (+ x offset)))
"#,
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :refer [add]]))\n(defn main [x] (add x))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_refer_loads_neighbor_namespace() {
    let dir = temp_dir("require-refer");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.kotoba"),
        "(ns demo.math)\n(defn twice [x] (* x 2))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.math :refer [twice]]))\n(defn main [x] (+ (twice x) 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("20")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_refer_all_loads_exported_names_only() {
    let dir = temp_dir("require-refer-all");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.kotoba"),
        "(ns demo.math)\n(defn twice [x] (* x 2))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.math :refer :all]))\n(defn main [x] (+ (twice x) 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("20")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_refer_all_exclude_preserves_local_name() {
    let dir = temp_dir("require-refer-all-exclude");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.kotoba"),
        "(ns demo.math)\n(defn twice [x] (* x 100))\n(defn inc2 [x] (+ x 2))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.math :refer :all :exclude [twice]]))\n(defn twice [x] (+ x 2))\n(defn main [x] (+ (twice x) (inc2 0)))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("38")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn destructuring_bindings_shadow_referred_names() {
    let dir = temp_dir("destructuring-shadow");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.kotoba"),
        "(ns demo.math)\n(defn x [n] (+ n 1000))\n(defn rest [n] (+ n 1000))\n(defn whole [n] (+ n 1000))\n(defn a [n] (+ n 1000))\n(defn b [n] (+ n 1000))\n(defn missing [n] (+ n 1000))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        r#"
(ns demo.main (:require [demo.math :refer [x rest whole a b missing]]))
(defn main [n]
  (let [[x & rest :as whole] [27 4 10]]
    (let [{:keys [a missing] :strs [b] :or {missing 5}} {:a 2 "b" 4}]
      (+ n x (count rest) (last rest) (count whole) a b missing))))
"#,
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("0")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "53");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_rename_rewrites_local_name_to_exported_name() {
    let dir = temp_dir("require-rename");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.kotoba"),
        "(ns demo.math)\n(defn twice [x] (* x 2))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.math :rename {twice double}]))\n(defn main [x] (+ (double x) 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("20")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_prefix_list_loads_nested_namespace() {
    let dir = temp_dir("require-prefix");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/util.kotoba"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo [util :as u]]))\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn ns_use_exclude_preserves_local_name() {
    let dir = temp_dir("ns-use-exclude");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.kotoba"),
        "(ns demo.math)\n(defn twice [x] (* x 100))\n(defn inc2 [x] (+ x 2))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:use [demo.math :exclude [twice]]))\n(defn twice [x] (+ x 2))\n(defn main [x] (+ (twice x) (inc2 0)))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("38")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_macros_is_loaded_like_require_for_compat() {
    let dir = temp_dir("require-macros");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.clj"),
        "(ns demo.math)\n(defn twice [x] (* x 2))\n",
    )
    .unwrap();
    let main = dir.join("main.cljs");
    fs::write(
        &main,
        "(ns demo.main (:require-macros [demo.math :refer [twice]]))\n(defn main [x] (+ (twice x) 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("--reader-target")
        .arg("cljs")
        .arg(&main)
        .arg("20")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_refer_macros_is_loaded_like_refer_for_compat() {
    let dir = temp_dir("require-refer-macros");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.clj"),
        "(ns demo.math)\n(defn twice [x] (* x 2))\n",
    )
    .unwrap();
    let main = dir.join("main.cljs");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.math :refer-macros [twice]]))\n(defn main [x] (+ (twice x) 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("--reader-target")
        .arg("cljs")
        .arg(&main)
        .arg("20")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn require_macros_can_load_macro_only_namespace() {
    let dir = temp_dir("require-macro-only");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/macros.clj"),
        r#"
(ns demo.macros)
(defmacro ignored-when-runtime-only [x] (list '+ x 1000))
"#,
    )
    .unwrap();
    let main = dir.join("main.cljs");
    fs::write(
        &main,
        "(ns demo.main (:require-macros [demo.macros :refer [ignored-when-runtime-only]]))\n(defn main [x] (+ x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("--reader-target")
        .arg("cljs")
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn ns_use_only_and_rename_load_neighbor_namespace() {
    let dir = temp_dir("ns-use");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.kotoba"),
        "(ns demo.math)\n(defn twice [x] (* x 2))\n(defn bump [x] (+ x 1))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:use [demo.math :only [twice] :rename {bump inc2}]))\n(defn main [x] (+ (twice x) (inc2 1)))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("20")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn top_level_require_loads_neighbor_namespace() {
    let dir = temp_dir("top-level-require");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/util.kotoba"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(require '[demo.util :as u])\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn top_level_use_loads_neighbor_namespace() {
    let dir = temp_dir("top-level-use");
    fs::create_dir_all(dir.join("demo")).unwrap();
    fs::write(
        dir.join("demo/math.kotoba"),
        "(ns demo.math)\n(defn twice [x] (* x 2))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(use '[demo.math :only [twice]])\n(defn main [x] (+ (twice x) 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("20")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn source_path_flag_resolves_require_outside_entry_dir() {
    let dir = temp_dir("source-path-flag");
    fs::create_dir_all(dir.join("src/demo")).unwrap();
    fs::write(
        dir.join("src/demo/util.kotoba"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :as u]))\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg("--source-path")
        .arg(dir.join("src"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn env_source_path_resolves_require_outside_entry_dir() {
    let dir = temp_dir("source-path-env");
    fs::create_dir_all(dir.join("lib/demo")).unwrap();
    fs::write(
        dir.join("lib/demo/util.kotoba"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :as u]))\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .env("KOTOBA_SOURCE_PATH", dir.join("lib"))
        .env_remove("KOTOBA_CLJ_PATH")
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn legacy_clj_env_source_path_still_resolves_require() {
    let dir = temp_dir("source-path-env-legacy");
    fs::create_dir_all(dir.join("lib/demo")).unwrap();
    fs::write(
        dir.join("lib/demo/util.kotoba"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :as u]))\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .env_remove("KOTOBA_SOURCE_PATH")
        .env("KOTOBA_CLJ_PATH", dir.join("lib"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn deps_edn_paths_resolve_project_source_root() {
    let dir = temp_dir("deps-edn-paths");
    fs::create_dir_all(dir.join("src/demo")).unwrap();
    fs::write(dir.join("deps.edn"), "{:paths [\"src\"]}\n").unwrap();
    fs::write(
        dir.join("src/demo/util.kotoba"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :as u]))\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn deps_edn_is_discovered_from_entry_ancestors() {
    let dir = temp_dir("deps-edn-ancestor");
    fs::create_dir_all(dir.join("app")).unwrap();
    fs::create_dir_all(dir.join("src/demo")).unwrap();
    fs::write(dir.join("deps.edn"), "{:paths [\"src\"]}\n").unwrap();
    fs::write(
        dir.join("src/demo/util.kotoba"),
        "(ns demo.util)\n(defn add [a b] (+ a b))\n",
    )
    .unwrap();
    let main = dir.join("app/main.kotoba");
    fs::write(
        &main,
        "(ns demo.main (:require [demo.util :as u]))\n(defn main [x] (u/add x 2))\n",
    )
    .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_kotoba-clj"))
        .arg(&main)
        .arg("40")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "42");

    let _ = fs::remove_dir_all(dir);
}

fn temp_path(name: &str) -> std::path::PathBuf {
    let mut path = std::env::temp_dir();
    path.push(format!("kotoba-clj-test-{}-{name}", std::process::id()));
    path
}

fn temp_dir(name: &str) -> std::path::PathBuf {
    let path = temp_path(name);
    let _ = fs::remove_dir_all(&path);
    fs::create_dir_all(&path).unwrap();
    path
}
