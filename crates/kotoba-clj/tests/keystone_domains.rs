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
fn set_literal_value_compiles() {
    // set *values* (`#{…}`) now lower (to a growable vector); membership via `some`. This
    // closes the residual data-subset gap — the physics matrix can use sets directly.
    assert_eq!(
        eval(
            "(let [s #{:bot :prop}
                   member? (fn [coll x] (if (some (fn [e] (= e x)) coll) 1 0))]
               (+ (member? s :bot)              ;; 1
                  (* 10 (member? s :player))))" // 0
        ),
        1
    );
}

#[test]
fn input_axes_from_held() {
    // kami.input/axes-from-held: an axis value from key-set bindings (pos/neg as #{…})
    // against the held-key set. Exercises get-in + nested set membership + subtraction.
    assert_eq!(
        eval(
            "(let [imap {:axes {:MoveX {:pos #{:d :right} :neg #{:a :left}}}}
                   held #{:d}
                   in? (fn [coll x] (if (some (fn [e] (= e x)) coll) 1 0))
                   any? (fn [ks] (if (some (fn [k] (= 1 (in? held k))) ks) 1 0))
                   axis (fn [ax] (- (any? (get-in imap [:axes ax :pos]))
                                    (any? (get-in imap [:axes ax :neg]))))]
               (axis :MoveX))" // :d held, in :pos → +1, none in :neg → 1
        ),
        1
    );
}

#[test]
fn netsync_interp_lerps_fields() {
    // kami.netsync/interp: blend an entity toward a target. reduce-kv + assoc + integer
    // lerp (percent t) — the per-field interpolation, as data.
    assert_eq!(
        eval(
            "(let [ent {:x 0 :hp 100}
                   target {:x 10 :hp 50}
                   lerped (reduce-kv (fn [acc k v]
                                       (assoc acc k (+ v (quot (* (- (get target k) v) 50) 100))))
                                     ent ent)]
               (+ (get lerped :x) (get lerped :hp)))" // x:0+5=5, hp:100-25=75 → 80
        ),
        80
    );
}

#[test]
fn level_zone_membership() {
    // kami.level/in-zone?: get-in for the zone center/radius + a squared-distance test.
    assert_eq!(
        eval(
            "(let [lvl {:zone {:center [0 0] :radius 100}}
                   r (get-in lvl [:zone :radius])
                   cx (nth (get-in lvl [:zone :center]) 0)
                   in? (fn [x y] (if (<= (+ (* (- x cx) (- x cx)) (* y y)) (* r r)) 1 0))]
               (+ (in? 50 0) (* 10 (in? 200 0))))" // inside(1) + 10*outside(0) = 1
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

#[test]
fn map_ops_compile_to_wasm() {
    // the interpreter plumbing: merge (netsync apply-snapshot), update (per-field), reduce.
    assert_eq!(
        eval(
            "(let [m (merge {:a 1} {:b 2})                  ;; {:a 1 :b 2}
                   u (update {:x 5} :x (fn [v] (+ v 10)))   ;; {:x 15}
                   s (reduce (fn [acc x] (+ acc x)) 0 [1 2 3 4])]
               (+ (get m :a) (get m :b) (get u :x) s))" // 1 + 2 + 15 + 10 = 28
        ),
        28
    );
}

#[test]
fn collection_ops_compile_to_wasm() {
    // vectors built/transformed as data: into (extend) + mapv (transform), summed via reduce
    assert_eq!(eval("(reduce (fn [a x] (+ a x)) 0 (into [1 2] [3 4]))"), 10); // 1+2+3+4
    assert_eq!(eval("(reduce (fn [a x] (+ a x)) 0 (mapv (fn [x] (* x x)) [1 2 3]))"), 14); // 1+4+9
}

// Regression: `into` returns a correctly-sized new vector even when dst is at exact
// capacity (a vector literal) — previously over-counted because vec-conj! doesn't grow.
#[test]
fn into_does_not_overflow_capacity() {
    assert_eq!(eval("(count (into [1 2] [3 4]))"), 4, "into count");
    assert_eq!(eval("(nth (into [1 2] [3 4]) 3)"), 4, "into preserves order");
    assert_eq!(eval("(nth (mapv (fn [x] (* x x)) [1 2 3]) 2)"), 9, "mapv/nth correct");
}

// Audit: the same capacity/count class of bug across prelude vector-builders.
#[test]
fn collection_ops_count_audit() {
    assert_eq!(eval("(count (concat [1 2] [3 4]))"), 4, "concat");
    assert_eq!(eval("(count (mapcat (fn [x] [x x]) [1 2 3]))"), 6, "mapcat");
    assert_eq!(eval("(count (interpose 0 [1 2 3]))"), 5, "interpose");
    assert_eq!(eval("(count (distinct [1 1 2 3 3]))"), 3, "distinct");
    assert_eq!(eval("(count (reverse [1 2 3]))"), 3, "reverse");
    assert_eq!(eval("(count (take 2 [1 2 3 4]))"), 2, "take");
    assert_eq!(eval("(count (drop 1 [1 2 3 4]))"), 3, "drop");
    assert_eq!(eval("(count (filterv (fn [x] (> x 1)) [1 2 3]))"), 2, "filterv");
}

// Audit: the map-builder side of the same capacity/count class (map-assoc! never grows).
#[test]
fn map_builders_count_audit() {
    assert_eq!(eval("(count (zipmap [:a :b] [1 2]))"), 2, "zipmap count");
    assert_eq!(eval("(get (zipmap [:a :b] [10 20]) :b)"), 20, "zipmap get");
    assert_eq!(eval("(count (frequencies [:a :a :b :c :c :c]))"), 3, "frequencies distinct count");
    assert_eq!(eval("(get (frequencies [:a :a :b]) :a)"), 2, "frequencies tally");
    assert_eq!(eval("(count (group-by (fn [x] x) [:a :b :a]))"), 2, "group-by groups");
}

// The actual kami.netsync/synced-fields: reduce-kv over :components, into-accumulating the
// per-component :fields. This is the accumulator pattern where the `into` capacity bug lived
// — a strong regression test for the fix in a real interpreter shape.
#[test]
fn netsync_synced_fields_accumulator() {
    assert_eq!(
        eval(
            "(let [schema {:components {:transform {:fields [:x :y]} :health {:fields [:hp]}}}
                   fields (reduce-kv (fn [acc _ comp] (into acc (get comp :fields)))
                                     [] (get schema :components))]
               (count fields))" // :x :y :hp → 3
        ),
        3
    );
    // into with an empty source and an empty accumulator stay well-defined
    assert_eq!(eval("(count (into [] []))"), 0, "into empty");
    assert_eq!(eval("(count (into [] [1 2 3]))"), 3, "into onto empty acc");
}

// Arithmetic semantics the game logic relies on (spawn = mod, AI = signed deltas). Negative
// mod/quot/rem are a classic compiler divergence point — assert Clojure semantics.
#[test]
fn arithmetic_edge_semantics() {
    assert_eq!(eval("(mod 7 3)"), 1);
    assert_eq!(eval("(mod -7 3)"), 2, "Clojure mod is floored (sign of divisor)");
    assert_eq!(eval("(quot 7 3)"), 2);
    assert_eq!(eval("(quot -7 3)"), -2, "quot truncates toward zero");
    assert_eq!(eval("(rem -7 3)"), -1, "rem keeps sign of dividend");
    assert_eq!(eval("(* -3 4)"), -12);
    assert_eq!(eval("(- 0 5)"), -5);
    assert_eq!(eval("(if (< -1 0) 1 0)"), 1, "signed comparison");
}
