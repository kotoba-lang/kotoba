//! Self-hosting footholds: Kotoba programs that implement small pieces of
//! the compiler/admission gate and run as WASM Components.

#![cfg(feature = "component")]

use std::collections::{BTreeMap, BTreeSet};
use std::fs;

use ciborium::value::Value;
use kotoba_clj::ast::{self, Builtin, Expr};
use kotoba_clj::component::{compile_component_str_with_prelude, run_component};
use kotoba_clj::{
    compile_safe_kotoba, compile_safe_kotoba_with_prelude_bootstrap, embedded_capability_ifaces,
    infer_effects, minimal_policy, selfhost, unused_grants, CljError, Policy, ReaderTarget,
};

const SAFE_ANALYZER: &str = include_str!("../selfhost/safe_analyzer.kotoba");

/// Rows describing a program for the self-hosted effect checker:
/// `(function-name, cbor args, optional declared `:effects`)`.
type EffectCheckRows<'a> = Vec<(&'a str, Vec<Value>, Option<Vec<&'a str>>)>;

fn input(op: &str, target: &str) -> Vec<u8> {
    let mut map = BTreeMap::new();
    map.insert("abi".to_string(), selfhost::SAFE_ANALYZER_ABI.to_string());
    map.insert("op".to_string(), op.to_string());
    map.insert("target".to_string(), target.to_string());
    let mut out = Vec::new();
    ciborium::into_writer(&map, &mut out).expect("encode input cbor");
    out
}

fn abi_entry() -> (Value, Value) {
    (
        Value::Text("abi".to_string()),
        Value::Text(selfhost::SAFE_ANALYZER_ABI.to_string()),
    )
}

fn calls_input(calls: &[(&str, &str)]) -> Vec<u8> {
    let calls = Value::Array(
        calls
            .iter()
            .map(|(op, target)| {
                Value::Array(vec![
                    Value::Text((*op).to_string()),
                    Value::Text((*target).to_string()),
                ])
            })
            .collect(),
    );
    let value = Value::Map(vec![abi_entry(), (Value::Text("calls".to_string()), calls)]);
    let mut out = Vec::new();
    ciborium::into_writer(&value, &mut out).expect("encode calls input cbor");
    out
}

fn form(items: Vec<Value>) -> Value {
    Value::Array(items)
}

fn text(s: &str) -> Value {
    Value::Text(s.to_string())
}

fn var(name: &str) -> Value {
    Value::Map(vec![(
        Value::Text("var".to_string()),
        Value::Text(name.to_string()),
    )])
}

fn kv(key: &str, value: Value) -> (Value, Value) {
    (Value::Text(key.to_string()), value)
}

fn ast_str(value: &str) -> Value {
    Value::Map(vec![kv("tag", text("str")), kv("value", text(value))])
}

fn ast_builtin(op: &str, args: Vec<Value>) -> Value {
    Value::Map(vec![
        kv("tag", text("builtin")),
        kv("op", text(op)),
        kv("args", Value::Array(args)),
    ])
}

fn ast_call(name: &str, args: Vec<Value>) -> Value {
    Value::Map(vec![
        kv("tag", text("call")),
        kv("name", text(name)),
        kv("args", Value::Array(args)),
    ])
}

fn ast_body_program_input(functions: Vec<(&str, Vec<Value>)>) -> Vec<u8> {
    let program = Value::Array(
        functions
            .into_iter()
            .map(|(name, body)| {
                Value::Map(vec![kv("name", text(name)), kv("body", Value::Array(body))])
            })
            .collect(),
    );
    let value = Value::Map(vec![abi_entry(), kv("program", program)]);
    let mut out = Vec::new();
    ciborium::into_writer(&value, &mut out).expect("encode ast body program input cbor");
    out
}

fn forms_input(forms: Vec<Value>) -> Vec<u8> {
    let value = Value::Map(vec![
        abi_entry(),
        (Value::Text("forms".to_string()), Value::Array(forms)),
    ]);
    let mut out = Vec::new();
    ciborium::into_writer(&value, &mut out).expect("encode forms input cbor");
    out
}

fn program_input(entry: &str, functions: Vec<(&str, Vec<Value>)>) -> Vec<u8> {
    program_input_with_entry(Some(entry), functions)
}

fn program_all_input(functions: Vec<(&str, Vec<Value>)>) -> Vec<u8> {
    program_input_with_entry(None, functions)
}

fn program_input_with_entry(entry: Option<&str>, functions: Vec<(&str, Vec<Value>)>) -> Vec<u8> {
    let program = Value::Array(
        functions
            .into_iter()
            .map(|(name, forms)| {
                Value::Map(vec![
                    (
                        Value::Text("name".to_string()),
                        Value::Text(name.to_string()),
                    ),
                    (Value::Text("forms".to_string()), Value::Array(forms)),
                ])
            })
            .collect(),
    );
    let mut entries = vec![abi_entry(), (Value::Text("program".to_string()), program)];
    if let Some(entry) = entry {
        entries.push((
            Value::Text("entry".to_string()),
            Value::Text(entry.to_string()),
        ));
    }
    let value = Value::Map(entries);
    let mut out = Vec::new();
    ciborium::into_writer(&value, &mut out).expect("encode program input cbor");
    out
}

fn program_effect_check_input(functions: EffectCheckRows<'_>) -> Vec<u8> {
    let program = Value::Array(
        functions
            .into_iter()
            .map(|(name, forms, declared)| {
                let mut entries = vec![
                    (
                        Value::Text("name".to_string()),
                        Value::Text(name.to_string()),
                    ),
                    (Value::Text("forms".to_string()), Value::Array(forms)),
                ];
                if let Some(declared) = declared {
                    entries.push((
                        Value::Text("declared".to_string()),
                        Value::Array(declared.into_iter().map(text).collect()),
                    ));
                }
                Value::Map(entries)
            })
            .collect(),
    );
    let value = Value::Map(vec![
        abi_entry(),
        (Value::Text("program".to_string()), program),
        (
            Value::Text("check".to_string()),
            Value::Text("effects".to_string()),
        ),
    ]);
    let mut out = Vec::new();
    ciborium::into_writer(&value, &mut out).expect("encode program check input cbor");
    out
}

fn program_policy_check_input(
    functions: Vec<(&str, Vec<Value>)>,
    graph_read: Vec<&str>,
    graph_write: Vec<&str>,
    infer: Vec<&str>,
    auth: bool,
) -> Vec<u8> {
    let program = Value::Array(
        functions
            .into_iter()
            .map(|(name, forms)| {
                Value::Map(vec![
                    (
                        Value::Text("name".to_string()),
                        Value::Text(name.to_string()),
                    ),
                    (Value::Text("forms".to_string()), Value::Array(forms)),
                ])
            })
            .collect(),
    );
    let policy = Value::Map(vec![
        (
            Value::Text("graph-read".to_string()),
            Value::Array(graph_read.into_iter().map(text).collect()),
        ),
        (
            Value::Text("graph-write".to_string()),
            Value::Array(graph_write.into_iter().map(text).collect()),
        ),
        (
            Value::Text("infer".to_string()),
            Value::Array(infer.into_iter().map(text).collect()),
        ),
        (
            Value::Text("auth".to_string()),
            Value::Text(if auth { "true" } else { "false" }.to_string()),
        ),
    ]);
    let value = Value::Map(vec![
        abi_entry(),
        (Value::Text("program".to_string()), program),
        (
            Value::Text("check".to_string()),
            Value::Text("policy".to_string()),
        ),
        (Value::Text("policy".to_string()), policy),
    ]);
    let mut out = Vec::new();
    ciborium::into_writer(&value, &mut out).expect("encode program policy input cbor");
    out
}

fn program_minimal_policy_input(functions: Vec<(&str, Vec<Value>)>) -> Vec<u8> {
    let program = Value::Array(
        functions
            .into_iter()
            .map(|(name, forms)| {
                Value::Map(vec![
                    (
                        Value::Text("name".to_string()),
                        Value::Text(name.to_string()),
                    ),
                    (Value::Text("forms".to_string()), Value::Array(forms)),
                ])
            })
            .collect(),
    );
    let value = Value::Map(vec![
        abi_entry(),
        (Value::Text("program".to_string()), program),
        (
            Value::Text("check".to_string()),
            Value::Text("minimal-policy".to_string()),
        ),
    ]);
    let mut out = Vec::new();
    ciborium::into_writer(&value, &mut out).expect("encode minimal policy input cbor");
    out
}

fn program_unused_grants_input(
    functions: Vec<(&str, Vec<Value>)>,
    graph_read: Vec<&str>,
    graph_write: Vec<&str>,
    infer: Vec<&str>,
    auth: bool,
) -> Vec<u8> {
    let program = Value::Array(
        functions
            .into_iter()
            .map(|(name, forms)| {
                Value::Map(vec![
                    (
                        Value::Text("name".to_string()),
                        Value::Text(name.to_string()),
                    ),
                    (Value::Text("forms".to_string()), Value::Array(forms)),
                ])
            })
            .collect(),
    );
    let policy = Value::Map(vec![
        (
            Value::Text("graph-read".to_string()),
            Value::Array(graph_read.into_iter().map(text).collect()),
        ),
        (
            Value::Text("graph-write".to_string()),
            Value::Array(graph_write.into_iter().map(text).collect()),
        ),
        (
            Value::Text("infer".to_string()),
            Value::Array(infer.into_iter().map(text).collect()),
        ),
        (
            Value::Text("auth".to_string()),
            Value::Text(if auth { "true" } else { "false" }.to_string()),
        ),
    ]);
    let value = Value::Map(vec![
        abi_entry(),
        (Value::Text("program".to_string()), program),
        (
            Value::Text("check".to_string()),
            Value::Text("unused-grants".to_string()),
        ),
        (Value::Text("policy".to_string()), policy),
    ]);
    let mut out = Vec::new();
    ciborium::into_writer(&value, &mut out).expect("encode unused grants input cbor");
    out
}

fn analyze(op: &str, target: &str) -> BTreeMap<String, String> {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out = run_component(&component, &input(op, target)).expect("run analyzer");
    let value: Value = ciborium::from_reader(out.as_slice()).expect("decode output cbor");
    let mut result = BTreeMap::new();
    for (k, v) in value.as_map().expect("output map") {
        result.insert(
            k.as_text().expect("text key").to_string(),
            v.as_text().expect("text value").to_string(),
        );
    }
    result
}

fn analyze_calls(calls: &[(&str, &str)]) -> Value {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out = run_component(&component, &calls_input(calls)).expect("run analyzer");
    ciborium::from_reader(out.as_slice()).expect("decode output cbor")
}

fn analyze_forms(forms: Vec<Value>) -> Value {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out = run_component(&component, &forms_input(forms)).expect("run analyzer");
    ciborium::from_reader(out.as_slice()).expect("decode output cbor")
}

fn analyze_program(entry: &str, functions: Vec<(&str, Vec<Value>)>) -> Value {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out =
        run_component(&component, &program_input(entry, functions)).expect("run analyzer program");
    ciborium::from_reader(out.as_slice()).expect("decode output cbor")
}

fn analyze_program_all(functions: Vec<(&str, Vec<Value>)>) -> Value {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out =
        run_component(&component, &program_all_input(functions)).expect("run analyzer program");
    ciborium::from_reader(out.as_slice()).expect("decode output cbor")
}

fn analyze_ast_body_program(functions: Vec<(&str, Vec<Value>)>) -> Value {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out = run_component(&component, &ast_body_program_input(functions))
        .expect("run analyzer ast body program");
    ciborium::from_reader(out.as_slice()).expect("decode output cbor")
}

fn analyze_effect_check(functions: EffectCheckRows<'_>) -> Value {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out = run_component(&component, &program_effect_check_input(functions))
        .expect("run analyzer effect check");
    ciborium::from_reader(out.as_slice()).expect("decode output cbor")
}

fn analyze_policy_check(
    functions: Vec<(&str, Vec<Value>)>,
    graph_read: Vec<&str>,
    graph_write: Vec<&str>,
    infer: Vec<&str>,
    auth: bool,
) -> Value {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out = run_component(
        &component,
        &program_policy_check_input(functions, graph_read, graph_write, infer, auth),
    )
    .expect("run analyzer policy check");
    ciborium::from_reader(out.as_slice()).expect("decode output cbor")
}

fn analyze_minimal_policy(functions: Vec<(&str, Vec<Value>)>) -> Value {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out = run_component(&component, &program_minimal_policy_input(functions))
        .expect("run analyzer minimal policy");
    ciborium::from_reader(out.as_slice()).expect("decode output cbor")
}

fn analyze_unused_grants(
    functions: Vec<(&str, Vec<Value>)>,
    graph_read: Vec<&str>,
    graph_write: Vec<&str>,
    infer: Vec<&str>,
    auth: bool,
) -> Value {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out = run_component(
        &component,
        &program_unused_grants_input(functions, graph_read, graph_write, infer, auth),
    )
    .expect("run analyzer unused grants");
    ciborium::from_reader(out.as_slice()).expect("decode output cbor")
}

fn builtin_name(op: Builtin) -> &'static str {
    match op {
        Builtin::HasCapability => "has-capability?",
        Builtin::LlmInfer => "llm-infer",
        Builtin::KqeAssert => "kqe-assert!",
        Builtin::KqeRetract => "kqe-retract!",
        Builtin::KqeGetObjects => "kqe-get-objects",
        Builtin::KqeQuery => "kqe-query",
        _ => "pure-builtin",
    }
}

fn expr_form(expr: &Expr) -> Value {
    match expr {
        Expr::Int(n) => Value::Integer((*n).into()),
        Expr::Float(f) => Value::Float(*f),
        Expr::Str(bytes) => text(std::str::from_utf8(bytes).expect("utf8 string literal")),
        Expr::Var(name) => var(name),
        Expr::If { cond, then, els } => form(vec![
            text("if"),
            expr_form(cond),
            expr_form(then),
            expr_form(els),
        ]),
        Expr::Let { bindings, body } => {
            let mut items = vec![text("let")];
            let mut binding_items = Vec::new();
            for (name, value) in bindings {
                binding_items.push(text(name));
                binding_items.push(expr_form(value));
            }
            items.push(form(binding_items));
            items.extend(body.iter().map(expr_form));
            form(items)
        }
        Expr::Do(body) => {
            let mut items = vec![text("do")];
            items.extend(body.iter().map(expr_form));
            form(items)
        }
        Expr::Loop { bindings, body } => {
            let mut items = vec![text("loop")];
            let mut binding_items = Vec::new();
            for (name, value) in bindings {
                binding_items.push(text(name));
                binding_items.push(expr_form(value));
            }
            items.push(form(binding_items));
            items.extend(body.iter().map(expr_form));
            form(items)
        }
        Expr::Recur(args) => {
            let mut items = vec![text("recur")];
            items.extend(args.iter().map(expr_form));
            form(items)
        }
        Expr::Builtin { op, args } => {
            let mut items = vec![text(builtin_name(*op))];
            items.extend(args.iter().map(expr_form));
            form(items)
        }
        Expr::Call { name, args } => {
            let mut items = vec![text(name)];
            items.extend(args.iter().map(expr_form));
            form(items)
        }
        Expr::Fn { params, body } => {
            let mut items = vec![text("fn"), form(params.iter().map(|p| text(p)).collect())];
            items.extend(body.iter().map(expr_form));
            form(items)
        }
        Expr::MakeClosure { captures, .. } => {
            let mut items = vec![text("make-closure")];
            items.extend(captures.iter().map(expr_form));
            form(items)
        }
        Expr::ClosureRef(slot) => text(&format!("closure-ref-{slot}")),
        Expr::CallValue { f, args } => {
            let mut items = vec![text("call-value"), expr_form(f)];
            items.extend(args.iter().map(expr_form));
            form(items)
        }
    }
}

