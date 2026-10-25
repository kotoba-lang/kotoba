(ns dft.scan
  "Scan chain insertion — distributes flip-flops into scan chains for
  manufacturing test access. Restored from kami-dft's `scan` module
  (kami-engine/kami-dft/src/scan.rs, deleted PR #82).")

(defn config
  "A scan-chain-insertion config. `chain-count` is how many parallel chains
  to distribute flip-flops across."
  [{:keys [chain-count max-length clock-name scan-enable scan-in-prefix scan-out-prefix]
    :or {max-length 100 clock-name "clk" scan-enable "SE"
         scan-in-prefix "SI" scan-out-prefix "SO"}}]
  {:chain-count chain-count :max-length max-length :clock-name clock-name
   :scan-enable scan-enable :scan-in-prefix scan-in-prefix
   :scan-out-prefix scan-out-prefix})

(defn insert-scan-chains
  "Insert scan chains by round-robin distributing `flip-flops` (a seq of
  net-name strings) across `(:chain-count config)` chains, wiring
  scan-in/scan-out between consecutive cells in each chain. Returns a vector
  of scan-chain maps `{:id :cells :length :scan-in-port :scan-out-port}`."
  [flip-flops config]
  (let [chain-count (:chain-count config)]
    (if (or (zero? chain-count) (empty? flip-flops))
      []
      (let [grouped (reduce-kv (fn [acc i ff]
                                  (update acc (mod i chain-count) (fnil conj []) ff))
                                (vec (repeat chain-count []))
                                (vec flip-flops))]
        (vec (map-indexed
              (fn [chain-id ffs]
                (let [scan-in-port (str (:scan-in-prefix config) chain-id)
                      scan-out-port (str (:scan-out-prefix config) chain-id)
                      length (count ffs)
                      cells (vec (map-indexed
                                  (fn [pos ff-name]
                                    {:ff-name ff-name
                                     :scan-in (if (zero? pos)
                                                scan-in-port
                                                (str (nth ffs (dec pos)) "_so"))
                                     :scan-out (if (= pos (dec length))
                                                 scan-out-port
                                                 (str ff-name "_so"))
                                     :chain-id chain-id
                                     :position pos})
                                  ffs))]
                  {:id chain-id :cells cells :length length
                   :scan-in-port scan-in-port :scan-out-port scan-out-port}))
              grouped))))))

(defn scan-chain-stats
  "Aggregate statistics for a seq of scan chains: chain count, total FFs,
  max/min chain length (0 if `chains` is empty)."
  [chains]
  (let [lengths (map :length chains)]
    {:num-chains (count chains)
     :total-ffs (reduce + 0 lengths)
     :max-length (if (seq lengths) (apply max lengths) 0)
     :min-length (if (seq lengths) (apply min lengths) 0)}))
