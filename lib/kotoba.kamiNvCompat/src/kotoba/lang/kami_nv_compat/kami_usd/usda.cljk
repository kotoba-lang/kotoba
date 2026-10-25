(ns kotoba.lang.kami-nv-compat.kami-usd.usda
  "kami-usd — clean-room USDA (ASCII USD) reader. Portable .cljc port of
  src/kami-usd/usda.ts. Wave 30.

  The canonical KAMI implementation behind nv-compat/omni-usd. Pixar's USD
  is the Universal Scene Description format; this module parses the
  documented ASCII (.usda) crate grammar for the geometry subset KAMI needs
  (UsdGeomMesh / Xform prims + their attributes) and exposes a small,
  pxr.Usd-shaped tree. Binary .usdc / .usdz are a later kami-usd milestone.

  Clean-room: this is a from-spec re-implementation of the USDA text
  grammar. No USD / OpenUSD / tinyusdz source, headers, or binaries are
  used. The parser is a small recursive-descent scanner over the public
  crate syntax.

  ADR-2605261800 SD6 / D10.4 kami-usd.")

;; ── value model ──────────────────────────────────────────────────────────
;;
;; UsdValue      number | string | boolean | [UsdValue ...]
;; UsdAttribute  {:type-name :name :value :uniform}
;; UsdPrimNode   {:specifier :type-name :name :path :attributes {name->UsdAttribute}
;;                :children [UsdPrimNode ...]}

;; ── scanner (an atom-held cursor over an immutable string) ──────────────

(defn- make-scanner [s] {:s s :pos (atom 0)})
(defn- sc-len [scanner] (count (:s scanner)))

(defn- sc-char-at
  "Character at index i as a 1-char string, or \"\" past the end."
  [scanner i]
  (if (< i (sc-len scanner)) (subs (:s scanner) i (inc i)) ""))

(defn- sc-skip!
  "Skip whitespace and # line comments."
  [scanner]
  (loop []
    (let [c (sc-char-at scanner @(:pos scanner))]
      (cond
        (contains? #{" " "\t" "\r" "\n"} c)
        (do (swap! (:pos scanner) inc) (recur))

        (= c "#")
        (do
          (loop []
            (when (and (< @(:pos scanner) (sc-len scanner))
                       (not= (sc-char-at scanner @(:pos scanner)) "\n"))
              (swap! (:pos scanner) inc)
              (recur)))
          (recur))

        :else nil))))

(defn- sc-eof?
  [scanner]
  (sc-skip! scanner)
  (>= @(:pos scanner) (sc-len scanner)))

(defn- sc-peek
  "Skip whitespace/comments, return the next char (1-char string) or \"\"."
  [scanner]
  (sc-skip! scanner)
  (sc-char-at scanner @(:pos scanner)))

(defn- sc-take!
  "Consume the next char regardless of whitespace handling."
  [scanner]
  (let [c (sc-char-at scanner @(:pos scanner))]
    (swap! (:pos scanner) inc)
    c))

(defn- sc-expect!
  [scanner ch]
  (sc-skip! scanner)
  (let [c (sc-char-at scanner @(:pos scanner))]
    (when (not= c ch)
      (throw (ex-info (str "USDA parse: expected '" ch "' at offset " @(:pos scanner)
                            ", got '" (if (= c "") "<eof>" c) "'")
                       {:offset @(:pos scanner) :expected ch :got c})))
    (swap! (:pos scanner) inc)))

(defn- sc-try-consume!
  [scanner ch]
  (sc-skip! scanner)
  (if (= (sc-char-at scanner @(:pos scanner)) ch)
    (do (swap! (:pos scanner) inc) true)
    false))

(defn- char-range? [c lo hi] (and (<= 0 (compare c lo)) (<= (compare c hi) 0)))

(defn- token-char?
  "identifiers, base type names, namespaced attribute names (with `:`),
  numbers, signs, dots. `[`/`]` are NOT token chars (they delimit arrays
  and the `[]` type suffix is read separately)."
  [c]
  (or (char-range? c "a" "z") (char-range? c "A" "Z") (char-range? c "0" "9")
      (contains? #{"_" ":" "." "-" "+" "e" "E"} c)))

(defn- sc-token!
  [scanner]
  (sc-skip! scanner)
  (let [start @(:pos scanner)]
    (loop []
      (when (and (< @(:pos scanner) (sc-len scanner))
                 (token-char? (sc-char-at scanner @(:pos scanner))))
        (swap! (:pos scanner) inc)
        (recur)))
    (subs (:s scanner) start @(:pos scanner))))

(defn- sc-array-suffix!
  "An optional empty `[]` array-type suffix, or \"\" if the next token is not
  one. Leaves a non-empty `[ ... ]` (an array value) untouched."
  [scanner]
  (if (= (sc-peek scanner) "[")
    (let [save @(:pos scanner)]
      (sc-expect! scanner "[")
      (if (sc-try-consume! scanner "]")
        "[]"
        (do (reset! (:pos scanner) save) "")))
    ""))

(defn- sc-type-token!
  [scanner]
  (str (sc-token! scanner) (sc-array-suffix! scanner)))

(defn- sc-quoted!
  "A double- or single-quoted string."
  [scanner]
  (sc-skip! scanner)
  (let [q (sc-char-at scanner @(:pos scanner))]
    (when-not (contains? #{"\"" "'"} q)
      (throw (ex-info (str "USDA parse: expected string at offset " @(:pos scanner)) {})))
    (swap! (:pos scanner) inc)
    (let [out (loop [acc ""]
                (let [c (sc-char-at scanner @(:pos scanner))]
                  (if (or (>= @(:pos scanner) (sc-len scanner)) (= c q))
                    acc
                    (if (= c "\\")
                      (do (swap! (:pos scanner) inc)
                          (let [escaped (sc-char-at scanner @(:pos scanner))]
                            (swap! (:pos scanner) inc)
                            (recur (str acc escaped))))
                      (do (swap! (:pos scanner) inc)
                          (recur (str acc c)))))))]
      (swap! (:pos scanner) inc) ; closing quote
      out)))

;; ── value parsing ────────────────────────────────────────────────────────

(defn- parse-scalar
  [raw]
  (cond
    (= raw "true") true
    (= raw "false") false
    (pos? (count raw))
    (let [n #?(:clj (try (Double/parseDouble raw) (catch Exception _ nil))
               :cljs (let [x (js/parseFloat raw)] (when-not (js/isNaN x) x)))]
      (if (some? n) n raw))
    :else raw))

(declare parse-value)

(defn- parse-array!
  [scanner]
  (sc-expect! scanner "[")
  (if (sc-try-consume! scanner "]")
    []
    (loop [out []]
      (let [out2 (conj out (parse-value scanner))]
        (if (sc-try-consume! scanner ",")
          (if (= (sc-peek scanner) "]")
            (do (sc-expect! scanner "]") out2)
            (recur out2))
          (do (sc-expect! scanner "]") out2))))))

(defn- parse-tuple!
  [scanner]
  (sc-expect! scanner "(")
  (if (sc-try-consume! scanner ")")
    []
    (loop [out []]
      (let [out2 (conj out (parse-value scanner))]
        (if (sc-try-consume! scanner ",")
          (if (= (sc-peek scanner) ")")
            (do (sc-expect! scanner ")") out2)
            (recur out2))
          (do (sc-expect! scanner ")") out2))))))

(defn- parse-value
  [scanner]
  (let [c (sc-peek scanner)]
    (cond
      (= c "[") (parse-array! scanner)
      (= c "(") (parse-tuple! scanner)
      (contains? #{"\"" "'"} c) (sc-quoted! scanner)
      :else (parse-scalar (sc-token! scanner)))))

;; ── prim / attribute parsing ─────────────────────────────────────────────

(def ^:private specifiers #{"def" "over" "class"})

(defn- attr-type-start?
  "Attribute type tokens are lower-cased schema value types; prim specifiers
  are def/over/class (handled separately). Anything else starting a line in
  a prim body that is not a specifier is an attribute declaration."
  [tok]
  (and (pos? (count tok)) (not (contains? specifiers tok))))

(defn- skip-balanced!
  [scanner open close]
  (sc-expect! scanner open)
  (loop [depth 1]
    (when (pos? depth)
      (when (sc-eof? scanner)
        (throw (ex-info "USDA parse: unbalanced metadata block" {})))
      (let [c (sc-take! scanner)]
        (recur (cond (= c open) (inc depth) (= c close) (dec depth) :else depth))))))

(declare parse-prim!)

(defn- parse-prim-body!
  [scanner node-atom]
  (sc-expect! scanner "{")
  (loop []
    (if (sc-try-consume! scanner "}")
      nil
      (do
        (when (sc-eof? scanner)
          (throw (ex-info "USDA parse: unexpected EOF inside prim body" {})))
        (let [tok (sc-token! scanner)]
          (if (contains? specifiers tok)
            (do (swap! node-atom update :children conj
                       (parse-prim! scanner tok (:path @node-atom)))
                (recur))
            ;; Attribute: [custom] [uniform] <type>[\[\]] <name> [= value] [( meta )].
            (let [[type-name uniform?]
                  (cond
                    (= tok "uniform") [(sc-type-token! scanner) true]
                    (= tok "custom")
                    (let [t1 (sc-type-token! scanner)]
                      (if (= t1 "uniform")
                        [(sc-type-token! scanner) true]
                        [t1 false]))
                    :else [(str tok (sc-array-suffix! scanner)) false])]
              (when-not (attr-type-start? type-name)
                (throw (ex-info (str "USDA parse: malformed attribute near '" type-name
                                      "' (path " (:path @node-atom) ")")
                                 {})))
              (let [attr-name (sc-token! scanner)
                    value (when (sc-try-consume! scanner "=") (parse-value scanner))]
                ;; Optional attribute metadata block ( ... ) — skipped.
                (when (= (sc-peek scanner) "(") (skip-balanced! scanner "(" ")"))
                (swap! node-atom assoc-in [:attributes attr-name]
                       {:type-name type-name :name attr-name :value value :uniform uniform?})
                (recur)))))))))

(defn- parse-prim!
  [scanner specifier parent-path]
  (let [nxt (sc-peek scanner)
        [type-name prim-name] (if (contains? #{"\"" "'"} nxt)
                                 ["" (sc-quoted! scanner)]
                                 (let [t (sc-token! scanner)] [t (sc-quoted! scanner)]))]
    ;; Optional prim metadata ( ... ).
    (when (= (sc-peek scanner) "(") (skip-balanced! scanner "(" ")"))
    (let [path (if (= parent-path "/") (str "/" prim-name) (str parent-path "/" prim-name))
          node-atom (atom {:specifier specifier :type-name type-name :name prim-name :path path
                            :attributes {} :children []})]
      (parse-prim-body! scanner node-atom)
      @node-atom)))

(defn parse-usda
  "Parse a USDA document into a list of root prims. An optional leading
  `#usda 1.0` header line and stage metadata `( ... )` are tolerated (the
  header line is skipped as a # comment; metadata is a balanced-paren
  block skipped wholesale)."
  [text]
  (let [scanner (make-scanner text)]
    (when (= (sc-peek scanner) "(") (skip-balanced! scanner "(" ")"))
    (loop [roots []]
      (if (sc-eof? scanner)
        roots
        (let [tok (sc-token! scanner)]
          (if (= tok "")
            roots
            (do
              (when-not (contains? specifiers tok)
                (throw (ex-info (str "USDA parse: expected def/over/class at top level, got '" tok "'") {})))
              (recur (conj roots (parse-prim! scanner tok "/"))))))))))
