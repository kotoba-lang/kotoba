#[cfg(target_arch = "wasm32")]
mod bindings {
    wit_bindgen::generate!({ world: "pregel", path: "wit" });
}

#[cfg(target_arch = "wasm32")]
struct Component;

#[cfg(target_arch = "wasm32")]
impl bindings::Guest for Component {
    fn run(input: String) -> String {
        // A trivial "superstep": call back into the host, then return a result.
        let from_host = bindings::host_get(&input);
        format!("pregel-superstep(input={input}) host-said={from_host}")
    }
}

#[cfg(target_arch = "wasm32")]
bindings::export!(Component with_types_in bindings);
