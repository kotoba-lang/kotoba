#![cfg(feature = "component")]
use kotoba_clj::component::compile_component_str_with_prelude;
#[test]
fn probe_component_determinism() {
    let src =
        r#"(defn run [input] (let [b (bytes-alloc 3)] (byte-append! b 65) (bytes-finish b)))"#;
    let a = compile_component_str_with_prelude(src).expect("compile a");
    let b = compile_component_str_with_prelude(src).expect("compile b");
    eprintln!("PROBE component bytes equal: {} (len {})", a == b, a.len());
}