fn parsed_function_body_forms(src: &str, function_name: &str) -> Vec<Value> {
    let program = ast::parse_program(src).expect("parse source to AST");
    let function = program
        .functions
        .iter()
        .find(|f| f.name == function_name)
        .unwrap_or_else(|| panic!("missing function {function_name}"));
    function.body.iter().map(expr_form).collect()
}

fn parsed_program_body_forms(src: &str) -> Vec<(String, Vec<Value>)> {
    let program = ast::parse_program(src).expect("parse source to AST");
    program
        .functions
        .iter()
        .map(|f| (f.name.clone(), f.body.iter().map(expr_form).collect()))
        .collect()
}

fn text_array_field<'a>(value: &'a Value, field: &str) -> Vec<&'a str> {
    let map = value.as_map().expect("output map");
    let arr = map
        .iter()
        .find_map(|(k, v)| (k.as_text() == Some(field)).then_some(v))
        .unwrap_or_else(|| panic!("missing field {field}"))
        .as_array()
        .unwrap_or_else(|| panic!("{field} is not an array"));
    arr.iter()
        .map(|v| v.as_text().expect("array item text"))
        .collect()
}

fn text_array_set(value: &Value, field: &str) -> BTreeSet<String> {
    text_array_field(value, field)
        .into_iter()
        .map(str::to_string)
        .collect()
}

fn text_field<'a>(value: &'a Value, field: &str) -> &'a str {
    map_field(value, field)
        .as_text()
        .unwrap_or_else(|| panic!("{field} is not text"))
}

fn map_field<'a>(value: &'a Value, field: &str) -> &'a Value {
    value
        .as_map()
        .expect("value map")
        .iter()
        .find_map(|(k, v)| (k.as_text() == Some(field)).then_some(v))
        .unwrap_or_else(|| panic!("missing field {field}"))
}

fn has_field(value: &Value, field: &str) -> bool {
    value
        .as_map()
        .expect("value map")
        .iter()
        .any(|(k, _)| k.as_text() == Some(field))
}

fn function_effect_sets(value: &Value) -> BTreeMap<String, BTreeSet<String>> {
    let functions = value
        .as_map()
        .expect("output map")
        .iter()
        .find_map(|(k, v)| (k.as_text() == Some("functions")).then_some(v))
        .expect("functions field")
        .as_array()
        .expect("functions array");

    let mut out = BTreeMap::new();
    for function in functions {
        let name = text_field(function, "name").to_string();
        out.insert(name, text_array_set(function, "effects"));
    }
    out
}

fn violation<'a>(value: &'a Value, function_name: &str) -> &'a Value {
    let violations = value
        .as_map()
        .expect("output map")
        .iter()
        .find_map(|(k, v)| (k.as_text() == Some("violations")).then_some(v))
        .expect("violations field")
        .as_array()
        .expect("violations array");
    violations
        .iter()
        .find(|v| text_field(v, "name") == function_name)
        .unwrap_or_else(|| panic!("missing violation for {function_name}"))
}

fn assert_rust_effect_denied(src: &str, policy: &Policy) {
    match compile_safe_kotoba(src, policy) {
        Err(CljError::Effect(_)) => {}
        other => panic!("expected rust CljError::Effect, got {other:?}"),
    }
}

fn assert_rust_policy_denied(src: &str, policy: &Policy) {
    match compile_safe_kotoba(src, policy) {
        Err(CljError::Policy(_)) => {}
        other => panic!("expected rust CljError::Policy, got {other:?}"),
    }
}

fn assert_minimal_policy_matches(value: &Value, policy: &Policy) {
    assert_eq!(text_array_set(value, "graph-read"), policy.graph_read);
    assert_eq!(text_array_set(value, "graph-write"), policy.graph_write);
    assert_eq!(text_array_set(value, "infer"), policy.infer);
    assert_eq!(
        text_field(value, "auth"),
        if policy.auth { "true" } else { "false" }
    );
}

#[test]
fn selfhost_analyzer_compiles_as_safe_kotoba_with_no_host_capabilities() {
    let wasm = compile_safe_kotoba_with_prelude_bootstrap(SAFE_ANALYZER, &Policy::deny_all())
        .expect("selfhost analyzer must fit safe Kotoba deny-all");
    assert!(
        embedded_capability_ifaces(&wasm).is_empty(),
        "selfhost analyzer must not embed host capability imports"
    );
}

#[test]
fn selfhost_analyzer_emits_versioned_abi_marker() {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let out = run_component(&component, &input("kqe-assert!", "graphA")).expect("run analyzer");
    let value: Value = ciborium::from_reader(out.as_slice()).expect("decode analyzer output");

    assert_eq!(
        text_field(&value, "abi"),
        selfhost::SAFE_ANALYZER_ABI,
        "bridge and analyzer must agree on the CBOR ABI marker"
    );
}

#[test]
fn selfhost_analyzer_rejects_missing_input_abi_marker() {
    let component = compile_component_str_with_prelude(SAFE_ANALYZER).expect("compile analyzer");
    let value = Value::Map(vec![
        (
            Value::Text("op".to_string()),
            Value::Text("kqe-assert!".to_string()),
        ),
        (
            Value::Text("target".to_string()),
            Value::Text("graphA".to_string()),
        ),
    ]);
    let mut input = Vec::new();
    ciborium::into_writer(&value, &mut input).expect("encode abi-less input");

    let out = run_component(&component, &input).expect("run analyzer");
    let value: Value = ciborium::from_reader(out.as_slice()).expect("decode analyzer output");

    assert_eq!(text_field(&value, "abi"), selfhost::SAFE_ANALYZER_ABI);
    assert_eq!(text_field(&value, "error"), "input-abi-mismatch");
    assert_eq!(text_field(&value, "expected"), selfhost::SAFE_ANALYZER_ABI);
    assert_eq!(text_field(&value, "got"), "");
}

fn rust_cap_set(policy: &kotoba_clj::Policy) -> BTreeSet<String> {
    let mut caps = BTreeSet::new();
    if !policy.graph_write.is_empty() {
        caps.insert("graph-write".to_string());
    }
    if !policy.graph_read.is_empty() {
        caps.insert("graph-read".to_string());
    }
    if !policy.infer.is_empty() {
        caps.insert("infer".to_string());
    }
    if policy.auth {
        caps.insert("auth".to_string());
    }
    caps
}

fn rust_target_set(policy: &kotoba_clj::Policy) -> BTreeSet<String> {
    let mut targets = BTreeSet::new();
    targets.extend(policy.graph_write.iter().cloned());
    targets.extend(policy.graph_read.iter().cloned());
    targets.extend(policy.infer.iter().cloned());
    targets
}

#[test]
fn selfhost_analyzer_classifies_graph_write_builtin() {
    let out = analyze("kqe-assert!", "graphA");
    assert_eq!(out["effect"], "graph-write");
    assert_eq!(out["cap"], "graph-write");
    assert_eq!(out["target"], "graphA");
    assert_eq!(out["known"], "true");
}

#[test]
fn selfhost_analyzer_classifies_infer_builtin() {
    let out = analyze("llm-infer", "modelA");
    assert_eq!(out["effect"], "infer");
    assert_eq!(out["cap"], "infer");
    assert_eq!(out["target"], "modelA");
    assert_eq!(out["known"], "true");
}

#[test]
fn selfhost_analyzer_keeps_unknown_ops_pure() {
    let out = analyze("str-len", "");
    assert_eq!(out["effect"], "pure");
    assert_eq!(out["cap"], "none");
    assert_eq!(out["known"], "false");
}

#[test]
fn selfhost_analyzer_infers_unique_sets_from_multiple_calls() {
    let out = analyze_calls(&[
        ("kqe-assert!", "graphA"),
        ("kqe-query", ""),
        ("llm-infer", "modelA"),
        ("kqe-assert!", "graphA"),
        ("str-len", ""),
    ]);

    assert_eq!(
        text_array_field(&out, "effects"),
        vec!["graph-write", "graph-read", "infer"]
    );
    assert_eq!(
        text_array_field(&out, "caps"),
        vec!["graph-write", "graph-read", "infer"]
    );
    assert_eq!(text_array_field(&out, "targets"), vec!["graphA", "modelA"]);
    assert_eq!(text_field(&out, "known"), "true");
}

#[test]
fn selfhost_analyzer_matches_rust_effect_and_policy_facts() {
    let src = r#"
        (defn run []
          (do (kqe-assert! "graphA" "s" "p" "v")
              (kqe-get-objects "graphB" "s" "p")
              (llm-infer "modelA" "prompt")
              (has-capability? "resource" "ability")))
    "#;
    let selfhost = analyze_calls(&[
        ("kqe-assert!", "graphA"),
        ("kqe-get-objects", "graphB"),
        ("llm-infer", "modelA"),
        ("has-capability?", ""),
    ]);

    let rust_effects = infer_effects(src).expect("rust infer_effects");
    assert_eq!(text_array_set(&selfhost, "effects"), rust_effects["run"]);

    let policy = minimal_policy(src).expect("rust minimal_policy");
    assert_eq!(text_array_set(&selfhost, "caps"), rust_cap_set(&policy));
    assert_eq!(
        text_array_set(&selfhost, "targets"),
        rust_target_set(&policy)
    );
}

#[test]
fn selfhost_analyzer_walks_simplified_forms_and_matches_rust() {
    let src = r#"
        (defn run []
          (do (kqe-assert! "graphA" "s" "p" "v")
              (let [x (llm-infer "modelA" "prompt")]
                (kqe-get-objects "graphB" "s" "p"))
              (has-capability? "resource" "ability")))
    "#;
    let selfhost = analyze_forms(vec![form(vec![
        text("do"),
        form(vec![
            text("kqe-assert!"),
            text("graphA"),
            text("s"),
            text("p"),
            text("v"),
        ]),
        form(vec![
            text("let"),
            form(vec![
                text("x"),
                form(vec![text("llm-infer"), text("modelA"), text("prompt")]),
            ]),
            form(vec![
                text("kqe-get-objects"),
                text("graphB"),
                text("s"),
                text("p"),
            ]),
        ]),
        form(vec![
            text("has-capability?"),
            text("resource"),
            text("ability"),
        ]),
    ])]);

    let rust_effects = infer_effects(src).expect("rust infer_effects");
    assert_eq!(text_array_set(&selfhost, "effects"), rust_effects["run"]);

    let policy = minimal_policy(src).expect("rust minimal_policy");
    assert_eq!(text_array_set(&selfhost, "caps"), rust_cap_set(&policy));
    assert_eq!(
        text_array_set(&selfhost, "targets"),
        rust_target_set(&policy)
    );
}

#[test]
fn selfhost_analyzer_accepts_forms_derived_from_kotoba_ast() {
    let src = r#"
        (defn run []
          (do (kqe-assert! "graphA" "s" "p" "v")
              (let [x (llm-infer "modelA" "prompt")]
                (kqe-get-objects "graphB" "s" "p"))
              (has-capability? "resource" "ability")))
    "#;

    let selfhost = analyze_forms(parsed_function_body_forms(src, "run"));

    let rust_effects = infer_effects(src).expect("rust infer_effects");
    assert_eq!(text_array_set(&selfhost, "effects"), rust_effects["run"]);

    let policy = minimal_policy(src).expect("rust minimal_policy");
    assert_eq!(text_array_set(&selfhost, "caps"), rust_cap_set(&policy));
    assert_eq!(
        text_array_set(&selfhost, "targets"),
        rust_target_set(&policy)
    );
}

#[test]
fn selfhost_analyzer_accepts_ast_body_facts_without_lowered_forms() {
    let src = r#"
        (defn helper []
          (llm-infer "modelA" "prompt"))

        (defn run []
          (do (kqe-assert! "graphA" "s" "p" "v")
              (helper)))
    "#;
    let selfhost = analyze_ast_body_program(vec![
        (
            "helper",
            vec![ast_builtin(
                "llm-infer",
                vec![ast_str("modelA"), ast_str("prompt")],
            )],
        ),
        (
            "run",
            vec![Value::Map(vec![
                kv("tag", text("do")),
                kv(
                    "body",
                    Value::Array(vec![
                        ast_builtin(
                            "kqe-assert!",
                            vec![ast_str("graphA"), ast_str("s"), ast_str("p"), ast_str("v")],
                        ),
                        ast_call("helper", vec![]),
                    ]),
                ),
            ])],
        ),
    ]);

    let functions = map_field(&selfhost, "functions")
        .as_array()
        .expect("functions array");
    let run = functions
        .iter()
        .find(|function| text_field(function, "name") == "run")
        .expect("run summary");

    let rust_effects = infer_effects(src).expect("rust infer_effects");
    assert_eq!(text_array_set(run, "effects"), rust_effects["run"]);

    let policy = minimal_policy(src).expect("rust minimal_policy");
    assert_eq!(text_array_set(run, "caps"), rust_cap_set(&policy));
    assert_eq!(text_array_set(run, "targets"), rust_target_set(&policy));
}

#[test]
fn selfhost_analyzer_ignores_quoted_and_commented_host_calls_like_rust() {
    let src = r#"
        (defn run []
          (do (kqe-assert! "realG" "s" "p" "v")
              (quote (kqe-assert! "quotedG" "s" "p" "v"))
              (comment (llm-infer "commentedModel" "prompt"))))
    "#;
    let forms = vec![form(vec![
        text("do"),
        form(vec![
            text("kqe-assert!"),
            text("realG"),
            text("s"),
            text("p"),
            text("v"),
        ]),
        form(vec![
            text("quote"),
            form(vec![
                text("kqe-assert!"),
                text("quotedG"),
                text("s"),
                text("p"),
                text("v"),
            ]),
        ]),
        form(vec![
            text("comment"),
            form(vec![
                text("llm-infer"),
                text("commentedModel"),
                text("prompt"),
            ]),
        ]),
    ])];

    let selfhost = analyze_forms(forms.clone());
    let rust_effects = infer_effects(src).expect("rust infer_effects");
    assert_eq!(text_array_set(&selfhost, "effects"), rust_effects["run"]);

    let policy = minimal_policy(src).expect("rust minimal_policy");
    assert_eq!(text_array_set(&selfhost, "caps"), rust_cap_set(&policy));
    assert_eq!(
        text_array_set(&selfhost, "targets"),
        rust_target_set(&policy)
    );
    assert_eq!(
        text_array_set(&selfhost, "targets"),
        BTreeSet::from(["realG".to_string()])
    );

    let selfhost_min = analyze_minimal_policy(vec![("run", forms)]);
    assert_minimal_policy_matches(&selfhost_min, &policy);
    assert!(!text_array_set(&selfhost_min, "graph-write").contains("quotedG"));
    assert!(text_array_set(&selfhost_min, "infer").is_empty());
}

#[test]
fn selfhost_analyzer_propagates_effects_across_parsed_function_calls() {
    let src = r#"
        (defn writer []
          (kqe-assert! "graphA" "s" "p" "v"))

        (defn reader []
          (kqe-get-objects "graphB" "s" "p"))

        (defn model []
          (llm-infer "modelA" "prompt"))

        (defn run []
          (do (writer)
              (reader)
              (model)
              (has-capability? "resource" "ability")))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs: Vec<(&str, Vec<Value>)> = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_program("run", function_refs);

    let rust_effects = infer_effects(src).expect("rust infer_effects");
    assert_eq!(text_array_set(&selfhost, "effects"), rust_effects["run"]);

    let policy = minimal_policy(src).expect("rust minimal_policy");
    assert_eq!(text_array_set(&selfhost, "caps"), rust_cap_set(&policy));
    assert_eq!(
        text_array_set(&selfhost, "targets"),
        rust_target_set(&policy)
    );
}

