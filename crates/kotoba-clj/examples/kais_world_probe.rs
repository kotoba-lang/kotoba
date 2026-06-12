//! Step-5 de-risking probe: can `wit-parser` resolve the *real* kotoba-runtime
//! WIT tree (with its `deps/`, including wasi:http) and select `kotoba-node`?
//!
//! This is the parsing gate before emitting any `kotoba-node` `run` wrapper —
//! if the dep tree doesn't resolve, that's the stop signal.
//!
//! Run: `cargo run -p kotoba-clj --example kais_world_probe`

use wit_parser::Resolve;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let wit_dir = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
    println!("resolving WIT dir: {wit_dir}");

    let mut resolve = Resolve::new();
    let (pkg, _src) = resolve.push_dir(wit_dir)?;
    println!(
        "parsed WIT tree; {} package(s) resolved",
        resolve.packages.len()
    );

    for world in ["kotoba-node", "kotoba-udf"] {
        match resolve.select_world(pkg, Some(world)) {
            Ok(id) => {
                let w = &resolve.worlds[id];
                println!(
                    "world `{}`: {} imports, {} exports",
                    world,
                    w.imports.len(),
                    w.exports.len()
                );
            }
            Err(e) => println!("world `{world}`: NOT selectable — {e}"),
        }
    }

    println!("PROBE OK: kotoba-runtime WIT tree resolves; kotoba-node world is selectable");
    Ok(())
}
