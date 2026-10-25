(ns vhdl.signal
  "Signal declaration model (IEEE 1076 §6.4.2.4): {:name :type :init-value}.
  Supports std_logic, std_logic_vector(N downto 0), integer, and boolean."
  (:require [vhdl.entity :as entity]))

(defn vector-type?
  [type-str]
  (boolean (re-find #"(?i)std_logic_vector" type-str)))

(defn default-value
  "Return the VHDL default initial value for a given type string, mirroring
  IEEE 1076's default-initialization rule for a signal with no explicit
  initial value expression: the leftmost (here, first / \"low\") value of
  the type. std_logic (and each element of std_logic_vector) defaults to
  the IEEE 1164 'U' (uninitialized) value, integer defaults to 0, and
  boolean defaults to false."
  [type-str]
  (cond
    (vector-type? type-str)
    (apply str (repeat (entity/bus-width type-str) \U))

    (re-find #"(?i)std_logic" type-str) "U"
    (re-find #"(?i)integer" type-str) 0
    (re-find #"(?i)boolean" type-str) false
    :else nil))

(defn make-signal
  "Build a signal declaration map, resolving :init-value from `type-str`
  via `default-value` when `init-value` is not supplied explicitly."
  ([name type-str] (make-signal name type-str (default-value type-str)))
  ([name type-str init-value]
   {:name name :type type-str :init-value init-value}))
