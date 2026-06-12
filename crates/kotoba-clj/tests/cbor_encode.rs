//! CBOR **encoder** (the [`kotoba_clj::CBOR_ENC_PRELUDE`]) — the symmetric
//! counterpart to the decoder, letting a guest return a *structured* result.
//!
//!   - **round-trip** (plain wasmtime): the guest encodes a value, then decodes
//!     it back with the in-guest decoder — proves the two are mutually consistent.
//!   - **interop** (component path): the guest encodes CBOR, then `ciborium`
//!     (the runtime's CBOR library) decodes it in Rust — proves the bytes are
//!     real, spec-conformant CBOR a host can read.

use kotoba_clj::compile_str_with_prelude;
use kotoba_clj::run::run;

fn eval(body: &str) -> i64 {
    let src = format!("(defn t [_] {body})");
    let wasm = compile_str_with_prelude(&src).expect("compile");
    run(&wasm, "t", &[0]).expect("run")
}

// ---- in-guest encode → decode round-trips -----------------------------------

#[test]
fn uint_round_trips() {
    // encode 1_000_000 as CBOR, decode it back → same value
    let v = eval(
        "(let [b (bytes-alloc 8)]
           (cbor-enc-uint! b 1000000)
           (cbor-uint (cbor-reader (bytes-finish b))))",
    );
    assert_eq!(v, 1_000_000);
}

#[test]
fn text_round_trips() {
    // encode "hello", decode → str-len 5, first byte 'h'(104)
    let v = eval(
        "(let [b (bytes-alloc 16)]
           (cbor-enc-text! b \"hello\")
           (let [t (cbor-text (cbor-reader (bytes-finish b)))]
             (+ (* 100 (str-len t)) (byte-at t 0))))",
    );
    assert_eq!(v, 604); // 5*100 + 104
}

#[test]
fn map_round_trips_via_seek() {
    // encode {"a": 7, "b": 9}, decode by seeking "b" → 9
    let v = eval(
        "(let [b (bytes-alloc 32)]
           (cbor-enc-map-header! b 2)
           (cbor-enc-text! b \"a\") (cbor-enc-uint! b 7)
           (cbor-enc-text! b \"b\") (cbor-enc-uint! b 9)
           (let [r (cbor-reader (bytes-finish b))]
             (if (= (cbor-map-seek r \"b\") 1) (cbor-uint r) -1)))",
    );
    assert_eq!(v, 9);
}

#[test]
fn two_byte_length_round_trips() {
    // a 300-byte string forces the 2-byte length header (info 25); decode len
    let v = eval(
        "(let [b (bytes-alloc 400) s (bytes-alloc 300)]
           (loop [i 0] (if (>= i 300) 0 (do (byte-append! s 65) (recur (+ i 1)))))
           (cbor-enc-text! b (bytes-finish s))
           (str-len (cbor-text (cbor-reader (bytes-finish b)))))",
    );
    assert_eq!(v, 300);
}

// ---- interop: guest encodes, ciborium decodes -------------------------------

#[cfg(feature = "component")]
mod interop {
    use kotoba_clj::component::compile_and_run_component;
    use kotoba_clj::prelude;

    /// Compile `(defn run [input] body)` with the prelude and return its bytes.
    fn run_bytes(body: &str) -> Vec<u8> {
        let src = format!("{}\n(defn run [input] {})", prelude(), body);
        compile_and_run_component(&src, b"").expect("compile + run component")
    }

    #[test]
    fn guest_encoded_map_decodes_in_ciborium() {
        // guest builds {"reply": "ok", "n": 7}; ciborium (the runtime's CBOR
        // library) must decode it to exactly that structure.
        let body = r#"
            (let [b (bytes-alloc 64)]
              (cbor-enc-map-header! b 2)
              (cbor-enc-text! b "reply") (cbor-enc-text! b "ok")
              (cbor-enc-text! b "n")     (cbor-enc-uint! b 7)
              (bytes-finish b))
        "#;
        let out = run_bytes(body);

        let value: ciborium::value::Value =
            ciborium::from_reader(&out[..]).expect("ciborium decode");
        let map = value.as_map().expect("a CBOR map");
        assert_eq!(map.len(), 2);
        // entry 0: "reply" -> "ok"
        assert_eq!(map[0].0.as_text(), Some("reply"));
        assert_eq!(map[0].1.as_text(), Some("ok"));
        // entry 1: "n" -> 7
        assert_eq!(map[1].0.as_text(), Some("n"));
        assert_eq!(map[1].1.as_integer(), Some(7.into()));
    }

    #[test]
    fn guest_encoded_array_decodes_in_ciborium() {
        // [1, 2, 3] as a CBOR array
        let body = r#"
            (let [b (bytes-alloc 16)]
              (cbor-enc-array-header! b 3)
              (cbor-enc-uint! b 1) (cbor-enc-uint! b 2) (cbor-enc-uint! b 3)
              (bytes-finish b))
        "#;
        let out = run_bytes(body);
        let value: ciborium::value::Value =
            ciborium::from_reader(&out[..]).expect("ciborium decode");
        let arr = value.as_array().expect("a CBOR array");
        let nums: Vec<i128> = arr.iter().map(|v| v.as_integer().unwrap().into()).collect();
        assert_eq!(nums, vec![1, 2, 3]);
    }
}
