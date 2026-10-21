(ns kotoba.lang.lsp
  "An LSP-style document model as pure data for the kotoba foundational stdlib.
  Layer 4 (tooling).

  Positions are 0-based {:line :character} (matching the LSP wire format). A
  range is {:start :end}. A diagnostic is {:range :severity :source :message}.
  No JSON-RPC transport is baked in — a kotoba cell gets the wire from the host;
  this lib owns the data contract. Pure functions, no host.

  Zero third-party runtime deps; .cljc (JVM / SCI / CLJS / GraalVM / kotoba-WASM)."
  (:require [kotoba.lang.text :as str]))

(def severities #{:error :warning :information :hint})
(def severity-rank {:error 1 :warning 2 :information 3 :hint 4})

(defn position
  "Construct a 0-based position."
  [line character] {:line line :character character})

(defn range
  "Construct a range from two positions."
  [start end] {:start start :end end})

(defn text-document
  "Build a line-indexed document from `source`. Returns a map with `:source`
  and `:line-starts` (a vector of the char-offset at which each line begins).
  Trailing newlines do not create a phantom line (matches editor behavior)."
  [source]
  (let [lines (if (str/ends-with? source "\n")
                (drop-last (str/split-lines source))
                (str/split-lines source))]
    {:source source
     :line-count (count lines)
     :line-starts
     (loop [i 0 acc [0]]
       (if (>= i (dec (count lines)))
         (vec acc)
         (recur (inc i) (conj acc (+ (peek acc) (count (nth lines i)) 1)))))}))

(defn position->offset
  "Convert a position to a character offset in the source."
  [doc pos]
  (let [line (:line pos)
        starts (:line-starts doc)]
    (if (>= line (count starts))
      (count (:source doc))
      (let [line-start (nth starts line)]
        (min (+ line-start (:character pos))
             (count (:source doc)))))))

(defn offset->position
  "Convert a character offset to a position."
  [doc offset]
  (let [starts (:line-starts doc)
        ;; largest line whose start is <= offset (linear — line counts are small)
        line (loop [l 0]
               (if (and (< (inc l) (count starts))
                        (<= (nth starts (inc l)) offset))
                 (recur (inc l))
                 l))]
    {:line line :character (- offset (nth starts line))}))

(defn- pos>= [a b]
  (or (> (:line a) (:line b))
      (and (= (:line a) (:line b))
           (>= (:character a) (:character b)))))

(defn- pos< [a b]
  (or (< (:line a) (:line b))
      (and (= (:line a) (:line b))
           (< (:character a) (:character b)))))

(defn within-range?
  "True iff `pos` lies within `r` (inclusive start, exclusive end, LSP style)."
  [r pos]
  (let [s (:start r) e (:end r)]
    (and (pos>= pos s) (pos< pos e))))

(defn diagnostic
  "Construct a diagnostic. `severity` is one of #{:error :warning :information :hint}."
  [r severity source message]
  (when-not (contains? severities severity)
    (throw (ex-info "lsp/diagnostic: invalid severity" {:severity severity})))
  {:range r :severity severity :source source :message message})

(defn diagnostics-by-severity
  "Sort diagnostics most-severe first."
  [diags]
  (sort-by #(get severity-rank (:severity %)) diags))
