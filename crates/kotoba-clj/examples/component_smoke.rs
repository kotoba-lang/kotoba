//! Step-3 de-risking smoke test: does a `wit-component`-encoded Component
//! actually instantiate in the workspace-pinned wasmtime 22?
//!
//! The component-model binary encoding shifted between the 0.209 (wasmtime 22's
//! internal wasm-tools) and 0.221 (our `wasm-encoder`) generations, so this
//! verifies the toolchain end-to-end on a trivial scalar export BEFORE building
//! the real `list<u8>` machinery.
//!
//! Run: `cargo run -p kotoba-clj --example component_smoke`

use wasm_encoder::{
    CodeSection, ExportKind, ExportSection, Function, FunctionSection, Instruction, Module,
    TypeSection, ValType,
};
use wit_component::{ComponentEncoder, StringEncoding};
use wit_parser::Resolve;

/// A trivial core module exporting `hello: func() -> i32` returning 42.
fn core_module() -> Vec<u8> {
    let mut types = TypeSection::new();
    types.ty().function([], [ValType::I32]);
    let mut funcs = FunctionSection::new();
    funcs.function(0);
    let mut exports = ExportSection::new();
    exports.export("hello", ExportKind::Func, 0);
    let mut code = CodeSection::new();
    let mut f = Function::new([]);
    f.instruction(&Instruction::I32Const(42));
    f.instruction(&Instruction::End);
    code.function(&f);
    let mut m = Module::new();
    m.section(&types);
    m.section(&funcs);
    m.section(&exports);
    m.section(&code);
    m.finish()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let wit = r#"
package kotoba:smoke;
world smoke {
  export hello: func() -> s32;
}
"#;
    let mut resolve = Resolve::new();
    let pkg = resolve.push_str("smoke.wit", wit)?;
    let world = resolve.select_world(pkg, Some("smoke"))?;

    let mut module = core_module();
    wit_component::embed_component_metadata(&mut module, &resolve, world, StringEncoding::UTF8)?;

    let component = ComponentEncoder::default()
        .module(&module)?
        .validate(true)
        .encode()?;
    println!("encoded component: {} bytes", component.len());

    // Instantiate in wasmtime 22 (component model).
    let mut config = wasmtime::Config::new();
    config.wasm_component_model(true);
    let engine = wasmtime::Engine::new(&config)?;
    let comp = wasmtime::component::Component::new(&engine, &component)?;
    let linker = wasmtime::component::Linker::new(&engine);
    let mut store = wasmtime::Store::new(&engine, ());
    let instance = linker.instantiate(&mut store, &comp)?;
    let func = instance.get_typed_func::<(), (i32,)>(&mut store, "hello")?;
    let (v,) = func.call(&mut store, ())?;
    func.post_return(&mut store)?;

    println!("hello() = {v}");
    assert_eq!(v, 42);
    println!("SMOKE OK: wit-component 0.221 component instantiates + runs in wasmtime 22");
    Ok(())
}
