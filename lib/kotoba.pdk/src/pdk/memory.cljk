(ns pdk.memory
  "Statistical memory compiler (SRAM/ROM/RegFile area+timing estimation).
  Restored from kami-pdk's `memory` module (deleted PR #82)."
  (:require [pdk.technology :as tech]))

(def memory-types #{:sram :rom :reg-file})

(defn- addr-bits
  "Number of address bits to enumerate `words` addresses (ceil(log2(words)),
  matching the original `32 - (words - 1).leading_zeros()` for u32)."
  [words]
  (if (<= words 1)
    1
    #?(:clj (- 32 (Integer/numberOfLeadingZeros (int (dec words))))
       :cljs (int (Math/ceil (/ (Math/log words) (Math/log 2)))))))

(defn compile-memory
  "Compile a memory spec `{:mem-type :words :bits :mux :banks}` into
  estimated area/timing/leakage/pins for technology node `tech-node`.
  Uses statistical models derived from published SRAM/ROM bitcell sizes
  scaled by technology node (reference: 6T SRAM ~0.05 µm² at N7)."
  [spec tech-node]
  (let [feat (double (tech/feature-nm tech-node))
        bitcell-area (case (:mem-type spec)
                       :sram (* 0.05 (/ feat 7.0) (/ feat 7.0))
                       :rom (* 0.02 (/ feat 7.0) (/ feat 7.0))
                       :reg-file (* 0.10 (/ feat 7.0) (/ feat 7.0)))
        total-bits (* (double (:words spec)) (:bits spec) (:banks spec))
        overhead (case (:mem-type spec) :sram 1.30 :rom 1.15 :reg-file 1.40)
        area-um2 (* total-bits bitcell-area overhead)
        log2-words (max 1.0 (/ (Math/log (:words spec)) (Math/log 2)))
        timing-scale (/ feat 7.0)
        read-time-ns (* (+ 0.2 (* 0.05 log2-words)) timing-scale)
        write-time-ns (* read-time-ns (case (:mem-type spec) :sram 1.1 :rom 0.0 :reg-file 0.9))
        leakage-per-bit-uw (* 1e-6 (/ feat 7.0))
        leakage-uw (* total-bits leakage-per-bit-uw)
        addr-pins (mapv #(str "A[" % "]") (range (addr-bits (:words spec))))
        data-pins (mapcat (fn [i] [(str "D[" i "]") (str "Q[" i "]")]) (range (:bits spec)))
        pins (vec (concat ["CLK" "CEN" "WEN"] addr-pins data-pins))
        type-prefix (case (:mem-type spec) :sram "SRAM" :rom "ROM" :reg-file "RF")
        name (str type-prefix "_" (:words spec) "x" (:bits spec) "m" (:mux spec) "b" (:banks spec))]
    {:name name :area-um2 area-um2 :read-time-ns read-time-ns
     :write-time-ns write-time-ns :leakage-uw leakage-uw :pins pins}))
