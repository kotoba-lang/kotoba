//! Stage C-3: an **in-guest CBOR decoder** (the [`kotoba_clj::CBOR_PRELUDE`]),
//! closing the ADR's long-standing step-4 gap — a `kotoba-node` `run(ctx-cbor)`
//! can now decode its `InvokeContext`/args rather than receive them raw.
//!
//! Two layers of proof:
//!   - **pure decode** — the guest *builds* known CBOR bytes with the Stage-A
//!     byte builder, then decodes them; runs on plain wasmtime. Exercises uint
//!     (inline / 1- / 2- / 4-byte), text slicing, and map key seek+skip.
//!   - **interop + end-to-end** — `ciborium` (the runtime's own CBOR library)
//!     encodes a `{"prompt": …}` map; the guest decodes it through the real
//!     `WasmExecutor`, extracts the prompt, and feeds it to `llm.infer` — a
//!     complete "decode ctx → call model → return output" agent.

use kotoba_clj::compile_str_with_prelude;
use kotoba_clj::run::run;

/// Compile `body` with the full prelude and run `(defn t [_] body)`.
fn eval(body: &str) -> i64 {
    let src = format!("(defn t [_] {body})");
    let wasm = compile_str_with_prelude(&src).expect("compile");
    run(&wasm, "t", &[0]).expect("run")
}

/// Build a CBOR byte sequence in-guest, returning the clj expression that
/// `bytes-finish`es it into a ctx handle bound as `ctx`.
fn build(bytes: &[u8]) -> String {
    let appends: String = bytes
        .iter()
        .map(|b| format!("(byte-append! b {b}) "))
        .collect();
    format!(
        "(let [b (bytes-alloc {})] {appends} (bytes-finish b))",
        bytes.len()
    )
}

// ---- pure uint decoding -----------------------------------------------------

#[test]
fn uint_inline() {
    // 0x05 → 5
    let v = eval(&format!("(cbor-uint (cbor-reader {}))", build(&[0x05])));
    assert_eq!(v, 5);
}

#[test]
fn uint_one_byte_ext() {
    // 0x18 0x2A → 42
    let v = eval(&format!(
        "(cbor-uint (cbor-reader {}))",
        build(&[0x18, 0x2A])
    ));
    assert_eq!(v, 42);
}

#[test]
fn uint_two_byte_ext() {
    // 0x19 0x01 0x00 → 256
    let v = eval(&format!(
        "(cbor-uint (cbor-reader {}))",
        build(&[0x19, 0x01, 0x00])
    ));
    assert_eq!(v, 256);
}

#[test]
fn uint_four_byte_ext() {
    // 0x1A 00 0F 42 40 → 1_000_000
    let v = eval(&format!(
        "(cbor-uint (cbor-reader {}))",
        build(&[0x1A, 0x00, 0x0F, 0x42, 0x40])
    ));
    assert_eq!(v, 1_000_000);
}

// ---- text -------------------------------------------------------------------

#[test]
fn text_slices_into_ctx() {
    // 0x62 'H' 'i'  → text(2) "Hi"; assert len*100 + first byte = 200 + 72
    let v = eval(&format!(
        "(let [t (cbor-text (cbor-reader {}))] (+ (* 100 (str-len t)) (byte-at t 0)))",
        build(&[0x62, b'H', b'i'])
    ));
    assert_eq!(v, 272);
}

// ---- map seek + skip --------------------------------------------------------

#[test]
fn map_seek_uint_value() {
    // {"a": 7, "b": 9}: A2 61'a' 07 61'b' 09 — seek "b" → uint 9
    let cbor = [0xA2, 0x61, b'a', 0x07, 0x61, b'b', 0x09];
    let v = eval(&format!(
        "(let [r (cbor-reader {})] (if (= (cbor-map-seek r \"b\") 1) (cbor-uint r) -1))",
        build(&cbor)
    ));
    assert_eq!(v, 9);
}

#[test]
fn map_seek_skips_text_value() {
    // {"x": "skipme", "y": 3} — seek "y" must skip x's text value → uint 3
    let mut cbor = vec![0xA2, 0x61, b'x', 0x66];
    cbor.extend_from_slice(b"skipme");
    cbor.extend_from_slice(&[0x61, b'y', 0x03]);
    let v = eval(&format!(
        "(let [r (cbor-reader {})] (if (= (cbor-map-seek r \"y\") 1) (cbor-uint r) -1))",
        build(&cbor)
    ));
    assert_eq!(v, 3);
}

#[test]
fn map_seek_missing_key_returns_zero() {
    let cbor = [0xA1, 0x61, b'a', 0x07]; // {"a": 7}
    let v = eval(&format!(
        "(cbor-map-seek (cbor-reader {}) \"z\")",
        build(&cbor)
    ));
    assert_eq!(v, 0);
}

// ---- interop + end-to-end (real ciborium + WasmExecutor) --------------------

#[cfg(feature = "component")]
mod live {
    use std::collections::BTreeMap;
    use std::collections::HashMap;
    use std::sync::Arc;

    use kotoba_clj::component::compile_kais_component_str;
    use kotoba_clj::prelude;
    use kotoba_runtime::host::WitQuad;
    use kotoba_runtime::WasmExecutor;

    const KAIS_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
    const GAS: u64 = 10_000_000;

    /// CBOR-encode a `{key: value}` map with `ciborium` — the same library the
    /// runtime uses, so a passing test proves real interop.
    fn cbor_map(pairs: &[(&str, &str)]) -> Vec<u8> {
        let map: BTreeMap<String, String> = pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        let mut out = Vec::new();
        ciborium::into_writer(&map, &mut out).expect("cbor encode");
        out
    }

    /// A one-node agent: decode the CBOR ctx, pull out "prompt", call the model.
    fn agent_component() -> Vec<u8> {
        let src = format!(
            "{}\n{}",
            prelude(),
            r#"
            (defn run [ctx]
              (let [r (cbor-reader ctx)]
                (if (= (cbor-map-seek r "prompt") 1)
                  (llm-infer "model-cid" (cbor-text r))
                  "NO-PROMPT")))
            "#
        );
        compile_kais_component_str(&src, KAIS_WIT_DIR).expect("compile + encode")
    }

    #[test]
    fn decode_ctx_extract_prompt_call_llm() {
        let engine = Arc::new(|prompt: &str, _max: usize| Ok(format!("echo:{prompt}")));
        let exec = WasmExecutor::with_inference(GAS, engine).expect("executor");
        let ctx = cbor_map(&[("prompt", "ping"), ("zzz", "ignored")]);
        let out = exec
            .execute(
                "clj-cbor-agent",
                &agent_component(),
                "did:key:z6MkTestAgent",
                ctx,
                Vec::<WitQuad>::new(),
                HashMap::new(),
            )
            .expect("execute")
            .output_cbor;
        // guest decoded the real ciborium CBOR, extracted "ping", llm echoed it
        assert_eq!(out, b"echo:ping");
    }

    #[test]
    fn missing_prompt_key_takes_else_branch() {
        let exec = WasmExecutor::new(GAS).expect("executor");
        let ctx = cbor_map(&[("other", "x")]);
        let out = exec
            .execute(
                "clj-cbor-agent",
                &agent_component(),
                "did:key:z6MkTestAgent",
                ctx,
                Vec::<WitQuad>::new(),
                HashMap::new(),
            )
            .expect("execute")
            .output_cbor;
        assert_eq!(out, b"NO-PROMPT");
    }
}
