//! Compile a Clojure-subset program to wasm and run it.
//!
//! Run with: `cargo run -p kotoba-clj --example factorial`

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let src = r#"
        ;; Clojure source — compiled to a real wasm module, not interpreted.
        (defn fact [n]
          (if (< n 2)
            1
            (* n (fact (- n 1)))))

        (defn fib [n]
          (if (< n 2)
            n
            (+ (fib (- n 1)) (fib (- n 2)))))
    "#;

    let wasm = kotoba_clj::compile_str(src)?;
    println!("compiled {} bytes of wasm (magic: {:?})", wasm.len(), &wasm[..4]);

    for n in 0..=10 {
        let f = kotoba_clj::run::run(&wasm, "fact", &[n])?;
        let g = kotoba_clj::run::run(&wasm, "fib", &[n])?;
        println!("n={n:2}  fact={f:<10}  fib={g}");
    }
    Ok(())
}
