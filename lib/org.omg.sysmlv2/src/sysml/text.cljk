(ns sysml.text
  "A deliberately scoped parser/emitter for the normative SysML v2 textual
  notation represented by `sysml.model`.

  Supported concrete syntax:
  - packages;
  - part/attribute/port/item/action/connection/interface/requirement
    Definitions and typed Usages;
  - nested Definitions/Usages;
  - Definition specialization (`:>`);
  - qualified names and conjugated Usage types (`~Type`);
  - Usage subsetting/redefinition (`:>`/`:>>`/`redefines`);
  - fixed, range and unbounded Usage multiplicity (`[n]`, `[n..m]`, `[*]`);
  - public/private/protected imports;
  - typed connection/interface Usage ends (`connect a to b`).

  Syntax outside the semantic subset is retained as explicit
  `:opaque-syntax` elements with `:sysml/raw-tokens`, so behavior/state/
  transition/expression/metadata constructs can round-trip without being
  silently discarded. This is not a claim to semantically interpret the
  complete OMG grammar."
  (:require [kotoba.lang.text :as str]
            [sysml.kerml :as kerml]
            [sysml.model :as sm]))

(def ^:private definition-builders
  {"part" sm/part-definition
   "attribute" sm/attribute-definition
   "port" sm/port-definition
   "item" sm/item-definition
   "action" sm/action-definition
   "connection" sm/connection-definition
   "interface" sm/interface-definition
   "requirement" sm/requirement-definition})

(def ^:private usage-builders
  {"part" sm/part-usage
   "attribute" sm/attribute-usage
   "port" sm/port-usage
   "item" sm/item-usage
   "action" sm/action-usage
   "requirement" sm/requirement-usage})

(def ^:private kind->keyword
  {"part" "part"
   "attribute" "attribute"
   "port" "port"
   "item" "item"
   "action" "action"
   "connection" "connection"
   "interface" "interface"
   "requirement" "requirement"})

(defn- tokenize [text]
  (->> (re-seq #"/\*[\s\S]*?\*/|//[^\r\n]*|\"(?:\\.|[^\"])*\"|::>|:>>|:>|::|\.\.|<=|>=|==|!=|->|\*\*|'(?:\\.|[^'])*'|[{};:\[\],~*]|[A-Za-z_][A-Za-z0-9_]*|[0-9]+(?:\.[0-9]+)?|\S" text)
       (remove #(or (str/starts-with? % "//")
                    (str/starts-with? % "/*")))
       vec))

(defn- parser-error [tokens index message]
  (throw (ex-info (str "sysml.text: " message)
                  {:token-index @index
                   :token (get tokens @index)
                   :near (subvec tokens @index (min (count tokens) (+ @index 6)))})))

(defn- peek-token [tokens index] (get tokens @index))
(defn- take-token! [tokens index]
  (let [token (peek-token tokens index)]
    (swap! index inc)
    token))
(defn- expect! [tokens index expected]
  (let [actual (take-token! tokens index)]
    (when-not (= expected actual)
      (parser-error tokens index (str "expected `" expected "`, got `" actual "`")))
    actual))

