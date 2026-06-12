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

fn temp_path(name: &str) -> std::path::PathBuf {
    let mut path = std::env::temp_dir();
    path.push(format!("kotoba-clj-test-{}-{name}", std::process::id()));
    path
}
