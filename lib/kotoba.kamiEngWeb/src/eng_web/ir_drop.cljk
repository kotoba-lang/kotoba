(ns eng-web.ir-drop
  "IR-drop current-map construction, restored from `kami-eng-web/src/lib.rs`
  (`power_analyze_ir_drop` wasm entry point), part of the legacy
  `kami-engine` Rust workspace deleted in kotoba-lang/kami-engine PR #82.
  See ADR-2607010930 (`com-junkawasaki/root`).

  Portable: building the uniform interior-current draw grid the original
  passes into `kami_power::ir_drop::analyze_ir_drop`. Excluded: the actual
  IR-drop solve, which lives in the unported `kami-power` crate.")

(defn current-map
  "Build an `rows` x `cols` current-draw grid with `current` (default 0.01,
  i.e. 10 mA, matching the original) at every interior node and 0.0 on the
  border, mirroring:
  `for row in 1..r-1 { for col in 1..c-1 { current_map[row][col] = 0.01 } }`."
  ([rows cols] (current-map rows cols 0.01))
  ([rows cols current]
   (vec (for [row (range rows)]
          (vec (for [col (range cols)]
                 (if (and (< 0 row (dec rows)) (< 0 col (dec cols)))
                   current
                   0.0)))))))
