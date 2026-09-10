(ns kotoba.adl
  "Kotoba ADL -- the pure S-expression notation Kotoba writes data in.

   One extension, one notation. A .kotoba file may hold a program, a schema, a
   query, a policy or a dataset; the extension does not classify it, because
   nothing about the file decides whether it runs. A schema and an evaluator do.

   Surface (what a .kotoba data file contains):

     value  := scalar | form
     scalar := nil | true | false | integer | float | string | keyword | symbol
     form   := \"(\" value* \")\"

   That is the whole grammar. Every composite is one shape, (tag child...), so
   the parser has nothing to decide -- list, map and set are well-known tags,
   not reader syntax:

     [a b]      ->  (vector a b)
     (a b)      ->  (list a b)
     {:a 1}     ->  (map (:a 1))
     #{a b}     ->  (set a b)
     #uuid \"x\"  ->  (uuid \"x\")
     #inst \"x\"  ->  (timestamp \"x\")
     #foo v     ->  (tag \"foo\" v)

   Map entries are written (k v). Inside (map ...) a two-element form is always
   an entry, so this is unambiguous without spending six bytes per entry on the
   word `entry` -- this workspace has 1,018,492 map keys.

   Below the surface sits DAG-Kotoba: the same value projected onto the IPLD
   Data Model's nine kinds (null, bool, integer, float, string, bytes, list,
   map, link), which is what gets a CID. `canonical` performs that projection.
   Encoding canonical values to DAG-CBOR is NOT done here -- io-ipld owns that
   codec and this namespace does not reimplement it."
  (:require [kotoba.adl.reader :as r]
            [clojure.edn :as edn]
            [clojure.string :as str]))

;; ------------------------------------------------------------- value types

(defrecord Bytes [b64])
(defrecord Link [cid])
(defrecord Form [tag children])

(defn bytes-value [b64] (->Bytes b64))
(defn link [cid] (->Link cid))
(defn form [tag children] (->Form tag children))

;; ------------------------------------------------------- EDN CST -> ADL text

(declare node->adl)

(defn- err [msg data] (throw (ex-info msg data)))

(defn- children->adl [nodes] (apply str (map node->adl nodes)))

(defn- qualify-key-text
  "Applies a namespaced map's namespace to one key, by Clojure's rules:
   :a -> :ns/a, a -> ns/a, :_/a -> :a, an already-qualified key is unchanged,
   and anything that is not a keyword or symbol is unchanged."
  [node ns*]
  (let [txt (:s node) kind (:kind node)]
    (cond
      (= kind :keyword)
      (let [body (subs txt 1)]
        (cond (str/starts-with? body "_/") (str ":" (subs body 2))
              (str/includes? body "/") txt
              :else (str ":" ns* "/" body)))
      (= kind :symbol)
      (cond (str/starts-with? txt "_/") (subs txt 2)
            (str/includes? txt "/") txt
            :else (str ns* "/" txt))
      :else txt)))

(defn- map-children->adl
  "Rewrites the children of an EDN map into (k v) entry forms, carrying the
   original whitespace and comments through. Trivia seen while a key is
   expected stays between entries; trivia seen while a value is expected goes
   inside the entry it belongs to."
  ([nodes] (map-children->adl nodes nil))
  ([nodes ns*]
  (loop [ns nodes, out [], pending [], expect :key]
    (if-let [n (first ns)]
      (cond
        (r/trivia? n)
        (if (= expect :key)
          (recur (rest ns) (conj out (node->adl n)) pending expect)
          (recur (rest ns) out (conj pending n) expect))

        (= expect :key)
        (recur (rest ns)
               (conj out (str "(" (if (and ns* (= :atom (:t n)))
                                    (qualify-key-text n ns*)
                                    (node->adl n))))
               [] :val)

        :else
        (recur (rest ns)
               (conj out (str (children->adl pending) (node->adl n) ")"))
               [] :key))
      (do
        (when (= expect :val) (err "map has an odd number of forms" {}))
        (str (apply str out) (children->adl pending)))))))

