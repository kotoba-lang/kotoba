//! UNSPSC actor micro-kernel — a langgraph-shaped verdict graph compiled to REAL
//! WebAssembly via the Kotoba/EDN-subset → wasm compiler.
//!
//! This is the Kotoba path for a UNSPSC actor: the actor's decision graph
//! (validate → ok? → approve | reject) is declared with the
//! `defgraph` DSL — nodes + a conditional `if-edge` branch + run-to-END — and
//! compiled to a wasm module that runs under plain wasmtime (no host needed).
//!
//! Run: cargo run -p kotoba-clj --example unspsc_actor

const ACTOR_SRC: &str = r#"
    ;; State map (i64 fields): presence flags of a procurement line for a
    ;; livestock commodity (UNSPSC segment 10). The graph computes a verdict.
    (defn validate [state]
      (let [ok (if (and (= (map-get state "has_qty") 1)
                        (= (map-get state "has_unit") 1)
                        (= (map-get state "has_cert") 1)
                        (= (map-get state "health") 1)
                        (= (map-get state "quarantine") 1))
                 1 0)]
        (map-assoc! state "ok" ok)))

    (defn approve [state] (map-assoc! state "verdict" 1))
    (defn reject  [state] (map-assoc! state "verdict" 0))
    (defn ok? [state] (= (map-get state "ok") 1))

    ;; langgraph-shaped: a real conditional edge (branch) to END.
    (defgraph actor
      :entry :validate
      :nodes {:validate validate :approve approve :reject reject}
      :edges {:validate (if-edge ok? :approve :reject)
              :approve :end
              :reject  :end})

    (defn run-actor [has_qty has_unit has_cert health quarantine]
      (let [s (map-make 8)]
        (map-assoc! s "has_qty"    has_qty)
        (map-assoc! s "has_unit"   has_unit)
        (map-assoc! s "has_cert"   has_cert)
        (map-assoc! s "health"     health)
        (map-assoc! s "quarantine" quarantine)
        (map-get (actor s) "verdict")))
"#;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let wasm = kotoba_clj::compile_str_with_prelude(ACTOR_SRC)?;
    println!(
        "compiled UNSPSC actor → {} bytes of real wasm (magic {:?})",
        wasm.len(),
        &wasm[..4]
    );

    // [has_qty, has_unit, has_cert, health, quarantine] → expected verdict
    let cases: [([i64; 5], i64); 4] = [
        ([1, 1, 1, 1, 1], 1), // complete livestock line → APPROVE
        ([1, 1, 0, 1, 1], 0), // missing health certificate → REJECT
        ([0, 1, 1, 1, 1], 0), // missing quantity → REJECT
        ([1, 1, 1, 0, 1], 0), // not health-certified → REJECT
    ];

    for (args, expected) in cases {
        let v = kotoba_clj::run::run(&wasm, "run-actor", &args)?;
        let label = if v == 1 { "APPROVE" } else { "REJECT" };
        let mark = if v == expected { "ok" } else { "MISMATCH" };
        println!("  run-actor{args:?} -> verdict={v} ({label}) [{mark}]");
        assert_eq!(v, expected);
    }
    println!("all cases passed — UNSPSC actor runs as real wasm");
    Ok(())
}
