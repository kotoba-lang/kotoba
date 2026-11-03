(ns flow
  "KAMI Flow — orchestration layer for end-to-end digital implementation.
  Restored from the legacy kami-engine/kami-flow Rust crate's `src/lib.rs`
  (kotoba-lang/kami-engine, deleted in PR #82 'Remove Rust workspace from
  kami-engine') as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  P10 integrated pipeline:
  RTL -> PnR -> GDSII -> Verify/Power/DFT/SI/Yield -> STA -> DRC/LVS -> Signoff.

  Scoping correction: this crate was earlier mistakenly recorded as an
  unrelated Node.js/Cypher graph-ingest tool. That description actually
  applies to the sibling `graph/` subdirectory that shares the same
  `kami-flow/` folder in kami-engine (a genuinely unrelated
  neo4j_bulk_ingest.cypher-based tool) — not to this crate's own
  `src/lib.rs`, which had never actually been inspected before. Only
  `src/lib.rs` is ported here; `graph/` remains correctly out of scope.

  A pure-data orchestrator: no GPU, no native FFI, no wasm-bindgen. Wires
  together 7 already-restored sibling EDA crates, one dependency per
  pipeline stage:
    kotoba-lang/rtr              -> rtl.hdl/parse-verilog                 (RTL)
    kotoba-lang/pnr              -> pnr.floorplan, pnr.gdsii              (PnR / GDSII)
    kotoba-lang/model-checking   -> model-checking.equivalence            (Verify, renamed from kami-verify)
    kotoba-lang/power            -> power.estimation, power.ir-drop       (Power)
    kotoba-lang/dft              -> dft.scan, dft.atpg                    (DFT)
    kotoba-lang/signal-integrity -> signal-integrity.transmission-line,
                                     signal-integrity.eye-diagram         (SI, renamed from kami-si)
    kotoba-lang/yield            -> yield.monte-carlo, yield.corner       (Yield)
  (STA and DRC/LVS are computed locally, as in the original Rust — there
  was never a dedicated kami-sta/kami-drc crate.)

  Zero-dependency portable data + pure functions, with one caveat inherited
  transitively: `pnr.gdsii/export-gdsii` is JVM-only (`java.io.
  ByteArrayOutputStream`), so `run-minimal-flow` (which calls it for the
  GDSII artifact) is JVM-only too — mirrors the original Rust crate's own
  unconditional dependency on kami-pnr's gdsii module.

  The original Rust used `serde_json` to hash/serialize `FlowInput` and to
  produce `run_minimal_flow_json`'s output. `serde_json` is not a
  zero-dependency-portable EDN/CLJC primitive, so this port substitutes
  `pr-str` (EDN) for JSON serialization throughout — the hash and JSON
  fields are semantically equivalent (deterministic serialization of the
  same input) but not byte-identical to the Rust JSON output."
  (:require [kotoba.lang.text :as str]
            [rtl.hdl :as hdl]
            [pnr.floorplan :as floorplan]
            [pnr.gdsii :as gdsii]
            [model-checking.equivalence :as equivalence]
            [power.estimation :as estimation]
            [power.ir-drop :as ir-drop]
            [dft.scan :as scan]
            [dft.atpg :as atpg]
            [signal-integrity.transmission-line :as tline]
            [signal-integrity.eye-diagram :as eye]
            [yield.monte-carlo :as mc]
            [yield.corner :as corner]))

;; ---------------------------------------------------------------------------
;; FlowThresholds / DrcLvsConfig / FlowInput

(defn flow-thresholds
  "Signoff pass/fail thresholds. `overrides` merges over the defaults."
  ([] (flow-thresholds {}))
  ([overrides]
   (merge {:max-ir-drop-mv 100.0
           :min-dft-atpg-coverage 0.95
           :si-z0-min-ohm 40.0
           :si-z0-max-ohm 60.0
           :min-yield-pass-ratio 0.95
           :min-setup-slack-ps 0.0
           :min-hold-slack-ps 0.0
           :max-drc-violations 0
           :max-lvs-mismatches 0}
          overrides)))

(defn drc-lvs-config
  "DRC/LVS run configuration. `overrides` merges over the defaults."
  ([] (drc-lvs-config {}))
  ([overrides]
   (merge {:run-drc true
           :run-lvs true
           :drc-rule-deck "default_drc.deck"
           :lvs-rule-deck "default_lvs.deck"}
          overrides)))

(defn flow-input
  "Top-level flow input. `overrides` merges over the defaults (a trivial
  1-bit AND-gate design)."
  ([] (flow-input {}))
  ([overrides]
   (merge {:rtl-source "module top(input a, input b, output y); assign y = a & b; endmodule"
           :top-module-hint nil
           :die-width-um 2000.0
           :die-height-um 2000.0
           :clock-freq-mhz 500.0
           :supply-v 0.8
           :cell-count-estimate 20000
           :policy-version "p11.1"
           :policy-profile "nominal"
           :thresholds (flow-thresholds)
           :drc-lvs (drc-lvs-config)}
          overrides)))

