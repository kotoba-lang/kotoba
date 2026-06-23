//! Component-Model emission (Step 3 of the kotoba:kais roadmap).
//!
//! Wraps an emitted core module into a real WASM **Component** exporting
//! `run: func(input: list<u8>) -> list<u8>`, using `wit-component` for the
//! Canonical-ABI adaptation. This is the same `list<u8>` lift/lower machinery
//! the future `kotoba-node` `run(ctx-cbor: list<u8>)` export reuses — here on a
//! minimal, self-owned world so it can be built and tested end-to-end now.
//!
//! The source program must define `(defn run [input] …)`: an arity-1 function
//! whose argument is the input bytes (as a string handle) and whose result is a
//! string handle for the output bytes. Source text is normalized through the
//! same Clojure reader compatibility layer as [`crate::compile_str`].

use wit_component::{ComponentEncoder, StringEncoding};
use wit_parser::Resolve;

use crate::codegen::{Entry, EntryAbi};
use crate::compat::{self, ReaderTarget};
use crate::CljError;

/// The WIT world every kotoba-clj program component targets.
const PROGRAM_WIT: &str = r#"
package kotoba:clj-program;

world program {
  export run: func(input: list<u8>) -> list<u8>;
}
"#;

/// Compile Clojure-subset source into a WASM **Component** exporting
/// `run(list<u8>) -> list<u8>`. Requires a `(defn run [input] …)`.
pub fn compile_component_str(src: &str) -> Result<Vec<u8>, CljError> {
    compile_component_str_with_reader_target(src, ReaderTarget::Kotoba)
}

/// Compile source into a WASM **Component** after applying Clojure reader
/// compatibility for `target`.
pub fn compile_component_str_with_reader_target(
    src: &str,
    target: ReaderTarget,
) -> Result<Vec<u8>, CljError> {
    let src = compat::normalize_source(src, target)?;
    let program = crate::ast::parse_program(&src)?;
    let core = crate::codegen::compile_core(
        &program,
        &[Entry {
            name: "run",
            abi: EntryAbi::BytesToBytes,
            export_name: "run",
        }],
    )?;
    encode_component(core)
}

/// Wrap a core module (already containing the `run`/`memory`/`cabi_realloc`
/// exports) into a Component targeting [`PROGRAM_WIT`].
fn encode_component(mut core_module: Vec<u8>) -> Result<Vec<u8>, CljError> {
    let mut resolve = Resolve::new();
    let pkg = resolve
        .push_str("program.wit", PROGRAM_WIT)
        .map_err(|e| CljError::Codegen(format!("WIT parse: {e}")))?;
    let world = resolve
        .select_world(pkg, Some("program"))
        .map_err(|e| CljError::Codegen(format!("WIT world: {e}")))?;

    wit_component::embed_component_metadata(
        &mut core_module,
        &resolve,
        world,
        StringEncoding::UTF8,
    )
    .map_err(|e| CljError::Codegen(format!("embed component metadata: {e}")))?;

    ComponentEncoder::default()
        .module(&core_module)
        .map_err(|e| CljError::Codegen(format!("component encode (module): {e}")))?
        .validate(true)
        .encode()
        .map_err(|e| CljError::Codegen(format!("component encode: {e}")))
}

/// Instantiate a `run(list<u8>) -> list<u8>` Component and invoke it.
pub fn run_component(component_bytes: &[u8], input: &[u8]) -> Result<Vec<u8>, CljError> {
    use wasmtime::component::{Component, Linker};
    use wasmtime::{Config, Engine, Store};

    let mut config = Config::new();
    config.wasm_component_model(true);
    let engine = Engine::new(&config).map_err(|e| CljError::Run(e.to_string()))?;
    let component =
        Component::new(&engine, component_bytes).map_err(|e| CljError::Run(e.to_string()))?;
    let linker = Linker::new(&engine);
    let mut store = Store::new(&engine, ());
    let instance = linker
        .instantiate(&mut store, &component)
        .map_err(|e| CljError::Run(e.to_string()))?;

    let func = instance
        .get_typed_func::<(Vec<u8>,), (Vec<u8>,)>(&mut store, "run")
        .map_err(|e| CljError::Run(format!("`run` export: {e}")))?;
    let (out,) = func
        .call(&mut store, (input.to_vec(),))
        .map_err(|e| CljError::Run(format!("`run` trapped: {e}")))?;
    func.post_return(&mut store)
        .map_err(|e| CljError::Run(e.to_string()))?;
    Ok(out)
}

/// Convenience: compile `src` to a Component and run `run(input)`.
pub fn compile_and_run_component(src: &str, input: &[u8]) -> Result<Vec<u8>, CljError> {
    let component = compile_component_str(src)?;
    run_component(&component, input)
}

// ---- Step 5 (reduced): the real kotoba:kais `kotoba-node` world -------------

