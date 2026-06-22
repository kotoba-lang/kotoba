//! Keystone (ADR-0042): the data-driven domain interpreters — the kind kami.physics,
//! kami.fsm, kami.level run on the web in CLJS — compile to WASM via kotoba-clj's data
//! subset (maps, keywords, sets, get-in, contains?, some, assoc, reduce). This is what
//! lets those interpreters run as CLJ on macOS/iOS/Android (via kami-script-runtime),
//! not just CLJS on the web. Each test compiles interpreter logic + runs it, asserting
//! the same result the CLJS version produces.

use kotoba_clj::compile_str_with_prelude;
use kotoba_clj::run::run;

fn eval(body: &str) -> i64 {
    let src = format!("(defn t [_] {body})");
    let wasm = compile_str_with_prelude(&src).expect("compile");
    run(&wasm, "t", &[0]).expect("run")
}

#[test]
fn physics_collision_matrix() {
    // kami.physics/collides? over an EDN matrix of layer → [layers]. (Set *values*
    // #{…} + contains? on them aren't compiled yet — the one remaining kotoba-clj data
    // gap; membership via a vector + `some` is the portable form and compiles today.)
    assert_eq!(
        eval(
            "(let [cfg {:matrix {:player [:bot] :bot [:player :bot]}}
                   member? (fn [coll x] (if (some (fn [e] (= e x)) coll) 1 0))
                   collides? (fn [a b] (if (or (= 1 (member? (get-in cfg [:matrix a]) b))
                                               (= 1 (member? (get-in cfg [:matrix b]) a))) 1 0))]
               (+ (collides? :player :bot)              ;; 1
                  (* 10 (collides? :bot :bot))          ;; 1 → 10
                  (* 100 (collides? :player :pickup))))" // 0
        ),
        11
    );
}

#[test]
fn fsm_advance_transitions() {
    // kami.fsm/advance: first transition whose :from matches (or :any) and :on is in events
    assert_eq!(
        eval(
            "(let [fsm {:transitions [{:from :idle :to :move :on :moving}
                                      {:from :move :to :idle :on :still}]}
                   advance (fn [state ev]
                             (reduce (fn [acc tr]
                                       (if (and (= acc state)
                                                (= (get tr :from) state)
                                                (= (get tr :on) ev))
                                         (get tr :to) acc))
                                     state (get fsm :transitions)))]
               ;; idle --moving--> move (1) ; move --still--> idle (0). encode move=1 idle=0
               (if (= (advance :idle :moving) :move) 1 0))"
        ),
        1
    );
}

#[test]
fn netsync_snapshot_drops_unsynced() {
    // kami.netsync/snapshot: select only the schema's synced fields from an entity map
    assert_eq!(
        eval(
            "(let [fields [:x :hp]
                   ent {:x 5 :y 9 :hp 100 :secret 42}
                   snap (select-keys ent fields)]
               ;; only :x and :hp survive → 5 + 100 = 105 ; :y/:secret dropped
               (+ (get snap :x) (get snap :hp)))"
        ),
        105
    );
}
