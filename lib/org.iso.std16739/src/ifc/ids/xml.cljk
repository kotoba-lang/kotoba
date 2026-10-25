(ns ifc.ids.xml
  "Secure IDS 1.0 XML transport for the portable `ifc.ids` contract."
  (:require [kotoba.lang.text :as string]
            [ifc.ids :as ids])
  (:import [java.io StringReader]
           [javax.xml.parsers DocumentBuilderFactory]
           [org.xml.sax InputSource SAXParseException]
           [org.xml.sax.helpers DefaultHandler]))

(def namespace-uri "http://standards.buildingsmart.org/IDS")

(defn- element-children [node]
  (if-not node
    []
    (let [^org.w3c.dom.NodeList child-nodes (.getChildNodes node)]
      (keep (fn [index]
              (let [child (.item child-nodes index)]
                (when (= org.w3c.dom.Node/ELEMENT_NODE (.getNodeType child)) child)))
            (range (.getLength child-nodes))))))

(defn- node-name [node]
  (or (.getLocalName node) (.getNodeName node)))

(defn- children [node name]
  (filter #(= name (node-name %)) (element-children node)))

(defn- child [node name] (first (children node name)))
(defn- text [node] (some-> node .getTextContent string/trim))
(defn- attribute [node name]
  (when (and node (.hasAttribute node name)) (.getAttribute node name)))

(defn- secure-document [xml]
  (let [factory (doto (DocumentBuilderFactory/newInstance)
                  (.setNamespaceAware true)
                  (.setXIncludeAware false)
                  (.setExpandEntityReferences false))]
    (.setFeature factory "http://apache.org/xml/features/disallow-doctype-decl" true)
    (.setFeature factory "http://xml.org/sax/features/external-general-entities" false)
    (.setFeature factory "http://xml.org/sax/features/external-parameter-entities" false)
    (let [builder (.newDocumentBuilder factory)]
      (.setErrorHandler
       builder
       (proxy [DefaultHandler] []
         (warning [^SAXParseException error] (throw error))
         (error [^SAXParseException error] (throw error))
         (fatalError [^SAXParseException error] (throw error))))
      (.parse builder (InputSource. (StringReader. xml))))))

(def numeric-facets
  {"minInclusive" :min-inclusive "maxInclusive" :max-inclusive
   "minExclusive" :min-exclusive "maxExclusive" :max-exclusive
   "minLength" :min-length "maxLength" :max-length "length" :length})

(defn- parse-number [value]
  (when value
    (if (re-matches #"-?[0-9]+" value)
      (Long/parseLong value)
      (Double/parseDouble value))))

(defn- parse-ids-value [node]
  (when node
    (if-let [simple (child node "simpleValue")]
      {:value (text simple)}
      (when-let [restriction (child node "restriction")]
        (reduce
         (fn [result facet]
           (let [name (node-name facet) value (attribute facet "value")]
             (cond
               (= "enumeration" name) (update result :values (fnil conj #{}) value)
               ;; xs:restriction combines multiple xs:pattern facets with
               ;; OR -- accumulate all of them rather than overwriting.
               (= "pattern" name) (update result :patterns (fnil conj []) value)
               (contains? numeric-facets name)
               (assoc result (get numeric-facets name) (parse-number value))
               :else result)))
         {} (element-children restriction))))))

(defn- parse-cardinality [node]
  (keyword (or (attribute node "cardinality") "required")))

(declare parse-facet)

(defn- parse-entity [node]
  (cond-> {:type :entity :name (parse-ids-value (child node "name"))}
    (child node "predefinedType")
    (assoc :predefined-type (parse-ids-value (child node "predefinedType")))))

(defn- parse-facet [node requirement?]
  (let [type (case (node-name node)
               "partOf" :part-of
               (keyword (string/lower (node-name node))))
        cardinality (if requirement? (parse-cardinality node) :required)]
    (case type
      :entity (assoc (parse-entity node) :cardinality cardinality)
      :attribute {:type :attribute :cardinality cardinality
                  :name (some-> (parse-ids-value (child node "name")) :value)
                  :name-restriction (parse-ids-value (child node "name"))
                  :value (parse-ids-value (child node "value"))}
      :property {:type :property :cardinality cardinality
                 :property-set (parse-ids-value (child node "propertySet"))
                 :name (parse-ids-value (child node "baseName"))
                 :value (parse-ids-value (child node "value"))
                 :data-type (some-> (attribute node "dataType") string/lower keyword)}
      :classification {:type :classification :cardinality cardinality
                       :value (parse-ids-value (child node "value"))
                       :system (parse-ids-value (child node "system"))}
      :material {:type :material :cardinality cardinality
                 :value (parse-ids-value (child node "value"))}
      :part-of {:type :part-of :cardinality cardinality
                :relation (some-> (attribute node "relation") keyword)
                :entity (parse-entity (child node "entity"))})))

(defn read-xml
  "Parse buildingSMART IDS 1.0 XML without resolving DTDs or external entities."
  [xml]
  (let [root (.getDocumentElement (secure-document xml))
        info (child root "info")
        specifications-node (child root "specifications")]
    (ids/document
     {:title (text (child info "title"))
      :version (text (child info "version"))
      :author (text (child info "author"))
      :specifications
      (mapv
       (fn [spec]
         (let [applicability (child spec "applicability")
               requirements (child spec "requirements")
               min-occurs (or (some-> (attribute applicability "minOccurs") parse-number) 1)
               max-value (attribute applicability "maxOccurs")]
           {:name (attribute spec "name")
            :ifc-versions (set (string/split (attribute spec "ifcVersion") #"\s+"))
            :min-occurs min-occurs
            :max-occurs (cond
                          (nil? max-value) 1
                          (= "unbounded" max-value) :unbounded
                          :else (parse-number max-value))
            :applicability (mapv #(parse-facet % false)
                                 (element-children applicability))
            :requirements (mapv #(parse-facet % true)
                                (element-children requirements))}))
       (children specifications-node "specification"))})))

(defn- escape-xml [value]
  (-> (str value) (string/replace "&" "&amp;") (string/replace "<" "&lt;")
      (string/replace ">" "&gt;") (string/replace "\"" "&quot;")
      (string/replace "'" "&apos;")))

(def restriction-tags
  {:min-inclusive "minInclusive" :max-inclusive "maxInclusive"
   :min-exclusive "minExclusive" :max-exclusive "maxExclusive"
   :min-length "minLength" :max-length "maxLength"})

(defn- write-ids-value [tag value]
  (when value
    (let [value (ids/restriction value)]
      (str "<" tag ">"
           (if (and (contains? value :value) (= 1 (count value)))
             (str "<simpleValue>" (escape-xml (:value value)) "</simpleValue>")
             (str "<xs:restriction base=\"xs:string\">"
                  (apply str (map #(str "<xs:enumeration value=\"" (escape-xml %)
                                        "\"/>") (sort-by str (:values value))))
                  (apply str
                         (map #(str "<xs:pattern value=\"" (escape-xml %) "\"/>")
                              (cond-> (vec (:patterns value)) (:pattern value)
                                (conj (:pattern value)))))
                  (apply str
                         (keep (fn [[key xml-name]]
                                 (when (contains? value key)
                                   (str "<xs:" xml-name " value=\""
                                        (escape-xml (get value key)) "\"/>")))
                               restriction-tags))
                  "</xs:restriction>"))
           "</" tag ">"))))

(defn- cardinality-attribute [facet requirement?]
  (when requirement?
    (str " cardinality=\"" (name (:cardinality facet)) "\"")))

(declare write-facet)

(defn- write-entity-body [facet]
  (str (write-ids-value "name" (:name facet))
       (write-ids-value "predefinedType" (:predefined-type facet))))

(defn- write-facet [facet requirement?]
  (let [cardinality (cardinality-attribute facet requirement?)]
    (case (:type facet)
      :entity (str "<entity>" (write-entity-body facet) "</entity>")
      :attribute
      (str "<attribute" cardinality ">"
           (write-ids-value "name" (or (:name-restriction facet) (:name facet)))
           (write-ids-value "value" (:value facet)) "</attribute>")
      :property
      (str "<property" cardinality
           (when-let [data-type (:data-type facet)]
             (str " dataType=\"" (string/upper (name data-type)) "\"")) ">"
           (write-ids-value "propertySet" (:property-set facet))
           (write-ids-value "baseName" (:name facet))
           (write-ids-value "value" (:value facet)) "</property>")
      :classification
      (str "<classification" cardinality ">"
           (write-ids-value "value" (:value facet))
           (write-ids-value "system" (:system facet)) "</classification>")
      :material
      (str "<material" cardinality ">" (write-ids-value "value" (:value facet))
           "</material>")
      :part-of
      (str "<partOf" cardinality
           (when-let [relation (:relation facet)]
             (str " relation=\"" (name relation) "\"")) "><entity>"
           (write-entity-body (:entity facet)) "</entity></partOf>"))))

(defn write-xml
  "Serialize the portable contract as buildingSMART IDS 1.0 XML."
  [document]
  (str "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
       "<ids xmlns=\"" namespace-uri "\" xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">"
       "<info><title>" (escape-xml (:ids/title document)) "</title>"
       (when-let [version (:ids/version document)]
         (str "<version>" (escape-xml version) "</version>"))
       (when-let [author (:ids/author document)]
         (str "<author>" (escape-xml author) "</author>"))
       "</info><specifications>"
       (apply str
              (map (fn [spec]
                     (str "<specification name=\""
                          (escape-xml (:ids.specification/name spec))
                          "\" ifcVersion=\""
                          (escape-xml (string/join " "
                                                   (sort (:ids.specification/ifc-versions spec))))
                          "\"><applicability minOccurs=\""
                          (:ids.specification/min-occurs spec) "\" maxOccurs=\""
                          (if (= :unbounded (:ids.specification/max-occurs spec))
                            "unbounded" (:ids.specification/max-occurs spec)) "\">"
                          (apply str (map #(write-facet % false)
                                          (:ids.specification/applicability spec)))
                          "</applicability><requirements>"
                          (apply str (map #(write-facet % true)
                                          (:ids.specification/requirements spec)))
                          "</requirements></specification>"))
                   (:ids/specifications document)))
       "</specifications></ids>"))
