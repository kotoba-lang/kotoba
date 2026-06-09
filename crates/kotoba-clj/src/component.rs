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
//! string handle for the output bytes.

use wit_component::{ComponentEncoder, StringEncoding};
use wit_parser::Resolve;

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
    let program = crate::ast::parse_program(src)?;
    let core = crate::codegen::compile_core(&program, Some("run"))?;
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

    wit_component::embed_component_metadata(&mut core_module, &resolve, world, StringEncoding::UTF8)
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
