(ns kotoba.strfmt
  "printf-style string formatting that produces the same text on every host.

  Measured 2026-08-20 across the compiler stack: 57 `(format ...)` call sites
  with no owner, and the directive mix is not what a general printf would
  assume --

      %x 39 · %s 15 · %d 4 · %f 3

  -- because this stack emits opcodes, offsets and digests. Hex is the job.

  **`clojure.core/format` does not exist on ClojureScript**, which is the
  whole reason a call site cannot simply use it: `format` is JVM-only
  (`String/format`), so every one of those 57 sites pins its file to the JVM.
  `goog.string/format` is close but not identical, and \"close\" in a
  digest-producing path is a defect that appears only in output nobody diffs.

  **This is deliberately not a full printf.** It implements the directives
  that are actually used, with width and zero-padding, and REFUSES anything
  else rather than passing it through. A formatter that silently emits an
  unrecognised directive verbatim turns a typo into output.

  `kotoba-lang/fmt` is a different thing entirely -- a deterministic EDN
  source formatter, the rustfmt equivalent. This is string formatting."
  (:refer-clojure :exclude [format])
  (:require [kotoba.lang.text :as str]
            [kotoba.i64 :as i64]))

(defn- pad [s width zero? left?]
  (let [n (- width (count s))]
    (if (pos? n)
      (let [fill (apply str (repeat n (if zero? "0" " ")))]
        (cond
          left? (str s (apply str (repeat n " ")))
          ;; a zero-padded negative keeps its sign in front of the zeros
          (and zero? (str/starts-with? s "-")) (str "-" fill (subs s 1))
          :else (str fill s)))
      s)))

(defn- hex [v]
  ;; i64 rather than the host: a hex rendering of a 64-bit value is exactly
  ;; where a JS double silently loses precision above 2^53.
  (let [n (i64/->i64 v)]
    (if (i64/neg? n)
      ;; two's-complement, so 0xff..ff rather than "-1"
      #?(:clj (Long/toHexString (long n))
         :cljs (.toString (js/BigInt.asUintN 64 n) 16))
      #?(:clj (Long/toHexString (long n))
         :cljs (.toString n 16)))))

(defn- render [directive flags width value]
  (let [zero? (str/includes? flags "0")
        left? (str/includes? flags "-")
        s (case directive
            \s (str value)
            \d (i64/->string (i64/->i64 value))
            \x (hex value)
            \X (str/upper (hex value))
            \f #?(:clj (String/format "%f" (into-array Object [(double value)]))
                  :cljs (.toFixed (js/Number value) 6))
            (throw (ex-info "unsupported format directive"
                            {:directive (str "%" directive)
                             :supported ["%s" "%d" "%x" "%X" "%f" "%%"]})))]
    (pad s (or width 0) zero? left?)))

(defn format
  "Format FMT with ARGS. Supports `%s %d %x %X %f %%`, optional `-` and `0`
  flags, and an optional width. Anything else throws rather than passing
  through."
  [fmt & args]
  (let [args (vec args)
        i (volatile! 0)]
    (str/replace fmt
                 #"%([-0]*)(\d*)([a-zA-Z%])"
                 (fn [[whole flags width d]]
                   (let [d (first d)]
                     (if (= d \%)
                       "%"
                       (let [v (get args @i)]
                         (when (>= @i (count args))
                           (throw (ex-info "format: not enough arguments"
                                           {:fmt fmt :directive whole
                                            :given (count args)})))
                         (vswap! i inc)
                         (render d flags
                                 (when (seq width)
                                   #?(:clj (Integer/parseInt width)
                                      :cljs (js/parseInt width 10)))
                                 v))))))))
