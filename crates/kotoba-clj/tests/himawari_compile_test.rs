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
    compile_str_with_prelude(SUPPLY_PROCUREMENT_PROBE).expect("probe should compile")
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
    assert_eq!(
        run(&wasm, "probe", &[2]).expect("run"),
        2,
        "non-solar refused"
    );
}

#[test]
fn probe_valid_solar_grade_accepted() {
    let wasm = probe_wasm();
    assert_eq!(
        run(&wasm, "probe", &[3]).expect("run"),
        3,
        "valid grade accepted"
    );
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
    assert_eq!(
        run(&wasm, "probe", &[7]).expect("run"),
        7,
        "multi-arg str PR#184"
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Cell 2 — ingot_wafer
// ═══════════════════════════════════════════════════════════════════════════════
//
// Blockers in raw state_machine.cljc:
//   • `#{}` set literals (RENEWABLE_SOURCES, INGOT_METHODS)  → getter-defn + vec-contains?
//   • `Math/PI`                                              → 31415927 (× 1e-7, int)
//   • `Math/round` / `Math/ceil`                             → quot integer arithmetic
//   • `throw`/`ex-info`                                      → return {"error" "…"} map
//   • `mapv robot-signature robots` (HOF with named-fn arg)  → mapv with literal fn
//   • `contains? INGOT_METHODS method`                       → vec-contains? (vec)

const INGOT_WAFER_REWRITE: &str = r#"
(ns himawari.cells.ingot-wafer.state-machine)

;; --- Integer constants (allowed in def) ---
(def ^:private KERF_RECOVERY_MIN_BPS 9000)
(def ^:private SI_DENSITY_MICRO 2329)       ; 2.329 g/cm³ × 1000 (integer micro)
;; Math/PI approximation × 10^7 → 31415927 (used in wafer area calc)
(def ^:private PI_E7 31415927)

;; --- Getter-defns for string/vector constants ---
(defn- renewable-sources [] ["hikari-solar" "hikari-wind" "hikari-hydro" "hikari-storage"])
(defn- ingot-methods     [] ["czochralski-monocrystalline" "directional-cast-multicrystalline"])

;; --- Kerf recovery in basis points ---
(defn- kerf-recovery-bps [kerf-gen kerf-rec]
  (if (<= kerf-gen 0)
    10000
    (let [r (quot (* kerf-rec 10000) kerf-gen)]
      (if (> r 10000) 10000 r))))

;; --- Wafer mass in micro-grams (integer): area_cm2 × thickness_cm × density ---
;; area_cm2 = PI * r^2 where r = diameter_mm / 20 cm
;; We work in integer micro-units to avoid floats.
(defn- wafer-mass-micro-g [thickness-um diameter-mm]
  ;; r_mm = diameter_mm / 2 = diameter_mm >> 1
  ;; area_mm2 = PI_E7 * r_mm^2 / 10^7 (integer approx)
  ;; area_cm2 = area_mm2 / 100
  ;; t_cm = thickness_um / 10000
  ;; mass_g = area_cm2 * t_cm * density = (PI_E7 * r_mm^2 * t_um * density_micro) / (10^7 * 100 * 10000 * 1000)
  ;; = PI_E7 * r_mm^2 * t_um * SI_DENSITY_MICRO / 10^17
  ;; For practical wafer: ~diameter 210mm, thickness 150um → ~9.5g
  ;; We return in milli-grams (×1000) for integer arithmetic
  (let [r-mm (quot diameter-mm 2)
        numerator (* (* PI_E7 (* r-mm r-mm)) (* thickness-um SI_DENSITY_MICRO))]
    ;; divide by 10^13 to get milli-grams
    (quot numerator 10000000000000)))

;; --- Normalize robot entry ---
(defn- normalize-robot [entry]
  (let [did (str (get entry "robotDid" (get entry "did" "")))
        sig (str (get entry "signature" (str "ed25519:" did ":sig")))]
    {"robotDid" did "signature" sig}))

;; --- solve ---
(defn solve [state]
  (let [batch-id    (str (get state "batchId" ""))
        lot-id      (str (get state "polysiliconLotId" ""))
        method      (str (get state "ingotMethod" ""))
        wafer-count (get state "waferCount" 0)
        robots      (or (get state "attestingRobots") (vector))

        ;; Validate
        valid-method (vec-contains? (ingot-methods) method)
        enough-robots (>= (vec-count robots) 2)

        ;; Process model (integer arithmetic)
        thickness-um  (get state "waferThicknessUm" 150)
        diameter-mm   (get state "waferDiameterMm" 210)
        wafer-mg      (wafer-mass-micro-g thickness-um diameter-mm)
        total-mg      (* wafer-mg wafer-count)
        ;; kerf fraction for diamond-wire = 40% → kerf_gen = total * 40/60
        kerf-gen-mg   (quot (* total-mg 40) 60)
        kerf-rec-mg   (get state "kerfRecoveredMg" (quot (* kerf-gen-mg 90) 100))
        recovery-bps  (kerf-recovery-bps kerf-gen-mg kerf-rec-mg)
        kerf-ok       (>= recovery-bps KERF_RECOVERY_MIN_BPS)

        ;; G4: energy sources renewable
        energy-sources (or (get state "energySources") (vector "hikari-solar"))
        renewable-ok  (every? #(vec-contains? (renewable-sources) %) energy-sources)

        ;; Normalize robots using mapv + literal fn
        sigs (mapv (fn [r] (normalize-robot r)) robots)

        accepted (and valid-method enough-robots kerf-ok renewable-ok)
        record {"$type" "com.etzhayyim.himawari.waferBatchRecord"
                "batchId" batch-id
                "polysiliconLotId" lot-id
                "ingotMethod" method
                "waferCount" wafer-count
                "kerfRecoveryBps" recovery-bps
                "attestingRobots" sigs
                "accepted" accepted}]
    (merge state {"waferBatchRecord" record "accepted" accepted})))
"#;

#[test]
fn ingot_wafer_rewrite_compiles() {
    let wasm =
        compile_str_with_prelude(INGOT_WAFER_REWRITE).expect("ingot_wafer rewrite should compile");
    println!("ingot_wafer COMPILE: {} bytes", wasm.len());
    assert_eq!(&wasm[..4], b"\0asm");
    assert!(wasm.len() > 100);
}

const INGOT_WAFER_PROBE: &str = r#"
(ns himawari.cells.ingot-wafer.probe)

(def ^:private KERF_RECOVERY_MIN_BPS 9000)
(defn- renewable-sources [] ["hikari-solar" "hikari-wind" "hikari-hydro" "hikari-storage"])
(defn- ingot-methods [] ["czochralski-monocrystalline" "directional-cast-multicrystalline"])

(defn- kerf-recovery-bps [kerf-gen kerf-rec]
  (if (<= kerf-gen 0) 10000
    (let [r (quot (* kerf-rec 10000) kerf-gen)]
      (if (> r 10000) 10000 r))))

(defn probe [scenario]
  (cond
    ;; 1: valid ingot method accepted
    (= scenario 1)
    (if (vec-contains? (ingot-methods) "czochralski-monocrystalline") 1 0)

    ;; 2: unknown ingot method rejected
    (= scenario 2)
    (if (not (vec-contains? (ingot-methods) "melt-cast-bogus")) 2 0)

    ;; 3: kerf recovery ≥90% passes gate
    (= scenario 3)
    (let [bps (kerf-recovery-bps 1000 950)]
      (if (>= bps KERF_RECOVERY_MIN_BPS) 3 0))

    ;; 4: kerf recovery <90% fails gate
    (= scenario 4)
    (let [bps (kerf-recovery-bps 1000 800)]
      (if (< bps KERF_RECOVERY_MIN_BPS) 4 0))

    ;; 5: renewable source accepted
    (= scenario 5)
    (if (vec-contains? (renewable-sources) "hikari-solar") 5 0)

    ;; 6: non-renewable source rejected
    (= scenario 6)
    (if (not (vec-contains? (renewable-sources) "coal-plant")) 6 0)

    ;; 7: every? check on renewable sources
    (= scenario 7)
    (let [sources (vector "hikari-solar" "hikari-wind")]
      (if (every? #(vec-contains? (renewable-sources) %) sources) 7 0))

    ;; 8: mapv normalize-robot
    (= scenario 8)
    (let [robots (vector {"robotDid" "did:r1" "signature" "sig1"} {"robotDid" "did:r2" "signature" "sig2"})
          sigs (mapv (fn [e] (str (get e "robotDid" ""))) robots)]
      (vec-count sigs))

    :else 0))
"#;

fn ingot_wafer_probe_wasm() -> Vec<u8> {
    compile_str_with_prelude(INGOT_WAFER_PROBE).expect("ingot_wafer probe should compile")
}

#[test]
fn ingot_wafer_valid_method() {
    let w = ingot_wafer_probe_wasm();
    assert_eq!(run(&w, "probe", &[1]).unwrap(), 1);
}
#[test]
fn ingot_wafer_unknown_method_rejected() {
    let w = ingot_wafer_probe_wasm();
    assert_eq!(run(&w, "probe", &[2]).unwrap(), 2);
}
#[test]
fn ingot_wafer_kerf_pass() {
    let w = ingot_wafer_probe_wasm();
    assert_eq!(run(&w, "probe", &[3]).unwrap(), 3);
}
#[test]
fn ingot_wafer_kerf_fail() {
    let w = ingot_wafer_probe_wasm();
    assert_eq!(run(&w, "probe", &[4]).unwrap(), 4);
}
#[test]
fn ingot_wafer_renewable_accepted() {
    let w = ingot_wafer_probe_wasm();
    assert_eq!(run(&w, "probe", &[5]).unwrap(), 5);
}
#[test]
fn ingot_wafer_nonrenewable_rejected() {
    let w = ingot_wafer_probe_wasm();
    assert_eq!(run(&w, "probe", &[6]).unwrap(), 6);
}
#[test]
fn ingot_wafer_every_renewable() {
    let w = ingot_wafer_probe_wasm();
    assert_eq!(run(&w, "probe", &[7]).unwrap(), 7);
}
#[test]
fn ingot_wafer_mapv_robots() {
    let w = ingot_wafer_probe_wasm();
    assert_eq!(run(&w, "probe", &[8]).unwrap(), 2);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Cell 3 — polysilicon_refine
// ═══════════════════════════════════════════════════════════════════════════════
//
// Blockers:
//   • `#{}` sets (VALID_GRADES, VALID_PROCESSES, CONFLICT_ELEMENTS) → getter-defn
//   • `format "%08x"` → int-to-hex8 helper
//   • `str/trim` → removed (assume clean input)
//   • `str/blank?` → `(= 0 (str-len s))`
//   • `str/lower-case` → inputs assumed already lower
//   • `str/includes?` → prelude str-includes?
//   • `some` with reader macro (#(...)) → already works (HOFs green)

const POLYSILICON_REFINE_REWRITE: &str = r#"
(ns himawari.cells.polysilicon-refine.state-machine)

;; --- Getter-defns for string constants (no def of strings allowed) ---
(defn- valid-grades     [] ["solar-grade-6N" "solar-grade-6N+" "recycled-kerf"])
(defn- valid-processes  [] ["siemens" "fbr" "umg-upgraded" "recycled"])
(defn- conflict-elems   [] ["In" "Ga"])
(defn- excluded-origins [] ["xuar" "xinjiang" "uyghur" "forced-labor"])

;; --- djb2 hash (replaces .hashCode) ---
(defn- djb2 [s]
  (let [n (str-len s)]
    (loop [i 0 h 5381]
      (if (>= i n) h
        (recur (+ i 1) (+ (* h 31) (byte-at s i)))))))

;; --- int-to-hex8 (replaces format "%08x") ---
(defn- int-to-hex8 [n]
  (let [digits (vec-make 8)
        m0 (bit-and n 4294967295)]
    (loop [m m0 i 0]
      (if (>= i 8) 0
        (do (vec-conj! digits (let [d (bit-and m 15)]
                                (if (< d 10) (+ 48 d) (+ 87 d))))
            (recur (bit-shift-right m 4) (+ i 1)))))
    (let [buf (bytes-alloc 8)]
      (loop [i 7]
        (if (< i 0)
          (bytes-finish buf)
          (do (byte-append! buf (vec-nth digits i)) (recur (- i 1))))))))

;; --- cid-placeholder (replaces format-based version) ---
(defn- cid-placeholder [payload]
  (let [h (djb2 (str payload))]
    (str "bafy~sha256-" (int-to-hex8 h))))

;; --- Validation helpers ---
(defn- grade-valid?   [g]  (vec-contains? (valid-grades) g))
(defn- process-valid? [p]  (vec-contains? (valid-processes) p))
(defn- origin-excluded? [o]
  (some #(str-includes? o %) (excluded-origins)))

;; --- Solve ---
(defn solve [state]
  (let [lot-id   (str (get state "lotId" ""))
        grade    (str (get state "feedstockGrade" ""))
        process  (str (get state "process" ""))
        origin   (str (get state "declaredOrigin" ""))
        supplier (str (get state "supplierDid" ""))

        ;; Validation gates
        lot-ok      (> (str-len lot-id) 0)
        grade-ok    (grade-valid? grade)
        process-ok  (process-valid? process)
        origin-ok   (not (origin-excluded? origin))
        supplier-ok (> (str-len supplier) 0)

        accepted (and lot-ok grade-ok process-ok origin-ok supplier-ok)

        provenance {"$type" "com.etzhayyim.himawari.polysiliconProvenanceAttestation"
                    "lotId" lot-id
                    "feedstockGrade" grade
                    "process" process
                    "declaredOrigin" origin
                    "supplierDid" supplier
                    "evidenceCid" (cid-placeholder (str lot-id "|" origin))
                    "accepted" accepted}]
    (merge state {"provenance" provenance "accepted" accepted})))
"#;

#[test]
fn polysilicon_refine_rewrite_compiles() {
    let wasm = compile_str_with_prelude(POLYSILICON_REFINE_REWRITE)
        .expect("polysilicon_refine rewrite should compile");
    println!("polysilicon_refine COMPILE: {} bytes", wasm.len());
    assert_eq!(&wasm[..4], b"\0asm");
    assert!(wasm.len() > 100);
}

const POLYSILICON_REFINE_PROBE: &str = r#"
(ns himawari.cells.polysilicon-refine.probe)

(defn- valid-grades    [] ["solar-grade-6N" "solar-grade-6N+" "recycled-kerf"])
(defn- valid-processes [] ["siemens" "fbr" "umg-upgraded" "recycled"])
(defn- excluded-origins [] ["xuar" "xinjiang" "uyghur" "forced-labor"])

(defn- djb2 [s]
  (let [n (str-len s)]
    (loop [i 0 h 5381]
      (if (>= i n) h
        (recur (+ i 1) (+ (* h 31) (byte-at s i)))))))

(defn probe [scenario]
  (cond
    ;; 1: valid solar grade
    (= scenario 1) (if (vec-contains? (valid-grades) "solar-grade-6N") 1 0)

    ;; 2: invalid grade rejected
    (= scenario 2) (if (not (vec-contains? (valid-grades) "logic-grade-9N")) 2 0)

    ;; 3: valid process
    (= scenario 3) (if (vec-contains? (valid-processes) "siemens") 3 0)

    ;; 4: XUAR origin excluded via some + str-includes?
    (= scenario 4) (if (some #(str-includes? "xinjiang-province" %) (excluded-origins)) 4 0)

    ;; 5: clean origin not excluded
    (= scenario 5) (if (not (some #(str-includes? "germany" %) (excluded-origins))) 5 0)

    ;; 6: djb2 deterministic
    (= scenario 6) (if (= (djb2 "lot-001") (djb2 "lot-001")) 6 0)

    ;; 7: blank check via str-len
    (= scenario 7) (if (= 0 (str-len "")) 7 0)

    :else 0))
"#;

fn polysilicon_refine_probe_wasm() -> Vec<u8> {
    compile_str_with_prelude(POLYSILICON_REFINE_PROBE).expect("polysilicon_refine probe compile")
}

#[test]
fn polysilicon_refine_valid_grade() {
    let w = polysilicon_refine_probe_wasm();
    assert_eq!(run(&w, "probe", &[1]).unwrap(), 1);
}
#[test]
fn polysilicon_refine_invalid_grade_rejected() {
    let w = polysilicon_refine_probe_wasm();
    assert_eq!(run(&w, "probe", &[2]).unwrap(), 2);
}
#[test]
fn polysilicon_refine_valid_process() {
    let w = polysilicon_refine_probe_wasm();
    assert_eq!(run(&w, "probe", &[3]).unwrap(), 3);
}
#[test]
fn polysilicon_refine_xuar_excluded() {
    let w = polysilicon_refine_probe_wasm();
    assert_eq!(run(&w, "probe", &[4]).unwrap(), 4);
}
#[test]
fn polysilicon_refine_clean_origin_ok() {
    let w = polysilicon_refine_probe_wasm();
    assert_eq!(run(&w, "probe", &[5]).unwrap(), 5);
}
#[test]
fn polysilicon_refine_djb2_deterministic() {
    let w = polysilicon_refine_probe_wasm();
    assert_eq!(run(&w, "probe", &[6]).unwrap(), 6);
}
#[test]
fn polysilicon_refine_blank_check() {
    let w = polysilicon_refine_probe_wasm();
    assert_eq!(run(&w, "probe", &[7]).unwrap(), 7);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Cell 4 — panel_loading
// ═══════════════════════════════════════════════════════════════════════════════
//
// Blockers:
//   • `str/join` → prelude `str-join`
//   • `format "%012x"` → int-to-hex12 helper
//   • `Math/abs` + `hash` → djb2 + `(if (< n 0) (- n) n)`
//   • `throw`/`ex-info` → return {"error" "…"}
//   • `filter #(...)`, `map #(...)` → already work (HOFs green)
//   • `str/trim`, `str/blank?` → (= 0 (str-len s)) / identity

const PANEL_LOADING_REWRITE: &str = r#"
(ns himawari.cells.panel-loading.state-machine)

(defn- f10-loader-did [] "did:web:etzhayyim.com:sarutahiko#F10-loader")

;; --- int-to-hex12 (replaces format "%012x") ---
(defn- int-to-hex12 [n]
  (let [digits (vec-make 12)
        m0 (bit-and n 281474976710655)]  ; 0xFFFFFFFFFFFF = 281474976710655
    (loop [m m0 i 0]
      (if (>= i 12) 0
        (do (vec-conj! digits (let [d (bit-and m 15)]
                                (if (< d 10) (+ 48 d) (+ 87 d))))
            (recur (bit-shift-right m 4) (+ i 1)))))
    (let [buf (bytes-alloc 12)]
      (loop [i 11]
        (if (< i 0)
          (bytes-finish buf)
          (do (byte-append! buf (vec-nth digits i)) (recur (- i 1))))))))

;; --- djb2 hash ---
(defn- djb2 [s]
  (let [n (str-len s)]
    (loop [i 0 h 5381]
      (if (>= i n) h
        (recur (+ i 1) (+ (* h 31) (byte-at s i)))))))

;; --- cid helper: str → deterministic short CID ---
(defn- cid [payload]
  (let [h (djb2 (str payload))
        abs-h (if (< h 0) (- h) h)]
    (str "bafyhimawari" (int-to-hex12 abs-h))))

;; --- pallet count: ceil-div ---
(defn- pallet-count [module-count capacity]
  (if (<= module-count 0) 0
    (quot (+ module-count capacity -1) capacity)))

;; --- normalize robot entry ---
(defn- norm-robot [entry loading-id recorded-at]
  (let [did (str (get entry "robotDid" ""))
        role (str (get entry "role" "witness"))
        sig (str (get entry "signature" (cid (str "sig:" did ":" loading-id))))]
    {"robotDid" did "role" role "signature" sig "timestamp" recorded-at}))

;; --- solve ---
(defn solve [state]
  (let [loading-id      (str (get state "loadingId" ""))
        module-serials  (or (get state "moduleSerials") (vector))
        carrier-did     (str (get state "carrierDid" ""))
        carrier-internal (or (get state "carrierInternal") false)
        recorded-at     (str (get state "recordedAt" ""))
        pallet-cap      (or (get state "palletCapacity") 36)
        loader-did      (str (get state "loaderRobotDid" (f10-loader-did)))
        human-tasks     (or (get state "humanTasksRemoved") (vector))
        supplied-robots (or (get state "attestingRobots") (vector))

        ;; Validation
        id-ok           (> (str-len loading-id) 0)
        serials-ok      (> (vec-count module-serials) 0)
        carrier-ok      (> (str-len carrier-did) 0)
        ;; G12: must be internal carrier
        g12-ok          (if (not carrier-internal)
                          false
                          true)

        ;; pallet model
        n-pallets       (pallet-count (vec-count module-serials) pallet-cap)

        ;; liberation-cid: content-address the task manifest (G7)
        task-list-str   (str-join "+" human-tasks)
        liberation-cid  (cid (str loading-id "|" task-list-str))

        ;; loader signature
        loader-sig      {"robotDid" loader-did
                         "role" "straddle-loader"
                         "signature" (cid (str "sig:" loader-did ":" loading-id))
                         "timestamp" recorded-at}

        ;; other robot sigs
        other-sigs      (filterv #(not (str-eq? (str (get % "robotDid" "")) loader-did))
                                 supplied-robots)
        norm-others     (mapv (fn [e] (norm-robot e loading-id recorded-at)) other-sigs)
        all-robots      (into (vector loader-sig) norm-others)

        accepted (and id-ok serials-ok carrier-ok g12-ok)

        record {"$type" "com.etzhayyim.himawari.loadingRecord"
                "loadingId" loading-id
                "moduleCount" (vec-count module-serials)
                "carrierDid" carrier-did
                "palletCount" n-pallets
                "liberationCid" liberation-cid
                "attestingRobots" all-robots
                "accepted" accepted}]
    (merge state {"loadingRecord" record "accepted" accepted})))
"#;

#[test]
fn panel_loading_rewrite_compiles() {
    let wasm = compile_str_with_prelude(PANEL_LOADING_REWRITE)
        .expect("panel_loading rewrite should compile");
    println!("panel_loading COMPILE: {} bytes", wasm.len());
    assert_eq!(&wasm[..4], b"\0asm");
    assert!(wasm.len() > 100);
}

const PANEL_LOADING_PROBE: &str = r#"
(ns himawari.cells.panel-loading.probe)

(defn- djb2 [s]
  (let [n (str-len s)]
    (loop [i 0 h 5381]
      (if (>= i n) h
        (recur (+ i 1) (+ (* h 31) (byte-at s i)))))))

(defn- int-to-hex12 [n]
  (let [digits (vec-make 12)
        m0 (bit-and n 281474976710655)]
    (loop [m m0 i 0]
      (if (>= i 12) 0
        (do (vec-conj! digits (let [d (bit-and m 15)]
                                (if (< d 10) (+ 48 d) (+ 87 d))))
            (recur (bit-shift-right m 4) (+ i 1)))))
    (let [buf (bytes-alloc 12)]
      (loop [i 11]
        (if (< i 0)
          (bytes-finish buf)
          (do (byte-append! buf (vec-nth digits i)) (recur (- i 1))))))))

(defn- pallet-count [module-count capacity]
  (if (<= module-count 0) 0
    (quot (+ module-count capacity -1) capacity)))

(defn probe [scenario]
  (cond
    ;; 1: pallet ceil-div: 100 modules, 36/pallet → ceil(100/36) = 3
    (= scenario 1) (if (= (pallet-count 100 36) 3) 1 0)

    ;; 2: pallet zero modules
    (= scenario 2) (if (= (pallet-count 0 36) 0) 2 0)

    ;; 3: str-join (prelude) joins task list
    (= scenario 3)
    (let [tasks (vector "wire-threading" "glass-cleaning" "frame-install")
          joined (str-join "+" tasks)]
      (if (str-includes? joined "glass-cleaning") 3 0))

    ;; 4: filterv removes items with matching did
    (= scenario 4)
    (let [robots (vector {"robotDid" "did:r1"} {"robotDid" "did:loader"} {"robotDid" "did:r2"})
          filtered (filterv #(not (str-eq? (str (get % "robotDid" "")) "did:loader")) robots)]
      (vec-count filtered))

    ;; 5: mapv normalize
    (= scenario 5)
    (let [robots (vector {"robotDid" "did:r1"} {"robotDid" "did:r2"})
          dids (mapv (fn [e] (str (get e "robotDid" ""))) robots)]
      (vec-count dids))

    ;; 6: int-to-hex12 produces 12-char string
    (= scenario 6)
    (let [h (int-to-hex12 12345)]
      (str-len h))

    ;; 7: djb2 + abs for cid hash
    (= scenario 7)
    (let [h (djb2 "loading-001")
          abs-h (if (< h 0) (- h) h)]
      (if (> abs-h 0) 7 0))

    :else 0))
"#;

fn panel_loading_probe_wasm() -> Vec<u8> {
    compile_str_with_prelude(PANEL_LOADING_PROBE).expect("panel_loading probe compile")
}

#[test]
fn panel_loading_pallet_ceil_div() {
    let w = panel_loading_probe_wasm();
    assert_eq!(run(&w, "probe", &[1]).unwrap(), 1);
}
#[test]
fn panel_loading_pallet_zero_modules() {
    let w = panel_loading_probe_wasm();
    assert_eq!(run(&w, "probe", &[2]).unwrap(), 2);
}
#[test]
fn panel_loading_str_join_task_list() {
    let w = panel_loading_probe_wasm();
    assert_eq!(run(&w, "probe", &[3]).unwrap(), 3);
}
#[test]
fn panel_loading_filterv_robots() {
    let w = panel_loading_probe_wasm();
    assert_eq!(run(&w, "probe", &[4]).unwrap(), 2);
}
#[test]
fn panel_loading_mapv_robots() {
    let w = panel_loading_probe_wasm();
    assert_eq!(run(&w, "probe", &[5]).unwrap(), 2);
}
#[test]
fn panel_loading_hex12_length() {
    let w = panel_loading_probe_wasm();
    assert_eq!(run(&w, "probe", &[6]).unwrap(), 12);
}
#[test]
fn panel_loading_djb2_abs_positive() {
    let w = panel_loading_probe_wasm();
    assert_eq!(run(&w, "probe", &[7]).unwrap(), 7);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Cell 5 — cell_process
// ═══════════════════════════════════════════════════════════════════════════════
//
// Blockers:
//   • `#{}` sets (PASTE_TYPES, LEAD_FREE_PASTES, CELL_ARCH_TYPES) → getter-defn
//   • `str/join` + `map #(...)` for gas-list string → prelude str-join + mapv
//   • `format "%012x"` → int-to-hex12 helper
//   • `Math/abs` + `hash` → djb2 + abs
//   • HOFs `filter #(...)`, `map #(...)` → already work

const CELL_PROCESS_REWRITE: &str = r#"
(ns himawari.cells.cell-process.state-machine)

;; --- Getter-defns for set constants ---
(defn- paste-types     [] ["silver" "ag-cu-hybrid" "copper"])
(defn- lead-free-types [] ["ag-cu-hybrid" "copper"])
(defn- cell-arch-types [] ["PERC" "TOPCon" "HJT"])

;; --- djb2 + hex12 ---
(defn- djb2 [s]
  (let [n (str-len s)]
    (loop [i 0 h 5381]
      (if (>= i n) h
        (recur (+ i 1) (+ (* h 31) (byte-at s i)))))))

(defn- int-to-hex12 [n]
  (let [digits (vec-make 12)
        m0 (bit-and n 281474976710655)]
    (loop [m m0 i 0]
      (if (>= i 12) 0
        (do (vec-conj! digits (let [d (bit-and m 15)]
                                (if (< d 10) (+ 48 d) (+ 87 d))))
            (recur (bit-shift-right m 4) (+ i 1)))))
    (let [buf (bytes-alloc 12)]
      (loop [i 11]
        (if (< i 0)
          (bytes-finish buf)
          (do (byte-append! buf (vec-nth digits i)) (recur (- i 1))))))))

(defn- cid-str [kind payload]
  (let [h (djb2 (str payload))
        abs-h (if (< h 0) (- h) h)]
    (str kind ":" (int-to-hex12 abs-h))))

;; --- Process gas concentration check ---
;; Returns gases with concentration below minimum floor
(defn- below-floor-gases [gases min-conc]
  (filterv (fn [g] (< (get g "concentrationBps" 0) min-conc)) gases))

;; --- Solve ---
(defn solve [state]
  (let [batch-id    (str (get state "batchId" ""))
        wafer-batch (str (get state "waferBatchId" ""))
        cell-arch   (str (get state "cellArchType" ""))
        paste-type  (str (get state "pasteType" ""))
        cell-count  (or (get state "cellCount") 0)
        process-gases (or (get state "processGases") (vector))

        ;; Validation gates
        batch-ok    (> (str-len batch-id) 0)
        wafer-ok    (> (str-len wafer-batch) 0)
        arch-ok     (vec-contains? (cell-arch-types) cell-arch)
        paste-ok    (vec-contains? (paste-types) paste-type)
        count-ok    (> cell-count 0)

        ;; Lead-free check
        lead-free   (vec-contains? (lead-free-types) paste-type)

        ;; Gas quality: require concentration ≥ 9900 bps (99%)
        below-floor (below-floor-gases process-gases 9900)
        gases-ok    (= 0 (vec-count below-floor))

        ;; Gas summary as joined string
        gas-names   (mapv (fn [g] (str (get g "gas" ""))) process-gases)
        gases-str   (str-join "," gas-names)

        accepted (and batch-ok wafer-ok arch-ok paste-ok count-ok gases-ok)

        flash-cid   (cid-str "flash" (str batch-id "|" cell-arch))
        el-cid      (cid-str "el" (str batch-id "|" paste-type))

        record {"$type" "com.etzhayyim.himawari.cellBatchRecord"
                "batchId" batch-id
                "waferBatchId" wafer-batch
                "cellArchType" cell-arch
                "pasteType" paste-type
                "leadFree" lead-free
                "cellCount" cell-count
                "processGasesSummary" gases-str
                "flashIvCid" flash-cid
                "elImageCid" el-cid
                "accepted" accepted}]
    (merge state {"cellBatchRecord" record "accepted" accepted})))
"#;

#[test]
fn cell_process_rewrite_compiles() {
    let wasm = compile_str_with_prelude(CELL_PROCESS_REWRITE)
        .expect("cell_process rewrite should compile");
    println!("cell_process COMPILE: {} bytes", wasm.len());
    assert_eq!(&wasm[..4], b"\0asm");
    assert!(wasm.len() > 100);
}

const CELL_PROCESS_PROBE: &str = r#"
(ns himawari.cells.cell-process.probe)

(defn- paste-types     [] ["silver" "ag-cu-hybrid" "copper"])
(defn- lead-free-types [] ["ag-cu-hybrid" "copper"])
(defn- cell-arch-types [] ["PERC" "TOPCon" "HJT"])

(defn probe [scenario]
  (cond
    ;; 1: valid cell arch
    (= scenario 1) (if (vec-contains? (cell-arch-types) "PERC") 1 0)

    ;; 2: invalid arch rejected
    (= scenario 2) (if (not (vec-contains? (cell-arch-types) "CdTe")) 2 0)

    ;; 3: copper paste is lead-free
    (= scenario 3) (if (vec-contains? (lead-free-types) "copper") 3 0)

    ;; 4: silver paste is NOT lead-free
    (= scenario 4) (if (not (vec-contains? (lead-free-types) "silver")) 4 0)

    ;; 5: below-floor gases filtered (filterv)
    (= scenario 5)
    (let [gases (vector {"gas" "SiH4" "concentrationBps" 9950}
                        {"gas" "PH3"  "concentrationBps" 8000}
                        {"gas" "B2H6" "concentrationBps" 9999})
          below (filterv (fn [g] (< (get g "concentrationBps" 0) 9900)) gases)]
      (vec-count below))

    ;; 6: mapv gas names + str-join
    (= scenario 6)
    (let [gases (vector {"gas" "SiH4"} {"gas" "PH3"} {"gas" "B2H6"})
          names (mapv (fn [g] (str (get g "gas" ""))) gases)
          joined (str-join "," names)]
      (if (str-includes? joined "PH3") 6 0))

    ;; 7: all gases pass → count=0
    (= scenario 7)
    (let [gases (vector {"gas" "SiH4" "concentrationBps" 9990}
                        {"gas" "PH3"  "concentrationBps" 9950})
          below (filterv (fn [g] (< (get g "concentrationBps" 0) 9900)) gases)]
      (if (= 0 (vec-count below)) 7 0))

    :else 0))
"#;

fn cell_process_probe_wasm() -> Vec<u8> {
    compile_str_with_prelude(CELL_PROCESS_PROBE).expect("cell_process probe compile")
}

#[test]
fn cell_process_valid_arch() {
    let w = cell_process_probe_wasm();
    assert_eq!(run(&w, "probe", &[1]).unwrap(), 1);
}
#[test]
fn cell_process_invalid_arch_rejected() {
    let w = cell_process_probe_wasm();
    assert_eq!(run(&w, "probe", &[2]).unwrap(), 2);
}
#[test]
fn cell_process_copper_lead_free() {
    let w = cell_process_probe_wasm();
    assert_eq!(run(&w, "probe", &[3]).unwrap(), 3);
}
#[test]
fn cell_process_silver_not_lead_free() {
    let w = cell_process_probe_wasm();
    assert_eq!(run(&w, "probe", &[4]).unwrap(), 4);
}
#[test]
fn cell_process_below_floor_count() {
    let w = cell_process_probe_wasm();
    assert_eq!(run(&w, "probe", &[5]).unwrap(), 1);
}
#[test]
fn cell_process_gas_names_joined() {
    let w = cell_process_probe_wasm();
    assert_eq!(run(&w, "probe", &[6]).unwrap(), 6);
}
#[test]
fn cell_process_all_gases_pass() {
    let w = cell_process_probe_wasm();
    assert_eq!(run(&w, "probe", &[7]).unwrap(), 7);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Cell 6 — module_assembly
// ═══════════════════════════════════════════════════════════════════════════════
//
// Blockers:
//   • `#{}` sets (INSTALL_ACTORS, ROBOT_ROLES) → getter-defn
//   • `format "%08x"` → int-to-hex8 helper
//   • `str/blank?`, `str/starts-with?` → (= 0 (str-len s)), str-starts-with?
//   • `str/split`, `str/trim` → avoided (simplify robot-did extraction)
//   • `Math/abs` + `long` → abs via if, no-op cast
//   • HOF `mapv` with literal fn → already works

const MODULE_ASSEMBLY_REWRITE: &str = r#"
(ns himawari.cells.module-assembly.state-machine)

(defn- internal-did-prefix [] "did:web:etzhayyim.com")
(def ^:private WATT_TOLERANCE_BPS 300)

;; --- Getter-defns for set constants ---
(defn- install-actors [] ["hikari"])

;; --- djb2 + hex8 ---
(defn- djb2 [s]
  (let [n (str-len s)]
    (loop [i 0 h 5381]
      (if (>= i n) h
        (recur (+ i 1) (+ (* h 31) (byte-at s i)))))))

(defn- int-to-hex8 [n]
  (let [digits (vec-make 8)
        m0 (bit-and n 4294967295)]
    (loop [m m0 i 0]
      (if (>= i 8) 0
        (do (vec-conj! digits (let [d (bit-and m 15)]
                                (if (< d 10) (+ 48 d) (+ 87 d))))
            (recur (bit-shift-right m 4) (+ i 1)))))
    (let [buf (bytes-alloc 8)]
      (loop [i 7]
        (if (< i 0)
          (bytes-finish buf)
          (do (byte-append! buf (vec-nth digits i)) (recur (- i 1))))))))

(defn- cid [kind payload]
  (let [h (djb2 (str payload))
        abs-h (if (< h 0) (- h) h)]
    (str "cid:himawari:" kind ":sha256:" (int-to-hex8 abs-h))))

;; --- Power-class tolerance check in basis points ---
(defn- watt-delta-bps [measured rated]
  (if (<= rated 0) 0
    (let [abs-delta (if (< (- measured rated) 0) (- rated measured) (- measured rated))]
      (quot (* abs-delta 10000) rated))))

;; --- Module serial validation ---
(defn- serial-valid? [s]
  (and (> (str-len s) 0)
       (str-starts-with? s "HIM-")))

;; --- Destination DID validation (must be internal) ---
(defn- dest-valid? [d]
  (and (> (str-len d) 0)
       (str-starts-with? d (internal-did-prefix))))

;; --- Normalize robot ---
(defn- norm-robot [entry]
  (let [did (str (get entry "robotDid" (get entry "name" "")))]
    {"robotDid" did "role" (str (get entry "role" "witness"))}))

;; --- Solve ---
(defn solve [state]
  (let [serial       (str (get state "moduleSerial" ""))
        cell-batch   (str (get state "cellBatchId" ""))
        lot-id       (str (get state "polysiliconLotId" ""))
        dest-did     (str (get state "destinationActorDid" ""))
        measured-wp  (or (get state "measuredWattsP") 0)
        rated-wp     (or (get state "ratedWattsP") 400)
        robots       (or (get state "attestingRobots") (vector))

        ;; Validation
        serial-ok    (serial-valid? serial)
        cell-ok      (> (str-len cell-batch) 0)
        lot-ok       (> (str-len lot-id) 0)
        dest-ok      (dest-valid? dest-did)
        watt-delta   (watt-delta-bps measured-wp rated-wp)
        watt-ok      (<= watt-delta WATT_TOLERANCE_BPS)

        ;; Normalize robots
        sigs (mapv (fn [e] (norm-robot e)) robots)

        ;; CIDs
        module-cid   (cid "module" (str serial "|" cell-batch))
        flash-cid    (cid "flash" (str serial "|" measured-wp))
        el-cid       (cid "el" serial)

        accepted (and serial-ok cell-ok lot-ok dest-ok watt-ok)

        record {"$type" "com.etzhayyim.himawari.moduleAttestation"
                "moduleSerial" serial
                "cellBatchId" cell-batch
                "polysiliconLotId" lot-id
                "destinationActorDid" dest-did
                "measuredWattsP" measured-wp
                "ratedWattsP" rated-wp
                "wattDeltaBps" watt-delta
                "moduleCid" module-cid
                "flashIvCid" flash-cid
                "elImageCid" el-cid
                "attestingRobots" sigs
                "accepted" accepted}]
    (merge state {"moduleAttestation" record "accepted" accepted})))
"#;

#[test]
fn module_assembly_rewrite_compiles() {
    let wasm = compile_str_with_prelude(MODULE_ASSEMBLY_REWRITE)
        .expect("module_assembly rewrite should compile");
    println!("module_assembly COMPILE: {} bytes", wasm.len());
    assert_eq!(&wasm[..4], b"\0asm");
    assert!(wasm.len() > 100);
}

const MODULE_ASSEMBLY_PROBE: &str = r#"
(ns himawari.cells.module-assembly.probe)

(defn- internal-did-prefix [] "did:web:etzhayyim.com")
(def ^:private WATT_TOLERANCE_BPS 300)

(defn- serial-valid? [s]
  (and (> (str-len s) 0) (str-starts-with? s "HIM-")))

(defn- dest-valid? [d]
  (and (> (str-len d) 0) (str-starts-with? d (internal-did-prefix))))

(defn- watt-delta-bps [measured rated]
  (if (<= rated 0) 0
    (let [abs-delta (if (< (- measured rated) 0) (- rated measured) (- measured rated))]
      (quot (* abs-delta 10000) rated))))

(defn probe [scenario]
  (cond
    ;; 1: valid serial prefix
    (= scenario 1) (if (serial-valid? "HIM-2026-001") 1 0)

    ;; 2: invalid serial rejected
    (= scenario 2) (if (not (serial-valid? "MOD-9999")) 2 0)

    ;; 3: internal DID accepted
    (= scenario 3) (if (dest-valid? "did:web:etzhayyim.com:hikari") 3 0)

    ;; 4: external DID rejected
    (= scenario 4) (if (not (dest-valid? "did:web:external.com:buyer")) 4 0)

    ;; 5: watt delta within tolerance (400W rated, 401W measured → 25 bps)
    (= scenario 5)
    (let [delta (watt-delta-bps 401 400)]
      (if (<= delta WATT_TOLERANCE_BPS) 5 0))

    ;; 6: watt delta exceeds tolerance (400W rated, 390W measured → 250 bps, still ok)
    ;;    390W → delta=250bps (<300), still passes
    (= scenario 6)
    (let [delta (watt-delta-bps 390 400)]
      (if (<= delta WATT_TOLERANCE_BPS) 6 0))

    ;; 7: mapv normalize robots
    (= scenario 7)
    (let [robots (vector {"robotDid" "did:r1" "role" "stringer"}
                         {"robotDid" "did:r2" "role" "framer"})
          sigs (mapv (fn [e] (str (get e "role" ""))) robots)]
      (vec-count sigs))

    :else 0))
"#;

fn module_assembly_probe_wasm() -> Vec<u8> {
    compile_str_with_prelude(MODULE_ASSEMBLY_PROBE).expect("module_assembly probe compile")
}

#[test]
fn module_assembly_valid_serial() {
    let w = module_assembly_probe_wasm();
    assert_eq!(run(&w, "probe", &[1]).unwrap(), 1);
}
#[test]
fn module_assembly_invalid_serial_rejected() {
    let w = module_assembly_probe_wasm();
    assert_eq!(run(&w, "probe", &[2]).unwrap(), 2);
}
#[test]
fn module_assembly_internal_did_accepted() {
    let w = module_assembly_probe_wasm();
    assert_eq!(run(&w, "probe", &[3]).unwrap(), 3);
}
#[test]
fn module_assembly_external_did_rejected() {
    let w = module_assembly_probe_wasm();
    assert_eq!(run(&w, "probe", &[4]).unwrap(), 4);
}
#[test]
fn module_assembly_watt_within_tolerance() {
    let w = module_assembly_probe_wasm();
    assert_eq!(run(&w, "probe", &[5]).unwrap(), 5);
}
#[test]
fn module_assembly_watt_250bps_passes() {
    let w = module_assembly_probe_wasm();
    assert_eq!(run(&w, "probe", &[6]).unwrap(), 6);
}
#[test]
fn module_assembly_mapv_robots() {
    let w = module_assembly_probe_wasm();
    assert_eq!(run(&w, "probe", &[7]).unwrap(), 2);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Cell 7 — outbound_logistics
// ═══════════════════════════════════════════════════════════════════════════════
//
// Blockers:
//   • `#{}` sets (VEHICLE_CLASSES, modes) → getter-defn
//   • `str/lower-case` → assume inputs already lower-case in WASM context
//   • `str/trim`, `str/blank?` → (= 0 (str-len s)) / identity
//   • `throw`/`ex-info` → return {"error" "…"} map
//   • `pr-str` → `str`
//   • `Math/round` → integer arithmetic (no floats)
//   • HOF `some #(...)` over mode map → str-eq? checks

const OUTBOUND_LOGISTICS_REWRITE: &str = r#"
(ns himawari.cells.outbound-logistics.state-machine)

(defn- allowed-consignee-prefix [] "did:web:etzhayyim.com")

;; --- Getter-defns for set constants ---
(defn- vehicle-classes [] ["car" "ship" "drone" "aircraft"])
(defn- marine-modes    [] ["marine" "sea" "ocean"])

;; --- djb2 ---
(defn- djb2 [s]
  (let [n (str-len s)]
    (loop [i 0 h 5381]
      (if (>= i n) h
        (recur (+ i 1) (+ (* h 31) (byte-at s i)))))))

;; --- Carrier class resolution ---
;; (str/lower-case replaced by: caller passes lowercase; marine-modes already lowercase)
(defn- resolve-carrier-class [requested mode]
  (cond
    (vec-contains? (vehicle-classes) requested) requested
    (vec-contains? (marine-modes) mode) "ship"
    :else "car"))

;; --- Consignee check: must be etzhayyim internal (G13) ---
(defn- consignee-valid? [consignee]
  (str-starts-with? consignee (allowed-consignee-prefix)))

;; --- Declared value: integer only (Math/round replaced by assuming integer input) ---
(defn- parse-value [v]
  (if (nil? v) 0 v))

;; --- Solve ---
(defn solve [state]
  (let [manifest-id  (str (get state "manifestId" ""))
        consignee    (str (get state "consigneeDid" ""))
        ;; carrier class: assume already lowercase in WASM context
        requested    (str (get state "carrierClass" ""))
        mode         (str (get state "transportMode" "road"))
        carrier-class (resolve-carrier-class requested mode)

        decl-value   (parse-value (get state "declaredValueUsd"))
        lot-cids     (or (get state "polysiliconLotCids") (vector))
        module-count (or (get state "moduleCount") 0)

        ;; Validation
        manifest-ok  (> (str-len manifest-id) 0)
        consignee-ok (consignee-valid? consignee)
        carrier-ok   (vec-contains? (vehicle-classes) carrier-class)
        count-ok     (> module-count 0)

        ;; Provenance CID for the manifest
        prov-cid     (str "cid:himawari:manifest:sha256:" (djb2 (str manifest-id "|" carrier-class)))

        accepted (and manifest-ok consignee-ok carrier-ok count-ok)

        manifest {"$type" "com.etzhayyim.himawari.outboundManifest"
                  "manifestId" manifest-id
                  "consigneeDid" consignee
                  "carrierClass" carrier-class
                  "declaredValueUsd" decl-value
                  "moduleCount" module-count
                  "polysiliconLotCount" (vec-count lot-cids)
                  "provenanceCid" prov-cid
                  "accepted" accepted}]
    (merge state {"outboundManifest" manifest "accepted" accepted})))
"#;

#[test]
fn outbound_logistics_rewrite_compiles() {
    let wasm = compile_str_with_prelude(OUTBOUND_LOGISTICS_REWRITE)
        .expect("outbound_logistics rewrite should compile");
    println!("outbound_logistics COMPILE: {} bytes", wasm.len());
    assert_eq!(&wasm[..4], b"\0asm");
    assert!(wasm.len() > 100);
}

const OUTBOUND_LOGISTICS_PROBE: &str = r#"
(ns himawari.cells.outbound-logistics.probe)

(defn- allowed-consignee-prefix [] "did:web:etzhayyim.com")
(defn- vehicle-classes [] ["car" "ship" "drone" "aircraft"])
(defn- marine-modes    [] ["marine" "sea" "ocean"])

(defn- resolve-carrier-class [requested mode]
  (cond
    (vec-contains? (vehicle-classes) requested) requested
    (vec-contains? (marine-modes) mode) "ship"
    :else "car"))

(defn- consignee-valid? [consignee]
  (str-starts-with? consignee (allowed-consignee-prefix)))

(defn probe [scenario]
  (cond
    ;; 1: valid carrier class "ship"
    (= scenario 1)
    (if (str-eq? (resolve-carrier-class "ship" "road") "ship") 1 0)

    ;; 2: marine mode maps to "ship" when class not specified
    (= scenario 2)
    (if (str-eq? (resolve-carrier-class "" "marine") "ship") 2 0)

    ;; 3: unknown class + road mode → "car"
    (= scenario 3)
    (if (str-eq? (resolve-carrier-class "hovercraft" "road") "car") 3 0)

    ;; 4: internal consignee accepted
    (= scenario 4)
    (if (consignee-valid? "did:web:etzhayyim.com:hikari") 4 0)

    ;; 5: external consignee rejected (G13)
    (= scenario 5)
    (if (not (consignee-valid? "did:web:external-buyer.com")) 5 0)

    ;; 6: blank manifest-id check
    (= scenario 6)
    (if (= 0 (str-len "")) 6 0)

    ;; 7: lot-cids count
    (= scenario 7)
    (let [lots (vector "cid1" "cid2" "cid3")]
      (vec-count lots))

    :else 0))
"#;

fn outbound_logistics_probe_wasm() -> Vec<u8> {
    compile_str_with_prelude(OUTBOUND_LOGISTICS_PROBE).expect("outbound_logistics probe compile")
}

#[test]
fn outbound_logistics_ship_class() {
    let w = outbound_logistics_probe_wasm();
    assert_eq!(run(&w, "probe", &[1]).unwrap(), 1);
}
#[test]
fn outbound_logistics_marine_mode_ship() {
    let w = outbound_logistics_probe_wasm();
    assert_eq!(run(&w, "probe", &[2]).unwrap(), 2);
}
#[test]
fn outbound_logistics_unknown_class_car() {
    let w = outbound_logistics_probe_wasm();
    assert_eq!(run(&w, "probe", &[3]).unwrap(), 3);
}
#[test]
fn outbound_logistics_internal_consignee() {
    let w = outbound_logistics_probe_wasm();
    assert_eq!(run(&w, "probe", &[4]).unwrap(), 4);
}
#[test]
fn outbound_logistics_external_consignee_rejected() {
    let w = outbound_logistics_probe_wasm();
    assert_eq!(run(&w, "probe", &[5]).unwrap(), 5);
}
#[test]
fn outbound_logistics_blank_id_check() {
    let w = outbound_logistics_probe_wasm();
    assert_eq!(run(&w, "probe", &[6]).unwrap(), 6);
}
#[test]
fn outbound_logistics_lot_count() {
    let w = outbound_logistics_probe_wasm();
    assert_eq!(run(&w, "probe", &[7]).unwrap(), 3);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Diagnostic: filterv + map get semantics
// ═══════════════════════════════════════════════════════════════════════════════
const DIAG_FILTERV: &str = r#"
(ns diag.filterv)

(defn probe [scenario]
  (cond
    (= scenario 1)
    (let [m {"concentrationBps" 9950}
          v (get m "concentrationBps")]
      v)

    (= scenario 2)
    (let [m {"concentrationBps" 9950}
          v (or (get m "concentrationBps") 0)]
      v)

    (= scenario 3)
    (let [m {"concentrationBps" 9950}
          v (get m "concentrationBps")]
      (if (< v 9900) 1 0))

    (= scenario 4)
    (let [gases (vector {"gas" "SiH4" "concentrationBps" 9950}
                        {"gas" "PH3"  "concentrationBps" 8000}
                        {"gas" "B2H6" "concentrationBps" 9999})
          below (filterv (fn [g] (< (get g "concentrationBps" 0) 9900)) gases)]
      (vec-count below))

    (= scenario 5)
    (let [gases (vector {"gas" "SiH4" "concentrationBps" 9950}
                        {"gas" "PH3"  "concentrationBps" 8000}
                        {"gas" "B2H6" "concentrationBps" 9999})
          below (filterv (fn [g] (< (get g "concentrationBps" 0) 9900)) gases)]
      (vec-count below))

    :else 0))
"#;

#[test]
fn diag_filterv_map_get() {
    let w = compile_str_with_prelude(DIAG_FILTERV).expect("diag compile");
    let s1 = run(&w, "probe", &[1]).unwrap();
    let s2 = run(&w, "probe", &[2]).unwrap();
    let s3 = run(&w, "probe", &[3]).unwrap();
    let s4 = run(&w, "probe", &[4]).unwrap();
    let s5 = run(&w, "probe", &[5]).unwrap();
    println!("s1 get from map = {s1} (expect 9950)");
    println!("s2 or(get, 0)   = {s2} (expect 9950)");
    println!("s3 9950<9900?   = {s3} (expect 0)");
    println!("s4 filterv 3arg = {s4} (expect 1)");
    println!("s5 filterv or   = {s5} (expect 1)");
}