#[test]
fn selfhost_analyzer_reports_transitive_effects_for_every_parsed_function() {
    let src = r#"
        (defn writer []
          (kqe-assert! "graphA" "s" "p" "v"))

        (defn reader []
          (kqe-get-objects "graphB" "s" "p"))

        (defn model []
          (llm-infer "modelA" "prompt"))

        (defn coordinator []
          (do (writer)
              (reader)))

        (defn run []
          (do (coordinator)
              (model)
              (has-capability? "resource" "ability")))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs: Vec<(&str, Vec<Value>)> = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_program_all(function_refs);
    let rust_effects = infer_effects(src).expect("rust infer_effects");

    assert_eq!(function_effect_sets(&selfhost), rust_effects);
}

#[test]
fn selfhost_bridge_infers_effects_from_source_like_rust() {
    let src = r#"
        (defn writer []
          (kqe-assert! "graphA" "s" "p" "v"))

        (defn reader []
          (kqe-query "ignored-filter"))

        (defn run []
          (do (writer)
              (reader)
              (llm-infer "modelA" "prompt")))
    "#;

    let selfhost = selfhost::infer_effects(src).expect("selfhost bridge infer_effects");
    let rust = infer_effects(src).expect("rust infer_effects");
    assert_eq!(selfhost, rust);
}

#[test]
fn selfhost_source_only_infers_named_function_effects() {
    let src = r#"
        (defn writer []
          (kqe-assert! "graphA" "s" "p" "v"))

        (defn inferer []
          (llm-infer "modelA" "prompt"))

        (defn run []
          (do (writer)
              (inferer)))

        (unsupported-top-level)
    "#;

    let effects = selfhost::infer_effects(src).expect("selfhost source-only infer_effects");
    assert_eq!(
        effects.get("writer"),
        Some(&BTreeSet::from(["graph-write".to_string()]))
    );
    assert_eq!(
        effects.get("inferer"),
        Some(&BTreeSet::from(["infer".to_string()]))
    );
    assert_eq!(
        effects.get("run"),
        Some(&BTreeSet::from([
            "graph-write".to_string(),
            "infer".to_string()
        ]))
    );
    assert!(!effects.contains_key("$source"), "{effects:?}");
}

#[test]
fn selfhost_bridge_synthesizes_minimal_policy_from_source_like_rust() {
    let src = r#"
        (defn run []
          (do (kqe-assert! "graphA" "s" "p" "v")
              (kqe-get-objects "graphB" "s" "p")
              (llm-infer "modelA" "prompt")
              (has-capability? "resource" "ability")))
    "#;

    let selfhost = selfhost::minimal_policy(src).expect("selfhost bridge minimal_policy");
    let rust = minimal_policy(src).expect("rust minimal_policy");
    assert_eq!(selfhost.graph_read, rust.graph_read);
    assert_eq!(selfhost.graph_write, rust.graph_write);
    assert_eq!(selfhost.infer, rust.infer);
    assert_eq!(selfhost.auth, rust.auth);
}