(defn artifact-record [name kind bytes hash-fnv1a64]
  {:name name :kind kind :bytes bytes :hash-fnv1a64 hash-fnv1a64})

;; ---------------------------------------------------------------------------
;; FNV-1a 64-bit hash + run-id

(def ^:private fnv-offset-basis-64 -3750763034362895579) ;; 0xcbf29ce484222325 as a signed i64
(def ^:private fnv-prime-64 1099511628211)               ;; 0x100000001b3

#?(:clj
   (defn fnv1a64-hex
     "FNV-1a 64-bit hash of `s` (a String), hex-encoded (16 lowercase digits,
     zero-padded) — matches the original Rust `fnv1a64_hex`."
     [^String s]
     (let [bs (.getBytes s "UTF-8")]
       (loop [i 0 h fnv-offset-basis-64]
         (if (>= i (alength bs))
           (format "%016x" h)
           (let [b (bit-and (long (aget bs i)) 0xff)]
             (recur (inc i) (unchecked-multiply (bit-xor h b) fnv-prime-64)))))))
   :cljs
   (defn fnv1a64-hex
     "FNV-1a 64-bit hash of `s` (a String), hex-encoded. CLJS fallback uses
     JS bit ops on 32-bit halves; not bit-exact with the JVM/Rust 64-bit
     result but deterministic and collision-resistant enough for artifact
     bookkeeping."
     [s]
     (loop [i 0 h1 0xcbf29ce4 h2 0x84222325]
       (if (>= i (count s))
         (str (.. (bit-and h1 0xffffffff) (toString 16) (padStart 8 "0"))
              (.. (bit-and h2 0xffffffff) (toString 16) (padStart 8 "0")))
         (let [b (bit-and (.charCodeAt s i) 0xff)
               h2 (bit-xor h2 b)
               h2 (Math/imul h2 0x1b3)]
           (recur (inc i) h1 h2))))))

(defn- fnv1a64-hex-bytes
  "FNV-1a 64-bit hash of a byte seq/array, hex-encoded."
  [bs]
  #?(:clj (loop [i 0 h fnv-offset-basis-64]
            (if (>= i (alength bs))
              (format "%016x" h)
              (let [b (bit-and (long (aget bs i)) 0xff)]
                (recur (inc i) (unchecked-multiply (bit-xor h b) fnv-prime-64)))))
     :cljs (fnv1a64-hex (apply str (map char bs)))))

(defn- utf8-byte-count
  "Number of UTF-8 bytes `s` encodes to (not `count`, which is char count)."
  [s]
  #?(:clj (alength (.getBytes ^String s "UTF-8"))
     :cljs (count s)))

(defn- build-run-id [input-hash gds-hash]
  (str "run-" (subs input-hash 0 8) "-" (subs gds-hash 0 8)))

(defn- status->str
  "Renders an equivalence status keyword the way Rust's `{:?}` Debug format
  would: `:pass` -> \"Pass\", `:fail` -> \"Fail\", `:inconclusive` ->
  \"Inconclusive\"."
  [k]
  (let [s (name k)]
    (str (str/upper (subs s 0 1)) (subs s 1))))

;; ---------------------------------------------------------------------------
;; Per-stage runners

(defn- run-pnr [die-width-um die-height-um]
  (let [blocks [{:name "stdcell_core" :block-type :std-cell-region
                 :x 0.0 :y 0.0
                 :width (* die-width-um 0.8) :height (* die-height-um 0.7)
                 :fixed false}
                {:name "sram0" :block-type :macro
                 :x 0.0 :y 0.0
                 :width (* die-width-um 0.15) :height (* die-height-um 0.15)
                 :fixed false}]
        fp (floorplan/auto-floorplan blocks die-width-um die-height-um)
        dw (long die-width-um)
        dh (long die-height-um)
        gds (gdsii/export-gdsii
             [{:name "TOP"
               :elements [{:kind :boundary :layer 1 :datatype 0
                           :xy [[0 0] [dw 0] [dw dh] [0 dh] [0 0]]}]}])]
    [fp gds]))

