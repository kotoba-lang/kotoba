//! Manifest-driven conformance checks against fixtures owned by `kotoba-lang`.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use kotoba_clj::{
    compile_expr_with_prelude_and_reader_target, compile_file_with_prelude,
    compile_file_with_prelude_reader_target_and_source_paths, compile_safe_file, run, Policy,
    ReaderTarget,
};
use kotoba_edn::{parse_all, EdnValue};

fn fixture_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("kotoba-lang/resources/kotoba/lang/conformance")
}

#[derive(Debug)]
enum CaseKind {
    Run,
    CompileExpr,
    ExpectError,
    ExtensionError,
}

#[derive(Debug)]
struct Case {
    id: String,
    kind: CaseKind,
    entry: Option<String>,
    expr: Option<String>,
    source_paths: Vec<String>,
    function: String,
    args: Vec<i64>,
    expect: BTreeMap<ReaderTarget, i64>,
    target: Option<ReaderTarget>,
    safe: bool,
    error_contains: Option<String>,
}

fn manifest_cases() -> Vec<Case> {
    let forms = parse_all(kotoba_lang::CONFORMANCE_MANIFEST_EDN).unwrap();
    let manifest = forms.first().unwrap().as_map().unwrap();
    manifest
        .get(&EdnValue::kw_bare("cases"))
        .unwrap()
        .as_vector()
        .unwrap()
        .iter()
        .map(parse_case)
        .collect()
}

fn parse_case(value: &EdnValue) -> Case {
    let map = value.as_map().unwrap();
    let id = kw_name(get(map, "id")).to_string();
    let kind = match kw_name(get(map, "kind")) {
        "run" => CaseKind::Run,
        "compile-expr" => CaseKind::CompileExpr,
        "expect-error" => CaseKind::ExpectError,
        "extension-error" => CaseKind::ExtensionError,
        other => panic!("unsupported conformance kind: {other}"),
    };
    let entry = map
        .get(&EdnValue::kw_bare("entry"))
        .and_then(EdnValue::as_string)
        .map(str::to_string);
    let expr = map
        .get(&EdnValue::kw_bare("expr"))
        .and_then(EdnValue::as_string)
        .map(str::to_string);
    let source_paths = map
        .get(&EdnValue::kw_bare("source-paths"))
        .and_then(EdnValue::as_vector)
        .unwrap_or(&[])
        .iter()
        .map(|v| v.as_string().unwrap().to_string())
        .collect();
    let function = map
        .get(&EdnValue::kw_bare("function"))
        .and_then(EdnValue::as_string)
        .unwrap_or("main")
        .to_string();
    let args = map
        .get(&EdnValue::kw_bare("args"))
        .and_then(EdnValue::as_vector)
        .unwrap_or(&[])
        .iter()
        .map(|v| v.as_integer().unwrap())
        .collect();
    let expect = map
        .get(&EdnValue::kw_bare("expect"))
        .and_then(EdnValue::as_map)
        .map(parse_expect)
        .unwrap_or_default();
    let target = map
        .get(&EdnValue::kw_bare("target"))
        .map(|v| parse_target(kw_name(v)));
    let safe = map
        .get(&EdnValue::kw_bare("safe"))
        .and_then(EdnValue::as_bool)
        .unwrap_or(false);
    let error_contains = map
        .get(&EdnValue::kw_bare("error-contains"))
        .and_then(EdnValue::as_string)
        .map(str::to_string);

    Case {
        id,
        kind,
        entry,
        expr,
        source_paths,
        function,
        args,
        expect,
        target,
        safe,
        error_contains,
    }
}

fn parse_expect(map: &BTreeMap<EdnValue, EdnValue>) -> BTreeMap<ReaderTarget, i64> {
    map.iter()
        .map(|(k, v)| (parse_target(kw_name(k)), v.as_integer().unwrap()))
        .collect()
}

fn get<'a>(map: &'a BTreeMap<EdnValue, EdnValue>, key: &str) -> &'a EdnValue {
    map.get(&EdnValue::kw_bare(key))
        .unwrap_or_else(|| panic!("missing conformance key: {key}"))
}