#[test]
fn selfhost_bridge_checks_effect_declarations_like_rust() {
    let src = r#"
        (defn helper []
          (kqe-assert! "graphA" "s" "p" "v"))

        (defn run {:effects #{}} []
          (helper))
    "#;

    let selfhost = selfhost::check_effect_declarations(src).expect("selfhost bridge effect check");
    assert!(!selfhost.ok);
    assert_eq!(selfhost.violations.len(), 1);
    assert_eq!(selfhost.violations[0].name, "run");
    assert_eq!(
        selfhost.violations[0].missing,
        BTreeSet::from(["graph-write".to_string()])
    );

    assert_rust_effect_denied(src, &Policy::deny_all().grant_graph_write(["graphA"]));
}

#[test]
fn selfhost_source_only_effect_declarations_use_source_function_facts() {
    let src = r#"
        (defn run {:effects #{}} []
          (kqe-assert! "graphA" "s" "p" "v"))
        (unsupported-top-level)
    "#;

    let check = selfhost::check_effect_declarations(src)
        .expect("selfhost source-only effect declaration check");
    assert!(!check.ok);
    assert_eq!(check.violations.len(), 1);
    assert_eq!(check.violations[0].name, "run");
    assert_eq!(
        check.violations[0].missing,
        BTreeSet::from(["graph-write".to_string()])
    );

    let declared = r#"
        (defn run {:effects #{:graph-write}} []
          (kqe-assert! "graphA" "s" "p" "v"))
        (unsupported-top-level)
    "#;
    let declared_check = selfhost::check_effect_declarations(declared)
        .expect("selfhost source-only declared effect check");
    assert!(declared_check.ok);
    assert!(declared_check.violations.is_empty());

    let multi_arity = r#"
        (defn run
          {:effects #{}}
          ([] 0)
          ([g] (kqe-assert! g "s" "p" "v")))
        (unsupported-top-level)
    "#;
    let multi_arity_check = selfhost::check_effect_declarations(multi_arity)
        .expect("selfhost source-only multi-arity effect declaration check");
    assert!(!multi_arity_check.ok);
    assert_eq!(multi_arity_check.violations.len(), 1);
    assert_eq!(multi_arity_check.violations[0].name, "run");
    assert_eq!(
        multi_arity_check.violations[0].missing,
        BTreeSet::from(["graph-write".to_string()])
    );

    let multi_arity_declared = r#"
        (defn run
          {:effects #{:graph-write}}
          ([] 0)
          ([g] (kqe-assert! g "s" "p" "v")))
        (unsupported-top-level)
    "#;
    let multi_arity_declared_check = selfhost::check_effect_declarations(multi_arity_declared)
        .expect("selfhost source-only multi-arity declared effect check");
    assert!(multi_arity_declared_check.ok);
    assert!(multi_arity_declared_check.violations.is_empty());

    let transitive = r#"
        (defn helper []
          (kqe-assert! "graphA" "s" "p" "v"))

        (defn run {:effects #{}} []
          (helper))
        (unsupported-top-level)
    "#;
    let transitive_check = selfhost::check_effect_declarations(transitive)
        .expect("selfhost source-only transitive effect declaration check");
    assert!(!transitive_check.ok);
    assert_eq!(transitive_check.violations.len(), 1);
    assert_eq!(transitive_check.violations[0].name, "run");
    assert_eq!(
        transitive_check.violations[0].missing,
        BTreeSet::from(["graph-write".to_string()])
    );
}

#[test]
fn selfhost_effect_call_graph_is_multi_arity_aware() {
    let src = r#"
        (defn helper
          ([] (kqe-assert! "graphA" "s" "p" "v"))
          ([n] n))

        (defn run {:effects #{}} []
          (helper 1))
    "#;

    let effects = selfhost::infer_effects(src).expect("selfhost effects");
    assert!(effects
        .get("run")
        .map_or(true, |used| !used.contains("graph-write")));

    let check = selfhost::check_effect_declarations(src).expect("selfhost effect check");
    assert!(check.ok);
    assert!(check.violations.is_empty());
}

#[test]
fn selfhost_effect_call_graph_reports_called_arity_effects() {
    let src = r#"
        (defn helper
          ([] 0)
          ([g] (kqe-assert! g "s" "p" "v")))

        (defn run {:effects #{}} []
          (helper "graphA"))
    "#;

    let check = selfhost::check_effect_declarations(src).expect("selfhost effect check");
    assert!(!check.ok);
    assert_eq!(check.violations.len(), 1);
    assert_eq!(check.violations[0].name, "run");
    assert_eq!(
        check.violations[0].missing,
        BTreeSet::from(["graph-write".to_string()])
    );
}

#[test]
fn selfhost_bridge_checks_policy_like_rust() {
    let src = r#"
        (defn run []
          (kqe-assert! "graphB" "s" "p" "v"))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);

    let selfhost = selfhost::check_policy(src, &policy).expect("selfhost bridge policy check");
    assert!(!selfhost.ok);
    assert!(selfhost.denials.is_empty());
    assert_eq!(
        selfhost.target_denials,
        BTreeSet::from(["graph-write:graphB".to_string()])
    );

    assert_rust_policy_denied(src, &policy);
}

#[test]
fn selfhost_bridge_checks_combined_admission_in_one_analyzer_run() {
    let src = r#"
        (defn helper []
          (kqe-assert! "graphB" "s" "p" "v"))

        (defn run {:effects #{}} []
          (helper))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);

    let admission =
        selfhost::check_admission(src, &policy).expect("selfhost bridge admission check");
    assert!(!admission.effects.ok);
    assert_eq!(admission.effects.violations.len(), 1);
    assert_eq!(admission.effects.violations[0].name, "run");
    assert_eq!(
        admission.effects.violations[0].missing,
        BTreeSet::from(["graph-write".to_string()])
    );
    assert!(!admission.policy.ok);
    assert_eq!(
        admission.policy.target_denials,
        BTreeSet::from(["graph-write:graphB".to_string()])
    );
}

#[test]
fn selfhost_bridge_checks_compile_gate_in_one_analyzer_run() {
    let src = r#"
        (defn writer {:effects #{}} []
          (do
            (read-string "(+ 1 2)")
            (kqe-assert! "graphB" "s" "p" "v")
            (+ "x" 1)))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);

    let gate = selfhost::check_compile_gate(src, &policy).expect("selfhost compile gate");
    assert!(!gate.subset.ok);
    assert_eq!(
        gate.subset.denials,
        BTreeSet::from(["read-string".to_string()])
    );
    assert!(!gate.types.ok);
    assert_eq!(gate.types.denials, BTreeSet::from(["+".to_string()]));
    assert!(!gate.effects.ok);
    assert_eq!(gate.effects.violations.len(), 1);
    assert_eq!(gate.effects.violations[0].name, "writer");
    assert_eq!(
        gate.effects.violations[0].missing,
        BTreeSet::from(["graph-write".to_string()])
    );
    assert!(!gate.policy.ok);
    assert_eq!(
        gate.policy.target_denials,
        BTreeSet::from(["graph-write:graphB".to_string()])
    );

    let source_only_src = r#"
        (defn run []
          (do
            (kqe-assert! "graphB" "s" "p" "v")
            (+ "x" 1)))
        (unsupported-top-level)
    "#;
    let source_only_gate = selfhost::check_compile_gate(source_only_src, &Policy::deny_all())
        .expect("selfhost source-only compile gate");
    assert!(source_only_gate.subset.ok);
    assert!(source_only_gate.subset.denials.is_empty());
    assert!(!source_only_gate.types.ok);
    assert_eq!(
        source_only_gate.types.denials,
        BTreeSet::from(["+".to_string()])
    );
    assert!(source_only_gate.effects.ok);
    assert!(!source_only_gate.policy.ok);
    assert_eq!(
        source_only_gate.policy.target_denials,
        BTreeSet::from(["graph-write:graphB".to_string()])
    );

    let source_only_lexical_target = r#"
        (defn run [c]
          (let [g (if c "graphC" "graphC")]
            (do
              (kqe-assert! g "s" "p" "v")
              (+ "x" 1))))
        (unsupported-top-level)
    "#;
    let lexical_gate =
        selfhost::check_compile_gate(source_only_lexical_target, &Policy::deny_all())
            .expect("selfhost source-only lexical compile gate");
    assert!(lexical_gate.subset.ok);
    assert!(!lexical_gate.types.ok);
    assert_eq!(
        lexical_gate.types.denials,
        BTreeSet::from(["+".to_string()])
    );
    assert!(lexical_gate.effects.ok);
    assert!(!lexical_gate.policy.ok);
    assert_eq!(
        lexical_gate.policy.target_denials,
        BTreeSet::from(["graph-write:graphC".to_string()])
    );

    let source_only_shadowed_target = r#"
        (defn run [g]
          (let [target "graphC"
                target g]
            (kqe-assert! target "s" "p" "v")))
        (unsupported-top-level)
    "#;
    let shadowed_gate =
        selfhost::check_compile_gate(source_only_shadowed_target, &Policy::deny_all())
            .expect("selfhost source-only shadowed compile gate");
    assert!(shadowed_gate.subset.ok);
    assert!(shadowed_gate.types.ok);
    assert!(shadowed_gate.effects.ok);
    assert!(!shadowed_gate.policy.ok);
    assert_eq!(
        shadowed_gate.policy.denials,
        BTreeSet::from(["graph-write".to_string()])
    );
    assert!(shadowed_gate.policy.target_denials.is_empty());

    let source_only_declared_effect = r#"
        (defn run {:effects #{}} []
          (kqe-assert! "graphD" "s" "p" "v"))
        (unsupported-top-level)
    "#;
    let declared_gate =
        selfhost::check_compile_gate(source_only_declared_effect, &Policy::deny_all())
            .expect("selfhost source-only declared-effect compile gate");
    assert!(declared_gate.subset.ok);
    assert!(declared_gate.types.ok);
    assert!(!declared_gate.effects.ok);
    assert_eq!(declared_gate.effects.violations.len(), 1);
    assert_eq!(declared_gate.effects.violations[0].name, "run");
    assert_eq!(
        declared_gate.effects.violations[0].missing,
        BTreeSet::from(["graph-write".to_string()])
    );
    assert!(!declared_gate.policy.ok);
    assert_eq!(
        declared_gate.policy.target_denials,
        BTreeSet::from(["graph-write:graphD".to_string()])
    );
}

#[test]
fn selfhost_compile_gate_accounts_for_package_dependency_capabilities() {
    let src = r#"(defn run [] 1)"#;
    let gate = selfhost::check_compile_gate_with_dependency_capabilities(
        src,
        ReaderTarget::Kotoba,
        &Policy::deny_all(),
        ["graph-write"],
    )
    .expect("selfhost package dependency compile gate");

    assert!(gate.subset.ok);
    assert!(gate.types.ok);
    assert!(gate.effects.ok);
    assert!(!gate.policy.ok);
    assert_eq!(
        gate.policy.used,
        BTreeSet::from(["graph-write".to_string()])
    );
    assert_eq!(
        gate.policy.denials,
        BTreeSet::from(["graph-write".to_string()])
    );

    let granted = selfhost::check_compile_gate_with_dependency_capabilities(
        src,
        ReaderTarget::Kotoba,
        &Policy::deny_all().grant_graph_write(["*"]),
        ["graph-write"],
    )
    .expect("selfhost granted package dependency compile gate");
    assert!(granted.policy.ok);
}

#[test]
fn selfhost_bridge_checks_executable_body_subset_denials() {
    let eval_src = r#"(defn run [x] (eval x))"#;
    let eval_check = selfhost::check_subset(eval_src).expect("selfhost subset check");
    assert!(!eval_check.ok);
    assert_eq!(eval_check.denials, BTreeSet::from(["eval".to_string()]));

    let raw_memory_src = r#"(defn run [] (alloc 8))"#;
    let raw_memory_check = selfhost::check_subset(raw_memory_src).expect("selfhost subset check");
    assert!(!raw_memory_check.ok);
    assert_eq!(
        raw_memory_check.denials,
        BTreeSet::from(["alloc".to_string()])
    );

    let broader_subset_src = r#"
        (defn run []
          (do
            (read-string "(+ 1 2)")
            (swap-vals! a f)
            (print-str "x")
            (rand-nth xs)
            (future-call f)
            (send-off a f)))
    "#;
    let broader_subset_check =
        selfhost::check_subset(broader_subset_src).expect("selfhost subset check");
    assert!(!broader_subset_check.ok);
    assert_eq!(
        broader_subset_check.denials,
        BTreeSet::from([
            "future-call".to_string(),
            "print-str".to_string(),
            "rand-nth".to_string(),
            "read-string".to_string(),
            "send-off".to_string(),
            "swap-vals!".to_string()
        ])
    );

    let inert_src = r#"(defn run [] (do (comment (eval x)) 1))"#;
    let inert_check = selfhost::check_subset(inert_src).expect("selfhost subset check");
    assert!(inert_check.ok);
    assert!(inert_check.denials.is_empty());

    let ns_require_src = r#"
        (ns demo.core
          (:require [evil.ns]))
        (defn run [] 1)
    "#;
    let ns_require_check = selfhost::check_subset(ns_require_src).expect("selfhost subset check");
    assert!(!ns_require_check.ok);
    assert_eq!(
        ns_require_check.denials,
        BTreeSet::from(["require".to_string()])
    );

    let top_level_defmacro_src = r#"
        (defmacro m [x] (eval x))
        (defn run [] 1)
    "#;
    let defmacro_check =
        selfhost::check_subset(top_level_defmacro_src).expect("selfhost subset check");
    assert!(!defmacro_check.ok);
    assert_eq!(
        defmacro_check.denials,
        BTreeSet::from(["defmacro".to_string()])
    );

    let host_constructor_src = r#"(defn run [] (String. "x"))"#;
    let host_constructor_check =
        selfhost::check_subset(host_constructor_src).expect("selfhost subset check");
    assert!(!host_constructor_check.ok);
    assert_eq!(
        host_constructor_check.denials,
        BTreeSet::from(["String.".to_string()])
    );

    let method_call_src = r#"(defn run [x] (.toString x))"#;
    let method_call_check = selfhost::check_subset(method_call_src).expect("selfhost subset check");
    assert!(!method_call_check.ok);
    assert_eq!(
        method_call_check.denials,
        BTreeSet::from([".toString".to_string()])
    );

    let interop_thread_src = r#"(defn run [x] (.. x foo bar))"#;
    let interop_thread_check =
        selfhost::check_subset(interop_thread_src).expect("selfhost subset check");
    assert!(!interop_thread_check.ok);
    assert_eq!(
        interop_thread_check.denials,
        BTreeSet::from(["..".to_string()])
    );

    let proxy_reify_src = r#"
        (defn proxy-run [] (proxy [Runnable] [] (run [] 1)))
        (defn reify-run [] (reify Runnable (run [_] 1)))
    "#;
    let proxy_reify_check = selfhost::check_subset(proxy_reify_src).expect("selfhost subset check");
    assert!(!proxy_reify_check.ok);
    assert_eq!(
        proxy_reify_check.denials,
        BTreeSet::from(["proxy".to_string(), "reify".to_string()])
    );

    let source_only_dynamic_var_src = r#"
        (defn run []
          (do
            (set! *warn-on-reflection* true)
            (binding [*out* *out*] 1)
            (with-redefs [f g] 1)))
        (unsupported-top-level)
    "#;
    let dynamic_var_check =
        selfhost::check_subset(source_only_dynamic_var_src).expect("selfhost subset check");
    assert!(!dynamic_var_check.ok);
    assert_eq!(
        dynamic_var_check.denials,
        BTreeSet::from([
            "binding".to_string(),
            "set!".to_string(),
            "with-redefs".to_string()
        ])
    );
}

#[test]
fn selfhost_compile_safe_kotoba_uses_selfhost_subset_slice_before_rust_fallback() {
    let src = r#"(defn run [x] (eval x))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Subset(msg)) => {
            assert!(
                msg.contains("self-hosted safe subset"),
                "expected selfhost subset message, got {msg}"
            );
            assert!(msg.contains("eval"), "{msg}");
        }
        other => panic!("expected selfhost subset denial, got {other:?}"),
    }

    let src = r#"(defn run [s] (read-string s))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Subset(msg)) => {
            assert!(
                msg.contains("self-hosted safe subset"),
                "expected selfhost subset message, got {msg}"
            );
            assert!(msg.contains("read-string"), "{msg}");
        }
        other => panic!("expected selfhost read-string subset denial, got {other:?}"),
    }

    let src = r#"
        (ns demo.core
          (:require [evil.ns]))
        (defn run [] 1)
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Subset(msg)) => {
            assert!(
                msg.contains("self-hosted safe subset"),
                "expected selfhost subset message, got {msg}"
            );
            assert!(msg.contains("require"), "{msg}");
        }
        other => panic!("expected selfhost ns require subset denial, got {other:?}"),
    }

    let src = r#"
        (defmacro m [x] x)
        (defn run [] 1)
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Subset(msg)) => {
            assert!(
                msg.contains("self-hosted safe subset"),
                "expected selfhost subset message, got {msg}"
            );
            assert!(msg.contains("defmacro"), "{msg}");
        }
        other => panic!("expected selfhost defmacro subset denial, got {other:?}"),
    }

    let src = r#"(defn run [] (String. "x"))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Subset(msg)) => {
            assert!(
                msg.contains("self-hosted safe subset"),
                "expected selfhost subset message, got {msg}"
            );
            assert!(msg.contains("String."), "{msg}");
        }
        other => panic!("expected selfhost host constructor subset denial, got {other:?}"),
    }

    for (src, needle) in [
        (r#"(defn run [x] (.toString x))"#, ".toString"),
        (r#"(defn run [x] (.. x foo bar))"#, ".."),
        (r#"(defn run [] (proxy [Runnable] [] (run [] 1)))"#, "proxy"),
        (r#"(defn run [] (reify Runnable (run [_] 1)))"#, "reify"),
        (r#"(defn run [] (new String "x"))"#, "new"),
        (
            r#"
            (defn run []
              (set! *warn-on-reflection* true))
            (unsupported-top-level)
            "#,
            "set!",
        ),
    ] {
        match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
            Err(CljError::Subset(msg)) => {
                assert!(
                    msg.contains("self-hosted safe subset"),
                    "expected selfhost subset message, got {msg}"
                );
                assert!(msg.contains(needle), "{msg}");
            }
            other => panic!("expected selfhost host interop subset denial, got {other:?}"),
        }
    }
}

#[test]
fn public_safe_compile_uses_selfhost_gate_by_default() {
    let subset_src = r#"(defn run [x] (eval x))"#;
    match compile_safe_kotoba(subset_src, &Policy::deny_all()) {
        Err(CljError::Subset(msg)) => {
            assert!(
                msg.contains("self-hosted safe subset"),
                "expected public safe compile to use selfhost subset gate, got {msg}"
            );
            assert!(msg.contains("eval"), "{msg}");
        }
        other => panic!("expected public selfhost subset denial, got {other:?}"),
    }

    let policy_src = r#"(defn run [] (kqe-assert! "graphB" "s" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);
    match compile_safe_kotoba(policy_src, &policy) {
        Err(CljError::Policy(msg)) => {
            assert!(
                msg.contains("self-hosted capability confinement"),
                "expected public safe compile to use selfhost policy gate, got {msg}"
            );
            assert!(msg.contains("graph-write:graphB"), "{msg}");
        }
        other => panic!("expected public selfhost policy denial, got {other:?}"),
    }
}

#[test]
fn public_analysis_apis_use_selfhost_by_default() {
    let src = r#"
        (defn writer [g]
          (kqe-assert! g "s" "p" "v"))
        (defn run []
          (writer "graphA"))
    "#;

    let public_effects = infer_effects(src).expect("public infer_effects");
    let selfhost_effects = selfhost::infer_effects(src).expect("selfhost infer_effects");
    assert_eq!(public_effects, selfhost_effects);
    assert_eq!(
        public_effects["run"],
        BTreeSet::from(["graph-write".to_string()])
    );

    let public_policy = minimal_policy(src).expect("public minimal_policy");
    let selfhost_policy = selfhost::minimal_policy(src).expect("selfhost minimal_policy");
    assert_eq!(public_policy.to_edn(), selfhost_policy.to_edn());
    assert_eq!(
        public_policy.graph_write,
        BTreeSet::from(["graphA".to_string()])
    );

    let over_granted = Policy::deny_all().grant_graph_write(["graphA", "graphB"]);
    let public_unused = unused_grants(src, &over_granted).expect("public unused_grants");
    let selfhost_unused =
        selfhost::unused_grants(src, &over_granted).expect("selfhost unused_grants");
    assert_eq!(public_unused, selfhost_unused);
    assert!(
        public_unused
            .iter()
            .any(|finding| finding.contains("graph-write") && finding.contains("graphB")),
        "{public_unused:?}"
    );

    compile_safe_kotoba(src, &public_policy)
        .expect("public selfhost minimal policy should compile");
}

#[test]
fn selfhost_bridge_checks_literal_type_denials() {
    let plus = selfhost::check_types(r#"(defn run [] (+ "x" 1))"#).expect("selfhost type check");
    assert!(!plus.ok);
    assert_eq!(plus.denials, BTreeSet::from(["+".to_string()]));

    let strlen =
        selfhost::check_types(r#"(defn run [] (str-len 1))"#).expect("selfhost type check");
    assert!(!strlen.ok);
    assert_eq!(strlen.denials, BTreeSet::from(["str-len".to_string()]));

    let byte_at =
        selfhost::check_types(r#"(defn run [] (byte-at "ab" "x"))"#).expect("selfhost type check");
    assert!(!byte_at.ok);
    assert_eq!(byte_at.denials, BTreeSet::from(["byte-at".to_string()]));

    let bytes_finish =
        selfhost::check_types(r#"(defn run [] (bytes-finish "x"))"#).expect("selfhost type check");
    assert!(!bytes_finish.ok);
    assert_eq!(
        bytes_finish.denials,
        BTreeSet::from(["bytes-finish".to_string()])
    );

    let byte_append_buffer = selfhost::check_types(r#"(defn run [] (byte-append! "x" 65))"#)
        .expect("selfhost type check");
    assert!(!byte_append_buffer.ok);
    assert_eq!(
        byte_append_buffer.denials,
        BTreeSet::from(["byte-append!".to_string()])
    );

    let byte_append_value =
        selfhost::check_types(r#"(defn run [] (byte-append! (bytes-alloc 4) "x"))"#)
            .expect("selfhost type check");
    assert!(!byte_append_value.ok);
    assert_eq!(
        byte_append_value.denials,
        BTreeSet::from(["byte-append!".to_string()])
    );

    let math_sqrt =
        selfhost::check_types(r#"(defn run [] (Math/sqrt "x"))"#).expect("selfhost type check");
    assert!(!math_sqrt.ok);
    assert_eq!(math_sqrt.denials, BTreeSet::from(["Math/sqrt".to_string()]));

    let conversion =
        selfhost::check_types(r#"(defn run [] (double "x"))"#).expect("selfhost type check");
    assert!(!conversion.ok);
    assert_eq!(conversion.denials, BTreeSet::from(["double".to_string()]));

    let llm_prompt = selfhost::check_types(r#"(defn run [] (llm-infer "modelA" 1))"#)
        .expect("selfhost type check");
    assert!(!llm_prompt.ok);
    assert_eq!(
        llm_prompt.denials,
        BTreeSet::from(["llm-infer".to_string()])
    );

    let llm_target = selfhost::check_types(r#"(defn run [] (llm-infer 1 "prompt"))"#)
        .expect("selfhost type check");
    assert!(!llm_target.ok);
    assert_eq!(
        llm_target.denials,
        BTreeSet::from(["llm-infer".to_string()])
    );

    let kqe_arg = selfhost::check_types(r#"(defn run [] (kqe-assert! "graphA" "s" "p" 1))"#)
        .expect("selfhost type check");
    assert!(!kqe_arg.ok);
    assert_eq!(kqe_arg.denials, BTreeSet::from(["kqe-assert!".to_string()]));

    let auth_arg = selfhost::check_types(r#"(defn run [] (has-capability? "resource" 1))"#)
        .expect("selfhost type check");
    assert!(!auth_arg.ok);
    assert_eq!(
        auth_arg.denials,
        BTreeSet::from(["has-capability?".to_string()])
    );

    let inert = selfhost::check_types(r#"(defn run [] (do (comment (+ "x" 1)) 1))"#)
        .expect("selfhost type check");
    assert!(inert.ok);
    assert!(inert.denials.is_empty());

    let source_only_type = selfhost::check_types(
        r#"
        (defn run [] (+ "x" 1))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only type check");
    assert!(!source_only_type.ok);
    assert_eq!(source_only_type.denials, BTreeSet::from(["+".to_string()]));

    let source_only_quot = selfhost::check_types(
        r#"
        (defn run [] (quot "x" 1))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only quot type check");
    assert!(!source_only_quot.ok);
    assert_eq!(
        source_only_quot.denials,
        BTreeSet::from(["quot".to_string()])
    );

    let source_only_java_math = selfhost::check_types(
        r#"
        (defn run [] (java.lang.Math/sqrt "x"))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only java.lang.Math type check");
    assert!(!source_only_java_math.ok);
    assert_eq!(
        source_only_java_math.denials,
        BTreeSet::from(["Math/sqrt".to_string()])
    );

    let source_only_long_alias = selfhost::check_types(
        r#"
        (defn run [] (long "x"))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only long alias type check");
    assert!(!source_only_long_alias.ok);
    assert_eq!(
        source_only_long_alias.denials,
        BTreeSet::from(["int".to_string()])
    );

    let source_only_let_string_arithmetic = selfhost::check_types(
        r#"
        (defn run [] (let [s "x"] (+ s 1)))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only let literal type check");
    assert!(!source_only_let_string_arithmetic.ok);
    assert_eq!(
        source_only_let_string_arithmetic.denials,
        BTreeSet::from(["+".to_string()])
    );

    let source_only_let_number_string_op = selfhost::check_types(
        r#"
        (defn run [] (let [n 5] (str-len n)))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only let numeric literal type check");
    assert!(!source_only_let_number_string_op.ok);
    assert_eq!(
        source_only_let_number_string_op.denials,
        BTreeSet::from(["str-len".to_string()])
    );

    let source_only_let_do_final = selfhost::check_types(
        r#"
        (defn run [] (let [s (do 0 "x")] (+ s 1)))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only let do-final type check");
    assert!(!source_only_let_do_final.ok);
    assert_eq!(
        source_only_let_do_final.denials,
        BTreeSet::from(["+".to_string()])
    );

    let source_only_let_if_join = selfhost::check_types(
        r#"
        (defn run [c] (let [s (if c "x" "y")] (+ s 1)))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only let if-join type check");
    assert!(!source_only_let_if_join.ok);
    assert_eq!(
        source_only_let_if_join.denials,
        BTreeSet::from(["+".to_string()])
    );

    let source_only_nested_let_return = selfhost::check_types(
        r#"
        (defn run [] (let [s (let [t "x"] t)] (+ s 1)))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only nested let-return type check");
    assert!(!source_only_nested_let_return.ok);
    assert_eq!(
        source_only_nested_let_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let macro_body_is_not_executable = selfhost::check_types(
        r#"
        (defmacro bad [] (+ "x" 1))
        (defn run [] 1)
        "#,
    )
    .expect("selfhost macro body type check");
    assert!(macro_body_is_not_executable.ok);
    assert!(macro_body_is_not_executable.denials.is_empty());

    let let_string_arithmetic = selfhost::check_types(r#"(defn run [] (let [s "x"] (+ s 1)))"#)
        .expect("selfhost type check");
    assert!(!let_string_arithmetic.ok);
    assert_eq!(
        let_string_arithmetic.denials,
        BTreeSet::from(["+".to_string()])
    );

    let let_number_string_op = selfhost::check_types(r#"(defn run [] (let [n 5] (str-len n)))"#)
        .expect("selfhost type check");
    assert!(!let_number_string_op.ok);
    assert_eq!(
        let_number_string_op.denials,
        BTreeSet::from(["str-len".to_string()])
    );

    let let_rebinding = selfhost::check_types(r#"(defn run [] (let [s "x" t s] (+ t 1)))"#)
        .expect("selfhost type check");
    assert!(!let_rebinding.ok);
    assert_eq!(let_rebinding.denials, BTreeSet::from(["+".to_string()]));

    let let_bytes_arithmetic =
        selfhost::check_types(r#"(defn run [] (let [b (bytes-alloc 8)] (+ b 1)))"#)
            .expect("selfhost type check");
    assert!(!let_bytes_arithmetic.ok);
    assert_eq!(
        let_bytes_arithmetic.denials,
        BTreeSet::from(["+".to_string()])
    );

    let let_shadowed_stays_permissive =
        selfhost::check_types(r#"(defn run [] (let [s "x" s 1] (+ s 1)))"#)
            .expect("selfhost type check");
    assert!(let_shadowed_stays_permissive.ok);
    assert!(let_shadowed_stays_permissive.denials.is_empty());
}

#[test]
fn selfhost_bridge_checks_value_dependent_literal_type_denials() {
    let byte_at_oob =
        selfhost::check_types(r#"(defn run [] (byte-at "ab" 2))"#).expect("selfhost type check");
    assert!(!byte_at_oob.ok);
    assert_eq!(byte_at_oob.denials, BTreeSet::from(["byte-at".to_string()]));

    let byte_at_negative =
        selfhost::check_types(r#"(defn run [] (byte-at "ab" -1))"#).expect("selfhost type check");
    assert!(!byte_at_negative.ok);
    assert_eq!(
        byte_at_negative.denials,
        BTreeSet::from(["byte-at".to_string()])
    );

    let bytes_alloc =
        selfhost::check_types(r#"(defn run [] (bytes-alloc -1))"#).expect("selfhost type check");
    assert!(!bytes_alloc.ok);
    assert_eq!(
        bytes_alloc.denials,
        BTreeSet::from(["bytes-alloc".to_string()])
    );

    let div_zero = selfhost::check_types(r#"(defn run [] (/ 8 0))"#).expect("selfhost type check");
    assert!(!div_zero.ok);
    assert_eq!(div_zero.denials, BTreeSet::from(["/".to_string()]));

    let source_only_div_zero = selfhost::check_types(
        r#"
        (defn run [] (quot 8 0))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only div-zero type check");
    assert!(!source_only_div_zero.ok);
    assert_eq!(
        source_only_div_zero.denials,
        BTreeSet::from(["quot".to_string()])
    );

    let source_only_byte_at_oob = selfhost::check_types(
        r#"
        (defn run [] (byte-at "ab" 2))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only byte-at type check");
    assert!(!source_only_byte_at_oob.ok);
    assert_eq!(
        source_only_byte_at_oob.denials,
        BTreeSet::from(["byte-at".to_string()])
    );

    let source_only_bytes_alloc = selfhost::check_types(
        r#"
        (defn run [] (bytes-alloc -1))
        (unsupported-top-level)
        "#,
    )
    .expect("selfhost source-only bytes-alloc type check");
    assert!(!source_only_bytes_alloc.ok);
    assert_eq!(
        source_only_bytes_alloc.denials,
        BTreeSet::from(["bytes-alloc".to_string()])
    );

    let valid_last_byte =
        selfhost::check_types(r#"(defn run [] (byte-at "é" 1))"#).expect("selfhost type check");
    assert!(valid_last_byte.ok);
    assert!(valid_last_byte.denials.is_empty());
}

#[test]
fn selfhost_bridge_checks_direct_literal_call_argument_type_denials() {
    let numeric_param = selfhost::check_types(
        r#"
        (defn add1 [n] (+ n 1))
        (defn run [] (add1 "x"))
        "#,
    )
    .expect("selfhost type check");
    assert!(!numeric_param.ok);
    assert_eq!(numeric_param.denials, BTreeSet::from(["add1".to_string()]));

    let string_param = selfhost::check_types(
        r#"
        (defn strlen [s] (str-len s))
        (defn run [] (strlen 7))
        "#,
    )
    .expect("selfhost type check");
    assert!(!string_param.ok);
    assert_eq!(string_param.denials, BTreeSet::from(["strlen".to_string()]));

    let bytes_param = selfhost::check_types(
        r#"
        (defn finish [b] (bytes-finish b))
        (defn run [] (finish "x"))
        "#,
    )
    .expect("selfhost type check");
    assert!(!bytes_param.ok);
    assert_eq!(bytes_param.denials, BTreeSet::from(["finish".to_string()]));

    let math_param = selfhost::check_types(
        r#"
        (defn root [n] (Math/sqrt n))
        (defn run [] (root "x"))
        "#,
    )
    .expect("selfhost type check");
    assert!(!math_param.ok);
    assert_eq!(math_param.denials, BTreeSet::from(["root".to_string()]));

    let host_param = selfhost::check_types(
        r#"
        (defn infer [prompt] (llm-infer "modelA" prompt))
        (defn run [] (infer 7))
        "#,
    )
    .expect("selfhost type check");
    assert!(!host_param.ok);
    assert_eq!(host_param.denials, BTreeSet::from(["infer".to_string()]));

    let host_target_param = selfhost::check_types(
        r#"
        (defn infer [model] (llm-infer model "prompt"))
        (defn run [] (infer 7))
        "#,
    )
    .expect("selfhost type check");
    assert!(!host_target_param.ok);
    assert_eq!(
        host_target_param.denials,
        BTreeSet::from(["infer".to_string()])
    );

    let matching = selfhost::check_types(
        r#"
        (defn add1 [n] (+ n 1))
        (defn run [] (add1 7))
        "#,
    )
    .expect("selfhost type check");
    assert!(matching.ok);
    assert!(matching.denials.is_empty());

    let shadowed = selfhost::check_types(
        r#"
        (defn add1 [n] (let [n "shadow"] (+ 1 2)))
        (defn run [] (add1 "x"))
        "#,
    )
    .expect("selfhost type check");
    assert!(shadowed.ok);
    assert!(shadowed.denials.is_empty());

    let local_string_param = selfhost::check_types(
        r#"
        (defn add1 [n] (+ n 1))
        (defn run [] (let [s "x"] (add1 s)))
        "#,
    )
    .expect("selfhost type check");
    assert!(!local_string_param.ok);
    assert_eq!(
        local_string_param.denials,
        BTreeSet::from(["add1".to_string()])
    );

    let local_rebinding_param = selfhost::check_types(
        r#"
        (defn add1 [n] (+ n 1))
        (defn run [] (let [s "x" t s] (add1 t)))
        "#,
    )
    .expect("selfhost type check");
    assert!(!local_rebinding_param.ok);
    assert_eq!(
        local_rebinding_param.denials,
        BTreeSet::from(["add1".to_string()])
    );

    let loop_local_string_param = selfhost::check_types(
        r#"
        (defn add1 [n] (+ n 1))
        (defn run [] (loop [s "x"] (add1 s)))
        "#,
    )
    .expect("selfhost type check");
    assert!(!loop_local_string_param.ok);
    assert_eq!(
        loop_local_string_param.denials,
        BTreeSet::from(["add1".to_string()])
    );

    let local_shadowed_param_stays_permissive = selfhost::check_types(
        r#"
        (defn strlen [s] (str-len s))
        (defn run [] (let [s "x" s 1] (strlen s)))
        "#,
    )
    .expect("selfhost type check");
    assert!(local_shadowed_param_stays_permissive.ok);
    assert!(local_shadowed_param_stays_permissive.denials.is_empty());

    let multi_arity_uses_matching_signature = selfhost::check_types(
        r#"
        (defn f
          ([n] (+ n 1))
          ([s extra] (str-len s)))
        (defn run [] (f "x" 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(multi_arity_uses_matching_signature.ok);
    assert!(multi_arity_uses_matching_signature.denials.is_empty());

    let multi_arity_rejects_matching_arity_mismatch = selfhost::check_types(
        r#"
        (defn f
          ([n] (+ n 1))
          ([s extra] (str-len s)))
        (defn run [] (f "x"))
        "#,
    )
    .expect("selfhost type check");
    assert!(!multi_arity_rejects_matching_arity_mismatch.ok);
    assert_eq!(
        multi_arity_rejects_matching_arity_mismatch.denials,
        BTreeSet::from(["f".to_string()])
    );
}

#[test]
fn selfhost_bridge_checks_loop_recur_type_change_denials() {
    let changed = selfhost::check_types(
        r#"
        (defn run [c]
          (loop [n 0]
            (if c
              (recur "x")
              n)))
        "#,
    )
    .expect("selfhost type check");
    assert!(!changed.ok);
    assert_eq!(changed.denials, BTreeSet::from(["recur".to_string()]));

    let matching = selfhost::check_types(
        r#"
        (defn run [c]
          (loop [s "x"]
            (if c
              (recur "y")
              (str-len s))))
        "#,
    )
    .expect("selfhost type check");
    assert!(matching.ok);
    assert!(matching.denials.is_empty());

    let unknown_stays_permissive = selfhost::check_types(
        r#"
        (defn run [x]
          (loop [n 0]
            (recur x)))
        "#,
    )
    .expect("selfhost type check");
    assert!(unknown_stays_permissive.ok);
    assert!(unknown_stays_permissive.denials.is_empty());

    let nearest_loop_wins = selfhost::check_types(
        r#"
        (defn run []
          (loop [s "x"]
            (loop [n 0]
              (recur "bad"))))
        "#,
    )
    .expect("selfhost type check");
    assert!(!nearest_loop_wins.ok);
    assert_eq!(
        nearest_loop_wins.denials,
        BTreeSet::from(["recur".to_string()])
    );
}

#[test]
fn selfhost_bridge_checks_direct_string_return_into_typed_builtin() {
    let analyzer = selfhost::Analyzer::new().expect("selfhost analyzer");

    let arithmetic = analyzer
        .check_types(
            r#"
        (defn greet [] "hi")
        (defn run [] (+ (greet) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(!arithmetic.ok);
    assert_eq!(arithmetic.denials, BTreeSet::from(["+".to_string()]));

    let string_op = analyzer
        .check_types(
            r#"
        (defn greet [] "hi")
        (defn run [] (str-len (greet)))
        "#,
        )
        .expect("selfhost type check");
    assert!(string_op.ok);
    assert!(string_op.denials.is_empty());

    let direct_call_return = analyzer
        .check_types(
            r#"
        (defn greet [] "hi")
        (defn relay [] (greet))
        (defn run [] (+ (relay) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(!direct_call_return.ok);
    assert_eq!(
        direct_call_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let do_tail_call_return = analyzer
        .check_types(
            r#"
        (defn greet [] "hi")
        (defn relay [] (do 1 (greet)))
        (defn run [] (+ (relay) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(!do_tail_call_return.ok);
    assert_eq!(
        do_tail_call_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let let_tail_call_return = analyzer
        .check_types(
            r#"
        (defn greet [] "hi")
        (defn relay [] (let [x 1] (greet)))
        (defn run [] (+ (relay) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(!let_tail_call_return.ok);
    assert_eq!(
        let_tail_call_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let loop_tail_call_return = analyzer
        .check_types(
            r#"
        (defn greet [] "hi")
        (defn relay [] (loop [x 1] (greet)))
        (defn run [] (+ (relay) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(!loop_tail_call_return.ok);
    assert_eq!(
        loop_tail_call_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let if_tail_call_return = analyzer
        .check_types(
            r#"
        (defn greet-a [] "a")
        (defn greet-b [] (bytes-finish (bytes-alloc 4)))
        (defn relay [c] (if c (greet-a) (greet-b)))
        (defn run [] (+ (relay 1) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(!if_tail_call_return.ok);
    assert_eq!(
        if_tail_call_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let if_mixed_tail_call_return_stays_permissive = analyzer
        .check_types(
            r#"
        (defn greet [] "a")
        (defn id [x] x)
        (defn relay [c] (if c (greet) (id "x")))
        (defn run [] (+ (relay 1) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(if_mixed_tail_call_return_stays_permissive.ok);
    assert!(if_mixed_tail_call_return_stays_permissive
        .denials
        .is_empty());

    let cyclic_call_return_stays_permissive = analyzer
        .check_types(
            r#"
        (defn a [] (b))
        (defn b [] (a))
        (defn run [] (+ (a) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(cyclic_call_return_stays_permissive.ok);
    assert!(cyclic_call_return_stays_permissive.denials.is_empty());

    let unknown_return = analyzer
        .check_types(
            r#"
        (defn id [x] x)
        (defn run [] (+ (id "x") 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(unknown_return.ok);
    assert!(unknown_return.denials.is_empty());

    let numeric_return_stays_permissive = analyzer
        .check_types(
            r#"
        (defn mk [] 5)
        (defn run [] (str-len (mk)))
        "#,
        )
        .expect("selfhost type check");
    assert!(numeric_return_stays_permissive.ok);
    assert!(numeric_return_stays_permissive.denials.is_empty());

    let bytes_finish_return = analyzer
        .check_types(
            r#"
        (defn build [] (bytes-finish (bytes-alloc 4)))
        (defn run [] (+ (build) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(!bytes_finish_return.ok);
    assert_eq!(
        bytes_finish_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let llm_return = analyzer
        .check_types(
            r#"
        (defn ask [] (llm-infer "modelA" "prompt"))
        (defn run [] (+ (ask) 1))
        "#,
        )
        .expect("selfhost type check");
    assert!(!llm_return.ok);
    assert_eq!(llm_return.denials, BTreeSet::from(["+".to_string()]));

    let if_join_string_return = selfhost::check_types(
        r#"
        (defn choose [c] (if c "a" (bytes-finish (bytes-alloc 4))))
        (defn run [] (+ (choose 1) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(!if_join_string_return.ok);
    assert_eq!(
        if_join_string_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let if_mixed_return_stays_permissive = selfhost::check_types(
        r#"
        (defn choose [c] (if c "a" 1))
        (defn run [] (+ (choose 1) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(if_mixed_return_stays_permissive.ok);
    assert!(if_mixed_return_stays_permissive.denials.is_empty());

    let multi_arity_return_uses_matching_signature = selfhost::check_types(
        r#"
        (defn f
          ([x] "hi")
          ([x y] 1))
        (defn run [] (+ (f 1 2) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(multi_arity_return_uses_matching_signature.ok);
    assert!(multi_arity_return_uses_matching_signature
        .denials
        .is_empty());

    let multi_arity_return_rejects_matching_arity_str = selfhost::check_types(
        r#"
        (defn f
          ([x] "hi")
          ([x y] 1))
        (defn run [] (+ (f 1) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(!multi_arity_return_rejects_matching_arity_str.ok);
    assert_eq!(
        multi_arity_return_rejects_matching_arity_str.denials,
        BTreeSet::from(["+".to_string()])
    );

    let multi_arity_tail_return_uses_matching_signature = selfhost::check_types(
        r#"
        (defn f
          ([x] "hi")
          ([x y] 1))
        (defn relay [] (f 1 2))
        (defn run [] (+ (relay) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(multi_arity_tail_return_uses_matching_signature.ok);
    assert!(multi_arity_tail_return_uses_matching_signature
        .denials
        .is_empty());

    let multi_arity_tail_return_rejects_matching_arity_str = selfhost::check_types(
        r#"
        (defn f
          ([x] "hi")
          ([x y] 1))
        (defn relay [] (f 1))
        (defn run [] (+ (relay) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(!multi_arity_tail_return_rejects_matching_arity_str.ok);
    assert_eq!(
        multi_arity_tail_return_rejects_matching_arity_str.denials,
        BTreeSet::from(["+".to_string()])
    );

    let multi_arity_if_tail_return_uses_matching_signature = selfhost::check_types(
        r#"
        (defn f
          ([x] "hi")
          ([x y] 1))
        (defn g [c] (if c (f 1 2) (f 3 4)))
        (defn run [] (+ (g 1) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(multi_arity_if_tail_return_uses_matching_signature.ok);
    assert!(multi_arity_if_tail_return_uses_matching_signature
        .denials
        .is_empty());

    let multi_arity_if_tail_return_rejects_matching_arity_str = selfhost::check_types(
        r#"
        (defn f
          ([x] "hi")
          ([x y] 1))
        (defn g [c] (if c (f 1) (f 2)))
        (defn run [] (+ (g 1) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(!multi_arity_if_tail_return_rejects_matching_arity_str.ok);
    assert_eq!(
        multi_arity_if_tail_return_rejects_matching_arity_str.denials,
        BTreeSet::from(["+".to_string()])
    );

    let do_final_string_return = selfhost::check_types(
        r#"
        (defn greet [] (do 1 "hi"))
        (defn run [] (+ (greet) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(!do_final_string_return.ok);
    assert_eq!(
        do_final_string_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let do_final_numeric_return_stays_permissive = selfhost::check_types(
        r#"
        (defn mk [] (do "ignored" 1))
        (defn run [] (str-len (mk)))
        "#,
    )
    .expect("selfhost type check");
    assert!(do_final_numeric_return_stays_permissive.ok);
    assert!(do_final_numeric_return_stays_permissive.denials.is_empty());

    let let_bound_string_return = selfhost::check_types(
        r#"
        (defn greet [] (let [s "hi"] s))
        (defn run [] (+ (greet) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(!let_bound_string_return.ok);
    assert_eq!(
        let_bound_string_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let let_rebound_string_return = selfhost::check_types(
        r#"
        (defn greet [] (let [s "hi" t s] t))
        (defn run [] (+ (greet) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(!let_rebound_string_return.ok);
    assert_eq!(
        let_rebound_string_return.denials,
        BTreeSet::from(["+".to_string()])
    );

    let let_shadowed_numeric_return_stays_permissive = selfhost::check_types(
        r#"
        (defn mk [] (let [s "hi" s 1] s))
        (defn run [] (str-len (mk)))
        "#,
    )
    .expect("selfhost type check");
    assert!(let_shadowed_numeric_return_stays_permissive.ok);
    assert!(let_shadowed_numeric_return_stays_permissive
        .denials
        .is_empty());

    let if_branch_let_does_not_leak = selfhost::check_types(
        r#"
        (defn choose [c] (if c (let [s "hi"] s) s))
        (defn run [] (+ (choose 1) 1))
        "#,
    )
    .expect("selfhost type check");
    assert!(if_branch_let_does_not_leak.ok);
    assert!(if_branch_let_does_not_leak.denials.is_empty());
}

#[test]
fn selfhost_type_walker_preserves_nested_effects_in_builtin_args() {
    let src = r#"
        (defn run []
          (+ (do (kqe-assert! "graphA" "s" "p" "v") 1) 2))
    "#;

    let effects = selfhost::infer_effects(src).expect("selfhost effects");
    assert_eq!(
        effects.get("run"),
        Some(&BTreeSet::from(["graph-write".to_string()]))
    );

    let policy = selfhost::minimal_policy(src).expect("selfhost minimal policy");
    assert_eq!(policy.graph_write, BTreeSet::from(["graphA".to_string()]));
}

#[test]
fn selfhost_call_arg_walker_preserves_nested_effects() {
    let src = r#"
        (defn id [x] x)
        (defn run []
          (id (do (kqe-assert! "graphA" "s" "p" "v") "done")))
    "#;

    let effects = selfhost::infer_effects(src).expect("selfhost effects");
    assert_eq!(
        effects.get("run"),
        Some(&BTreeSet::from(["graph-write".to_string()]))
    );

    let policy = selfhost::minimal_policy(src).expect("selfhost minimal policy");
    assert_eq!(policy.graph_write, BTreeSet::from(["graphA".to_string()]));
}

#[test]
fn selfhost_compile_safe_kotoba_uses_selfhost_type_slice_before_rust_fallback() {
    let src = r#"(defn run [] (+ "x" 1))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("+"), "{msg}");
        }
        other => panic!("expected selfhost type denial, got {other:?}"),
    }

    let src = r#"(defn run [] (byte-at "ab" 2))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("byte-at"), "{msg}");
        }
        other => panic!("expected selfhost value-dependent type denial, got {other:?}"),
    }

    let src = r#"
        (defn add1 [n] (+ n 1))
        (defn run [] (add1 "x"))
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("add1"), "{msg}");
        }
        other => panic!("expected selfhost call-arg type denial, got {other:?}"),
    }

    let src = r#"
        (defn strlen [s] (str-len s))
        (defn run [] (strlen 7))
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("strlen"), "{msg}");
        }
        other => panic!("expected selfhost call-arg type denial, got {other:?}"),
    }

    let src = r#"(defn run [] (bytes-finish "x"))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("bytes-finish"), "{msg}");
        }
        other => panic!("expected selfhost bytes type denial, got {other:?}"),
    }

    let src = r#"(defn run [] (Math/sqrt "x"))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("Math/sqrt"), "{msg}");
        }
        other => panic!("expected selfhost math type denial, got {other:?}"),
    }

    let src = r#"(defn run [] (llm-infer "modelA" 1))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("llm-infer"), "{msg}");
        }
        other => panic!("expected selfhost host-arg type denial, got {other:?}"),
    }

    let src = r#"
        (defn greet [] "hi")
        (defn run [] (+ (greet) 1))
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("+"), "{msg}");
        }
        other => panic!("expected selfhost return type denial, got {other:?}"),
    }

    let src = r#"
        (defn greet [] "hi")
        (defn relay [] (greet))
        (defn run [] (+ (relay) 1))
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("+"), "{msg}");
        }
        other => panic!("expected selfhost direct-call return type denial, got {other:?}"),
    }

    let src = r#"
        (defn greet [] "hi")
        (defn relay [] (let [x 1] (greet)))
        (defn run [] (+ (relay) 1))
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("+"), "{msg}");
        }
        other => panic!("expected selfhost tail-call return type denial, got {other:?}"),
    }

    let src = r#"
        (defn greet [] "hi")
        (defn relay [] (loop [x 1] (greet)))
        (defn run [] (+ (relay) 1))
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("+"), "{msg}");
        }
        other => panic!("expected selfhost loop tail-call return type denial, got {other:?}"),
    }

    let src = r#"
        (defn greet-a [] "a")
        (defn greet-b [] (bytes-finish (bytes-alloc 4)))
        (defn relay [c] (if c (greet-a) (greet-b)))
        (defn run [] (+ (relay 1) 1))
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("+"), "{msg}");
        }
        other => panic!("expected selfhost if-tail-call return type denial, got {other:?}"),
    }

    let src = r#"(defn run [] (let [s "x"] (+ s 1)))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("+"), "{msg}");
        }
        other => panic!("expected selfhost let-local type denial, got {other:?}"),
    }

    let src = r#"(defn run [] (loop [s "x"] (+ s 1)))"#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("+"), "{msg}");
        }
        other => panic!("expected selfhost loop-local type denial, got {other:?}"),
    }

    let src = r#"
        (defn run [c]
          (loop [n 0]
            (if c
              (recur "x")
              n)))
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("recur"), "{msg}");
        }
        other => panic!("expected selfhost recur type denial, got {other:?}"),
    }

    let src = r#"
        (defn add1 [n] (+ n 1))
        (defn run [] (let [s "x"] (add1 s)))
    "#;
    match selfhost::compile_safe_kotoba(src, &Policy::deny_all()) {
        Err(CljError::Type(msg)) => {
            assert!(
                msg.contains("self-hosted literal type"),
                "expected selfhost type message, got {msg}"
            );
            assert!(msg.contains("add1"), "{msg}");
        }
        other => panic!("expected selfhost let-local call-arg type denial, got {other:?}"),
    }

    let wasm = selfhost::compile_safe_kotoba(
        r#"
        (defn f
          ([n] (+ n 1))
          ([s extra] (str-len s)))
        (defn run [] (f "x" 1))
        "#,
        &Policy::deny_all(),
    )
    .expect("selfhost compile should use the arity-matched type signature");
    assert!(wasm.starts_with(b"\0asm"));

    let wasm = selfhost::compile_safe_kotoba(
        r#"
        (defn f
          ([x] "hi")
          ([x y] 1))
        (defn run [] (+ (f 1 2) 1))
        "#,
        &Policy::deny_all(),
    )
    .expect("selfhost compile should use the arity-matched return signature");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn selfhost_bridge_reports_unused_grants_like_rust() {
    let src = r#"
        (defn run []
          (kqe-assert! "graphA" "s" "p" "v"))
    "#;
    let policy = Policy::deny_all()
        .grant_graph_write(["graphA", "graphB"])
        .grant_infer(["modelA"])
        .grant_auth();

    let selfhost_ids =
        selfhost::unused_grant_ids(src, &policy).expect("selfhost bridge unused grant ids");
    assert_eq!(
        selfhost_ids.into_iter().collect::<BTreeSet<_>>(),
        BTreeSet::from([
            "graph-write:graphB".to_string(),
            "infer:*".to_string(),
            "auth".to_string()
        ])
    );

    let selfhost = selfhost::unused_grants(src, &policy).expect("selfhost bridge unused grants");
    let rust = unused_grants(src, &policy).expect("rust unused_grants");
    assert_eq!(
        selfhost.into_iter().collect::<BTreeSet<_>>(),
        rust.into_iter().collect::<BTreeSet<_>>()
    );
}

#[test]
fn selfhost_analyzer_handle_reuses_compiled_component_for_multiple_queries() {
    let component = selfhost::analyzer_component().expect("compile analyzer component");
    assert!(component.starts_with(b"\0asm"));

    let analyzer = selfhost::Analyzer::from_component(component);

    let src_effects = r#"
        (defn writer []
          (kqe-assert! "graphA" "s" "p" "v"))

        (defn run []
          (do (writer)
              (llm-infer "modelA" "prompt")))
    "#;
    assert_eq!(
        analyzer
            .infer_effects(src_effects)
            .expect("selfhost handle infer_effects"),
        infer_effects(src_effects).expect("rust infer_effects")
    );

    let src_policy = r#"
        (defn run []
          (do (kqe-get-objects "graphB" "s" "p")
              (has-capability? "resource" "ability")))
    "#;
    let selfhost_policy = analyzer
        .minimal_policy(src_policy)
        .expect("selfhost handle minimal_policy");
    let rust_policy = minimal_policy(src_policy).expect("rust minimal_policy");
    assert_eq!(selfhost_policy.graph_read, rust_policy.graph_read);
    assert_eq!(selfhost_policy.graph_write, rust_policy.graph_write);
    assert_eq!(selfhost_policy.infer, rust_policy.infer);
    assert_eq!(selfhost_policy.auth, rust_policy.auth);
}

#[test]
fn selfhost_analyzer_request_can_be_serialized_and_run_by_external_tooling() {
    let src = r#"
        (defn run {:effects #{:graph-write}} [g]
          (kqe-assert! "graphA" "s" "p" "v"))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);
    let request = selfhost::AnalyzerRequest::from_source(src)
        .expect("build analyzer request")
        .with_check("admission")
        .with_policy(&policy);

    assert_eq!(request.abi(), selfhost::SAFE_ANALYZER_ABI);
    assert_eq!(request.check(), Some("admission"));
    assert_eq!(request.function_count(), 1);

    let input = request.to_cbor().expect("serialize analyzer request");
    let input_value: Value = ciborium::from_reader(input.as_slice()).expect("decode request cbor");
    assert_eq!(text_field(&input_value, "abi"), selfhost::SAFE_ANALYZER_ABI);
    assert_eq!(text_field(&input_value, "check"), "admission");
    let program = map_field(&input_value, "program")
        .as_array()
        .expect("request program array");
    assert!(!has_field(&program[0], "forms"));
    assert_eq!(
        text_array_set(&program[0], "params"),
        BTreeSet::from(["g".to_string()])
    );
    let body = map_field(&program[0], "body")
        .as_array()
        .expect("request ast body array");
    assert_eq!(text_field(&body[0], "tag"), "builtin");
    assert_eq!(text_field(&body[0], "op"), "kqe-assert!");
    assert_eq!(
        text_array_set(&program[0], "declared"),
        BTreeSet::from(["graph-write".to_string()])
    );

    let analyzer = selfhost::Analyzer::new().expect("compile analyzer handle");
    let output = analyzer
        .run_request_value(&request)
        .expect("run serialized analyzer request");
    assert_eq!(text_field(&output, "abi"), selfhost::SAFE_ANALYZER_ABI);
    assert!(text_field(map_field(&output, "effects"), "ok") == "true");
    assert!(text_field(map_field(&output, "policy"), "ok") == "true");
}

#[test]
fn selfhost_analyzer_request_honors_reader_target() {
    let src = r#"
        (defn run []
          #?(:cljs (kqe-assert! "cljsGraph" "s" "p" "v")
             :clj  (kqe-assert! "cljGraph" "s" "p" "v")))
    "#;
    let request =
        selfhost::AnalyzerRequest::from_source_with_reader_target(src, ReaderTarget::Cljs)
            .expect("build cljs-target analyzer request")
            .with_check("minimal-policy");

    let input = request.to_cbor().expect("serialize analyzer request");
    let input_value: Value = ciborium::from_reader(input.as_slice()).expect("decode request cbor");
    let program = map_field(&input_value, "program")
        .as_array()
        .expect("request program array");
    let body = map_field(&program[0], "body")
        .as_array()
        .expect("request ast body array");
    let args = map_field(&body[0], "args")
        .as_array()
        .expect("builtin args array");
    assert_eq!(text_field(&args[0], "value"), "cljsGraph");

    let analyzer = selfhost::Analyzer::new().expect("compile analyzer handle");
    let policy = analyzer
        .minimal_policy_with_reader_target(src, ReaderTarget::Cljs)
        .expect("cljs-target selfhost minimal policy");
    assert_eq!(
        policy.graph_write,
        BTreeSet::from(["cljsGraph".to_string()])
    );
}

#[test]
fn selfhost_compile_safe_kotoba_honors_reader_target() {
    let src = r#"
        (defn run []
          #?(:cljs (kqe-assert! "cljsGraph" "s" "p" "v")
             :clj  (kqe-assert! "cljGraph" "s" "p" "v")
             :kotoba (kqe-assert! "kotobaGraph" "s" "p" "v")))
    "#;
    let analyzer = selfhost::Analyzer::new().expect("compile analyzer handle");
    let cljs_policy = Policy::deny_all().grant_graph_write(["cljsGraph"]);

    let wasm = analyzer
        .compile_safe_kotoba_with_reader_target(src, ReaderTarget::Cljs, &cljs_policy)
        .expect("selfhost cljs-target compile");
    assert_eq!(
        embedded_capability_ifaces(&wasm),
        vec!["kotoba:kais/kqe@0.1.0"]
    );

    match analyzer.compile_safe_kotoba_with_reader_target(
        src,
        ReaderTarget::Cljs,
        &Policy::deny_all().grant_graph_write(["cljGraph"]),
    ) {
        Err(CljError::Policy(msg)) => assert!(msg.contains("graph-write:cljsGraph")),
        other => panic!("expected cljs-target policy rejection, got {other:?}"),
    }
}

#[test]
fn selfhost_compile_safe_file_honors_reader_target() {
    let path = temp_path("selfhost-file-reader-target.cljc");
    fs::write(
        &path,
        r#"
#?(:cljs (defn run [] (kqe-assert! "cljsGraph" "s" "p" "v"))
   :clj  (defn run [] (kqe-assert! "cljGraph" "s" "p" "v")))
"#,
    )
    .unwrap();
    let policy = Policy::deny_all().grant_graph_write(["cljsGraph"]);

    let wasm = selfhost::compile_safe_file_with_reader_target(&path, ReaderTarget::Cljs, &policy)
        .expect("selfhost cljs-target file compile");
    assert_eq!(
        embedded_capability_ifaces(&wasm),
        vec!["kotoba:kais/kqe@0.1.0"]
    );

    let _ = fs::remove_file(path);
}

#[test]
fn selfhost_analyzer_handle_reuses_compiled_component_for_compilation() {
    let analyzer = selfhost::Analyzer::new().expect("compile analyzer handle");

    let write_src = r#"
        (defn run []
          (kqe-assert! "graphA" "s" "p" "v"))
    "#;
    let write_policy = Policy::deny_all().grant_graph_write(["graphA"]);
    let write_wasm = analyzer
        .compile_safe_kotoba(write_src, &write_policy)
        .expect("selfhost handle compile");
    assert_eq!(
        embedded_capability_ifaces(&write_wasm),
        vec!["kotoba:kais/kqe@0.1.0"]
    );

    let pure_path = temp_path("selfhost-handle-file-compile.kotoba");
    fs::write(&pure_path, "(defn run [n] (count (vector n (+ n 1))))\n").unwrap();
    let pure_wasm = analyzer
        .compile_safe_file_with_prelude(&pure_path, &Policy::deny_all())
        .expect("selfhost handle file compile");
    assert!(embedded_capability_ifaces(&pure_wasm).is_empty());

    let _ = fs::remove_file(pure_path);
}

#[test]
fn selfhost_compile_safe_kotoba_accepts_granted_program_and_emits_confined_wasm() {
    let src = r#"
        (defn run []
          (kqe-assert! "graphA" "s" "p" "v"))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);

    let wasm = selfhost::compile_safe_kotoba(src, &policy).expect("selfhost safe compile");
    assert_eq!(
        embedded_capability_ifaces(&wasm),
        vec!["kotoba:kais/kqe@0.1.0"]
    );
}

#[test]
fn selfhost_compile_safe_kotoba_with_prelude_accepts_pure_prelude_program() {
    let src = r#"
        (defn run [n]
          (count (vector n (+ n 1))))
    "#;

    let wasm = selfhost::compile_safe_kotoba_with_prelude(src, &Policy::deny_all())
        .expect("selfhost safe compile with prelude");
    assert!(embedded_capability_ifaces(&wasm).is_empty());
}

#[test]
fn selfhost_compile_safe_kotoba_rejects_effect_under_declaration() {
    let src = r#"
        (defn helper []
          (kqe-assert! "graphA" "s" "p" "v"))

        (defn run {:effects #{}} []
          (helper))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);

    match selfhost::compile_safe_kotoba(src, &policy) {
        Err(CljError::Effect(msg)) => assert!(msg.contains("self-hosted effect soundness")),
        other => panic!("expected selfhost CljError::Effect, got {other:?}"),
    }
}

#[test]
fn selfhost_compile_safe_kotoba_rejects_ungranted_resource() {
    let src = r#"
        (defn run []
          (kqe-assert! "graphB" "s" "p" "v"))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);

    match selfhost::compile_safe_kotoba(src, &policy) {
        Err(CljError::Policy(msg)) => {
            assert!(msg.contains("self-hosted capability confinement"));
            assert!(msg.contains("graph-write:graphB"));
        }
        other => panic!("expected selfhost CljError::Policy, got {other:?}"),
    }
}

#[test]
fn selfhost_compile_safe_file_with_prelude_accepts_file_input() {
    let path = temp_path("selfhost-file-compile.kotoba");
    fs::write(&path, "(defn run [n] (count (vector n (+ n 1))))\n").unwrap();

    let wasm = selfhost::compile_safe_file_with_prelude(&path, &Policy::deny_all())
        .expect("selfhost safe file compile");
    assert!(embedded_capability_ifaces(&wasm).is_empty());

    let _ = fs::remove_file(path);
}

#[test]
fn selfhost_minimal_policy_file_matches_source_api() {
    let path = temp_path("selfhost-policy-file.kotoba");
    let src = r#"(defn run [] (llm-infer "modelA" "prompt"))"#;
    fs::write(&path, src).unwrap();

    let from_file = selfhost::minimal_policy_file(&path).expect("selfhost file policy");
    let from_src = selfhost::minimal_policy(src).expect("selfhost source policy");
    assert_eq!(from_file.infer, from_src.infer);
    assert_eq!(from_file.infer, BTreeSet::from(["modelA".to_string()]));

    let _ = fs::remove_file(path);
}

#[test]
fn selfhost_analyzer_converges_on_mutual_recursion_like_rust_infer_effects() {
    let src = r#"
        (defn ping [n]
          (if (= n 0)
            (kqe-get-objects "graphB" "s" "p")
            (pong (- n 1))))

        (defn pong [n]
          (if (= n 0)
            (llm-infer "modelA" "prompt")
            (ping (- n 1))))

        (defn run []
          (ping 2))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_program_all(function_refs);
    let rust_effects = infer_effects(src).expect("rust infer_effects");

    assert_eq!(function_effect_sets(&selfhost), rust_effects);
}

#[test]
fn selfhost_effect_check_rejects_transitive_under_declaration_like_rust() {
    let src = r#"
        (defn helper []
          (kqe-assert! "graphA" "s" "p" "v"))

        (defn run {:effects #{}} []
          (helper))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| {
            let declared = (name == "run").then_some(Vec::new());
            (name.as_str(), forms.clone(), declared)
        })
        .collect();

    let selfhost = analyze_effect_check(function_refs);
    assert_eq!(text_field(&selfhost, "ok"), "false");
    let run = violation(&selfhost, "run");
    assert_eq!(
        text_array_set(run, "missing"),
        BTreeSet::from(["graph-write".to_string()])
    );
    assert!(text_array_set(run, "unknown").is_empty());

    assert_rust_effect_denied(src, &Policy::deny_all().grant_graph_write(["graphA"]));
}

#[test]
fn selfhost_effect_check_rejects_closure_body_under_declaration_like_rust() {
    let src = r#"
        (defn run {:effects #{}} []
          ((fn [] (kqe-assert! "kg" "a" "p" "v"))))
    "#;

    let check = selfhost::check_effect_declarations(src).expect("selfhost effect check");
    assert!(!check.ok);
    assert_eq!(check.violations.len(), 1);
    assert_eq!(check.violations[0].name, "run");
    assert_eq!(
        check.violations[0].missing,
        BTreeSet::from(["graph-write".to_string()])
    );
    assert_rust_effect_denied(src, &Policy::deny_all().grant_graph_write(["kg"]));
}

#[test]
fn selfhost_effect_check_rejects_unknown_declared_effect_like_rust() {
    let src = r#"
        (defn run {:effects #{:graphwrite}} []
          1)
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone(), Some(vec!["graphwrite"])))
        .collect();

    let selfhost = analyze_effect_check(function_refs);
    assert_eq!(text_field(&selfhost, "ok"), "false");
    let run = violation(&selfhost, "run");
    assert!(text_array_set(run, "missing").is_empty());
    assert_eq!(
        text_array_set(run, "unknown"),
        BTreeSet::from(["graphwrite".to_string()])
    );

    assert_rust_effect_denied(src, &Policy::deny_all());
}

#[test]
fn selfhost_policy_check_rejects_ungranted_capability_classes_like_rust() {
    let src = r#"
        (defn run []
          (do (kqe-assert! "graphA" "s" "p" "v")
              (llm-infer "modelA" "prompt")
              (has-capability? "resource" "ability")))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_policy_check(function_refs, vec![], vec![], vec![], false);
    assert_eq!(text_field(&selfhost, "ok"), "false");
    assert_eq!(
        text_array_set(&selfhost, "denials"),
        BTreeSet::from([
            "graph-write".to_string(),
            "infer".to_string(),
            "auth".to_string()
        ])
    );

    assert_rust_policy_denied(src, &Policy::deny_all());
}

#[test]
fn selfhost_policy_check_accepts_granted_capability_classes_like_rust() {
    let src = r#"
        (defn helper []
          (kqe-get-objects "graphB" "s" "p"))

        (defn run []
          (do (kqe-assert! "graphA" "s" "p" "v")
              (helper)
              (llm-infer "modelA" "prompt")
              (has-capability? "resource" "ability")))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_policy_check(
        function_refs,
        vec!["graphB"],
        vec!["graphA"],
        vec!["modelA"],
        true,
    );
    assert_eq!(text_field(&selfhost, "ok"), "true");
    assert!(text_array_set(&selfhost, "denials").is_empty());

    let policy = Policy::deny_all()
        .grant_graph_read(["graphB"])
        .grant_graph_write(["graphA"])
        .grant_infer(["modelA"])
        .grant_auth();
    compile_safe_kotoba(src, &policy).expect("rust policy should accept granted classes");
}

#[test]
fn selfhost_policy_check_rejects_ungranted_resource_targets_like_rust() {
    let src = r#"
        (defn run []
          (do (kqe-assert! "graphB" "s" "p" "v")
              (llm-infer "modelB" "prompt")))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost =
        analyze_policy_check(function_refs, vec![], vec!["graphA"], vec!["modelA"], false);
    assert_eq!(text_field(&selfhost, "ok"), "false");
    assert!(text_array_set(&selfhost, "denials").is_empty());
    assert_eq!(
        text_array_set(&selfhost, "target-denials"),
        BTreeSet::from(["graph-write:graphB".to_string(), "infer:modelB".to_string()])
    );

    let policy = Policy::deny_all()
        .grant_graph_write(["graphA"])
        .grant_infer(["modelA"]);
    assert_rust_policy_denied(src, &policy);
}

#[test]
fn selfhost_bridge_rejects_ungranted_resource_passed_through_function_param_like_rust() {
    let src = r#"
        (defn helper [g]
          (kqe-assert! g "s" "p" "v"))

        (defn run []
          (helper "graphB"))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);

    let request = selfhost::AnalyzerRequest::from_source(src).expect("build analyzer request");
    let input = request.to_cbor().expect("serialize analyzer request");
    let input_value: Value = ciborium::from_reader(input.as_slice()).expect("decode request cbor");
    let program = map_field(&input_value, "program")
        .as_array()
        .expect("request program array");
    let helper = program
        .iter()
        .find(|function| text_field(function, "name") == "helper")
        .expect("helper request row");
    assert!(!has_field(helper, "param-targets"));
    let run = program
        .iter()
        .find(|function| text_field(function, "name") == "run")
        .expect("run request row");
    assert!(!has_field(run, "call-args"));

    let selfhost = selfhost::check_policy(src, &policy).expect("selfhost policy check");
    assert_eq!(selfhost.ok, false);
    assert!(selfhost.denials.is_empty());
    assert_eq!(
        selfhost.target_denials,
        BTreeSet::from(["graph-write:graphB".to_string()])
    );

    assert_rust_policy_denied(src, &policy);
}

#[test]
fn selfhost_bridge_does_not_propagate_shadowed_resource_params() {
    let src = r#"
        (defn writer [g]
          (let [g "graphA"]
            (kqe-assert! g "s" "p" "v")))

        (defn run []
          (writer "graphB"))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);

    let selfhost = selfhost::check_policy(src, &policy).expect("selfhost policy check");
    assert!(selfhost.ok, "{selfhost:?}");
    assert!(selfhost.denials.is_empty());
    assert!(selfhost.target_denials.is_empty());
    compile_safe_kotoba(src, &policy)
        .expect("public selfhost-first compile should accept shadowed cid");
}

#[test]
fn selfhost_bridge_rejects_read_and_infer_resources_passed_through_params_like_rust() {
    let src = r#"
        (defn read-helper [g]
          (kqe-get-objects g "s" "p"))

        (defn infer-helper [m]
          (llm-infer m "prompt"))

        (defn run []
          (do (read-helper "graphB")
              (infer-helper "modelB")))
    "#;
    let policy = Policy::deny_all()
        .grant_graph_read(["graphA"])
        .grant_infer(["modelA"]);

    let selfhost = selfhost::check_policy(src, &policy).expect("selfhost policy check");
    assert_eq!(selfhost.ok, false);
    assert!(selfhost.denials.is_empty());
    assert_eq!(
        selfhost.target_denials,
        BTreeSet::from(["graph-read:graphB".to_string(), "infer:modelB".to_string()])
    );

    assert_rust_policy_denied(src, &policy);
}

#[test]
fn selfhost_policy_check_accepts_wildcard_resource_targets_like_rust() {
    let src = r#"
        (defn run []
          (do (kqe-assert! "graphB" "s" "p" "v")
              (llm-infer "modelB" "prompt")))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_policy_check(function_refs, vec![], vec!["*"], vec!["*"], false);
    assert_eq!(text_field(&selfhost, "ok"), "true");
    assert!(text_array_set(&selfhost, "denials").is_empty());
    assert!(text_array_set(&selfhost, "target-denials").is_empty());

    let policy = Policy::deny_all()
        .grant_graph_write(["*"])
        .grant_infer(["*"]);
    compile_safe_kotoba(src, &policy).expect("rust policy should accept wildcard targets");
}

#[test]
fn selfhost_minimal_policy_matches_rust_for_literal_resources() {
    let src = r#"
        (defn helper []
          (kqe-get-objects "graphB" "s" "p"))

        (defn run []
          (do (kqe-assert! "graphA" "s" "p" "v")
              (helper)
              (llm-infer "modelA" "prompt")
              (has-capability? "resource" "ability")))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_minimal_policy(function_refs);
    let rust = minimal_policy(src).expect("rust minimal_policy");
    assert_minimal_policy_matches(&selfhost, &rust);
    compile_safe_kotoba(src, &rust).expect("rust minimal policy should compile");
}

#[test]
fn selfhost_minimal_policy_matches_rust_for_pure_program() {
    let src = r#"
        (defn helper [n] (* n 2))
        (defn run [n] (helper n))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_minimal_policy(function_refs);
    let rust = minimal_policy(src).expect("rust minimal_policy");
    assert_minimal_policy_matches(&selfhost, &rust);
    compile_safe_kotoba(src, &rust).expect("rust minimal policy should compile");
}

#[test]
fn selfhost_minimal_policy_widens_dynamic_targets_like_rust() {
    let src = r#"
        (defn run [g]
          (kqe-assert! g "s" "p" "v"))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_minimal_policy(function_refs);
    let rust = minimal_policy(src).expect("rust minimal_policy");
    assert_minimal_policy_matches(&selfhost, &rust);
    assert_eq!(
        text_array_set(&selfhost, "graph-write"),
        BTreeSet::from(["*".to_string()])
    );
    compile_safe_kotoba(src, &rust).expect("rust minimal policy should compile");
}

#[test]
fn selfhost_bridge_minimal_policy_uses_literal_resource_passed_through_param_like_rust() {
    let src = r#"
        (defn writer [g]
          (kqe-assert! g "s" "p" "v"))

        (defn reader [g]
          (kqe-get-objects g "s" "p"))

        (defn inferer [m]
          (llm-infer m "prompt"))

        (defn run []
          (do (writer "graphA")
              (reader "graphR")
              (inferer "modelA")))
    "#;

    let selfhost = selfhost::minimal_policy(src).expect("selfhost minimal_policy");
    let rust = minimal_policy(src).expect("rust minimal_policy");
    assert_eq!(selfhost.graph_write, BTreeSet::from(["graphA".to_string()]));
    assert_eq!(selfhost.graph_read, BTreeSet::from(["graphR".to_string()]));
    assert_eq!(selfhost.infer, BTreeSet::from(["modelA".to_string()]));
    assert_eq!(selfhost, rust);
    compile_safe_kotoba(src, &rust).expect("rust minimal policy should compile");
}

#[test]
fn selfhost_source_only_tooling_uses_direct_host_call_facts() {
    let src = r#"
        (defn run []
          (do
            (kotoba/kqe-assert! "graphB" "s" "p" "v")
            (kotoba/llm-infer "modelB" "prompt")
            (kotoba/kqe-query "kg/role")))
        (unsupported-top-level)
    "#;

    let minimal = selfhost::minimal_policy(src).expect("selfhost source-only minimal policy");
    assert_eq!(minimal.graph_write, BTreeSet::from(["graphB".to_string()]));
    assert_eq!(minimal.graph_read, BTreeSet::from(["*".to_string()]));
    assert_eq!(minimal.infer, BTreeSet::from(["modelB".to_string()]));

    let denied = selfhost::check_policy(src, &Policy::deny_all())
        .expect("selfhost source-only policy check");
    assert!(!denied.ok);
    assert_eq!(
        denied.denials,
        BTreeSet::from([
            "graph-read".to_string(),
            "graph-write".to_string(),
            "infer".to_string()
        ])
    );
    assert_eq!(
        denied.target_denials,
        BTreeSet::from(["graph-write:graphB".to_string(), "infer:modelB".to_string()])
    );

    let admission = selfhost::check_admission(src, &Policy::deny_all())
        .expect("selfhost source-only admission check");
    assert!(admission.effects.ok);
    assert!(!admission.policy.ok);
    assert_eq!(
        admission.policy.target_denials,
        BTreeSet::from(["graph-write:graphB".to_string(), "infer:modelB".to_string()])
    );

    let exact_policy = Policy::deny_all()
        .grant_graph_write(["graphB"])
        .grant_graph_read(["*"])
        .grant_infer(["modelB"]);
    let exact = selfhost::check_policy(src, &exact_policy)
        .expect("selfhost source-only exact policy check");
    assert!(exact.ok);

    let over_policy = Policy::deny_all()
        .grant_graph_write(["graphA", "graphB"])
        .grant_graph_read(["*"])
        .grant_infer(["modelA", "modelB"]);
    let unused = selfhost::Analyzer::new()
        .expect("selfhost analyzer")
        .unused_grant_ids(src, &over_policy)
        .expect("selfhost source-only unused grants");
    assert_eq!(
        unused,
        vec!["graph-write:graphA".to_string(), "infer:modelA".to_string()]
    );
}

#[test]
fn selfhost_source_only_tooling_resolves_lexical_resource_targets() {
    let src = r#"
        (defn run [c]
          (let [write-target (do "ignored" "graphB")
                infer-target (if c "modelB" "modelB")
                read-target (let [g "graphR"] g)]
            (do
              (kqe-assert! write-target "s" "p" "v")
              (llm-infer infer-target "prompt")
              (kqe-get-objects read-target "s" "p"))))
        (unsupported-top-level)
    "#;

    let minimal = selfhost::minimal_policy(src).expect("selfhost source-only minimal policy");
    assert_eq!(minimal.graph_write, BTreeSet::from(["graphB".to_string()]));
    assert_eq!(minimal.graph_read, BTreeSet::from(["graphR".to_string()]));
    assert_eq!(minimal.infer, BTreeSet::from(["modelB".to_string()]));

    let denied = selfhost::check_policy(src, &Policy::deny_all())
        .expect("selfhost source-only lexical policy check");
    assert!(!denied.ok);
    assert_eq!(
        denied.target_denials,
        BTreeSet::from([
            "graph-read:graphR".to_string(),
            "graph-write:graphB".to_string(),
            "infer:modelB".to_string()
        ])
    );
}

#[test]
fn selfhost_source_only_tooling_widens_shadowed_resource_targets() {
    let src = r#"
        (defn run [dynamic-graph]
          (let [g "graphB"
                g dynamic-graph]
            (kqe-assert! g "s" "p" "v")))
        (unsupported-top-level)
    "#;

    let minimal = selfhost::minimal_policy(src).expect("selfhost source-only minimal policy");
    assert_eq!(minimal.graph_write, BTreeSet::from(["*".to_string()]));

    let denied = selfhost::check_policy(src, &Policy::deny_all())
        .expect("selfhost source-only shadowed policy check");
    assert!(!denied.ok);
    assert_eq!(denied.denials, BTreeSet::from(["graph-write".to_string()]));
    assert!(denied.target_denials.is_empty());
}

#[test]
fn selfhost_bridge_resource_param_pass_through_is_multi_arity_aware() {
    let src = r#"
        (defn writer
          ([n] (+ n 1))
          ([g v] (kqe-assert! g "s" "p" v)))

        (defn run []
          (writer "graphA" "v"))
    "#;

    let selfhost = selfhost::minimal_policy(src).expect("selfhost minimal_policy");
    assert_eq!(selfhost.graph_write, BTreeSet::from(["graphA".to_string()]));
    selfhost::compile_safe_kotoba(src, &selfhost).expect("selfhost minimal policy should compile");

    let denied_policy = Policy::deny_all().grant_graph_write(["graphB"]);
    let denied = selfhost::check_policy(src, &denied_policy).expect("selfhost policy check");
    assert!(!denied.ok);
    assert_eq!(
        denied.target_denials,
        BTreeSet::from(["graph-write:graphA".to_string()])
    );

    let exact_policy = Policy::deny_all().grant_graph_write(["graphA"]);
    let unused = selfhost::unused_grant_ids(src, &exact_policy).expect("selfhost unused grant ids");
    assert!(unused.is_empty(), "{unused:?}");
}

#[test]
fn selfhost_bridge_minimal_policy_widens_dynamic_resource_passed_through_param_like_rust() {
    let src = r#"
        (defn writer [g]
          (kqe-assert! g "s" "p" "v"))

        (defn run [g]
          (writer g))
    "#;

    let selfhost = selfhost::minimal_policy(src).expect("selfhost minimal_policy");
    let rust = minimal_policy(src).expect("rust minimal_policy");
    assert_eq!(selfhost.graph_write, BTreeSet::from(["*".to_string()]));
    assert_eq!(selfhost, rust);
    compile_safe_kotoba(src, &rust).expect("rust minimal policy should compile");
}

#[test]
fn selfhost_minimal_policy_widens_kqe_query_to_graph_read_wildcard_like_rust() {
    let src = r#"
        (defn run []
          (kqe-query "kg/role"))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_minimal_policy(function_refs);
    let rust = minimal_policy(src).expect("rust minimal_policy");
    assert_minimal_policy_matches(&selfhost, &rust);
    assert_eq!(
        text_array_set(&selfhost, "graph-read"),
        BTreeSet::from(["*".to_string()])
    );
    compile_safe_kotoba(src, &rust).expect("rust minimal policy should compile");
}

#[test]
fn selfhost_policy_check_dynamic_targets_fall_back_to_class_level_like_rust() {
    let src = r#"
        (defn run [g]
          (kqe-assert! g "s" "p" "v"))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_policy_check(function_refs, vec![], vec!["graphA"], vec![], false);
    assert_eq!(text_field(&selfhost, "ok"), "true");
    assert!(text_array_set(&selfhost, "denials").is_empty());
    assert!(text_array_set(&selfhost, "target-denials").is_empty());

    let policy = Policy::deny_all().grant_graph_write(["graphA"]);
    compile_safe_kotoba(src, &policy).expect("rust policy should accept dynamic class grant");
}

#[test]
fn selfhost_policy_check_kqe_query_uses_graph_read_class_without_target_denial_like_rust() {
    let src = r#"
        (defn run []
          (kqe-query "kg/role"))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs: Vec<(&str, Vec<Value>)> = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let denied = analyze_policy_check(function_refs.clone(), vec![], vec![], vec![], false);
    assert_eq!(text_field(&denied, "ok"), "false");
    assert_eq!(
        text_array_set(&denied, "denials"),
        BTreeSet::from(["graph-read".to_string()])
    );
    assert!(text_array_set(&denied, "target-denials").is_empty());
    assert_rust_policy_denied(src, &Policy::deny_all());

    let granted = analyze_policy_check(function_refs, vec!["kg"], vec![], vec![], false);
    assert_eq!(text_field(&granted, "ok"), "true");
    assert!(text_array_set(&granted, "denials").is_empty());
    assert!(text_array_set(&granted, "target-denials").is_empty());
    compile_safe_kotoba(src, &Policy::deny_all().grant_graph_read(["kg"]))
        .expect("rust policy should accept graph-read class grant");
}

#[test]
fn selfhost_unused_grants_empty_for_exact_fit_policy_like_rust() {
    let src = r#"
        (defn run []
          (kqe-assert! "graphA" "s" "p" "v"))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_unused_grants(function_refs, vec![], vec!["graphA"], vec![], false);
    assert!(text_array_set(&selfhost, "unused").is_empty());

    let policy = Policy::deny_all().grant_graph_write(["graphA"]);
    assert!(unused_grants(src, &policy)
        .expect("rust unused_grants")
        .is_empty());
}

#[test]
fn selfhost_bridge_unused_grants_accounts_for_literal_resource_passed_through_param_like_rust() {
    let src = r#"
        (defn writer [g]
          (kqe-assert! g "s" "p" "v"))

        (defn run []
          (writer "graphA"))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["graphA", "graphB"]);

    let selfhost = selfhost::unused_grants(src, &policy).expect("selfhost bridge unused grants");
    let rust = unused_grants(src, &policy).expect("rust unused_grants");
    assert_eq!(selfhost, rust);
    assert_eq!(rust.len(), 1, "{rust:?}");
    assert!(
        rust.iter()
            .any(|u| u.contains("graph-write") && u.contains("graphB")),
        "{rust:?}"
    );
}

fn temp_path(name: &str) -> std::path::PathBuf {
    let mut path = std::env::temp_dir();
    path.push(format!(
        "kotoba-clj-selfhost-test-{}-{name}",
        std::process::id()
    ));
    path
}

#[test]
fn selfhost_unused_grants_suppresses_specific_graph_read_for_kqe_query_like_rust() {
    let src = r#"
        (defn run []
          (kqe-query "kg/role"))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_unused_grants(
        function_refs,
        vec!["graphA", "graphB"],
        vec![],
        vec![],
        false,
    );
    assert!(text_array_set(&selfhost, "unused").is_empty());

    let policy = Policy::deny_all().grant_graph_read(["graphA", "graphB"]);
    assert!(unused_grants(src, &policy)
        .expect("rust unused_grants")
        .is_empty());
}

#[test]
fn selfhost_unused_grants_reports_over_grants_like_rust() {
    let src = r#"
        (defn run []
          (kqe-assert! "graphA" "s" "p" "v"))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_unused_grants(
        function_refs,
        vec![],
        vec!["graphA", "graphB"],
        vec!["modelA"],
        true,
    );
    assert_eq!(
        text_array_set(&selfhost, "unused"),
        BTreeSet::from([
            "graph-write:graphB".to_string(),
            "infer:*".to_string(),
            "auth".to_string(),
        ])
    );

    let policy = Policy::deny_all()
        .grant_graph_write(["graphA", "graphB"])
        .grant_infer(["modelA"])
        .grant_auth();
    let rust = unused_grants(src, &policy).expect("rust unused_grants");
    assert_eq!(rust.len(), 3, "{rust:?}");
    assert!(
        rust.iter()
            .any(|u| u.contains("graph-write") && u.contains("graphB")),
        "{rust:?}"
    );
    assert!(rust.iter().any(|u| u.contains("infer")), "{rust:?}");
    assert!(rust.iter().any(|u| u.contains("auth")), "{rust:?}");
}

#[test]
fn selfhost_unused_grants_suppresses_specific_cids_for_dynamic_targets_like_rust() {
    let src = r#"
        (defn run [g]
          (kqe-assert! g "s" "p" "v"))
    "#;
    let parsed = parsed_program_body_forms(src);
    let function_refs = parsed
        .iter()
        .map(|(name, forms)| (name.as_str(), forms.clone()))
        .collect();

    let selfhost = analyze_unused_grants(
        function_refs,
        vec![],
        vec!["graphA", "graphB"],
        vec![],
        false,
    );
    assert!(text_array_set(&selfhost, "unused").is_empty());

    let policy = Policy::deny_all().grant_graph_write(["graphA", "graphB"]);
    assert!(unused_grants(src, &policy)
        .expect("rust unused_grants")
        .is_empty());
}

#[test]
fn shell_evidence_profile_oracle_compiles_and_reports_contract_counts() {
    let wasm = selfhost::shell_evidence_profile_oracle_wasm()
        .expect("compile shell evidence profile oracle");
    assert!(wasm.starts_with(b"\0asm"));
    assert!(embedded_capability_ifaces(&wasm).is_empty());
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "profile-count", &[], 1_000_000).unwrap(),
        3
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "required-command-count", &[], 1_000_000).unwrap(),
        25
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "required-evidence-stem-count", &[], 1_000_000)
            .unwrap(),
        31
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "contract-score", &[], 1_000_000).unwrap(),
        32531
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "profile-list-digest", &[], 1_000_000).unwrap(),
        614
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "required-command-digest", &[], 1_000_000).unwrap(),
        4822
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "required-evidence-stem-digest", &[], 1_000_000)
            .unwrap(),
        61285
    );
}

#[test]
fn provider_surface_policy_oracle_compiles_and_reports_contract_counts() {
    let wasm =
        selfhost::provider_surface_policy_oracle_wasm().expect("compile provider surface oracle");
    assert!(wasm.starts_with(b"\0asm"));
    assert!(embedded_capability_ifaces(&wasm).is_empty());
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "provider-family-count", &[], 1_000_000).unwrap(),
        8
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "provider-command-count", &[], 1_000_000).unwrap(),
        13
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "portable-provider-command-count", &[], 1_000_000)
            .unwrap(),
        10
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "provider-status-class-count", &[], 1_000_000)
            .unwrap(),
        2
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "provider-contract-score", &[], 1_000_000).unwrap(),
        81302
    );
    assert_eq!(
        kotoba_clj::run::run_with_fuel(&wasm, "provider-catalog-digest", &[], 1_000_000).unwrap(),
        12688
    );
    for (function, expected) in [
        ("ledger-provider-score", 112),
        ("fs-app-data-provider-score", 301),
        ("notification-provider-score", 111),
        ("clipboard-provider-score", 221),
        ("http-fetch-provider-score", 111),
        ("keychain-provider-score", 331),
        ("contacts-provider-score", 111),
        ("calendar-provider-score", 111),
    ] {
        assert_eq!(
            kotoba_clj::run::run_with_fuel(&wasm, function, &[], 1_000_000).unwrap(),
            expected,
            "{function}"
        );
    }
}
