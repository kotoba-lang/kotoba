#[cfg(target_arch = "wasm32")]
mod bindings { wit_bindgen::generate!({ world: "bsp", path: "wit" }); }

#[cfg(target_arch = "wasm32")]
use serde::{Deserialize, Serialize};

#[cfg(target_arch = "wasm32")]
#[derive(Deserialize)]
struct StateIn { n: u32, acc: String }

#[cfg(target_arch = "wasm32")]
#[derive(Serialize)]
struct StateOut { status: String, n: u32, acc: String }

#[cfg(target_arch = "wasm32")]
struct Component;

#[cfg(target_arch = "wasm32")]
impl bindings::Guest for Component {
    fn run(state_cbor: Vec<u8>) -> Result<Vec<u8>, String> {
        let st: StateIn = ciborium::from_reader(state_cbor.as_slice())
            .map_err(|e| format!("cbor: {e}"))?;
        bindings::host_log(&format!("superstep n={} acc={}", st.n, st.acc));
        let out = if st.n > 0 {
            StateOut { status: "continue".into(), n: st.n - 1, acc: format!("{}.", st.acc) }
        } else {
            StateOut { status: "ok".into(), n: 0, acc: st.acc }
        };
        let mut buf = Vec::new();
        ciborium::into_writer(&out, &mut buf).map_err(|e| format!("cbor: {e}"))?;
        Ok(buf)
    }
}

#[cfg(target_arch = "wasm32")]
bindings::export!(Component with_types_in bindings);
