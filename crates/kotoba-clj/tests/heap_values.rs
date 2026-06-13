//! Stage B — heap values: growable `vector` and string-keyed `map` from the
//! [`kotoba_clj::PRELUDE`], the substrate a langgraph `state` dict and
//! `messages` vector ride on. The containers are written in the kotoba-clj
//! subset itself (on `alloc`/`load64`/`store64!` + `loop`/`recur`), so these
//! tests double as proof that Stage A is expressive enough to bootstrap them.
//!
//! Each test compiles `PRELUDE + src`, runs an arity-1 `t` on wasmtime, and
//! asserts an i64 derived from the container — the whole read→lower→codegen→run
//! path, end to end.

use kotoba_clj::compile_str_with_prelude;
use kotoba_clj::run::run;

/// Compile `body` (with the prelude) and run `(defn t [_] …)`.
fn eval(body: &str) -> i64 {
    let src = format!("(defn t [_] {body})");
    let wasm = compile_str_with_prelude(&src).expect("compile");
    run(&wasm, "t", &[0]).expect("run")
}

// ---- vector -----------------------------------------------------------------

#[test]
fn vector_conj_count_nth() {
    // build [10,20,30]; assert count + last element = 3 + 30 = 33
    let v = eval(
        "(let [v (vec-make 8)]
           (vec-conj! v 10)
           (vec-conj! v 20)
           (vec-conj! v 30)
           (+ (vec-count v) (vec-nth v 2)))",
    );
    assert_eq!(v, 33);
}

#[test]
fn vector_sum_via_loop() {
    // fill [0,2,4,…,2*(n-1)] then sum the elements with a loop over nth
    let v = eval(
        "(let [v (vec-make 64)]
           (loop [i 0]
             (if (>= i 10)
               0
               (do (vec-conj! v (* i 2)) (recur (+ i 1)))))
           (loop [j 0 acc 0]
             (if (>= j (vec-count v))
               acc
               (recur (+ j 1) (+ acc (vec-nth v j))))))",
    );
    assert_eq!(v, 90); // 0+2+4+…+18
}

#[test]
fn clojure_core_vector_aliases() {
    let v = eval(
        "(let [v (vec-make 8)]
           (conj! v 11)
           (conj! v 22)
           (conj! v 33)
           (+ (count v) (first v) (nth v 1) (last v)))",
    );
    assert_eq!(v, 69);
}

#[test]
fn vector_literals_lower_to_prelude_vectors() {
    let v = eval("(let [v [11 22 33]] (+ (count v) (first v) (nth v 1) (last v)))");
    assert_eq!(v, 69);
}

#[test]
fn nested_vector_literals_are_independent_handles() {
    let v = eval(
        "(let [outer [[10 20] [30 40 50]]
               left (nth outer 0)
               right (nth outer 1)]
           (+ (count outer) (count left) (count right) (nth right 2)))",
    );
    assert_eq!(v, 57);
}

#[test]
fn vector_destructuring_in_let_and_params() {
    let src = r#"
        (defn sum-pair [[a b]] (+ a b))
        (defn t [_]
          (let [[x y] [10 20]
                [[a b] [c d]] [[1 2] [3 4]]]
            (+ (sum-pair [x y]) a b c d)))
    "#;
    let wasm = compile_str_with_prelude(src).expect("compile");
    let v = run(&wasm, "t", &[0]).expect("run");
    assert_eq!(v, 40);
}

#[test]
fn vector_destructuring_in_if_and_when_let() {
    let v = eval(
        "(+ (if-let [[a b] [10 20]] (+ a b) 0)
            (when-let [[x y] [5 7]] (+ x y)))",
    );
    assert_eq!(v, 42);
}

#[test]
fn add_messages_extend_reducer() {
    // vec-extend! is the add_messages reducer: a=[1,2], extend by b=[3,4,5]
    // → a=[1,2,3,4,5]; assert count + a[4] = 5 + 5 = 10
    let v = eval(
        "(let [a (vec-make 16) b (vec-make 16)]
           (vec-conj! a 1) (vec-conj! a 2)
           (vec-conj! b 3) (vec-conj! b 4) (vec-conj! b 5)
           (vec-extend! a b)
           (+ (vec-count a) (vec-nth a 4)))",
    );
    assert_eq!(v, 10);
}