(def ^:private coll-tag {:vector "vector" :list "list" :set "set"})

(defn- node->adl [n]
  (case (:t n)
    (:ws :comment) (:s n)
    :atom (:s n)
    :coll (let [tag (if (= :map (:kind n)) "map" (get coll-tag (:kind n)))
                inner (if (= :map (:kind n))
                        (map-children->adl (:children n))
                        (children->adl (:children n)))]
            (if (str/blank? inner)
              (str "(" tag inner ")")
              (str "(" tag " " inner ")")))
    :tagged (let [t (:tag n)
                  raw (children->adl (:children n))
                  ;; the trivia between #tag and its value already carries a
                  ;; separator; adding another would double it
                  sep (if (re-find #"^\s" raw) "" " ")
                  inner (str sep raw)]
              (case t
                "uuid" (str "(uuid" inner ")")
                "inst" (str "(timestamp" inner ")")
                (str "(tag \"" t "\"" inner ")")))
    :nsmap (let [mapnode (first (filter #(= :coll (:t %)) (:children n)))
                 inner (map-children->adl (:children mapnode) (:ns n))]
             (if (str/blank? inner) "(map)" (str "(map " inner ")")))
    :discard (str "#_" (children->adl (:children n)))
    :meta (str "(with-meta " (children->adl (:children n)) ")")
    (err "unknown CST node" {:node (pr-str n)})))

(defn edn->adl
  "Converts EDN source text to Kotoba ADL source text, preserving comments."
  [^String edn-text]
  (children->adl (r/read-cst edn-text)))

;; --------------------------------------------------------- ADL text -> value

(declare node->value form->value* entry->pair*)

(defn- value-children [nodes] (mapv node->value (r/forms nodes)))

(defn- build-map [pairs]
  (let [ks (map first pairs)]
    (when-not (= (count ks) (count (set ks)))
      (err "duplicate key in map" {:duplicates (->> ks frequencies (filter #(> (val %) 1)) (map key) vec)}))
    (into {} pairs)))

(defn- build-set [vs]
  (when-not (= (count vs) (count (set vs)))
    (err "duplicate element in set" {}))
  (set vs))

(defn- node->value [n]
  (case (:t n)
    :atom (:v n)
    :discard (err "discard is not a value" {})
    :coll (err "bare EDN collection syntax in ADL" {:kind (:kind n)})
    :tagged (err "bare EDN tagged literal in ADL" {:tag (:tag n)})
    :meta (err "bare EDN metadata in ADL" {})
    (err "unexpected node" {:node (pr-str n)})))

(defn- form->value [n]
  (let [fs (r/forms (:children n))
        head (first fs)
        args (rest fs)]
    (when (nil? head) (err "empty form ()" {}))
    (let [tag (when (= :atom (:t head)) (:v head))
          tag (cond (symbol? tag) (name tag) (string? tag) tag :else nil)]
      (case tag
        "vector" (mapv form->value* args)
        "list" (apply list (map form->value* args))
        "set" (build-set (map form->value* args))
        "map" (build-map (map entry->pair* args))
        "uuid" (let [s (form->value* (first args))] (uuid s))
        "timestamp" (let [s (form->value* (first args))]
                      #?(:clj (java.util.Date. (.getTime (java.util.Date. ^String s)))
                         :cljs (js/Date. s)))
        "bytes" (->Bytes (form->value* (first args)))
        "link" (->Link (form->value* (first args)))
        "tag" (->Form (form->value* (first args)) (mapv form->value* (rest args)))
        "with-meta" (with-meta (form->value* (second args)) (form->value* (first args)))
        ;; Any other head is a generic Form. Being a form is not being callable;
        ;; a schema and an evaluator decide that, not the parentheses.
        (->Form (if (= :atom (:t head)) (:v head) (form->value* head))
                (mapv form->value* args))))))

(defn- form->value* [n]
  (if (and (= :coll (:t n)) (= :list (:kind n)))
    (form->value n)
    (node->value n)))

(defn- entry->pair* [n]
  (when-not (and (= :coll (:t n)) (= :list (:kind n)))
    (err "map entry must be a (k v) form" {:node (pr-str n)}))
  (let [fs (r/forms (:children n))]
    (when-not (= 2 (count fs)) (err "map entry must have exactly two elements" {:count (count fs)}))
    [(form->value* (first fs)) (form->value* (second fs))]))

(defn read-all
  "Reads Kotoba ADL text into a vector of values (a file may hold several)."
  [^String adl-text]
  (mapv form->value* (r/forms (r/read-cst adl-text))))

(defn read-string
  "Reads the first value from Kotoba ADL text.
   This is the drop-in for (clojure.edn/read-string (slurp f))."
  [^String adl-text]
  (first (read-all adl-text)))

;; -------------------------------------------------------------- DAG-Kotoba

(defn- kw->text [k] (if-let [ns* (namespace k)] (str ns* "/" (name k)) (name k)))

(defn canonical
  "Projects a value onto the IPLD Data Model -- the form that gets a CID.

   Only the nine IPLD kinds come out: nil, boolean, number, string, Bytes,
   Link, vector (List) and map (Map, string keys only). Everything else becomes
   a Form, and a Form is an IPLD List whose first element is its tag string.

   A map whose keys are all strings stays an IPLD Map. Any other map becomes
   (\"map\" [k v] ...) with its entries in canonical key order, because IPLD Map
   keys are strings and this workspace's keys are overwhelmingly keywords --
   silently stringifying them would collide with the 4,557 keys that really
   are strings, and with the 32 maps that use both."
  [v]
  (cond
    (nil? v) nil
    (boolean? v) v
    (number? v) v
    (string? v) v
    (instance? Bytes v) v
    (instance? Link v) v
    (keyword? v) ["kw" (kw->text v)]
    (symbol? v) ["sym" (str v)]
    (instance? Form v) (into ["tag" (canonical (:tag v))] (map canonical (:children v)))
    (map? v) (if (every? string? (keys v))
               (into {} (map (fn [[k vv]] [k (canonical vv)]) v))
               (into ["map"] (->> v
                                  (map (fn [[k vv]] [(canonical k) (canonical vv)]))
                                  (sort-by (comp pr-str first)))))
    (set? v) (into ["set"] (sort-by pr-str (map canonical v)))
    (vector? v) (mapv canonical v)
    (sequential? v) (into ["list"] (map canonical v))
    :else (err "value has no IPLD Data Model projection" {:type (str (type v))})))

;; ------------------------------------------------------------- reading files

(defn- slurp* [p]
  #?(:clj (slurp p)
     :cljs (let [fs (js/require "fs")] (.readFileSync fs p "utf8"))))

(defn- exists? [p]
  #?(:clj (.exists (java.io.File. ^String p))
     :cljs (let [fs (js/require "fs")] (.existsSync fs p))))

(defn read-file
  "Reads one value from a file, choosing the notation by extension:
   .kotoba is Kotoba ADL, .edn is EDN."
  [p]
  (let [txt (slurp* p)]
    (if (str/ends-with? p ".edn")
      (edn/read-string txt)
      (read-string txt))))

(defn sibling
  "The same path under the other notation's extension."
  [p]
  (cond (str/ends-with? p ".edn") (str (subs p 0 (- (count p) 4)) ".kotoba")
        (str/ends-with? p ".kotoba") (str (subs p 0 (- (count p) 7)) ".edn")
        :else p))

(defn read-data
  "Reads a data file whichever notation it is currently in: the given path if it
   exists, otherwise its sibling under the other extension.

   This is what makes the migration tractable. A call site rewritten to
   read-data behaves identically before and after its file is converted, so the
   two halves -- moving call sites and moving files -- stop having to happen in
   the same commit, and either can be rolled back alone."
  [p]
  (cond
    (exists? p) (read-file p)
    (exists? (sibling p)) (read-file (sibling p))
    :else (throw (ex-info "no data file under either notation"
                          {:tried [p (sibling p)]}))))
