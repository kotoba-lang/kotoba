(ns xmile.xml
  "Convert XMILE XML text or a parsed XML element tree to/from xmile.model
  EDN. `parse-string` is the file-content boundary; `parse-doc` remains the
  portable pure-data boundary for hosts that already have an XML tree.

  Round-trip guarantee (for well-formed data):
    (= model (parse-model (emit-model model)))
    (= doc   (parse-doc   (emit-doc   doc)))

  Covers the OASIS XMILE v1.0 structural elements needed to reconstruct a
  runnable model: <header>, <sim_specs>, <model_units>, <dimensions>,
  <model>/<variables> (<stock>/<flow>/<aux>), <gf>. Does NOT cover the
  diagram/display layer (<views>, <style>) -- sec 3.7.5 itself says
  'any software which supports XMILE should be able to simulate all
  whole-models, even those without diagrams', so the display layer is out
  of scope here (see README Follow-ups)."
  (:require [kotoba.lang.text :as str])
  #?(:clj
     (:import (java.io StringReader)
              (javax.xml XMLConstants)
              (javax.xml.parsers DocumentBuilderFactory)
              (org.w3c.dom NamedNodeMap Node NodeList)
              (org.xml.sax ErrorHandler InputSource))))

(def ^:private xmile-namespace
  "http://docs.oasis-open.org/xmile/ns/XMILE/v1.0")

;; --- generic parsed-XML element accessors ---

(defn- tag-kw [t] (keyword (name t)))
(defn- tag= [elem t] (and (map? elem) (= (tag-kw (:tag elem)) t)))
(defn- elem-children [elem] (filter map? (:content elem)))
(defn- by-tag [elem t] (filter #(tag= % t) (elem-children elem)))
(defn- first-child [elem t] (first (by-tag elem t)))
(defn- text-of [elem] (str/trim (apply str (filter string? (:content elem)))))
(defn- child-text [elem t]
  (some-> (first-child elem t) text-of (as-> s (when (seq s) s))))
(defn- attr [elem k] (get (:attrs elem) k))
(defn- elem [tag attrs content] (cond-> {:tag tag} (seq attrs) (assoc :attrs attrs) true (assoc :content (vec content))))
(defn- text-elem [tag s] (elem tag {} [s]))

(defn- parse-num [s] #?(:clj (Double/parseDouble s) :cljs (js/parseFloat s)))
(defn- num->str [n] (str n))

;; --- XML text boundary ---

#?(:clj
   (defn- set-feature-if-supported! [factory feature value]
     (try
       (.setFeature factory feature value)
       (catch Exception _ nil))
     factory))

#?(:clj
   (defn- secure-document-builder []
     (let [factory (DocumentBuilderFactory/newInstance)]
       (.setNamespaceAware factory true)
       (.setXIncludeAware factory false)
       (.setExpandEntityReferences factory false)
       (doseq [[feature value]
               [[XMLConstants/FEATURE_SECURE_PROCESSING true]
                ["http://apache.org/xml/features/disallow-doctype-decl" true]
                ["http://xml.org/sax/features/external-general-entities" false]
                ["http://xml.org/sax/features/external-parameter-entities" false]
                ["http://apache.org/xml/features/nonvalidating/load-external-dtd" false]]]
         (set-feature-if-supported! factory feature value))
       (.newDocumentBuilder factory))))

#?(:clj
   (defn- node-name [^Node node]
     (keyword (or (.getLocalName node) (.getNodeName node)))))

#?(:clj
   (defn- dom-element->tree [^Node node]
     (let [^NamedNodeMap attrs (.getAttributes node)
           attrs-map
           (into {}
                 (keep (fn [i]
                         (let [a (.item attrs i)
                               nm (or (.getLocalName a) (.getNodeName a))]
                           (when-not (or (= "xmlns" nm)
                                         (= "http://www.w3.org/2000/xmlns/" (.getNamespaceURI a)))
                             [(keyword nm) (.getNodeValue a)]))))
                 (range (.getLength attrs)))
           ^NodeList children (.getChildNodes node)
           content
           (into []
                 (keep (fn [i]
                         (let [child (.item children i)]
                           (case (.getNodeType child)
                             1 (dom-element->tree child)
                             (3 4) (.getNodeValue child)
                             nil))))
                 (range (.getLength children)))]
       (cond-> {:tag (node-name node) :content content}
         (seq attrs-map) (assoc :attrs attrs-map)))))

