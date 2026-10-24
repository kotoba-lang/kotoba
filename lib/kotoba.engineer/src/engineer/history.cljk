(ns engineer.history
  "Command-pattern undo/redo stack. Restored from kami-eng-core's `history`
  module (deleted PR #82). Pure data — `push`/`undo`/`redo` all return the
  updated history map; the caller threads it. Entry `:data` is an opaque
  byte/EDN payload the caller controls (the original used `Vec<u8>`; here
  any value works since CLJC has no byte-array requirement).")

(defn history
  "A fresh, empty history (no entries, next id = 1)."
  []
  {:undo-stack [] :redo-stack [] :next-id 1})

(defn push
  "Push a new entry `{:action action :data data}` onto the undo stack,
  clearing the redo stack (a new action invalidates any pending redo).
  Returns `[id history']`."
  [history action data]
  (let [id (:next-id history)
        entry {:id id :action action :timestamp 0 :data data}]
    [id (-> history
            (update :undo-stack conj entry)
            (assoc :redo-stack [])
            (update :next-id inc))]))

(defn undo
  "Pop the most recent undo entry onto the redo stack. Returns
  `[entry history']`, or `[nil history]` unchanged if nothing to undo."
  [history]
  (if-let [entry (peek (:undo-stack history))]
    [entry (-> history
               (update :undo-stack pop)
               (update :redo-stack conj entry))]
    [nil history]))

(defn redo
  "Pop the most recent redo entry back onto the undo stack. Returns
  `[entry history']`, or `[nil history]` unchanged if nothing to redo."
  [history]
  (if-let [entry (peek (:redo-stack history))]
    [entry (-> history
               (update :redo-stack pop)
               (update :undo-stack conj entry))]
    [nil history]))

(defn can-undo? [history] (boolean (seq (:undo-stack history))))
(defn can-redo? [history] (boolean (seq (:redo-stack history))))
(defn stack [history] (:undo-stack history))
