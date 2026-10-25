(ns uvm.sequence
  "UVM sequence / sequence-item model — mirrors uvm_sequence_item (the
  transaction) and uvm_sequence (an ordered stream of transactions
  driven by a sequencer into a driver). Both are plain data here:
  there is no uvm_sequencer arbitration, response FIFO, or
  virtual-sequence class layering — just the item/sequence shape and
  the drive loop itself.")

(defn sequence-item
  "A sequence-item (transaction) is just a plain map tagged
  :kind :sequence-item, e.g. `(sequence-item {:addr 0x10 :data 0xff})`."
  [fields]
  (merge {:kind :sequence-item} fields))

(defn uvm-sequence
  "A sequence is a named, ordered collection of sequence-items:
  `{:name name :items [item ...]}`."
  [name items]
  {:name name :items (vec items)})

(defn append-item
  "Return `seq-map` with `item` appended to its :items — the way a
  sequence body incrementally builds up the transactions it will send,
  e.g. from a `uvm_do` macro loop."
  [seq-map item]
  (update seq-map :items conj item))

(defn concat-sequences
  "Compose several sequences into one, concatenating their :items in
  order under `name` — the same idea as a virtual sequence that runs
  a fixed order of sub-sequences end to end on a single sequencer."
  [name seqs]
  (uvm-sequence name (mapcat :items seqs)))

(defn apply-sequence
  "Drive `seq-map` through `driver-fn`: call `driver-fn` with each
  item of `(:items seq-map)` in order (mirroring a sequencer handing
  items to `uvm_driver::run_phase` one at a time via
  get_next_item/item_done) and return the vector of driver-fn's
  responses in the same order. `driver-fn` is `(fn [item] response)`."
  [seq-map driver-fn]
  (mapv driver-fn (:items seq-map)))

(defn apply-sequence-indexed
  "Like `apply-sequence`, but `driver-fn` also receives the
  zero-based position of the item within the sequence:
  `(fn [item index] response)`. Useful when a driver or scoreboard
  needs the sequence number of the transaction it is handling."
  [seq-map driver-fn]
  (vec (map-indexed (fn [i item] (driver-fn item i)) (:items seq-map))))