(defn- run-verify []
  (let [golden [["y" "AND" ["a" "b"]]]
        revised golden]
    (equivalence/check-equivalence golden revised)))

(defn- run-power [cell-count-estimate clock-freq-mhz supply-v]
  (let [dynamic-uw (estimation/estimate-dynamic-power
                     cell-count-estimate 0.15 clock-freq-mhz supply-v 0.01)
        rows 8 cols 8
        current-map (vec (for [r (range rows)]
                            (vec (for [c (range cols)]
                                   (if (and (pos? r) (< r (dec rows))
                                            (pos? c) (< c (dec cols)))
                                     0.01 0.0)))))
        ir (ir-drop/analyze-ir-drop rows cols supply-v current-map 0.1)]
    [(/ dynamic-uw 1000.0) (:max-drop-mv ir)]))

(defn- run-dft [ff-count gate-count]
  (let [ffs (mapv #(str "ff_" %) (range ff-count))
        chains (scan/insert-scan-chains
                ffs
                (scan/config {:chain-count 4 :max-length 1024
                              :clock-name "clk" :scan-enable "scan_en"
                              :scan-in-prefix "SI_" :scan-out-prefix "SO_"}))
        scan-stats (scan/scan-chain-stats chains)
        faults (mapv (fn [i]
                       {:net-name (str "n_" i)
                        :fault-type (if (even? i) :stuck-at-0 :stuck-at-1)
                        :detected false})
                     (range 64))
        atpg-result (atpg/generate-patterns faults gate-count)]
    [(:num-chains scan-stats) (:fault-coverage atpg-result)]))

(defn- run-si []
  (let [tl (tline/microstrip 0.3 0.2 4.2)
        z (tline/calculate-z0 tl 10.0)
        eye (eye/generate-eye-data 10.0 800.0 30.0 10.0 5.0 128)]
    [(:z0-ohm z) (get-in eye [:metrics :eye-height-mv])]))

(defn- run-yield []
  (let [config (mc/monte-carlo-config
                1000 42 [(mc/mc-parameter "vth" 0.4 (mc/gaussian 0.02))])
        results (mc/run-monte-carlo config (fn [p] (first p)) 0.35 0.45)
        yield-pass (or (:yield-pass (last results)) 0.0)
        corners (corner/standard-corners)]
    [yield-pass (count corners)]))

(defn- run-sta [clock-freq-mhz cell-count-estimate]
  (let [period-ps (/ 1000000.0 (max clock-freq-mhz 1.0))
        estimated-path-delay-ps (+ (* period-ps 0.45)
                                    (* (/ cell-count-estimate 1000.0) 2.5))
        setup-slack-ps (- period-ps estimated-path-delay-ps)
        hold-slack-ps (- 15.0 (/ cell-count-estimate 5000.0))]
    [setup-slack-ps hold-slack-ps]))

(defn- run-drc-lvs [fp equiv config]
  (let [drc-violations (if (:run-drc config)
                          (cond-> (count (floorplan/validate fp))
                            (> (floorplan/utilization fp) 0.85) inc)
                          0)
        lvs-mismatches (if (:run-lvs config)
                          (if (= (:status equiv) :pass) 0 1)
                          0)]
    [drc-violations lvs-mismatches]))

;; ---------------------------------------------------------------------------
;; Top-level entry points

(defn run-minimal-flow
  "Run the full P10 flow on `input` (a flow-input map). Returns
  `[:ok signoff-report]` or `[:error message]` (RTL-parse failure is the
  only modelled error, matching the original Rust `FlowError`)."
  [input]
  (let [input-edn (pr-str input)
        input-hash-fnv1a64 (fnv1a64-hex input-edn)
        [tag parsed] (hdl/parse-verilog (:rtl-source input))]
    (if (= tag :error)
      [:error (str "RTL parse failed: " parsed)]
      (let [[parsed-module-name ports] parsed
            top-module (or (:top-module-hint input) parsed-module-name)

            [fp gds-bytes] (run-pnr (:die-width-um input) (:die-height-um input))
            gdsii-size-bytes (count gds-bytes)
            floorplan-violations (floorplan/validate fp)

            equiv (run-verify)
            [dynamic-power-mw ir-max-drop-mv]
            (run-power (:cell-count-estimate input) (:clock-freq-mhz input) (:supply-v input))
            [dft-scan-chain-count dft-atpg-coverage]
            (run-dft (max (quot (:cell-count-estimate input) 100) 16)
                     (quot (:cell-count-estimate input) 10))
            [si-z0-ohm si-eye-height-mv] (run-si)
            [yield-pass-ratio pvt-corner-count] (run-yield)
            [sta-setup-slack-ps sta-hold-slack-ps]
            (run-sta (:clock-freq-mhz input) (:cell-count-estimate input))
            [drc-violations lvs-mismatches] (run-drc-lvs fp equiv (:drc-lvs input))

            t (:thresholds input)
            checks [["rtl_parse" true]
                    ["floorplan_valid" (empty? floorplan-violations)]
                    ["equivalence" (= (:status equiv) :pass)]
                    ["sta_setup_slack" (>= sta-setup-slack-ps (:min-setup-slack-ps t))]
                    ["sta_hold_slack" (>= sta-hold-slack-ps (:min-hold-slack-ps t))]
                    ["ir_drop_under_threshold" (<= ir-max-drop-mv (:max-ir-drop-mv t))]
                    ["dft_atpg_coverage" (>= dft-atpg-coverage (:min-dft-atpg-coverage t))]
                    ["si_z0_range" (and (>= si-z0-ohm (:si-z0-min-ohm t))
                                        (<= si-z0-ohm (:si-z0-max-ohm t)))]
                    ["yield_threshold" (>= yield-pass-ratio (:min-yield-pass-ratio t))]
                    ["drc_violations_threshold" (<= drc-violations (:max-drc-violations t))]
                    ["lvs_mismatches_threshold" (<= lvs-mismatches (:max-lvs-mismatches t))]]
            signoff-pass (every? second checks)

            rtl-bytes (:rtl-source input)
            floorplan-edn (pr-str fp)
            gds-hash (fnv1a64-hex-bytes gds-bytes)
            run-id (build-run-id input-hash-fnv1a64 gds-hash)

            artifacts [(artifact-record "rtl_source.v" "rtl"
                                         (utf8-byte-count rtl-bytes) (fnv1a64-hex rtl-bytes))
                       (artifact-record "floorplan.json" "pnr-floorplan"
                                         (utf8-byte-count floorplan-edn) (fnv1a64-hex floorplan-edn))
                       (artifact-record "layout.gds" "gdsii"
                                         gdsii-size-bytes gds-hash)]]
        [:ok {:run-id run-id
              :input-hash-fnv1a64 input-hash-fnv1a64
              :policy-version (:policy-version input)
              :policy-profile (:policy-profile input)
              :top-module top-module
              :rtl-port-count (count ports)
              :rtl-parse-ok true
              :floorplan-utilization (floorplan/utilization fp)
              :floorplan-violations floorplan-violations
              :gdsii-size-bytes gdsii-size-bytes
              :equivalence-status (status->str (:status equiv))
              :equivalence-mismatch-count (count (:mismatches equiv))
              :dynamic-power-mw dynamic-power-mw
              :ir-max-drop-mv ir-max-drop-mv
              :dft-scan-chain-count dft-scan-chain-count
              :dft-atpg-coverage dft-atpg-coverage
              :si-z0-ohm si-z0-ohm
              :si-eye-height-mv si-eye-height-mv
              :yield-pass-ratio yield-pass-ratio
              :pvt-corner-count pvt-corner-count
              :sta-setup-slack-ps sta-setup-slack-ps
              :sta-hold-slack-ps sta-hold-slack-ps
              :drc-violations drc-violations
              :lvs-mismatches lvs-mismatches
              :drc-rule-deck (:drc-rule-deck (:drc-lvs input))
              :lvs-rule-deck (:lvs-rule-deck (:drc-lvs input))
              :artifact-count (count artifacts)
              :artifacts artifacts
              :signoff-pass signoff-pass
              :checks checks}]))))

(defn run-minimal-flow-json
  "Runs `run-minimal-flow` and, on success, serializes the report as an EDN
  string (substituting for the original Rust's JSON — see namespace
  docstring). Returns `[:ok edn-string]` or `[:error message]`."
  [input]
  (let [[tag v] (run-minimal-flow input)]
    (if (= tag :ok)
      [:ok (pr-str v)]
      [:error v])))

(defn- fixed
  "`n` formatted to `digits` decimal places (portable stand-in for
  `(format \"%.Nf\" n)`, which has no cljs equivalent)."
  [n digits]
  (let [scale (Math/pow 10 digits)
        rounded (/ (Math/round (* n scale)) scale)
        s (str rounded)
        dot (str/index-of s ".")
        s (if dot s (str s "."))
        dot (or dot (dec (count s)))
        have (- (count s) dot 1)]
    (if (< have digits)
      (str s (apply str (repeat (- digits have) "0")))
      (subs s 0 (+ dot 1 digits)))))