/// Compile Clojure-subset source into a Component targeting the **actual**
/// `kotoba:kais` `kotoba-node` world from `kotoba-runtime/wit` — exporting
/// `run: func(ctx-cbor: list<u8>) -> result<list<u8>, string>`.
///
/// `wit_dir` is the path to `crates/kotoba-runtime/wit` (with its `deps/` tree).
///
/// **Scope (honest):** the generated wrapper passes the raw `ctx-cbor` bytes to
/// `(defn run [ctx] …)` and returns its output as `ok`. It does **not** decode
/// the CBOR `InvokeContext` — that needs the language to grow loops +
/// byte-building (step 4). So this proves the *plumbing*: a valid `kotoba-node`
/// component that `kotoba-runtime` can load. It does not make a program that
/// meaningfully reads `ctx`/`args`.
pub fn compile_kais_component_str(src: &str, wit_dir: &str) -> Result<Vec<u8>, CljError> {
    compile_kais_component_str_with_reader_target(src, wit_dir, ReaderTarget::Kotoba)
}

/// Compile source into a `kotoba-node` Component after applying Clojure reader
/// compatibility for `target`.
pub fn compile_kais_component_str_with_reader_target(
    src: &str,
    wit_dir: &str,
    target: ReaderTarget,
) -> Result<Vec<u8>, CljError> {
    let src = compat::normalize_source(src, target)?;
    let program = crate::ast::parse_program(&src)?;
    let core = crate::codegen::compile_core(
        &program,
        &[Entry {
            name: "run",
            abi: EntryAbi::BytesToResultBytes,
            export_name: "run",
        }],
    )?;

    let mut resolve = Resolve::new();
    let (pkg, _src) = resolve
        .push_dir(wit_dir)
        .map_err(|e| CljError::Codegen(format!("WIT push_dir({wit_dir}): {e}")))?;
    let world = resolve
        .select_world(pkg, Some("kotoba-node"))
        .map_err(|e| CljError::Codegen(format!("select kotoba-node world: {e}")))?;

    let mut module = core;
    wit_component::embed_component_metadata(&mut module, &resolve, world, StringEncoding::UTF8)
        .map_err(|e| CljError::Codegen(format!("embed kotoba-node metadata: {e}")))?;
    ComponentEncoder::default()
        .module(&module)
        .map_err(|e| CljError::Codegen(format!("kotoba-node encode (module): {e}")))?
        .validate(true)
        .encode()
        .map_err(|e| CljError::Codegen(format!("kotoba-node encode: {e}")))
}

/// Compile a KOTOBA Mesh component (M7): exports `run`, plus `on-http` when the
/// guest defines `(defn on-http [req] …)`. With an `on-http` handler the output
/// targets the `kotoba-component` world (run + on-http); otherwise it falls back
/// to the `kotoba-node` world (run only) — so existing run-only guests are
/// unaffected. `wit_dir` is `crates/kotoba-runtime/wit`.
pub fn compile_kais_mesh_component_str(src: &str, wit_dir: &str) -> Result<Vec<u8>, CljError> {
    let normalized = compat::normalize_source(src, ReaderTarget::Kotoba)?;
    let program = crate::ast::parse_program(&normalized)?;

    // detect optional trigger handlers (arity-1 `defn`s) in the guest
    let has = |name: &str| {
        program
            .functions
            .iter()
            .any(|f| f.name == name && f.params.len() == 1)
    };
    if !has("run") {
        return Err(CljError::Codegen(
            "mesh component must define `(defn run [ctx] …)`".into(),
        ));
    }

    let mut entries = vec![Entry {
        name: "run",
        abi: EntryAbi::BytesToResultBytes,
        export_name: "run",
    }];
    let world_name = if has("on-http") {
        entries.push(Entry {
            name: "on-http",
            abi: EntryAbi::BytesToResultBytes,
            export_name: "on-http",
        });
        "kotoba-component"
    } else {
        "kotoba-node"
    };

    let core = crate::codegen::compile_core(&program, &entries)?;

    let mut resolve = Resolve::new();
    let (pkg, _src) = resolve
        .push_dir(wit_dir)
        .map_err(|e| CljError::Codegen(format!("WIT push_dir({wit_dir}): {e}")))?;
    let world = resolve
        .select_world(pkg, Some(world_name))
        .map_err(|e| CljError::Codegen(format!("select {world_name} world: {e}")))?;

    let mut module = core;
    wit_component::embed_component_metadata(&mut module, &resolve, world, StringEncoding::UTF8)
        .map_err(|e| CljError::Codegen(format!("embed {world_name} metadata: {e}")))?;
    ComponentEncoder::default()
        .module(&module)
        .map_err(|e| CljError::Codegen(format!("{world_name} encode (module): {e}")))?
        .validate(true)
        .encode()
        .map_err(|e| CljError::Codegen(format!("{world_name} encode: {e}")))
}

/// Load-proof: does this component compile under wasmtime's Component Model
/// (the same path `kotoba-runtime`'s `ProgramStore::get_or_compile` uses)?
/// Returns `Ok(())` if `Component::new` accepts the bytes. Does **not**
/// instantiate — the `kotoba-node` world's 14 host imports would need a full
/// linker (the live-invoke stretch, deferred).
pub fn assert_loads(component_bytes: &[u8]) -> Result<(), CljError> {
    use wasmtime::component::Component;
    use wasmtime::{Config, Engine};

    let mut config = Config::new();
    config.wasm_component_model(true);
    let engine = Engine::new(&config).map_err(|e| CljError::Run(e.to_string()))?;
    Component::new(&engine, component_bytes)
        .map(|_| ())
        .map_err(|e| CljError::Run(format!("component failed to load: {e}")))
}
