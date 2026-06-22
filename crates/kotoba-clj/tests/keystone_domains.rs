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
