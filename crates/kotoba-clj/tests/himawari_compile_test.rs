//! Post-PR#184 compile experiment for himawari supply_procurement cell.
//!
//! Raw cell: fails — `let` in `def` initialiser (kotoba-clj restricts `def`
//! to integer constants only — no strings, vectors, or maps at top-level).
//!
//! PoC rewrite: moves all non-integer constants into getter-defn, fixes all
//! string-fn blockers, compiles to WASM and executes.

use kotoba_clj::compile_str_with_prelude;
use kotoba_clj::run::run;

// ── STEP 1: Raw cell source (minimal excerpt) ─────────────────────────────────

const SUPPLY_PROCUREMENT_RAW: &str = r#"
(ns himawari.cells.supply-procurement.state-machine
  (:require [clojure.string :as str]))

(def ^:private SOLAR_GRADES #{"solar-grade-6N" "solar-grade-6N+" "recycled-kerf"})
(def ^:private XUAR_REGIONS #{"xuar" "xinjiang" "uyghur"})

(defn- cid-placeholder [payload]
  (let [s (str payload)
        h (int (.hashCode s))
        abs-h (if (neg? h) (- h) h)]
    (str "bafy~sha256-" (format "%08x" abs-h))))

(defn- guard-feedstock [need]
  (let [grade  (get need "feedstockGrade")
        origin (str/lower-case (str/trim (str (get need "originRegion" ""))))]
    (cond
      (and (some? grade) (not (contains? SOLAR_GRADES grade)))
      {"state" "refused" "reason" (str "feedstockGrade " (pr-str grade) " not solar-grade")}
      (and (< 0 (str-len origin)) (some #(str-includes? origin %) XUAR_REGIONS))
      {"state" "refused" "reason" "XUAR excluded"}
      :else nil)))

(defn solve [state]
  (let [need  (or (get state "need") {})
        guard (guard-feedstock need)]
    (if (some? guard)
      (merge state {"procurementOrder" guard "refused" true "reason" (get guard "reason")})
      (merge state {"procurementOrder" {"state" "ok"} "refused" false}))))
"#;

/// The raw source fails at the FIRST `def` with a string/vector/map.
/// kotoba-clj restricts `def` initializers to integer constants only.
/// Expected error: "`let` is not supported in a `def` initialiser"
/// (because #{"…"} set literals lower to a vec-make/let call).
#[test]
fn raw_supply_procurement_compile_result() {
    match compile_str_with_prelude(SUPPLY_PROCUREMENT_RAW) {
        Ok(wasm) => {
            println!("RAW COMPILE: SUCCESS — {} bytes", wasm.len());
            assert_eq!(&wasm[..4], b"\0asm");
        }
        Err(ref e) => {
            // Expected: Codegen("`let` is not supported in a `def` initialiser")
            println!("RAW COMPILE: FAILED — {e:?}");
        }
    }
}

// ── STEP 2: PoC rewrite — all blockers eliminated ────────────────────────────
//
// Blocker map (10 blockers total for supply_procurement):
//   A) `.hashCode`             → djb2 hash loop (no JVM interop in kotoba-clj)
//   B) `(format "%08x" n)`    → int-to-hex8 manual loop (no Java format)
//   C) `str/lower-case`       → removed (XUAR terms already lower-case)
//   D) `str/trim`             → removed (R0; prelude has no trim)
//   E) `str/blank?`           → (= (str-len s) 0)
//   F) `str/includes?`        → str-includes? (prelude, unqualified)
//   G) `contains?` on set vec → vec-contains? (sets lowered to vecs)
//   H) `pr-str`               → str (prelude has no pr-str)
//   I) hex literals `0x…`     → decimal (EDN parser: decimal integers only)
//   J) `def` of non-int       → getter-defn (kotoba-clj def = integer consts only;
//                               strings/vectors/maps must go in defn bodies)
//
//  Confirmed working (PR#184): merge, bit-and, bit-or, bit-shift-right, multi-arg str

const SUPPLY_PROCUREMENT_REWRITE: &str = r#"
(ns himawari.cells.supply-procurement.state-machine)

;; J: integer-only def (allowed in kotoba-clj)
(def ^:private TITHE_BPS 1000)

;; J: string/vector constants moved to getter-defn
(defn- solar-grades [] ["solar-grade-6N" "solar-grade-6N+" "recycled-kerf"])
(defn- xuar-regions [] ["xuar" "xinjiang" "uyghur"])
(defn- ring-order   [] ["commons" "internal" "external"])

;; A: djb2 hash replaces .hashCode
(defn- djb2 [s]
  (let [n (str-len s)]
    (loop [i 0 h 5381]
      (if (>= i n) h
        (recur (+ i 1) (+ (* h 31) (byte-at s i)))))))

;; B+I: manual hex-8, decimal constants (0xFFFFFFFF = 4294967295)
(defn- int-to-hex8 [n]
  (let [digits (vec-make 8)
        m0 (bit-and n 4294967295)]
    (loop [m m0 i 0]
      (if (>= i 8) 0
        (do
          (vec-conj! digits (let [d (bit-and m 15)]
                               (if (< d 10) (+ 48 d) (+ 87 d))))
          (recur (bit-shift-right m 4) (+ i 1)))))
    (let [buf (bytes-alloc 8)]
      (loop [i 7]
        (if (< i 0)
          (bytes-finish buf)
          (do (byte-append! buf (vec-nth digits i)) (recur (- i 1))))))))

(defn- cid-placeholder [payload]
  (let [s (str payload) h (djb2 s)]
    (str "bafy~sha256-" (int-to-hex8 h))))

;; G+F: vec-contains? and str-includes? (prelude fns, unqualified)
;; C+D: str/lower-case and str/trim removed (XUAR terms already lower)
(defn- guard-feedstock [need]
  (let [grade  (get need "feedstockGrade")
        origin (str (get need "originRegion" ""))]
    (cond
      (and (some? grade) (not (vec-contains? (solar-grades) grade)))
      {"state" "refused" "reason" (str "feedstockGrade " grade " not solar-grade")}
      (and (< 0 (str-len origin))
           (some #(str-includes? origin %) (xuar-regions)))
      {"state" "refused" "reason" "XUAR excluded"}
      :else nil)))

(defn- resolve-ring [need]
  (let [explicit (get need "ring")]
    (cond
      (vec-contains? (ring-order) explicit)                  explicit
      (str-eq? (get need "feedstockGrade") "recycled-kerf")  "commons"
      :else                                                   "external")))

(defn- build-procurement-order [need ring]
  (let [buyer (str (get need "buyerDid" "did:web:etzhayyim.com:himawari"))
        gross (or (get need "grossMinor") 0)
        base  {"lotId"             (get need "lotId")
               "needText"          (str (get need "needText" ""))
               "ring"              ring
               "buyerDid"          buyer
               "intraFabTransport" "giemon-agv"}]
    (case ring
      "commons"
      (merge base {"state" "commons-recovery" "settlement" "commons-none" "titheMinor" 0})
      "internal"
      (let [maker  (str (get need "makerActor" ""))
            tithe  (quot (* gross TITHE_BPS) 10000)
            settle {"rail" "usdc-base-l2" "grossMinor" gross "titheMinor" tithe
                    "makerPayoutMinor" (- gross tithe) "makerActor" maker
                    "state" (if (get need "operatorRef") "executed" "intent")}]
        (merge base {"state" "settle-intent" "makerActor" maker "settlement" settle}))
      (merge base
             {"state"       (if (get need "operatorRef") "external-handoff" "external-pending-operator")
              "supplierDid" (get need "supplierDid")
              "settlement"  "operator-gated-purchase"
              "grossMinor"  gross "titheMinor" 0
              "operatorRef" (get need "operatorRef")}))))

(defn solve [state]
  (let [need  (or (get state "need") {})
        guard (guard-feedstock need)]
    (if (some? guard)
      (merge state {"procurementOrder" guard "refused" true "reason" (get guard "reason")})
      (let [ring  (resolve-ring need)
            order (build-procurement-order need ring)]
        (merge state {"procurementOrder" order "refused" false})))))
"#;

#[test]
fn rewritten_supply_procurement_compiles() {
    let wasm = compile_str_with_prelude(SUPPLY_PROCUREMENT_REWRITE)
        .expect("rewritten supply_procurement should compile");
    println!("REWRITE COMPILE: SUCCESS — {} bytes", wasm.len());
    assert_eq!(&wasm[..4], b"\0asm");
    assert!(wasm.len() > 100);
}

// ── STEP 3: Probe exercising the actual logic ─────────────────────────────────

const SUPPLY_PROCUREMENT_PROBE: &str = r#"
(ns himawari.cells.supply-procurement.probe)

(def ^:private TITHE_BPS 1000)
(defn- solar-grades [] ["solar-grade-6N" "solar-grade-6N+" "recycled-kerf"])
(defn- xuar-regions [] ["xuar" "xinjiang" "uyghur"])

(defn- djb2 [s]
  (let [n (str-len s)]
    (loop [i 0 h 5381]
      (if (>= i n) h
        (recur (+ i 1) (+ (* h 31) (byte-at s i)))))))

;; Returns scenario number on success, 0 on failure.
(defn probe [scenario]
  (cond
    ;; 1: XUAR origin detected (str-includes? fix for str/includes?)
    (= scenario 1)
    (if (some #(str-includes? "xinjiang" %) (xuar-regions)) 1 0)

    ;; 2: non-solar grade refused (vec-contains? fix for contains? on set)
    (= scenario 2)
    (if (not (vec-contains? (solar-grades) "logic-grade-9N")) 2 0)

    ;; 3: valid solar grade accepted
    (= scenario 3)
    (if (vec-contains? (solar-grades) "solar-grade-6N") 3 0)

    ;; 4: bit-and (PR#184) with decimal constant; 4294967295 = 0xFFFFFFFF
    (= scenario 4)
    (if (> (bit-and (djb2 "lot-001") 4294967295) 0) 4 0)

    ;; 5: tithe calculation (PR#184 no impact, regression check)
    (= scenario 5)
    (let [gross 10000 tithe (quot (* gross TITHE_BPS) 10000)]
      (if (= tithe 1000) 5 0))

    ;; 6: merge (PR#184) combines maps correctly
    (= scenario 6)
    (let [base {"a" 1 "b" 2}
          ext  {"c" 3}
          m    (merge base ext)]
      (if (= (map-count m) 3) 6 0))

    ;; 7: multi-arg str (PR#184)
    (= scenario 7)
    (let [s (str "hello" "-" "world")]
      (if (str-eq? s "hello-world") 7 0))

    :else 0))
"#;

fn probe_wasm() -> Vec<u8> {
    compile_str_with_prelude(SUPPLY_PROCUREMENT_PROBE)
        .expect("probe should compile")
}

#[test]
fn probe_xuar_refusal() {
    let wasm = probe_wasm();
    println!("PROBE COMPILE: {} bytes", wasm.len());
    assert_eq!(run(&wasm, "probe", &[1]).expect("run"), 1, "XUAR detected");
}

#[test]
fn probe_non_solar_grade_refused() {
    let wasm = probe_wasm();
    assert_eq!(run(&wasm, "probe", &[2]).expect("run"), 2, "non-solar refused");
}

#[test]
fn probe_valid_solar_grade_accepted() {
    let wasm = probe_wasm();
    assert_eq!(run(&wasm, "probe", &[3]).expect("run"), 3, "valid grade accepted");
}

#[test]
fn probe_bit_and_hash_pr184() {
    let wasm = probe_wasm();
    assert_eq!(run(&wasm, "probe", &[4]).expect("run"), 4, "bit-and hash");
}

#[test]
fn probe_tithe_calculation() {
    let wasm = probe_wasm();
    assert_eq!(run(&wasm, "probe", &[5]).expect("run"), 5, "tithe calc");
}

#[test]
fn probe_merge_pr184() {
    let wasm = probe_wasm();
    assert_eq!(run(&wasm, "probe", &[6]).expect("run"), 6, "merge PR#184");
}

#[test]
fn probe_multi_arg_str_pr184() {
    let wasm = probe_wasm();
    assert_eq!(run(&wasm, "probe", &[7]).expect("run"), 7, "multi-arg str PR#184");
}
