(ns pcb.erc
  "Electrical Rule Check (ERC) for schematic validation. Restored from
  kami-eda's `erc` module (deleted PR #82). Violations are plain maps
  matching kotoba-lang/engineer's `engineer.drc` violation shape."
  (:require [pcb.schematic :as schematic]))

(defn- v-distance [[ax ay] [bx by]] (Math/sqrt (+ (Math/pow (- bx ax) 2) (Math/pow (- by ay) 2))))
(defn- v+ [[ax ay] [bx by]] [(+ ax bx) (+ ay by)])

(defn- pin-of [sch sym-id pin-num pin-type-pred]
  (some (fn [sym]
          (when (= (:id sym) sym-id)
            (some #(when (and (= (:number %) pin-num) (pin-type-pred (:pin-type %))) %) (:pins sym))))
        (:symbols sch)))

;; ERC-001: unconnected pins
(defn- check-unconnected-pins [sch]
  (let [eps 0.01]
    (for [sym (:symbols sch)
          p (:pins sym)
          :when (not= (:pin-type p) :not-connected)
          :let [abs-pos (v+ (:position sym) (:position p))
                connected (some (fn [w] (or (< (v-distance abs-pos (:start w)) eps)
                                             (< (v-distance abs-pos (:end w)) eps)))
                                 (:wires sch))]
          :when (not connected)]
      {:rule-id "ERC_UNCONNECTED_PIN" :severity :warning
       :message (str "Pin " (:number p) " (" (:name p) ") of " (:designator sym) " is unconnected")
       :entity-ids [(:id sym)] :location abs-pos})))

;; ERC-002: output-to-output conflict
(defn- check-output-to-output [sch]
  (let [netlist (schematic/generate-netlist sch)]
    (for [[_ net] netlist
          :let [outputs (filter (fn [[sym-id pin-num]] (pin-of sch sym-id pin-num #(= % :output))) (:pins net))]
          :when (> (count outputs) 1)]
      {:rule-id "ERC_OUTPUT_CONFLICT" :severity :error
       :message (str "Net '" (:name net) "' has " (count outputs) " output drivers — potential contention")
       :entity-ids (mapv first outputs) :location nil})))

;; ERC-003: power net with no driving source
(defn- check-power-undriven [sch]
  (let [netlist (schematic/generate-netlist sch)]
    (for [[_ net] netlist
          :let [has-power-pin (some (fn [[sym-id pin-num]] (pin-of sch sym-id pin-num #(= % :power))) (:pins net))]
          :when has-power-pin
          :let [has-driver (some (fn [[sym-id pin-num]] (pin-of sch sym-id pin-num #(or (= % :output) (= % :power))))
                                  (:pins net))]
          :when (not has-driver)]
      {:rule-id "ERC_POWER_UNDRIVEN" :severity :error
       :message (str "Power net '" (:name net) "' has no driving source")
       :entity-ids [] :location nil})))

;; ERC-004: single-pin nets
(defn- check-net-single-pin [sch]
  (let [netlist (schematic/generate-netlist sch)]
    (for [[_ net] netlist :when (= (count (:pins net)) 1)]
      {:rule-id "ERC_NET_SINGLE_PIN" :severity :warning
       :message (str "Net '" (:name net) "' has only one pin connected")
       :entity-ids (mapv first (:pins net)) :location nil})))

;; ERC-005: duplicate reference designators
(defn- check-duplicate-designator [sch]
  (let [by-desig (group-by :designator (:symbols sch))]
    (for [[desig syms] by-desig :when (> (count syms) 1)]
      {:rule-id "ERC_DUPLICATE_DESIGNATOR" :severity :error
       :message (str "Designator '" desig "' used by " (count syms) " symbols")
       :entity-ids (mapv :id syms) :location nil})))

(defn run-erc
  "Run all ERC rules on `sch` and return a vector of violations."
  [sch]
  (vec (concat (check-unconnected-pins sch)
               (check-output-to-output sch)
               (check-power-undriven sch)
               (check-net-single-pin sch)
               (check-duplicate-designator sch))))
