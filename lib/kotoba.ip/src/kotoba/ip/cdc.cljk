(ns kotoba.ip.cdc
  "Clock Domain Crossing (CDC) analysis and violation detection.

  Ported from kami-engine's `kami-ip` Rust crate (`src/cdc.rs`). Pure data
  analysis — no network, no I/O, no GPU. Portable `.cljc` across JVM /
  ClojureScript.")

;; ---------------------------------------------------------------------------
;; Vocabulary
;; ---------------------------------------------------------------------------

(def crossing-types
  "Type of CDC crossing."
  #{:single-bit    ; Single-bit signal crossing.
    :multi-bit     ; Multi-bit bus crossing.
    :handshake     ; Handshake protocol crossing.
    :fifo-async})  ; Asynchronous FIFO crossing.

(def synchronizer-types
  "Synchronizer type applied to a crossing."
  #{:two-ff      ; Two flip-flop synchronizer.
    :three-ff    ; Three flip-flop synchronizer (for high reliability).
    :gray-code   ; Gray code encoding (for multi-bit).
    :mux-sync}) ; Mux-based synchronizer.

(def violation-kinds
  "Kind of CDC violation."
  #{:missing-synchronizer  ; No synchronizer on a clock domain crossing.
    :convergence-issue     ; Multiple signals converging after separate synchronizers.
    :reconvergence-issue   ; Signal reconverges after being synchronized differently.
    :glitch-prone})        ; Multi-bit crossing without proper encoding (glitch-prone).

;; ---------------------------------------------------------------------------
;; Constructors
;; ---------------------------------------------------------------------------

(defn clock-domain
  "Clock domain definition. `freq-mhz` is the frequency in MHz."
  [name freq-mhz]
  {:name name :freq-mhz freq-mhz})

(defn cdc-signal
  "Signal with clock domain assignment. `width` is the bit width;
  `has-synchronizer?` whether a synchronizer is present; `synchronizer` the
  synchronizer type if present (else nil)."
  [name source-clock dest-clock width has-synchronizer? synchronizer]
  {:name name
   :source-clock source-clock
   :dest-clock dest-clock
   :width width
   :has-synchronizer? has-synchronizer?
   :synchronizer synchronizer})

;; ---------------------------------------------------------------------------
;; Analysis
;; ---------------------------------------------------------------------------

(defn- signal->crossing+violations
  "Given a signal and the set of known clock domain names, return
  `[crossing violations]` (violations is a vector, possibly empty), or nil
  if the signal does not cross between two known clock domains."
  [clock-names {:keys [name source-clock dest-clock width has-synchronizer? synchronizer]
                :as _signal}]
  (when (and (not= source-clock dest-clock)
             (contains? clock-names source-clock)
             (contains? clock-names dest-clock))
    (let [crossing-type (if (= 1 width) :single-bit :multi-bit)
          crossing {:signal-name name
                     :from-clock source-clock
                     :to-clock dest-clock
                     :crossing-type crossing-type
                     :synchronizer synchronizer}
          ;; NOTE: faithfully ported from the Rust source, including its
          ;; quirk — `crossing-type` here is only ever :single-bit or
          ;; :multi-bit (never :fifo-async), so the "has-fifo" exemption
          ;; below can never trigger. Kept as-is for parity.
          has-gray? (= :gray-code synchronizer)
          has-fifo? (= :fifo-async crossing-type)
          violations (cond-> []
                       (not has-synchronizer?)
                       (conj {:signal name :issue :missing-synchronizer})

                       (and (> width 1) has-synchronizer? (not has-gray?) (not has-fifo?))
                       (conj {:signal name :issue :glitch-prone}))]
      [crossing violations])))

(defn analyze-cdc
  "Analyze `signals` for CDC issues against the known `clocks`. Checks each
  signal that crosses clock domains for missing synchronizers, multi-bit
  glitch-prone crossings, and structural issues. Signals whose source/dest
  clock is not a known clock domain, or whose source equals its dest, are
  skipped."
  [signals clocks]
  (let [clock-names (set (map :name clocks))
        results (keep #(signal->crossing+violations clock-names %) signals)]
    {:crossings (mapv first results)
     :violations (vec (mapcat second results))}))
