(ns icd10.claml
  "A parser (and, for round-trip testing, a serializer) for the **ClaML**
  (Classification Markup Language, ISO/CEN 12610-family) XML format WHO and
  other classification bodies use to DISTRIBUTE released classifications —
  so a licensee who has obtained their own copy of an actual WHO ICD-10
  ClaML release can load it with this. This file does not ship, embed, or
  hardcode any such release: no `Class` entries, no `Rubric`/`Label` text
  for any real disease, nothing that could stand in for the tabular list.
  See README for exactly where that line is drawn.

  Built on `kotoba-lang/xml` (a workspace-local dependency, already used
  elsewhere in this workspace for this exact hiccup-shaped
  parse/serialize pattern, e.g. by `org-ietf-netconf`) rather than a new
  XML parser — this repo's job is the ClaML SCHEMA, not XML syntax itself."
  (:require [xml.parse :as xp]
            [xml.core :as xc]))

;; ---------------------------------------------------------------------
;; parsing: ClaML text -> EDN
;; ---------------------------------------------------------------------

(defn- rubric->edn [rubric-el]
  (let [label-el (xp/find-child rubric-el :Label)]
    {:kind (xp/el-attr rubric-el "kind")
     :text (when label-el (xp/el-text label-el))}))

(defn- class-el->edn [class-el]
  {:code (xp/el-attr class-el "code")
   :kind (xp/el-attr class-el "kind")
   :rubrics (mapv rubric->edn (xp/find-children class-el :Rubric))
   :super-classes (mapv #(xp/el-attr % "code") (xp/find-children class-el :SuperClass))
   :sub-classes (mapv #(xp/el-attr % "code") (xp/find-children class-el :SubClass))})

(defn parse
  "Parses a ClaML XML document into
  `{:title str-or-nil :classes [{:code :kind :rubrics [{:kind :text}...]
                                  :super-classes [code...] :sub-classes [code...]}
                                 ...]}`.
  Returns `[:ok doc]` or a named `[:error :icd10/... detail]` — never
  throws, including on XML that fails to parse at all or whose root
  element is not `<ClaML>`."
  [xml-text]
  (try
    (let [root (xp/parse xml-text)]
      (cond
        (nil? root)
        [:error :icd10/claml-empty-document {}]

        (not= :ClaML (xp/el-tag root))
        [:error :icd10/claml-unexpected-root {:got (xp/el-tag root)}]

        :else
        [:ok {:title (some-> (xp/find-child root :Title) xp/el-text)
              :classes (mapv class-el->edn (xp/find-all root :Class))}]))
    (catch #?(:clj Exception :cljs :default) e
      [:error :icd10/claml-malformed-xml
       {:message #?(:clj (.getMessage ^Exception e) :cljs (.-message e))}])))

(defn classes-by-code
  "Convenience index over a parsed document's :classes, keyed by :code."
  [{:keys [classes]}]
  (into {} (map (fn [c] [(:code c) c])) classes))

;; ---------------------------------------------------------------------
;; serializing: EDN -> ClaML hiccup -> XML text (round-trip direction, and
;; a genuine use for a caller assembling/editing ClaML rather than only
;; reading a release someone else produced)
;; ---------------------------------------------------------------------

(defn- rubric->hiccup [{:keys [kind text]}]
  [:Rubric (cond-> {} kind (assoc "kind" kind)) [:Label text]])

(defn class-entry->hiccup [{:keys [code kind rubrics super-classes sub-classes]}]
  (into [:Class (cond-> {"code" code} kind (assoc "kind" kind))]
        (concat (map rubric->hiccup rubrics)
                (map (fn [c] [:SuperClass {"code" c}]) super-classes)
                (map (fn [c] [:SubClass {"code" c}]) sub-classes))))

(defn document->hiccup [{:keys [title classes]}]
  (into [:ClaML]
        (concat (when title [[:Title title]])
                (map class-entry->hiccup classes))))

(defn document-str
  "Serializes a parsed (or hand-built) ClaML document map back to XML
  text. Uses `xml.core/compact`, not `xml.core/xml` -- ClaML's `<Label>`/
  `<Title>` element content is a text VALUE, not further markup, and
  `xml.core/xml`'s indentation becomes part of that value (its own
  docstring says exactly this); caught by this repo's own round-trip test,
  which failed with every label growing embedded newlines and leading
  whitespace until this was fixed to use `compact`."
  [doc]
  (xc/compact (document->hiccup doc)))
