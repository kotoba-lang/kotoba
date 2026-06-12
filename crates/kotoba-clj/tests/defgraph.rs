//! Stage D: the `defgraph` DSL — a langgraph-shaped control-flow graph declared
//! as data, lowered to three generated `defn`s (dispatch / next / runner). This
//! is the capstone: nodes + edges + conditional routing + run-to-END, with the
//! Stage-B `map` as the threaded state.
//!
//!   - **pure** (plain wasmtime): a static linear graph, a `(if-edge …)` loop,
//!     and a `(if-edge …)` branch — driven through `run` with i64 args.
//!   - **end-to-end** (`WasmExecutor`): a real agent — CBOR ctx (C-3) → state
//!     map (B) → `defgraph` executor (D) → `llm.infer` (C-2) → output.

use kotoba_clj::compile_str_with_prelude;
use kotoba_clj::run::run;

/// Compile `defs` (with the full prelude) and call `fn_name(args)`.
fn run_prog(defs: &str, fn_name: &str, args: &[i64]) -> i64 {
    let wasm = compile_str_with_prelude(defs).expect("compile");
    run(&wasm, fn_name, args).expect("run")
}

// ---- static linear graph ----------------------------------------------------

#[test]
fn linear_graph_runs_each_node_once() {
    // a → b → end; each node increments state["n"]. Start 0 → 2.
    let defs = r#"
        (defn step [state] (map-assoc! state "n" (+ (map-get state "n") 1)))
        (defgraph g
          :entry :a
          :nodes {:a step :b step}
          :edges {:a :b :b :end})
        (defn t [_]
          (let [s (map-make 4)]
            (map-assoc! s "n" 0)
            (map-get (g s) "n")))
    "#;
    assert_eq!(run_prog(defs, "t", &[0]), 2);
}

// ---- conditional edge forming a loop ----------------------------------------

#[test]
fn if_edge_loops_until_predicate() {
    // tick increments n; loop back to :tick until (>= n 3), then :end.
    let defs = r#"
        (defn inc1 [state] (map-assoc! state "n" (+ (map-get state "n") 1)))
        (defn done? [state] (>= (map-get state "n") 3))
        (defgraph counter
          :entry :tick
          :nodes {:tick inc1}
          :edges {:tick (if-edge done? :end :tick)})
        (defn t [_]
          (let [s (map-make 4)]
            (map-assoc! s "n" 0)
            (map-get (counter s) "n")))
    "#;
    assert_eq!(run_prog(defs, "t", &[0]), 3);
}

// ---- conditional edge as a branch -------------------------------------------

#[test]
fn if_edge_branches_on_state() {
    // classify routes to :big or :small based on the input; each sets "label".
    let defs = r#"
        (defn noop [state] state)
        (defn set-big [state] (map-assoc! state "label" 100))
        (defn set-small [state] (map-assoc! state "label" 1))
        (defn big? [state] (> (map-get state "n") 5))
        (defgraph classify
          :entry :c
          :nodes {:c noop :big set-big :small set-small}
          :edges {:c (if-edge big? :big :small) :big :end :small :end})
        (defn t [n]
          (let [s (map-make 4)]
            (map-assoc! s "n" n)
            (map-get (classify s) "label")))
    "#;
    assert_eq!(run_prog(defs, "t", &[7]), 100); // big
    assert_eq!(run_prog(defs, "t", &[2]), 1); //  small
}

// ---- reducer auto-merge (:state declared) -----------------------------------

#[test]
fn add_messages_reducer_extends_across_nodes() {
    // :state declares :messages as add-messages → each node returns a partial
    // update {"messages": [..]} and the driver EXTENDS the running vector.
    let defs = r#"
        (defn n1 [state]
          (let [u (map-make 2) m (vec-make 4)]
            (vec-conj! m 10)
            (map-assoc! u "messages" m) u))
        (defn n2 [state]
          (let [u (map-make 2) m (vec-make 4)]
            (vec-conj! m 20) (vec-conj! m 30)
            (map-assoc! u "messages" m) u))
        (defgraph g
          :state {:messages add-messages}
          :entry :a
          :nodes {:a n1 :b n2}
          :edges {:a :b :b :end})
        (defn t [_]
          (let [s (map-make 4) m0 (vec-make 8)]
            (map-assoc! s "messages" m0)
            (let [final (g s) msgs (map-get final "messages")]
              (+ (* 100 (vec-count msgs)) (vec-nth msgs 2)))))
    "#;
    // n1 → [10]; n2 extends → [10,20,30]; count=3, msgs[2]=30 → 330
    assert_eq!(run_prog(defs, "t", &[0]), 330);
}

#[test]
fn override_reducer_is_last_write_wins() {
    // :count has no add-messages reducer → default override; two nodes write it.
    let defs = r#"
        (defn put5 [state] (let [u (map-make 2)] (map-assoc! u "count" 5) u))
        (defn put9 [state] (let [u (map-make 2)] (map-assoc! u "count" 9) u))
        (defgraph g
          :state {:count :override}
          :entry :a
          :nodes {:a put5 :b put9}
          :edges {:a :b :b :end})
        (defn t [_]
          (let [s (map-make 4)]
            (map-assoc! s "count" 0)
            (map-get (g s) "count")))
    "#;
    assert_eq!(run_prog(defs, "t", &[0]), 9); // last write
}

// ---- end-to-end langgraph-shaped agent (real host) --------------------------

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

    fn cbor_map(pairs: &[(&str, &str)]) -> Vec<u8> {
        let map: BTreeMap<String, String> = pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        let mut out = Vec::new();
        ciborium::into_writer(&map, &mut out).expect("cbor encode");
        out
    }

    /// A langgraph-shaped agent: a one-node graph whose node reads the prompt
    /// from state, calls the model, and writes the reply back into state. `run`
    /// decodes the CBOR ctx into the state map, runs the graph, returns reply.
    const AGENT: &str = r#"
        (defn call-model [state]
          (map-assoc! state "reply" (llm-infer "model-cid" (map-get state "prompt"))))
        (defgraph agent
          :entry :call
          :nodes {:call call-model}
          :edges {:call :end})
        (defn run [ctx]
          (let [r (cbor-reader ctx) s (map-make 8)]
            (if (= (cbor-map-seek r "prompt") 1)
              (do (map-assoc! s "prompt" (cbor-text r))
                  (map-get (agent s) "reply"))
              "NO-PROMPT")))
    "#;

    fn agent_component() -> Vec<u8> {
        let src = format!("{}\n{}", prelude(), AGENT);
        compile_kais_component_str(&src, KAIS_WIT_DIR).expect("compile + encode")
    }

    #[test]
    fn cbor_ctx_through_defgraph_to_llm() {
        let engine = Arc::new(|prompt: &str, _max: usize| Ok(format!("reply<{prompt}>")));
        let exec = WasmExecutor::with_inference(GAS, engine).expect("executor");
        let out = exec
            .execute(
                "clj-defgraph-agent",
                &agent_component(),
                "did:key:z6MkTestAgent",
                cbor_map(&[("prompt", "hello")]),
                Vec::<WitQuad>::new(),
                HashMap::new(),
            )
            .expect("execute")
            .output_cbor;
        // CBOR decoded → state["prompt"]="hello" → graph node called llm → reply
        assert_eq!(out, b"reply<hello>");
    }
}
