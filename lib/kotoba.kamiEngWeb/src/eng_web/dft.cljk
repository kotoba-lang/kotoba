(ns eng-web.dft
  "Design-for-test input synthesis, restored from `kami-eng-web/src/lib.rs`
  (`dft_insert_scan`/`dft_generate_atpg` wasm entry points), part of the
  legacy `kami-engine` Rust workspace deleted in kotoba-lang/kami-engine
  PR #82. See ADR-2607010930 (`com-junkawasaki/root`).

  Portable: synthesizing the flip-flop names / scan-chain config / fault
  list the original hands to `kami_dft`. Excluded: the actual
  `kami_dft::scan::insert_scan_chains`/`kami_dft::atpg::generate_patterns`
  algorithms, which live in the unported `kami-dft` crate.")

(defn ff-names
  "Generate `ff-count` flip-flop names \"ff_0\", \"ff_1\", ..., mirroring
  `(0..ff_count).map(|i| format!(\"ff_{}\", i))`."
  [ff-count]
  (mapv #(str "ff_" %) (range ff-count)))

(defn scan-chain-config
  "Build the `ScanChainConfig` used by `dft_insert_scan`, with the original
  Rust's fixed `max_length`/clock/scan-enable/prefix defaults."
  [chain-count]
  {:chain-count chain-count
   :max-length 1000
   :clock-name "clk"
   :scan-enable "scan_en"
   :scan-in-prefix "SI_"
   :scan-out-prefix "SO_"})

(defn atpg-faults
  "Generate `fault-count` synthetic stuck-at faults across net_0..net_n-1,
  alternating stuck-at-0/stuck-at-1 by even/odd index, mirroring the
  original Rust's fault synthesis loop in `dft_generate_atpg`."
  [fault-count]
  (mapv (fn [i]
          {:net-name (str "net_" i)
           :fault-type (if (even? i) :stuck-at-0 :stuck-at-1)
           :detected false})
        (range fault-count)))
