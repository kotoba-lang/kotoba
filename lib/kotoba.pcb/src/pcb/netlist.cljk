(ns pcb.netlist
  "Netlist export (SPICE, Verilog gate-level, EDIF) and BOM generation.
  Restored from kami-eda's `netlist` module (deleted PR #82)."
  (:require [kotoba.lang.text :as str]))

(def netlist-formats #{:spice :verilog-gate-level :edif})

(defn bom-entry [designator value footprint quantity]
  {:designator designator :value value :footprint footprint :quantity quantity})

(defn generate-bom
  "Bill of materials from placed symbols. Symbols sharing the same
  `(value, library-ref)` are grouped and counted, sorted by combined
  designator string."
  [symbols]
  (let [groups (reduce
                (fn [groups sym]
                  (let [key [(:value sym) (:library-ref sym)]]
                    (-> groups
                        (update-in [key :quantity] (fnil inc 0))
                        (update-in [key :footprint] #(or % (:library-ref sym)))
                        (update-in [key :designators] (fnil conj []) (:designator sym)))))
                {} symbols)]
    (vec (sort-by :designator
                  (map (fn [[[value _] {:keys [footprint quantity designators]}]]
                         (bom-entry (str/join ", " designators) value footprint quantity))
                       groups)))))

(defn- find-net-name [nets sym-id pin-number]
  (or (some (fn [[_ net]] (when (some #(= % [sym-id pin-number]) (:pins net)) (:name net)))
            nets)
      "?"))

(defn- find-symbol [symbols sym-id]
  (some #(when (= (:id %) sym-id) %) symbols))

(defn- find-pin [symbols sym-id pin-number]
  (some #(when (= (:number %) pin-number) %) (:pins (find-symbol symbols sym-id))))

(defn- pin-label
  "Port/instance-pin label shared by `verilog-netlist` and `edif-netlist` for
  every per-pin connection point (Verilog named port `.<label>(net)`, EDIF
  `(portRef <label> ...)`): the pin's own `:name` (the schematic pin's
  label, e.g. \"A\"/\"K\"/\"VCC\") when present and non-blank, else the
  positional fallback `p<number>` for symbols whose pins carry only a bare
  number. This is the single place documenting that convention; callers
  should not re-derive it."
  [pin]
  (let [n (:name pin)]
    (if (and n (not (str/blank? (str n))))
      (str n)
      (str "p" (:number pin)))))

(defn spice-netlist
  "Render a SPICE netlist string for `symbols` connected via `nets`."
  [symbols nets]
  (str "* KAMI EDA — SPICE netlist\n"
       (apply str
              (for [sym symbols]
                (str (:designator sym) " "
                     (apply str (for [p (:pins sym)] (str (find-net-name nets (:id sym) (:number p)) " ")))
                     (:value sym) "\n")))
       ".end\n"))

(defn verilog-netlist
  "Render a Verilog gate-level netlist string for `symbols` connected via
  `nets`. Emits one `wire` declaration per distinct net name (deduped),
  then one module instantiation per symbol with a named port connection
  per pin — each pin resolved to its connected net via `find-net-name`,
  the same connectivity helper `spice-netlist` uses. Port labels follow
  the `pin-label` convention (pin `:name` else `p<number>`)."
  [symbols nets]
  (str "// KAMI EDA — Verilog gate-level netlist\n"
       "module top;\n"
       (apply str (for [net-name (->> (vals nets) (map :name) distinct sort)]
                    (str "  wire " net-name ";\n")))
       (apply str
              (for [sym symbols]
                (str "  " (:library-ref sym) " " (:designator sym) " (\n"
                     (str/join ",\n"
                               (for [p (:pins sym)]
                                 (str "    ." (pin-label p) "("
                                      (find-net-name nets (:id sym) (:number p)) ")")))
                     (when (seq (:pins sym)) "\n")
                     "  );\n")))
       "endmodule\n"))

(defn edif-netlist
  "Render an EDIF 2 0 0 netlist string for `symbols` connected via `nets`.
  Emits one `(instance ...)` per symbol and one `(net ...)` per net that
  has at least one connected pin, with real `(portRef ... (instanceRef
  ...))` connectivity pulled from each net's `:pins` (the same
  `sym-id`/pin-`:number` pairs `find-net-name` resolves for SPICE/Verilog)
  — not bare instance declarations with no port/net information. Port
  labels follow the `pin-label` convention (pin `:name` else `p<number>`)."
  [symbols nets]
  (str "(edif kami_eda\n"
       "  (edifVersion 2 0 0)\n"
       "  (edifLevel 0)\n"
       "  (keywordMap (keywordLevel 0))\n"
       "  (library kami_lib\n"
       "    (edifLevel 0)\n"
       "    (technology (numberDefinition))\n"
       "    (cell top\n"
       "      (cellType GENERIC)\n"
       "      (view netlist\n"
       "        (viewType NETLIST)\n"
       "        (interface)\n"
       "        (contents\n"
       (apply str
              (for [sym symbols]
                (str "          (instance " (:designator sym)
                     " (viewRef " (:library-ref sym)
                     " (cellRef " (:library-ref sym)
                     " (libraryRef kami_lib))))\n")))
       (apply str
              (for [[_ net] (sort-by first nets)
                    :when (seq (:pins net))]
                (str "          (net " (:name net) "\n"
                     "            (joined\n"
                     (str/join "\n"
                               (for [[sym-id pin-number] (:pins net)]
                                 (str "              (portRef "
                                      (pin-label (find-pin symbols sym-id pin-number))
                                      " (instanceRef " (:designator (find-symbol symbols sym-id)) "))")))
                     "))\n")))
       "        )))))\n"))

(defn export-netlist
  "Export a netlist in `format` (`:spice`/`:verilog-gate-level`/`:edif`).
  All three formats are fully implemented with real symbol/pin/net
  connectivity (resolved via `find-net-name`/`pin-label`), not stubs.
  Known limitations: every pin is a scalar 1-bit connection (no bus/vector
  nets or multi-bit ports), and everything flattens into a single
  top-level module/cell (no hierarchical sub-modules/sub-cells)."
  [format symbols nets]
  (case format
    :spice (spice-netlist symbols nets)
    :verilog-gate-level (verilog-netlist symbols nets)
    :edif (edif-netlist symbols nets)))