(defn- identifier? [token]
  (boolean
   (or (re-matches #"[A-Za-z_][A-Za-z0-9_]*" (or token ""))
       (re-matches #"'(?:\\.|[^'])*'" (or token "")))))

(defn- parse-name! [tokens index]
  (let [first-part (take-token! tokens index)]
    (when-not (identifier? first-part)
      (parser-error tokens index "expected identifier"))
    (loop [result first-part]
      (if (contains? #{"::" "."} (peek-token tokens index))
        (let [separator (take-token! tokens index)
              part (take-token! tokens index)]
            (when-not (or (identifier? part) (= "*" part) (= "**" part))
              (parser-error tokens index "expected qualified-name segment"))
            (recur (str result separator part)))
        result))))

(defn- unique-element [model owner element]
  (let [declared-name (:kerml/name element)]
    (if-not (sm/lookup model declared-name)
      element
      (let [base (str (or owner "__root") "::" declared-name)
            internal-name
            (loop [candidate base suffix 2]
              (if (sm/lookup model candidate)
                (recur (str base "#" suffix) (inc suffix))
                candidate))]
        (assoc element
               :kerml/name internal-name
               :sysml/declared-name declared-name)))))

(defn- add-owned! [model owner element]
  (let [element (unique-element @model owner element)]
    (swap! model sm/add-element element)
  (swap! model update-in [:sysml/source-order owner] (fnil conj [])
         (:kerml/name element))
    (when owner
      (if-let [owner-element (sm/lookup @model owner)]
        (swap! model sm/add-element (sm/nest owner-element (:kerml/name element)))
        (throw (ex-info "sysml.text: internal missing owner" {:owner owner}))))
    element))

(defn- parse-multiplicity! [tokens index element]
  (if (= "[" (peek-token tokens index))
    (do
      (take-token! tokens index)
      (let [lower-token (take-token! tokens index)
            [lower upper]
            (cond
              (= "*" lower-token) [0 :*]
              (re-matches #"[0-9]+" (or lower-token ""))
              (let [lower #?(:clj (Long/parseLong lower-token)
                             :cljs (js/parseInt lower-token 10))]
                (if (= ".." (peek-token tokens index))
                  (do
                    (take-token! tokens index)
                    (let [upper-token (take-token! tokens index)]
                      [lower (if (= "*" upper-token)
                               :*
                               (if (re-matches #"[0-9]+" (or upper-token ""))
                                 #?(:clj (Long/parseLong upper-token)
                                    :cljs (js/parseInt upper-token 10))
                                 (parser-error tokens index "expected integer or `*` upper multiplicity")))]))
                  [lower lower]))
              :else (parser-error tokens index "expected multiplicity integer or `*`"))]
        (expect! tokens index "]")
        (kerml/with-multiplicity element (kerml/multiplicity lower upper))))
    element))

(defn- parse-connection-end! [tokens index]
  (let [cardinality
        (when (= "[" (peek-token tokens index))
          (take-token! tokens index)
          (loop [parts []]
            (let [token (take-token! tokens index)]
              (cond
                (nil? token) (parser-error tokens index "unterminated connection-end cardinality")
                (= "]" token) (str "[" (str/join " " parts) "]")
                :else (recur (conj parts token))))))
        reference (parse-name! tokens index)
        reference (if (= "::>" (peek-token tokens index))
                    (do (take-token! tokens index)
                        (str reference " ::> " (parse-name! tokens index)))
                    reference)]
    (str (when cardinality (str cardinality " ")) reference)))

(declare parse-block!)

(defn- take-element-tail! [tokens index]
  (loop [result []]
    (let [token (peek-token tokens index)]
      (cond
        (nil? token) (parser-error tokens index "unterminated element")
        (contains? #{";" "{"} token) result
        :else (do (take-token! tokens index)
                  (recur (conj result token)))))))

(defn- finish-element! [tokens index model owner element]
  (let [element (parse-multiplicity! tokens index element)
        raw-tail (take-element-tail! tokens index)
        element (cond-> element
                  (seq raw-tail) (assoc :sysml/raw-tail raw-tail))
        element (add-owned! model owner element)]
    (case (peek-token tokens index)
      ";" (take-token! tokens index)
      "{" (do (take-token! tokens index)
              (parse-block! tokens index model (:kerml/name element))
              (when (= ";" (peek-token tokens index)) (take-token! tokens index)))
      (parser-error tokens index "expected `;` or element body"))
    element))

(defn- capture-opaque-tokens! [tokens index]
  (loop [result [] depth 0 saw-block? false]
    (let [token (peek-token tokens index)]
      (cond
        (nil? token)
        (if (seq result)
          result
          (parser-error tokens index "unexpected end of input"))

        (and (= "}" token) (zero? depth))
        (if (seq result)
          result
          (parser-error tokens index "unexpected block terminator"))

        (and (= ";" token) (zero? depth))
        (do (take-token! tokens index) (conj result token))

        (= "{" token)
        (do (take-token! tokens index)
            (recur (conj result token) (inc depth) true))

        (= "}" token)
        (let [next-depth (dec depth)
              result* (conj result (take-token! tokens index))]
          (if (and saw-block? (zero? next-depth))
            (if (= ";" (peek-token tokens index))
              (conj result* (take-token! tokens index))
              result*)
            (recur result* next-depth saw-block?)))

        :else
        (do (take-token! tokens index)
            (recur (conj result token) depth saw-block?))))))

(defn- parse-opaque! [tokens index model owner]
  (let [raw (capture-opaque-tokens! tokens index)
        nm (str "__opaque_" (count (sm/elements @model)))
        element (merge (kerml/feature nm)
                       {:sysml/element-kind :opaque-syntax
                        :sysml/raw-tokens raw})]
    (add-owned! model owner element)))

(defn- parse-perform! [tokens index model owner]
  (let [raw (capture-opaque-tokens! tokens index)
        statement (vec (butlast raw))
        body-index (first (keep-indexed #(when (= "{" %2) %1) statement))
        redefine-index (first (keep-indexed #(when (= "redefines" %2) %1) statement))
        target-end (or redefine-index body-index (count statement))
        target-tokens (cond-> (subvec statement 1 target-end)
                        (= "action" (second statement)) (subvec 1))
        target (apply str target-tokens)
        declared-name (last (str/split target #"::|\."))
        redefines (when redefine-index (get statement (inc redefine-index)))
        element (cond-> (sm/action-usage declared-name nil)
                  (seq target) (assoc :sysml/performs target)
                  redefines (assoc :sysml/redefines redefines)
                  true (assoc :sysml/raw-tokens raw))]
    (add-owned! model owner element)))

(defn- parse-package! [tokens index model owner]
  (expect! tokens index "package")
  (let [nm (parse-name! tokens index)
        package-element (add-owned! model owner (sm/package nm))
        internal-name (:kerml/name package-element)]
    (expect! tokens index "{")
    (parse-block! tokens index model internal-name)
    (when (= ";" (peek-token tokens index)) (take-token! tokens index))))

(defn- parse-definition! [tokens index model owner kind]
  (expect! tokens index "def")
  (let [nm (parse-name! tokens index)
        builder (get definition-builders kind)
        general (when (= ":>" (peek-token tokens index))
                  (take-token! tokens index)
                  (parse-name! tokens index))
        element (finish-element! tokens index model owner (builder nm))]
    (when general
      (swap! model sm/specialize (:kerml/name element) general))))

(defn- parse-usage! [tokens index model owner kind]
  (let [nm (parse-name! tokens index)
        relation-token (when (contains? #{":" ":>" ":>>"} (peek-token tokens index))
                         (take-token! tokens index))
        conjugated? (when (and (= ":" relation-token) (= "~" (peek-token tokens index)))
                      (take-token! tokens index)
                      true)
        relation-name (when relation-token (parse-name! tokens index))
        redefine-name (when (= "redefines" (peek-token tokens index))
                        (take-token! tokens index)
                        (parse-name! tokens index))
        definition-name (when (= ":" relation-token) relation-name)
        subsets-name (when (= ":>" relation-token) relation-name)
        redefines-name (or (when (= ":>>" relation-token) relation-name) redefine-name)
        connection? (contains? #{"connection" "interface"} kind)
        ends (when connection?
               (when (= "connect" (peek-token tokens index))
                 (take-token! tokens index)
                 (let [first-end (parse-connection-end! tokens index)]
                   (loop [result [first-end]]
                     (if (= "to" (peek-token tokens index))
                       (do (take-token! tokens index)
                           (recur (conj result (parse-connection-end! tokens index))))
                       result)))))
        element (if connection?
                  ((if (= kind "connection") sm/connection-usage sm/interface-usage)
                   nm definition-name (or ends []))
                  ((get usage-builders kind) nm definition-name))
        element (cond-> element
                  conjugated? (assoc :sysml/conjugated? true)
                  subsets-name (assoc :sysml/subsets subsets-name)
                  redefines-name (assoc :sysml/redefines redefines-name))
        stored-element (finish-element! tokens index model owner element)]
    (when subsets-name
      (swap! model sm/specialize (:kerml/name stored-element) subsets-name))))

(defn- parse-import! [tokens index model owner]
  (let [visibility (when (contains? #{"public" "private" "protected"} (peek-token tokens index))
                     (take-token! tokens index))]
    (expect! tokens index "import")
    (let [target (parse-name! tokens index)]
      (expect! tokens index ";")
      (swap! model update :sysml/imports (fnil conj [])
             (cond-> {:sysml/import-target target}
               visibility (assoc :sysml/visibility (keyword visibility))
               owner (assoc :sysml/import-owner owner))))))

(defn- parse-block! [tokens index model owner]
  (loop []
    (let [token (peek-token tokens index)]
      (cond
        (nil? token) (when owner (parser-error tokens index "unterminated element body"))
        (= "}" token) (take-token! tokens index)
        (= "package" token) (do (parse-package! tokens index model owner) (recur))
        (= "perform" token) (do (parse-perform! tokens index model owner) (recur))
        (or (= "import" token)
            (and (contains? #{"public" "private" "protected"} token)
                 (= "import" (get tokens (inc @index)))))
        (do (parse-import! tokens index model owner) (recur))
        (contains? kind->keyword token)
        (let [next-token (get tokens (inc @index))]
          (if (or (= "def" next-token)
                  (and (identifier? next-token)
                       (not (contains? #{"redefines" "subsets" "references"}
                                       next-token))))
            (do
              (take-token! tokens index)
              (if (= "def" (peek-token tokens index))
                (parse-definition! tokens index model owner token)
                (parse-usage! tokens index model owner token))
              (recur))
            (do (parse-opaque! tokens index model owner) (recur))))
        :else (do (parse-opaque! tokens index model owner) (recur))))))

(defn parse-string
  "Parse the supported SysML v2 textual subset into a `sysml.model` model.
  An optional model name controls only the EDN container name."
  ([text] (parse-string text "sysml-text-model"))
  ([text model-name]
   (let [tokens (tokenize text)
         index (atom 0)
         model (atom (sm/model model-name))]
     (parse-block! tokens index model nil)
     @model)))

(def ^:private element-kind->syntax
  {:part-definition ["part" true]
   :attribute-definition ["attribute" true]
   :port-definition ["port" true]
   :item-definition ["item" true]
   :action-definition ["action" true]
   :connection-definition ["connection" true]
   :interface-definition ["interface" true]
   :requirement-definition ["requirement" true]
   :part-usage ["part" false]
   :attribute-usage ["attribute" false]
   :port-usage ["port" false]
   :item-usage ["item" false]
   :action-usage ["action" false]
   :connection-usage ["connection" false]
   :interface-usage ["interface" false]
   :requirement-usage ["requirement" false]})

(defn- specialization-general [model nm]
  (some (fn [rel]
          (when (and (= :specialization (:kerml/kind rel))
                     (= nm (:kerml/specific rel)))
            (:kerml/general rel)))
        (:kerml/relationships model)))

(defn emit-string
  "Emit the represented compatibility subset as deterministic SysML v2
  text. Throws when the model contains an element kind this subset cannot
  represent."
  [model]
  (let [owned (into #{} (mapcat #(get % :sysml/nested #{})) (sm/elements model))
        top-level (or (seq (get-in model [:sysml/source-order nil]))
                      (sort (remove owned (map :kerml/name (sm/elements model)))))]
    (letfn [(indent [level] (apply str (repeat level "  ")))
            (tokens->text [tokens] (str/join " " tokens))
            (emit-import [import level]
              (str (indent level)
                   (when-let [visibility (:sysml/visibility import)]
                     (str (name visibility) " "))
                   "import " (:sysml/import-target import) ";\n"))
            (emit-element [nm level]
              (let [element (sm/lookup model nm)
                    kind (:sysml/element-kind element)
                    display-name (:sysml/declared-name element nm)
                    nested (or (seq (get-in model [:sysml/source-order nm]))
                               (sort (:sysml/nested element #{})))]
                (cond
                  (seq (:sysml/raw-tokens element))
                  (str (indent level) (tokens->text (:sysml/raw-tokens element)) "\n")

                  (= :package kind)
                  (str (indent level) "package " display-name " {\n"
                       (apply str
                              (map #(emit-import % (inc level))
                                   (filter #(= nm (:sysml/import-owner %))
                                           (:sysml/imports model))))
                       (apply str (map #(emit-element % (inc level)) nested))
                       (indent level) "}\n")

                  :else
                  (let [[word definition?] (get element-kind->syntax kind)]
                    (when-not word
                      (throw (ex-info "sysml.text: element kind is outside the textual subset"
                                      {:name nm :kind kind})))
                    (let [general (and definition? (specialization-general model nm))
                          ends (:sysml/ends element)
                          mult (:kerml/multiplicity element)
                          fixed-mult (when (and mult (= (:kerml/lower mult) (:kerml/upper mult)))
                                       (:kerml/lower mult))
                          head (str (indent level) word
                                    (if definition?
                      (str " def " display-name (when general (str " :> " general)))
                                      (str " " display-name
                                           (cond
                                             (:sysml/subsets element) (str " :> " (:sysml/subsets element))
                                             (:sysml/definition element)
                                             (str " : " (when (:sysml/conjugated? element) "~")
                                                  (:sysml/definition element)
                                                  (when (:sysml/redefines element)
                                                    (str " redefines " (:sysml/redefines element))))
                                             (:sysml/redefines element) (str " :>> " (:sysml/redefines element))
                                             :else "")
                                           (when (seq ends)
                                             (str " connect " (str/join " to " ends)))
                                           (when mult
                                             (str " ["
                                                  (if (= :* (:kerml/upper mult))
                                                    (if (zero? (:kerml/lower mult))
                                                      "*"
                                                      (str (:kerml/lower mult) "..*"))
                                                    (if (= (:kerml/lower mult) (:kerml/upper mult))
                                                      fixed-mult
                                                      (str (:kerml/lower mult) ".." (:kerml/upper mult))))
                                                  "]")))))
                          head (str head
                                    (when-let [raw-tail (seq (:sysml/raw-tail element))]
                                      (str " " (tokens->text raw-tail))))]
                      (if (seq nested)
                        (str head " {\n"
                             (apply str (map #(emit-element % (inc level)) nested))
                             (indent level) "}\n")
                        (str head ";\n")))))))]
      (apply str
             (concat
              (map #(emit-import % 0)
                   (filter #(nil? (:sysml/import-owner %)) (:sysml/imports model)))
              (map #(emit-element % 0) top-level))))))
