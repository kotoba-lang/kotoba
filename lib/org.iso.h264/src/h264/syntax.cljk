(ns h264.syntax
  "Generic, table-driven reader for ITU-T H.264 / ISO/IEC 14496-10 §7.3-style
   *syntax tables*.

   The premise this namespace tests: a §7.3 syntax table is literally a
   table. The standard prints rows of (element name, descriptor, presence
   condition) — `u(n)`, `ue(v)`, `se(v)`, `f(n)`, `ae(v)` — plus `if`/`for`
   scaffolding. If those rows are EDN *data*, one reader interprets them and
   a new bitstream structure costs one EDN file rather than one hand-written
   parser: O(N) data, O(1) code.

   The boundary this namespace refuses to cross is the standard's own:
   §7.3 is SYNTAX (which bits are present, in what order, read how);
   §7.4 is SEMANTICS (what the values mean, what is derived from them).
   This reader implements §7.3 only. It returns a map keyed by the spec's
   own syntax-element names, with the reader positioned immediately after
   the last row. Everything in §7.4 — SubWidthC, CropUnitX, the width/height
   derivation, `pic_init_qp_minus26 + 26`, the Table 7-6 slice_type mod-5
   collapse — stays ordinary code in the calling namespace. Pretending
   otherwise would make the table a lie; see docs/adr for the measurement.

   Pure cljc, no ambient authority: the table, the escape map and the byte
   vector are all arguments.

   ## Row grammar

     [:u  n-expr name]  unsigned n bits, MSB first          (u(n))
     [:f  n-expr name]  fixed-pattern n bits (read as u(n))  (f(n))
     [:ue name]         unsigned Exp-Golomb                  (ue(v))
     [:se name]         signed Exp-Golomb                    (se(v))
     [:infer name expr] §7.4 \"when not present, infer\" — reads no bits
     [:when cond-expr then-rows]
     [:when cond-expr then-rows else-rows]
     [:for  count-expr rows]     ; loop index available to exprs as [:idx]
     [:escape escape-key & arg-exprs]
                        ; hand off to (escapes escape-key), called as
                        ; (f reader vals evaluated-args) -> vals'. The
                        ; honest exit door: sub-structures whose bodies are
                        ; NOT descriptor rows (§7.3.2.1.1.1 scaling_list's
                        ; lastScale/nextScale state machine is the canonical
                        ; case) go here rather than being faked as
                        ; declarative.
     [:unsupported reason-keyword info-expr?]
                        ; reached => throw. Used for descriptors this reader
                        ; cannot interpret at all (see `ae(v)` below).

   `name` is either a keyword (scalar) or `[:vec kw]` (conj into a vector
   under kw — the spec's `element[ i ]` array form).

   ## Expression grammar (closed; evaluated over already-read elements)

     <int> <bool> <set> <keyword>    literals
     [:var k]                        value of a previously read element, or
                                     of a `context` element seeded from a
                                     referenced structure (SPS -> slice)
                                     (THROWS if unread — a table that reads
                                     an element out of order fails loudly
                                     rather than silently seeing nil)
     [:idx]                          current [:for] index
     [:has? k]                       was k read?
     [:at k i-expr]                  element i of a [:vec k] array — the
                                     standard's `element[ i ]` condition form
     [:= a b] [:not= a b] [:< a b] [:<= a b] [:> a b]
     [:in v set] [:and ...] [:or ...] [:not a]
     [:+ a b] [:- a b] [:* a b] [:if c a b]

   ## What this format CANNOT express, by construction

   - `ae(v)` (CABAC). An arithmetic-coded element's bit cost depends on the
     adaptive context state, which depends on every previously decoded
     element in the slice. There is no (name, descriptor, condition) triple
     that determines it. `[:unsupported :ae]` is the only honest row.
   - §7.4 derivations and inferred values other than plain constants.
   - Sub-structures whose spec body contains assignment statements rather
     than descriptor rows (scaling_list) — those take [:escape].
   - `more_rbsp_data()`-gated tails, which need the RBSP's exact trailing-bit
     position rather than any property of the table."
  (:require [h264.expgolomb :as eg]))

(def ^:private idx-key ::idx)

(defn- unbound! [k vals]
  (throw (ex-info "h264.syntax: expression references an unread syntax element"
                  {:element k :read (vec (sort (remove #{idx-key} (keys vals))))})))

(defn eval-expr
  "Evaluate a table expression against `vals` (spec-name -> value)."
  [e vals]
  (cond
    (number? e)  e
    (boolean? e) e
    (set? e)     e
    (keyword? e) e
    (nil? e)     nil
    (vector? e)
    (let [op (nth e 0)
          a  (fn [i] (eval-expr (nth e i) vals))]
      (case op
        :var  (let [k (nth e 1)]
                (if (contains? vals k) (get vals k) (unbound! k vals)))
        :idx  (if (contains? vals idx-key) (get vals idx-key)
                  (throw (ex-info "h264.syntax: [:idx] outside [:for]" {})))
        :has? (contains? vals (nth e 1))
        :at   (let [k (nth e 1)]
                (if (contains? vals k)
                  (nth (get vals k) (a 2))
                  (unbound! k vals)))
        :=     (= (a 1) (a 2))
        :not=  (not= (a 1) (a 2))
        :<     (< (a 1) (a 2))
        :<=    (<= (a 1) (a 2))
        :>     (> (a 1) (a 2))
        :in    (contains? (eval-expr (nth e 2) vals) (a 1))
        :and   (every? true? (mapv #(eval-expr % vals) (subvec e 1)))
        :or    (boolean (some true? (mapv #(eval-expr % vals) (subvec e 1))))
        :not   (not (a 1))
        :+     (+ (a 1) (a 2))
        :-     (- (a 1) (a 2))
        :*     (* (a 1) (a 2))
        :if    (if (true? (a 1)) (a 2) (a 3))
        (throw (ex-info "h264.syntax: unknown expression operator" {:op op :expr e}))))
    :else (throw (ex-info "h264.syntax: unknown expression form" {:expr e}))))

(defn- cond-expr
  "Presence conditions must evaluate to a strict boolean. H.264 flags are
   read as 0/1 ints, so `[:= [:var :some_flag] 1]` is required rather than
   relying on truthiness — a table that writes `[:var :some_flag]` as a
   condition is a bug and is rejected here rather than silently taking the
   `0` branch as true."
  [e vals]
  (let [v (eval-expr e vals)]
    (if (boolean? v)
      v
      (throw (ex-info "h264.syntax: presence condition did not evaluate to a boolean"
                      {:expr e :value v})))))

(defn- store [vals name v]
  (if (keyword? name)
    (assoc vals name v)
    (let [[tag k] name]
      (case tag
        :vec (update vals k (fnil conj []) v)
        (throw (ex-info "h264.syntax: unknown element name form" {:name name}))))))

(declare read-rows)

(defn- read-row [r escapes vals row]
  (let [op (nth row 0)]
    (case op
      (:u :f) (store vals (nth row 2) (eg/bits! r (eval-expr (nth row 1) vals)))
      :ue     (store vals (nth row 1) (eg/ue! r))
      :se     (store vals (nth row 1) (eg/se! r))
      :infer  (store vals (nth row 1) (eval-expr (nth row 2) vals))
      :when   (if (cond-expr (nth row 1) vals)
                (read-rows r escapes vals (nth row 2))
                (if (> (count row) 3) (read-rows r escapes vals (nth row 3)) vals))
      :for    (let [n (eval-expr (nth row 1) vals)
                    rows (nth row 2)]
                (loop [i 0 vs vals]
                  (if (>= i n)
                    (dissoc vs idx-key)
                    (recur (inc i) (read-rows r escapes (assoc vs idx-key i) rows)))))
      :escape (let [k (nth row 1)
                    f (or (get escapes k)
                          (throw (ex-info "h264.syntax: no handler for escape"
                                          {:escape k :available (vec (sort (keys escapes)))})))
                    args (mapv #(eval-expr % vals) (subvec row 2))]
                (f r vals args))
      :unsupported
      (throw (ex-info "h264.syntax: syntax table reached an element this reader cannot express"
                      {:reason (nth row 1)
                       :info (when (> (count row) 2) (eval-expr (nth row 2) vals))}))
      (throw (ex-info "h264.syntax: unknown row operator" {:op op :row row})))))

(defn read-rows
  "Read `rows` against reader `r`, threading and returning the element map."
  [r escapes vals rows]
  (reduce (fn [vs row] (read-row r escapes vs row)) vals rows))

(defn read-structure
  "Read one syntax structure `table` (a map with :syntax/rows) from the
   already-positioned bit reader `r`. Returns [element-map r] with `r`
   advanced past the structure, so a caller can keep reading (the shape
   `h264.slice/parse-header!` needs). `escapes` maps escape keys to
   (fn [r vals args] -> vals').

   `context` seeds the value map with elements read from ANOTHER structure.
   H.264 needs this: §7.3.3 slice_header reads `frame_num` as
   `u( log2_max_frame_num_minus4 + 4 )`, and that width lives in the
   referenced SPS, not in the slice header. Seeded values are returned
   alongside the ones read here; a caller wanting only this structure's
   elements can remove the context keys it supplied."
  ([r table] (read-structure r table {} {}))
  ([r table escapes] (read-structure r table escapes {}))
  ([r table escapes context]
   [(dissoc (read-rows r escapes context (:syntax/rows table)) idx-key) r]))

(defn read-bytes
  "Convenience: read `table` from the start of byte vector `data`
   (an already-unescaped RBSP, this repo's convention). Returns the element
   map only."
  ([data table] (read-bytes data table {}))
  ([data table escapes]
   (first (read-structure (eg/reader data) table escapes))))
