(ns toshokan.sources.ndl-core
  "Pure CLJC NDL parser. It has no fetch, filesystem, clock, environment, or
  process access, so the exact parser runs under JVM Clojure and ClojureScript
  hosts. Network authority remains in a host adapter."
  (:require [kotoba.lang.text :as str]))

(defn- unescape-xml [s]
  (-> s
      (str/replace "&lt;" "<")
      (str/replace "&gt;" ">")
      (str/replace "&quot;" "\"")
      (str/replace "&apos;" "'")
      (str/replace "&#39;" "'")
      (str/replace "&amp;" "&")))

(defn- tag1 [tag block]
  (some-> (re-find (re-pattern (str "<" tag "[^>]*>([^<]*)</" tag ">")) block)
          second
          str/trim
          not-empty))

(defn- blocks [tag s]
  (re-seq (re-pattern (str "<" tag "[^>]*>[\\s\\S]*?</" tag ">")) s))

(defn- bib-resources [rdf-xml]
  (blocks "dcndl:BibResource" rdf-xml))

(defn- record-datas [sru-xml]
  (map second (re-seq #"<recordData>([\s\S]*?)</recordData>" sru-xml)))

(defn- entity-id [about-url]
  (when about-url
    (-> about-url
        (str/replace #"#.*$" "")
        (str/split #"/")
        last
        (->> (str "ndl:")))))

(defn parse-bib-resource
  "One dcndl:BibResource block to a bounded bibliographic field map."
  [block]
  (let [about (some-> (re-find #"rdf:about=\"([^\"]+)\"" block) second)
        title (or (tag1 "dcterms:title" block) (tag1 "rdf:value" block))
        creators (->> (blocks "dcterms:creator" block)
                      (keep #(tag1 "foaf:name" %)))
        publishers (->> (blocks "dcterms:publisher" block)
                        (keep #(tag1 "foaf:name" %)))
        issued (or (tag1 "dcterms:issued" block) (tag1 "dcterms:date" block))
        ndc (some-> (re-find #"dc:subject rdf:datatype=\"[^\"]*NDC[^\"]*\">([^<]*)<" block)
                    second str/trim not-empty)
        extent (tag1 "dcterms:extent" block)]
    (when (and about title)
      {:entity (entity-id about)
       :source-url about
       :title title
       :creators creators
       :publishers publishers
       :issued issued
       :ndc ndc
       :extent extent})))

(defn parse-records
  "Full NDL SRU response XML to field maps. This is the portable semantic
  core used by both the existing nbb adapter and JVM/workerd-style hosts."
  [sru-xml-text]
  (->> (record-datas sru-xml-text)
       (map (comp unescape-xml unescape-xml))
       (mapcat (comp (partial take 1) bib-resources))
       (keep parse-bib-resource)))