fn kw_name(value: &EdnValue) -> &str {
    let kw = value.as_keyword().unwrap();
    assert!(
        kw.namespace().is_none(),
        "conformance keywords must be bare"
    );
    kw.name()
}

fn parse_target(name: &str) -> ReaderTarget {
    ReaderTarget::parse(name).unwrap_or_else(|| panic!("unsupported reader target: {name}"))
}

fn compile_and_run(case: &Case, target: ReaderTarget) -> i64 {
    let root = fixture_root();
    let paths = case
        .source_paths
        .iter()
        .map(|p| root.join(p))
        .collect::<Vec<_>>();
    let wasm = compile_file_with_prelude_reader_target_and_source_paths(
        root.join(case.entry.as_ref().expect("run case requires :entry")),
        target,
        &paths,
    )
    .unwrap_or_else(|err| {
        panic!(
            "{} failed to compile for {}: {err}",
            case.id,
            target.as_str()
        )
    });
    run::run(&wasm, &case.function, &case.args)
        .unwrap_or_else(|err| panic!("{} failed to run for {}: {err}", case.id, target.as_str()))
}

fn compile_expr_and_run(case: &Case, target: ReaderTarget) -> i64 {
    let expr = case
        .expr
        .as_ref()
        .expect("compile-expr case requires :expr");
    let wasm = compile_expr_with_prelude_and_reader_target(expr, target).unwrap_or_else(|err| {
        panic!(
            "{} failed to compile expression for {}: {err}",
            case.id,
            target.as_str()
        )
    });
    run::run(&wasm, &case.function, &case.args).unwrap_or_else(|err| {
        panic!(
            "{} failed to run expression for {}: {err}",
            case.id,
            target.as_str()
        )
    })
}

fn compile_error(case: &Case) -> String {
    let root = fixture_root();
    let path = root.join(case.entry.as_ref().expect("error case requires :entry"));
    if case.safe {
        compile_safe_file(path, &Policy::deny_all())
            .expect_err("negative safe conformance case unexpectedly compiled")
            .to_string()
    } else {
        let target = case.target.unwrap_or(ReaderTarget::Kotoba);
        compile_file_with_prelude_reader_target_and_source_paths(path, target, &[])
            .expect_err("negative conformance case unexpectedly compiled")
            .to_string()
    }
}

#[test]
fn conformance_manifest_cases_pass() {
    for case in manifest_cases() {
        match case.kind {
            CaseKind::Run => {
                for (target, expected) in &case.expect {
                    assert_eq!(
                        compile_and_run(&case, *target),
                        *expected,
                        "{} target {}",
                        case.id,
                        target.as_str()
                    );
                }
            }
            CaseKind::CompileExpr => {
                for (target, expected) in &case.expect {
                    assert_eq!(
                        compile_expr_and_run(&case, *target),
                        *expected,
                        "{} target {}",
                        case.id,
                        target.as_str()
                    );
                }
            }
            CaseKind::ExpectError => {
                let error = compile_error(&case);
                let expected = case.error_contains.as_deref().unwrap();
                assert!(
                    error.contains(expected),
                    "{} error did not contain {expected:?}: {error}",
                    case.id
                );
            }
            CaseKind::ExtensionError => {
                let path = fixture_root()
                    .join(case.entry.as_ref().expect("extension case requires :entry"));
                assert!(
                    !kotoba_lang::is_supported_source_path(&path),
                    "{} unexpectedly accepted extension",
                    case.id
                );
                let expected = case.error_contains.as_deref().unwrap();
                let error = "unsupported source extension";
                assert!(error.contains(expected), "{} mismatch", case.id);
            }
        }
    }
}

#[test]
fn default_file_compile_uses_kotoba_reader_target() {
    let wasm = compile_file_with_prelude(fixture_root().join("reader_target/branching.cljc"))
        .expect("default compile must accept portable .cljc source");
    let value = run::run(&wasm, "main", &[41]).expect("compiled fixture must run");
    assert_eq!(value, 51);
}
