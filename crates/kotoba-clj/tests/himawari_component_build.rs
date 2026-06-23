//! Attempt to build a WASM component from each himawari cell.
//! Each cell exposes `solve` — the component API requires `run`.
//! We prepend the kotoba-clj prelude (which includes vec-make, into, mapv, etc.)
//! and append `(defn run [input] (solve input))` to each cell source.
//!
//! Run via: cargo test --test himawari_component_build

use kotoba_clj::component::{assert_loads, compile_component_str};

const OUTBOUND_LOGISTICS_SRC: &str = include_str!("/Users/junkawasaki/github/com-junkawasaki/orgs/etzhayyim/root/.claude/worktrees/agent-a8af0de40b8b64013/20-actors/himawari/cells/outbound_logistics/state_machine.cljc");
const PANEL_LOADING_SRC: &str = include_str!("/Users/junkawasaki/github/com-junkawasaki/orgs/etzhayyim/root/.claude/worktrees/agent-a8af0de40b8b64013/20-actors/himawari/cells/panel_loading/state_machine.cljc");
const SUPPLY_PROCUREMENT_SRC: &str = include_str!("/Users/junkawasaki/github/com-junkawasaki/orgs/etzhayyim/root/.claude/worktrees/agent-a8af0de40b8b64013/20-actors/himawari/cells/supply_procurement/state_machine.cljc");
const POLYSILICON_REFINE_SRC: &str = include_str!("/Users/junkawasaki/github/com-junkawasaki/orgs/etzhayyim/root/.claude/worktrees/agent-a8af0de40b8b64013/20-actors/himawari/cells/polysilicon_refine/state_machine.cljc");
const INGOT_WAFER_SRC: &str = include_str!("/Users/junkawasaki/github/com-junkawasaki/orgs/etzhayyim/root/.claude/worktrees/agent-a8af0de40b8b64013/20-actors/himawari/cells/ingot_wafer/state_machine.cljc");
const CELL_PROCESS_SRC: &str = include_str!("/Users/junkawasaki/github/com-junkawasaki/orgs/etzhayyim/root/.claude/worktrees/agent-a8af0de40b8b64013/20-actors/himawari/cells/cell_process/state_machine.cljc");
const MODULE_ASSEMBLY_SRC: &str = include_str!("/Users/junkawasaki/github/com-junkawasaki/orgs/etzhayyim/root/.claude/worktrees/agent-a8af0de40b8b64013/20-actors/himawari/cells/module_assembly/state_machine.cljc");

/// Wrap a cell's `solve` fn as the component's `run` entry point,
/// prepending the kotoba-clj prelude so vec-make/into/mapv etc. are available.
fn with_run_entry(src: &str) -> String {
    format!(
        "{}\n{}\n(defn run [input] (solve input))",
        kotoba_clj::prelude(),
        src,
    )
}

fn try_compile(name: &str, src: &str) -> Result<Vec<u8>, String> {
    let augmented = with_run_entry(src);
    compile_component_str(&augmented).map_err(|e| format!("{name}: {e:?}"))
}

#[test]
fn outbound_logistics_compiles_to_component() {
    let bytes = try_compile("outbound_logistics", OUTBOUND_LOGISTICS_SRC)
        .expect("outbound_logistics compile_component_str");
    println!("outbound_logistics: {} bytes", bytes.len());
    assert_eq!(&bytes[..4], b"\0asm");
    assert_loads(&bytes).expect("outbound_logistics must load under wasmtime component model");
    println!("outbound_logistics: LOADS OK");
}

#[test]
fn panel_loading_compiles_to_component() {
    let bytes = try_compile("panel_loading", PANEL_LOADING_SRC)
        .expect("panel_loading compile_component_str");
    println!("panel_loading: {} bytes", bytes.len());
    assert_eq!(&bytes[..4], b"\0asm");
    assert_loads(&bytes).expect("panel_loading must load");
    println!("panel_loading: LOADS OK");
}

#[test]
fn supply_procurement_compiles_to_component() {
    let bytes = try_compile("supply_procurement", SUPPLY_PROCUREMENT_SRC)
        .expect("supply_procurement compile_component_str");
    println!("supply_procurement: {} bytes", bytes.len());
    assert_eq!(&bytes[..4], b"\0asm");
    assert_loads(&bytes).expect("supply_procurement must load");
    println!("supply_procurement: LOADS OK");
}

#[test]
fn polysilicon_refine_compiles_to_component() {
    let bytes = try_compile("polysilicon_refine", POLYSILICON_REFINE_SRC)
        .expect("polysilicon_refine compile_component_str");
    println!("polysilicon_refine: {} bytes", bytes.len());
    assert_eq!(&bytes[..4], b"\0asm");
    assert_loads(&bytes).expect("polysilicon_refine must load");
    println!("polysilicon_refine: LOADS OK");
}

#[test]
fn ingot_wafer_compiles_to_component() {
    let bytes = try_compile("ingot_wafer", INGOT_WAFER_SRC)
        .expect("ingot_wafer compile_component_str");
    println!("ingot_wafer: {} bytes", bytes.len());
    assert_eq!(&bytes[..4], b"\0asm");
    assert_loads(&bytes).expect("ingot_wafer must load");
    println!("ingot_wafer: LOADS OK");
}

#[test]
fn cell_process_compiles_to_component() {
    let bytes = try_compile("cell_process", CELL_PROCESS_SRC)
        .expect("cell_process compile_component_str");
    println!("cell_process: {} bytes", bytes.len());
    assert_eq!(&bytes[..4], b"\0asm");
    assert_loads(&bytes).expect("cell_process must load");
    println!("cell_process: LOADS OK");
}

#[test]
fn module_assembly_compiles_to_component() {
    let bytes = try_compile("module_assembly", MODULE_ASSEMBLY_SRC)
        .expect("module_assembly compile_component_str");
    println!("module_assembly: {} bytes", bytes.len());
    assert_eq!(&bytes[..4], b"\0asm");
    assert_loads(&bytes).expect("module_assembly must load");
    println!("module_assembly: LOADS OK");
}
