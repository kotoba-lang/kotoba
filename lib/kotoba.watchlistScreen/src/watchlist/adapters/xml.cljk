(ns watchlist.adapters.xml
  "Minimal, zero-dependency, portable .cljc XML-string reader — a neutral
   element tree `{:tag \"process\" :attrs {\"id\" \"…\"} :content […]}` with
   namespace-prefix-stripped string tags. Not a general XML parser (no DTD/
   CDATA/processing-instruction handling beyond skipping them, entity
   decoding covers only the five predefined XML entities) — for the
   well-formed government-published sanctions-list XML this repo consumes,
   that's sufficient. This is the same hand-rolled pattern
   kotoba-lang/org-omg-bpmn's `bpmn.xml`, kotoba-lang/org-oasis-open-xmile's
   `xmile.xml`, kotoba-lang/org-omg-uml's `uml.xml`, and kotoba-lang/org-sbml's
   `sbml.xml` each already carry independently (house convention: this
   utility is small enough that duplicating it per-consumer beats a shared
   dependency — see kotoba-lang/composer's ADR-2607031510 on avoiding
   speculative generality)."
  (:require [kotoba.lang.text :as str]))

(defn- decode [s]
  (-> s
      (str/replace "&lt;" "<") (str/replace "&gt;" ">")
      (str/replace "&quot;" "\"") (str/replace "&apos;" "'")
      (str/replace "&amp;" "&"))) ; ampersand last

(defn- strip-ns [s]
  (let [i (str/index-of s ":")] (if i (subs s (inc i)) s)))

(def ^:private attr-re #"([\w:.\-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")

(defn- parse-attrs [s]
  (reduce (fn [m [_ k v1 v2]] (assoc m (strip-ns k) (decode (or v1 v2))))
          {} (re-seq attr-re s)))

(defn parse-elements
  "Well-formed XML string -> neutral element tree (or nil for an empty/
   comment-only document)."
  [xml]
  (loop [i 0 stack [] root nil]
    (let [lt (str/index-of xml "<" i)]
      (if (nil? lt)
        root
        (let [text (subs xml i lt)
              stack (if (and (seq stack) (seq (str/trim text)))
                      (update-in stack [(dec (count stack)) :content]
                                 conj (str/trim (decode text)))
                      stack)
              head (subs xml lt (min (count xml) (+ lt 9)))]
          (cond
            (str/starts-with? head "<!--")
            (recur (+ (str/index-of xml "-->" lt) 3) stack root)

            (str/starts-with? head "<?")
            (recur (+ (str/index-of xml "?>" lt) 2) stack root)

            (str/starts-with? head "<![CDATA[")
            (let [close (str/index-of xml "]]>" lt)
                  cdata (subs xml (+ lt 9) close)
                  stack (if (seq stack)
                          (update-in stack [(dec (count stack)) :content] conj cdata)
                          stack)]
              (recur (+ close 3) stack root))

            (str/starts-with? head "</")
            (let [gt (str/index-of xml ">" lt)
                  done (peek stack) stack' (pop stack)]
              (if (seq stack')
                (recur (inc gt)
                       (update-in stack' [(dec (count stack')) :content] conj done)
                       root)
                (recur (inc gt) stack' done)))

            :else
            (let [gt (str/index-of xml ">" lt)
                  inner (subs xml (inc lt) gt)
                  self? (str/ends-with? inner "/")
                  inner (if self? (subs inner 0 (dec (count inner))) inner)
                  [_ nm at] (re-find #"^([\w:.\-]+)\s*([\s\S]*)$" inner)
                  el {:tag (strip-ns nm) :attrs (parse-attrs at) :content []}]
              (if self?
                (if (seq stack)
                  (recur (inc gt)
                         (update-in stack [(dec (count stack)) :content] conj el) root)
                  (recur (inc gt) stack el))
                (recur (inc gt) (conj stack el) root)))))))))

(defn children [el tag] (filter #(and (map? %) (= tag (:tag %))) (:content el)))
(defn child [el tag] (first (children el tag)))
(defn text-of [el] (some-> (str/join (filter string? (:content el))) str/trim not-empty))
(defn child-text [el tag] (some-> (child el tag) text-of))