(defn render-signoff-html
  "Renders `report` (a signoff-report map) as a self-contained HTML signoff
  summary page, matching the original Rust `render_signoff_html`'s
  structure/content."
  [report]
  (let [rows (apply str
                    (for [[name ok] (:checks report)]
                      (str "<tr><td>" name "</td><td style=\"color:"
                           (if ok "#0a0" "#b00") "\">"
                           (if ok "PASS" "FAIL") "</td></tr>")))]
    (str
     "<!doctype html><html><head><meta charset=\"utf-8\"><title>KAMI Signoff</title></head><body>"
     "<h1>KAMI P10 Signoff Report</h1>"
     "<p><b>Run ID:</b> " (:run-id report) "</p>"
     "<p><b>Input Hash:</b> " (:input-hash-fnv1a64 report) "</p>"
     "<p><b>Policy:</b> " (:policy-version report) " (" (:policy-profile report) ")</p>"
     "<p><b>Top:</b> " (:top-module report) "</p>"
     "<p><b>RTL Ports:</b> " (:rtl-port-count report) "</p>"
     "<p><b>PnR Utilization:</b> " (fixed (double (:floorplan-utilization report)) 3) "</p>"
     "<p><b>GDSII Size:</b> " (:gdsii-size-bytes report) " bytes</p>"
     "<p><b>Equivalence:</b> " (:equivalence-status report)
     " (mismatch=" (:equivalence-mismatch-count report) ")</p>"
     "<p><b>STA Setup Slack:</b> " (fixed (double (:sta-setup-slack-ps report)) 3) " ps</p>"
     "<p><b>STA Hold Slack:</b> " (fixed (double (:sta-hold-slack-ps report)) 3) " ps</p>"
     "<p><b>Dynamic Power:</b> " (fixed (double (:dynamic-power-mw report)) 3) " mW</p>"
     "<p><b>IR Max Drop:</b> " (fixed (double (:ir-max-drop-mv report)) 3) " mV</p>"
     "<p><b>DRC Violations:</b> " (:drc-violations report) " (deck=" (:drc-rule-deck report) ")</p>"
     "<p><b>LVS Mismatches:</b> " (:lvs-mismatches report) " (deck=" (:lvs-rule-deck report) ")</p>"
     "<p><b>DFT Scan Chains:</b> " (:dft-scan-chain-count report) "</p>"
     "<p><b>ATPG Coverage:</b> " (fixed (* 100.0 (double (:dft-atpg-coverage report))) 2) "%</p>"
     "<p><b>SI Z0:</b> " (fixed (double (:si-z0-ohm report)) 3) " ohm</p>"
     "<p><b>SI Eye Height:</b> " (fixed (double (:si-eye-height-mv report)) 3) " mV</p>"
     "<p><b>Yield:</b> " (fixed (* 100.0 (double (:yield-pass-ratio report))) 2) "%</p>"
     "<p><b>PVT Corners:</b> " (:pvt-corner-count report) "</p>"
     "<p><b>Artifacts:</b> " (:artifact-count report) "</p>"
     "<p><b>Overall:</b> <span style=\"color:" (if (:signoff-pass report) "#0a0" "#b00") "\">"
     (if (:signoff-pass report) "PASS" "FAIL") "</span></p>"
     "<table border=\"1\" cellspacing=\"0\" cellpadding=\"6\">"
     "<tr><th>Check</th><th>Result</th></tr>" rows "</table>"
     "</body></html>")))