(defn parse-xml-string
  "Parse XML text into the generic element-tree shape accepted by
  `parse-doc`. On the JVM the parser disables DTDs, external entities and
  XInclude. In ClojureScript this uses the host `DOMParser`."
  [xml-text]
  #?(:clj
     (let [builder (secure-document-builder)
           _ (.setErrorHandler
              builder
              (reify ErrorHandler
                (warning [_ error] (throw error))
                (error [_ error] (throw error))
                (fatalError [_ error] (throw error))))
           doc (.parse builder (InputSource. (StringReader. xml-text)))]
       (dom-element->tree (.getDocumentElement doc)))
     :cljs
     (let [parser (js/DOMParser.)
           doc (.parseFromString parser xml-text "application/xml")
           error (.querySelector doc "parsererror")]
       (when error
         (throw (ex-info "xmile.xml: malformed XML"
                         {:message (.-textContent error)})))
       (letfn [(node->tree [node]
                 (let [attrs (.-attributes node)
                       children (.-childNodes node)]
                   (cond-> {:tag (keyword (or (.-localName node) (.-nodeName node)))
                            :content
                            (into []
                                  (keep (fn [child]
                                          (case (.-nodeType child)
                                            1 (node->tree child)
                                            (3 4) (.-nodeValue child)
                                            nil)))
                                  (array-seq children))}
                     (pos? (.-length attrs))
                     (assoc :attrs
                            (into {}
                                  (keep (fn [a]
                                          (when-not (= "http://www.w3.org/2000/xmlns/" (.-namespaceURI a))
                                            [(keyword (or (.-localName a) (.-name a)))
                                             (.-value a)])))
                                  (array-seq attrs))))))]
         (node->tree (.-documentElement doc))))))

(defn- xml-escape [s attribute?]
  (cond-> (-> (str s)
              (str/replace "&" "&amp;")
              (str/replace "<" "&lt;")
              (str/replace ">" "&gt;"))
    attribute? (str/replace "\"" "&quot;")))

(defn emit-xml-string
  "Serialize a generic element tree produced by `emit-doc` as XML text."
  [root]
  (letfn [(write-element [{:keys [tag attrs content]}]
            (let [tag-name (name tag)
                  attrs-text (apply str
                                    (for [[k v] (sort-by (comp name key) attrs)]
                                      (str " " (name k) "=\"" (xml-escape v true) "\"")))
                  body (apply str
                              (map #(if (map? %)
                                      (write-element %)
                                      (xml-escape % false))
                                   content))]
              (if (seq content)
                (str "<" tag-name attrs-text ">" body "</" tag-name ">")
                (str "<" tag-name attrs-text "/>"))))]
    (str "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
         (write-element root))))

;; --- sim_specs (sec 3.7.1) ---

(defn parse-sim-specs [e]
  (cond-> {:xmile/start (parse-num (child-text e :start))
           :xmile/stop  (parse-num (child-text e :stop))}
    (child-text e :dt)
    (as-> ss (assoc ss :xmile/dt (parse-num (child-text e :dt)))
      (if (= "true" (attr (first-child e :dt) :reciprocal))
        (assoc ss :xmile/dt-reciprocal? true)
        ss))
    (attr e :method) (assoc :xmile/method (keyword (str/lower (attr e :method))))
    (attr e :time_units) (assoc :xmile/time-units (attr e :time_units))
    (attr e :pause) (assoc :xmile/pause (attr e :pause))))

(defn emit-sim-specs [ss]
  (elem :sim_specs
        (cond-> {}
          (:xmile/method ss) (assoc :method (name (:xmile/method ss)))
          (:xmile/time-units ss) (assoc :time_units (:xmile/time-units ss))
          (:xmile/pause ss) (assoc :pause (:xmile/pause ss)))
        (cond-> [(text-elem :start (num->str (:xmile/start ss)))
                 (text-elem :stop (num->str (:xmile/stop ss)))]
          (:xmile/dt ss)
          (conj (elem :dt (when (:xmile/dt-reciprocal? ss) {:reciprocal "true"})
                      [(num->str (:xmile/dt ss))])))))