// ---- map (string keys) ------------------------------------------------------

#[test]
fn map_assoc_get_string_keys() {
    let v = eval(
        "(let [m (map-make 8)]
           (map-assoc! m \"role\" 7)
           (map-assoc! m \"count\" 99)
           (+ (map-get m \"role\") (map-get m \"count\")))",
    );
    assert_eq!(v, 106);
}

#[test]
fn map_missing_key_is_zero() {
    let v = eval(
        "(let [m (map-make 4)]
           (map-assoc! m \"a\" 5)
           (map-get m \"absent\"))",
    );
    assert_eq!(v, 0);
}

#[test]
fn map_assoc_overwrites_existing_key() {
    let v = eval(
        "(let [m (map-make 4)]
           (map-assoc! m \"k\" 1)
           (map-assoc! m \"k\" 42)
           (+ (* 100 (map-count m)) (map-get m \"k\")))",
    );
    // one entry (overwrite, not append) → count=1, value=42 → 142
    assert_eq!(v, 142);
}

#[test]
fn clojure_core_map_aliases() {
    let v = eval(
        "(let [m (map-make 4)]
           (assoc! m \"k\" 41)
           (assoc! m \"k\" 42)
           (+ (count m)
              (get m \"k\")
              (contains-key? m \"k\")
              (empty? (map-make 1))))",
    );
    assert_eq!(v, 45);
}

#[test]
fn map_literals_lower_to_prelude_maps() {
    let v = eval(
        "(let [m {\"k\" 41 \"other\" 1}]
           (+ (count m)
              (get m \"k\")
              (contains-key? m \"other\")))",
    );
    assert_eq!(v, 44);
}

#[test]
fn keyword_keys_in_map_literals_use_canonical_string_keys() {
    let v = eval("(let [m {:k 40 :other 2}] (+ (get m :k) (get m :other)))");
    assert_eq!(v, 42);
}

#[test]
fn map_literals_can_hold_vector_literals() {
    let v = eval(
        "(let [m {:messages [10 20 30]} msgs (get m :messages)] (+ (count msgs) (last msgs)))",
    );
    assert_eq!(v, 33);
}

#[test]
fn literal_lowering_does_not_shadow_source_locals() {
    let v = eval(
        "(let [__kotoba_vec_literal 40
               __kotoba_map_literal 2
               v [__kotoba_vec_literal __kotoba_map_literal]
               m {:v v :x __kotoba_vec_literal}]
           (+ (get m :x) (last (get m :v))))",
    );
    assert_eq!(v, 42);
}

// ---- the langgraph state substrate -----------------------------------------

#[test]
fn state_map_holds_a_messages_vector() {
    // state = {"messages": [100, 200]} — a map whose value is a vector handle.
    // Round-trip: stash the vector under "messages", fetch it back, read it.
    let v = eval(
        "(let [state (map-make 4)
               msgs (vec-make 8)]
           (vec-conj! msgs 100)
           (vec-conj! msgs 200)
           (map-assoc! state \"messages\" msgs)
           (let [m (map-get state \"messages\")]
             (+ (vec-count m) (vec-nth m 1))))",
    );
    assert_eq!(v, 202); // count 2 + element[1] 200
}

#[test]
fn node_appends_to_state_messages() {
    // Simulate one langgraph node step: read state["messages"], append a new
    // message id, write nothing else; assert the vector grew in place.
    let v = eval(
        "(let [state (map-make 4)
               msgs (vec-make 8)]
           (vec-conj! msgs 1)
           (map-assoc! state \"messages\" msgs)
           ;; node body: (assoc state :messages (conj messages new))
           (vec-conj! (map-get state \"messages\") 2)
           (vec-conj! (map-get state \"messages\") 3)
           (vec-count (map-get state \"messages\")))",
    );
    assert_eq!(v, 3);
}
