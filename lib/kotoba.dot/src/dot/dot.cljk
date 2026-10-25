(ns dot.dot
  "Graphviz DOT language ⇄ EDN graph model, with zero third-party deps and portable .cljc.

  `parse-str` parses the well-formed DOT subset:
    strict? (digraph|graph) ID { stmts }
  Statements:
    - node:         a [k=v, ...] ;
    - edge:         a -> b -> c [k=v] ;   (-- for undirected)
    - graph-attr:   rankdir=LR ;
    - default-attr: node [shape=box] ;  edge [color=red] ;
  Quoted ids (\\\"a b\\\"), // and /* */ comments, optional semicolons.
  Edge chains (a -> b -> c) produce one edge per hop.
  An edge auto-declares its endpoints as nodes (empty attrs if unseen).
  node/edge default-attr blocks apply attrs to subsequently-declared nodes/edges.

  `emit-str` produces canonical DOT: graph-attrs first, then nodes sorted by id,
  then edges in declaration order. The output round-trips through `parse-str`.

  Limitations: no subgraphs/clusters, no HTML labels (<...>), no ports (:port),
  no compass points. Attribute values must be string scalars."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Tokeniser
;; ---------------------------------------------------------------------------

(defn- skip-ws
  "Return index after whitespace starting at i."
  [s i]
  (let [n (count s)]
    (loop [i i]
      (if (or (>= i n) (not (str/blank? (subs s i (inc i)))))
        i
        (recur (inc i))))))

(defn- read-line-comment [s i]
  (let [nl (str/index-of s "\n" i)]
    (if nl (inc nl) (count s))))

(defn- read-block-comment [s i]
  (let [end (str/index-of s "*/" i)]
    (if end (+ end 2) (count s))))

(defn- read-quoted [s i]
  ;; i points just past the opening quote; returns [string next-index]
  (loop [j i acc ""]
    (let [c (get s j)]
      (cond
        (nil? c) [acc j]
        (= c \\) (recur (+ j 2) (str acc (get s (inc j))))
        (= c \") [(str acc) (inc j)]
        :else    (recur (inc j) (str acc c))))))

(defn- read-unquoted [s i]
  (let [n (count s)
        end (loop [j i]
              (if (>= j n)
                j
                (let [c (get s j)]
                  (if (or (str/blank? (str c))
                          (contains? #{\[ \] \{ \} \= \, \;} c)
                          (= c \"))
                    j
                    (recur (inc j))))))]
    [(subs s i end) end]))

(defn- tokenise
  "Return a vector of string tokens (keywords as strings, punctuation as strings)."
  [s]
  (let [n (count s)]
    (loop [i 0 toks (transient [])]
      (let [i (skip-ws s i)]
        (if (>= i n)
          (persistent! toks)
          (let [c  (get s i)
                c2 (if (< (inc i) n) (subs s i (+ i 2)) "")]
            (cond
              (= c2 "//") (recur (read-line-comment s (+ i 2)) toks)
              (= c2 "/*") (recur (read-block-comment s (+ i 2)) toks)
              (= c2 "->") (recur (+ i 2) (conj! toks "->"))
              (= c2 "--") (recur (+ i 2) (conj! toks "--"))
              (= c \")   (let [[v j] (read-quoted s (inc i))]
                           (recur j (conj! toks (str "\"" v "\""))))
              (contains? #{\[ \] \{ \} \= \, \;} c)
              (recur (inc i) (conj! toks (str c)))
              :else        (let [[v j] (read-unquoted s i)]
                             (if (empty? v)
                               (recur (inc i) toks)
                               (recur j (conj! toks v)))))))))))

;; ---------------------------------------------------------------------------
;; Token helpers
;; ---------------------------------------------------------------------------

(defn- tok-val
  "Strip surrounding quotes from a token if present."
  [t]
  (if (and (str/starts-with? t "\"") (str/ends-with? t "\""))
    (subs t 1 (dec (count t)))
    t))

(defn- skip-semi [toks i]
  (if (= ";" (get toks i)) (inc i) i))

;; ---------------------------------------------------------------------------
;; Attr list parser  [k=v, k=v]
;; ---------------------------------------------------------------------------

(defn- parse-attr-list
  "Parse [ k=v ... ] starting at i (i points at \"[\"). Returns [attrs next-i]."
  [toks i]
  (if (not= "[" (get toks i))
    [{} i]
    (loop [i (inc i) attrs {}]
      (let [t (get toks i)]
        (cond
          (nil? t)  [attrs i]
          (= t "]") [attrs (inc i)]
          (= t ",") (recur (inc i) attrs)
          (= t ";") (recur (inc i) attrs)
          :else
          (let [k (tok-val t)]
            (if (= "=" (get toks (inc i)))
              (let [v (tok-val (get toks (+ i 2)))]
                (recur (+ i 3) (assoc attrs k v)))
              (recur (inc i) attrs))))))))

;; ---------------------------------------------------------------------------
;; Statement parser
;; ---------------------------------------------------------------------------

(defn- parse-stmts
  "Parse statements inside { ... }. Returns the completed graph map."
  [toks start-i directed?]
  (let [n (count toks)]
    (loop [i start-i
           nodes     {}   ; id -> {:dot/id :dot/attrs}
           edges     []   ; [{:dot/from :dot/to :dot/attrs}]
           graph-attrs {}
           node-defaults {}
           edge-defaults {}]
      (if (or (>= i n) (= "}" (get toks i)))
        {:nodes nodes :edges edges :graph-attrs graph-attrs}
        (let [t0 (get toks i)
              t1 (get toks (inc i))
              op (if directed? "->" "--")]
          (cond
            ;; default-attr: node [...] or edge [...]
            (and (= t0 "node") (= t1 "["))
            (let [[attrs ni] (parse-attr-list toks (inc i))]
              (recur (skip-semi toks ni) nodes edges graph-attrs attrs edge-defaults))

            (and (= t0 "edge") (= t1 "["))
            (let [[attrs ni] (parse-attr-list toks (inc i))]
              (recur (skip-semi toks ni) nodes edges graph-attrs node-defaults attrs))

            ;; graph keyword — skip (already consumed above)
            (= t0 "graph")
            (if (= t1 "[")
              (let [[attrs ni] (parse-attr-list toks (inc i))]
                (recur (skip-semi toks ni) nodes edges (merge graph-attrs attrs)
                       node-defaults edge-defaults))
              (recur (inc i) nodes edges graph-attrs node-defaults edge-defaults))

            ;; bare k=v graph-attr
            (= t1 "=")
            (let [v  (tok-val (get toks (+ i 2)))
                  k  (tok-val t0)]
              (recur (skip-semi toks (+ i 3)) nodes edges
                     (assoc graph-attrs k v) node-defaults edge-defaults))

            ;; edge chain or node statement
            :else
            (let [id0 (tok-val t0)
                  t-next (get toks (inc i))]
              (if (= t-next op)
                ;; edge chain: id0 -> id1 -> id2 ...
                ;; inner loop returns [next-i new-nodes new-edges] then outer recur takes over
                (let [[next-i new-nodes new-edges]
                      (loop [chain [id0] ci (inc i) cur-edges edges cur-nodes nodes]
                        (let [t (get toks ci)]
                          (if (= t op)
                            (let [id-next (tok-val (get toks (inc ci)))
                                  peek-i  (+ ci 2)
                                  [attrs ni] (if (= "[" (get toks peek-i))
                                               (parse-attr-list toks peek-i)
                                               [{} peek-i])
                                  from (last chain)
                                  edge-a (merge edge-defaults attrs)
                                  cur-nodes' (-> cur-nodes
                                                 (update from #(or % {:dot/id from :dot/attrs node-defaults}))
                                                 (update id-next #(or % {:dot/id id-next :dot/attrs node-defaults})))
                                  cur-edges' (conj cur-edges {:dot/from from :dot/to id-next
                                                              :dot/attrs edge-a})]
                              (recur (conj chain id-next)
                                     (if (= "[" (get toks peek-i)) ni (+ ci 2))
                                     cur-edges' cur-nodes'))
                            ;; done with chain — return to outer loop
                            [(skip-semi toks ci) cur-nodes cur-edges])))]
                  (recur next-i new-nodes new-edges graph-attrs node-defaults edge-defaults))
                ;; node statement: id [attrs]
                (let [[attrs ni] (if (= "[" t-next)
                                   (parse-attr-list toks (inc i))
                                   [{} (inc i)])
                      merged (merge node-defaults attrs)
                      existing (get nodes id0)
                      new-node {:dot/id id0
                                :dot/attrs (merge (:dot/attrs existing {}) merged)}]
                  (recur (skip-semi toks ni)
                         (assoc nodes id0 new-node)
                         edges graph-attrs node-defaults edge-defaults))))))))))

;; ---------------------------------------------------------------------------
;; parse-str
;; ---------------------------------------------------------------------------

(defn parse-str
  "Parse a well-formed DOT string → graph model map.
  Supports: strict?, digraph/graph, node/edge/graph-attr/default-attr statements,
  edge chains, quoted ids, // and /* */ comments, optional semicolons.
  Limitations: no subgraphs, no HTML labels, no ports."
  [s]
  (let [toks    (tokenise s)
        i0      0
        strict? (= "strict" (str/lower (get toks i0 "")))
        i1      (if strict? 1 0)
        kw      (str/lower (get toks i1 ""))
        directed? (= kw "digraph")
        i2      (inc i1)
        ;; graph id (may be missing if next token is "{")
        id-tok  (get toks i2)
        [gid i3] (if (= id-tok "{") ["G" i2] [(tok-val id-tok) (inc i2)])
        ;; expect "{"
        i4      (if (= "{" (get toks i3)) (inc i3) i3)
        {:keys [nodes edges graph-attrs]} (parse-stmts toks i4 directed?)]
    {:dot/id          gid
     :dot/strict      strict?
     :dot/directed    directed?
     :dot/graph-attrs graph-attrs
     :dot/nodes       nodes
     :dot/edges       edges}))

;; ---------------------------------------------------------------------------
;; emit-str
;; ---------------------------------------------------------------------------

(defn- quote-id
  "Wrap id in double quotes if it contains spaces or special chars."
  [id]
  (let [s (str id)]
    (if (re-find #"[\s\[\]{},;=\"\\]" s)
      ;; Backslash MUST be escaped first -- escaping " before \ would let a
      ;; pre-existing \ in the id combine with the just-inserted \" into an
      ;; escaped-quote sequence \\", which a DOT parser reads as \\ (literal
      ;; backslash) followed by an UNESCAPED " that closes the quoted id
      ;; early. The rest of the id then reads as new DOT syntax (attribute
      ;; lists, additional node statements) -- verified via this repo's own
      ;; parse-str: a single crafted node id desynced into three separate
      ;; nodes on reparse, with attacker-controlled attributes attached to
      ;; the fabricated ones.
      (str "\"" (-> s (str/replace "\\" "\\\\") (str/replace "\"" "\\\"")) "\"")
      s)))

(defn- emit-attrs [attrs]
  (let [ks (sort (keys attrs))]
    (if (empty? ks)
      ""
      (str " [" (str/join ", " (map #(str (quote-id %) "=" (quote-id (get attrs %))) ks)) "]"))))

(defn emit-str
  "Graph model → canonical DOT string. Nodes sorted by id; edges in declaration order."
  [g]
  (let [{:dot/keys [id strict directed graph-attrs nodes edges]} g
        kw    (str (when strict "strict ") (if directed "digraph" "graph"))
        op    (if directed " -> " " -- ")
        lines (transient [])]
    (conj! lines (str kw " " (quote-id id) " {"))
    ;; graph attrs
    (doseq [k (sort (keys graph-attrs))]
      (conj! lines (str "  " (quote-id k) "=" (quote-id (get graph-attrs k)) ";")))
    ;; nodes sorted by id
    (doseq [nid (sort (keys nodes))]
      (let [n (get nodes nid)
            a (dissoc (:dot/attrs n) ":dot/edge-op")]
        (conj! lines (str "  " (quote-id nid) (emit-attrs a) ";"))))
    ;; edges in order
    (doseq [{:dot/keys [from to attrs]} edges]
      (let [a (dissoc attrs ":dot/edge-op")]
        (conj! lines (str "  " (quote-id from) op (quote-id to) (emit-attrs a) ";"))))
    (conj! lines "}")
    (str/join "\n" (persistent! lines))))