;; --- graphical function (sec 3.2.2) ---

(defn- parse-csv-nums [s] (mapv parse-num (str/split s #",")))
(defn- nums->csv [ns] (str/join "," (map num->str ns)))

(defn parse-gf [e]
  (cond-> {:xmile/gf-type (keyword (str/lower (or (attr e :type) "continuous")))}
    (child-text e :ypts) (assoc :xmile/ypts (parse-csv-nums (child-text e :ypts)))
    (child-text e :xpts) (assoc :xmile/xpts (parse-csv-nums (child-text e :xpts)))
    (first-child e :xscale)
    (assoc :xmile/xscale
           (let [xs (first-child e :xscale)]
             (if (and (attr xs :min) (attr xs :max))
               [(parse-num (attr xs :min)) (parse-num (attr xs :max))]
               (mapv parse-num (str/split (text-of xs) #"-" 2)))))))

(defn emit-gf [gf]
  (elem :gf {:type (name (:xmile/gf-type gf :continuous))}
        (cond-> []
          (:xmile/xscale gf) (conj (elem :xscale {:min (num->str (first (:xmile/xscale gf)))
                                                   :max (num->str (second (:xmile/xscale gf)))} []))
          (:xmile/xpts gf) (conj (text-elem :xpts (nums->csv (:xmile/xpts gf))))
          true (conj (text-elem :ypts (nums->csv (:xmile/ypts gf)))))))

;; --- stock / flow / aux (sec 3.1, 3.7.2, 3.7.3) ---

(defn- parse-common [e]
  (cond-> {:xmile/name (attr e :name) :xmile/eqn (or (child-text e :eqn) "0")}
    (child-text e :units) (assoc :xmile/units (child-text e :units))
    (child-text e :doc) (assoc :xmile/doc (child-text e :doc))
    (seq (by-tag e :non_negative)) (assoc :xmile/non-negative? true)
    (first-child e :gf) (assoc :xmile/gf (parse-gf (first-child e :gf)))))

(defn parse-stock [e]
  (let [inflows (mapv text-of (by-tag e :inflow))
        outflows (mapv text-of (by-tag e :outflow))]
    (merge (parse-common e)
           (cond-> {:xmile/kind :stock
                    :xmile/inflows (set inflows)
                    :xmile/outflows (set outflows)
                    :xmile/stock-type (keyword (str/lower (or (attr e :type) "stock")))}
             ;; Priority is semantically significant for queues, conveyors and
             ;; constrained/non-negative stocks (XMILE 1.0 sec 4.2). Keep the
             ;; compact set API, but retain non-canonical wire order explicitly.
             (not= inflows (vec (sort inflows))) (assoc :xmile/inflow-order inflows)
             (not= outflows (vec (sort outflows))) (assoc :xmile/outflow-order outflows))
           (when (child-text e :len) {:xmile/length (parse-num (child-text e :len))})
           (when (child-text e :discrete) {:xmile/conveyor-discrete? (= "true" (child-text e :discrete))})
           (when (child-text e :leak) {:xmile/leak (child-text e :leak)})
           (when (seq (by-tag e :leak_integer)) {:xmile/leak-integer? true})
           (when (seq (by-tag e :arrest)) {:xmile/arrest? true})
           (when (child-text e :capacity) {:xmile/capacity (parse-num (child-text e :capacity))})
           (when (child-text e :overflow) {:xmile/overflow (child-text e :overflow)}))))

(defn parse-flow [e]
  (merge (parse-common e)
         {:xmile/kind :flow}
         (when (child-text e :leak) {:xmile/leak (child-text e :leak)})
         (when (seq (by-tag e :leak_integer)) {:xmile/leak-integer? true})
         (when (child-text e :leak_start) {:xmile/leak-start (parse-num (child-text e :leak_start))})
         (when (child-text e :leak_end) {:xmile/leak-end (parse-num (child-text e :leak_end))})))

(defn parse-aux [e] (merge (parse-common e) {:xmile/kind :aux}))

(defn parse-variable [e]
  (case (tag-kw (:tag e))
    :stock (parse-stock e)
    :flow (parse-flow e)
    (:aux :auxiliary) (parse-aux e)
    (throw (ex-info "xmile.xml: unknown variable tag" {:tag (:tag e)}))))

(defn- emit-common-content [v]
  (cond-> [(text-elem :eqn (:xmile/eqn v))]
    (:xmile/units v) (conj (text-elem :units (:xmile/units v)))
    (:xmile/doc v) (conj (text-elem :doc (:xmile/doc v)))
    (:xmile/gf v) (conj (emit-gf (:xmile/gf v)))
    (:xmile/non-negative? v) (conj (elem :non_negative {} []))))

(defn emit-variable [v]
  (case (:xmile/kind v)
    :stock (elem :stock
                 (cond-> {:name (:xmile/name v)}
                   (not= :stock (:xmile/stock-type v :stock)) (assoc :type (name (:xmile/stock-type v))))
                 (concat (emit-common-content v)
                         (map #(text-elem :inflow %)
                              (or (:xmile/inflow-order v) (sort (:xmile/inflows v))))
                         (map #(text-elem :outflow %)
                              (or (:xmile/outflow-order v) (sort (:xmile/outflows v))))
                         (when (:xmile/length v) [(text-elem :len (num->str (:xmile/length v)))])
                         (when (contains? v :xmile/conveyor-discrete?)
                           [(text-elem :discrete (str (:xmile/conveyor-discrete? v)))])
                         (when (:xmile/leak v) [(text-elem :leak (:xmile/leak v))])
                         (when (:xmile/leak-integer? v) [(elem :leak_integer {} [])])
                         (when (:xmile/arrest? v) [(elem :arrest {} [])])
                         (when (:xmile/capacity v) [(text-elem :capacity (num->str (:xmile/capacity v)))])
                         (when (:xmile/overflow v) [(text-elem :overflow (:xmile/overflow v))])))
    :flow (elem :flow {:name (:xmile/name v)}
                (concat (emit-common-content v)
                        (when (:xmile/leak v) [(text-elem :leak (:xmile/leak v))])
                        (when (:xmile/leak-integer? v) [(elem :leak_integer {} [])])
                        (when (:xmile/leak-start v) [(text-elem :leak_start (num->str (:xmile/leak-start v)))])
                        (when (:xmile/leak-end v) [(text-elem :leak_end (num->str (:xmile/leak-end v)))])))
    :aux (elem :aux {:name (:xmile/name v)} (emit-common-content v))))

;; --- dimensions (sec 4.5) / units (sec 3.6) -- structural only, no dimensional analysis (v2) ---

(defn parse-dimensions [e]
  (into {}
        (for [d (by-tag e :dim)]
          [(attr d :name)
           (cond-> {}
             (attr d :size) (assoc :xmile/size (parse-num (attr d :size)))
             (seq (by-tag d :elem)) (assoc :xmile/elements (mapv #(attr % :name) (by-tag d :elem))))])))

(defn emit-dimensions [dims]
  (elem :dimensions {}
        (for [[nm d] dims]
          (elem :dim (cond-> {:name nm} (:xmile/size d) (assoc :size (num->str (:xmile/size d))))
                (map #(elem :elem {:name %} []) (:xmile/elements d))))))

(defn parse-units [e]
  (into {}
        (for [u (by-tag e :unit)]
          [(attr u :name)
           (cond-> {}
             (child-text u :eqn) (assoc :xmile/unit-eqn (child-text u :eqn))
             (seq (by-tag u :alias)) (assoc :xmile/aliases (mapv text-of (by-tag u :alias)))
             (= "true" (attr u :disabled)) (assoc :xmile/disabled? true))])))

(defn emit-units [units]
  (elem :model_units {}
        (for [[nm u] units]
          (elem :unit (cond-> {:name nm} (:xmile/disabled? u) (assoc :disabled "true"))
                (concat (when (:xmile/unit-eqn u) [(text-elem :eqn (:xmile/unit-eqn u))])
                        (map #(text-elem :alias %) (:xmile/aliases u)))))))

;; --- model / doc (sec 3.1, 3.7) ---

(defn parse-model [e]
  (let [variable-elements (vec (elem-children (first-child e :variables)))
        supported-variable? #(contains? #{:stock :flow :aux :auxiliary}
                                        (tag-kw (:tag %)))
        supported (filter supported-variable? variable-elements)
        variable-extensions (vec (remove supported-variable? variable-elements))
        extensions (vec (remove #(contains? #{:sim_specs :variables}
                                             (tag-kw (:tag %)))
                                (elem-children e)))]
    (cond-> {:xmile/variables
             (into {}
                   (for [v supported]
                     (let [pv (parse-variable v)] [(:xmile/name pv) pv])))}
      (attr e :name) (assoc :xmile/name (attr e :name))
      (first-child e :sim_specs) (assoc :xmile/sim-specs (parse-sim-specs (first-child e :sim_specs)))
      (seq variable-extensions) (assoc :xmile/variable-extensions variable-extensions)
      (seq extensions) (assoc :xmile/extensions extensions))))

(defn emit-model [m]
  (elem :model
        (cond-> {} (:xmile/name m) (assoc :name (:xmile/name m)))
        (cond-> []
          (:xmile/sim-specs m) (conj (emit-sim-specs (:xmile/sim-specs m)))
          true (conj (elem :variables {}
                           (concat (map emit-variable (vals (:xmile/variables m)))
                                   (:xmile/variable-extensions m))))
          (seq (:xmile/extensions m)) (into (:xmile/extensions m)))))

(defn parse-header [e]
  (cond-> {}
    (child-text e :vendor) (assoc :xmile/vendor (child-text e :vendor))
    (first-child e :product)
    (assoc :xmile/product (cond-> {:xmile/name (text-of (first-child e :product))}
                             (attr (first-child e :product) :version)
                             (assoc :xmile/version (attr (first-child e :product) :version))))
    (child-text e :name) (assoc :xmile/name (child-text e :name))
    (child-text e :uuid) (assoc :xmile/uuid (child-text e :uuid))))

(defn emit-header [h]
  (elem :header {}
        (concat (when (:xmile/vendor h) [(text-elem :vendor (:xmile/vendor h))])
                (when (:xmile/product h)
                  [(elem :product (cond-> {} (get-in h [:xmile/product :xmile/version]) (assoc :version (get-in h [:xmile/product :xmile/version])))
                         [(get-in h [:xmile/product :xmile/name])])])
                (when (:xmile/name h) [(text-elem :name (:xmile/name h))])
                (when (:xmile/uuid h) [(text-elem :uuid (:xmile/uuid h))]))))

(defn parse-doc
  "Parse a full <xmile> root element into {:xmile/header .. :xmile/sim-specs
  .. :xmile/model-units .. :xmile/dimensions .. :xmile/models [..]}."
  [root]
  (let [extensions
        (vec (remove #(contains? #{:header :sim_specs :model_units :dimensions :model}
                                  (tag-kw (:tag %)))
                     (elem-children root)))]
    (cond-> {:xmile/models (mapv parse-model (by-tag root :model))}
      (first-child root :header) (assoc :xmile/header (parse-header (first-child root :header)))
      (first-child root :sim_specs) (assoc :xmile/sim-specs (parse-sim-specs (first-child root :sim_specs)))
      (first-child root :model_units) (assoc :xmile/model-units (parse-units (first-child root :model_units)))
      (first-child root :dimensions) (assoc :xmile/dimensions (parse-dimensions (first-child root :dimensions)))
      (seq extensions) (assoc :xmile/extensions extensions))))

(defn emit-doc [doc]
  (elem :xmile {:version "1.0" :xmlns xmile-namespace}
        (concat (when (:xmile/header doc) [(emit-header (:xmile/header doc))])
                (when (:xmile/sim-specs doc) [(emit-sim-specs (:xmile/sim-specs doc))])
                (when (:xmile/model-units doc) [(emit-units (:xmile/model-units doc))])
                (when (:xmile/dimensions doc) [(emit-dimensions (:xmile/dimensions doc))])
                (map emit-model (:xmile/models doc))
                (:xmile/extensions doc))))

(defn parse-string
  "Parse a complete XMILE XML string into the library's EDN document."
  [xml-text]
  (let [root (parse-xml-string xml-text)]
    (when-not (tag= root :xmile)
      (throw (ex-info "xmile.xml: expected <xmile> document root"
                      {:tag (:tag root)})))
    (parse-doc root)))

(defn emit-string
  "Serialize an XMILE EDN document as a complete namespaced XML document."
  [doc]
  (emit-xml-string (emit-doc doc)))
