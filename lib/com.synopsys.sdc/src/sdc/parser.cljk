(ns sdc.parser
  "Simplified TCL-style tokenizer/parser for a subset of SDC (Synopsys
  Design Constraints) commands: create_clock, set_input_delay,
  set_output_delay, set_false_path, set_multicycle_path. Part of the
  kotoba-lang org-<vendor>-<spec> reverse-domain naming initiative
  (ADR-2607072500, com-junkawasaki/root)."
  (:require [kotoba.lang.text :as str]
            [sdc.clock :as clock]
            [sdc.io-delay :as io-delay]
            [sdc.path-exception :as path-exception]))

;; ---------------------------------------------------------------------------
;; Tokenizer -- `{...}` and `[...]` are each collapsed into a single token
;; so their contents are never split on internal whitespace.
;; ---------------------------------------------------------------------------

#?(:clj
   (defn- ws? [c] (Character/isWhitespace ^char c))
   :cljs
   (defn- ws? [c] (re-matches #"\s" (str c))))

(defn- find-close
  "Index of the `close` char matching the `open` char at `start` in `s`,
  honoring nesting of the same bracket pair. Returns (count s) if the
  group is unterminated."
  [s start open close]
  (let [n (count s)]
    (loop [i (inc start) depth 1]
      (cond
        (>= i n) n
        (= (get s i) open) (recur (inc i) (inc depth))
        (= (get s i) close) (if (= depth 1) i (recur (inc i) (dec depth)))
        :else (recur (inc i) depth)))))

(defn- grouped-token [line i open close]
  (let [n (count line)
        stop (min n (inc (find-close line i open close)))]
    [stop (subs line i stop)]))

(defn tokenize
  "Tokenize a single SDC command line into a vector of strings. A `{...}`
  or `[...]` group is emitted as one token, whitespace elsewhere splits."
  [line]
  (let [n (count line)]
    (loop [i 0 tokens []]
      (cond
        (>= i n) tokens
        (ws? (get line i)) (recur (inc i) tokens)
        (= (get line i) \{) (let [[stop tok] (grouped-token line i \{ \})]
                              (recur stop (conj tokens tok)))
        (= (get line i) \[) (let [[stop tok] (grouped-token line i \[ \])]
                              (recur stop (conj tokens tok)))
        :else
        (let [end (loop [j i] (if (or (>= j n) (ws? (get line j))) j (recur (inc j))))]
          (recur end (conj tokens (subs line i end))))))))

;; ---------------------------------------------------------------------------
;; Flag parsing -- `-flag value` pairs into a map, `-rise`/`-fall` boolean
;; switches, `[get_ports ...]`/`[get_pins ...]` groups as the command's
;; target, everything else as positional (e.g. set_multicycle_path's
;; leading multiplier).
;; ---------------------------------------------------------------------------

(def ^:private boolean-switches #{"-rise" "-fall"})

(defn- parse-args [tokens]
  (loop [ts tokens flags {} switches #{} target nil positional []]
    (if (empty? ts)
      {:flags flags :switches switches :target target :positional positional}
      (let [t (first ts)]
        (cond
          (contains? boolean-switches t)
          (recur (rest ts) flags (conj switches t) target positional)

          (str/starts-with? t "-")
          (recur (nnext ts) (assoc flags t (second ts)) switches target positional)

          (str/starts-with? t "[")
          (recur (rest ts) flags switches t positional)

          :else
          (recur (rest ts) flags switches target (conj positional t)))))))

(defn- parse-num [s]
  (when s
    #?(:clj (Double/parseDouble (str/trim s))
       :cljs (js/parseFloat s))))

(defn- parse-int [s]
  (when s
    #?(:clj (Integer/parseInt (str/trim s))
       :cljs (js/parseInt s 10))))

(defn- strip-ends [s] (subs s 1 (dec (count s))))

(defn- parse-waveform [s]
  (mapv parse-num (str/split (str/trim (strip-ends s)) #"\s+")))

(defn- ref-name
  "\"[get_ports clk]\" / \"[get_pins reg1/D]\" -> \"clk\" / \"reg1/D\" (the
  last whitespace-separated word inside the brackets)."
  [s]
  (last (str/split (str/trim (strip-ends s)) #"\s+")))

(defn- resolve-ref [s]
  (when s (if (str/starts-with? s "[") (ref-name s) s)))

;; ---------------------------------------------------------------------------
;; Command builders
;; ---------------------------------------------------------------------------

(defn- build-create-clock [{:keys [flags target]}]
  (clock/create-clock
    {:name (get flags "-name")
     :period (parse-num (get flags "-period"))
     :waveform (when-let [w (get flags "-waveform")] (parse-waveform w))
     :source-port (resolve-ref target)}))

(defn- build-io-delay [ctor {:keys [flags switches target]}]
  (ctor {:port (resolve-ref target)
         :clock (get flags "-clock")
         :delay (parse-num (or (get flags "-max") (get flags "-min")))
         :max? (contains? flags "-max")
         :min? (contains? flags "-min")
         :rise? (contains? switches "-rise")
         :fall? (contains? switches "-fall")}))

(defn- build-false-path [{:keys [flags]}]
  (path-exception/false-path
    {:from (resolve-ref (get flags "-from"))
     :to (resolve-ref (get flags "-to"))}))

(defn- build-multicycle-path [{:keys [flags positional]}]
  (path-exception/multicycle-path
    {:from (resolve-ref (get flags "-from"))
     :to (resolve-ref (get flags "-to"))
     :multiplier (if-let [p (first positional)] (parse-int p) 1)}))

(defn parse-command
  "Parse a single SDC command line, e.g. \"create_clock -period 10 -name
  CLK -waveform {0 5} [get_ports clk]\", into the corresponding command
  data map (see sdc.clock/sdc.io-delay/sdc.path-exception). Returns nil
  for blank input or an unrecognized command."
  [line]
  (let [tokens (tokenize (str/trim line))]
    (when (seq tokens)
      (let [args (parse-args (rest tokens))]
        (case (first tokens)
          "create_clock" (build-create-clock args)
          "set_input_delay" (build-io-delay io-delay/input-delay args)
          "set_output_delay" (build-io-delay io-delay/output-delay args)
          "set_false_path" (build-false-path args)
          "set_multicycle_path" (build-multicycle-path args)
          nil)))))

(defn parse-script
  "Parse a multi-line SDC script string into a vector of parsed command
  maps, skipping blank lines and `#`-prefixed comment lines."
  [script]
  (into []
        (comp (map str/trim)
              (remove str/blank?)
              (remove #(str/starts-with? % "#"))
              (keep parse-command))
        (str/split-lines script)))
