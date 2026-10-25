(ns materialx.core
  "MaterialX as data — 'hiccup for materials'. MaterialX (the open material/shader-graph interchange,
   used across DCCs and renderers) is XML, so it is the most literal hiccup of all: an element is
   `[:tag {attrs} & children]`. This wraps the xml.core emitter with the `<?xml?>` declaration and the
   `<materialx>` root so a node graph / surface material is composable data you fork and diff. Extends
   the GPU/shading axis (pairs with kotoba.wgsl / kotoba.spirv). `.cljc`, built on xml.core.

     [:nodegraph {:name \"NG\"}
       [:constant {:name \"c\" :type \"color3\"} [:input {:name \"value\" :type \"color3\" :value \"1, 0, 0\"}]]
       [:output {:name \"out\" :type \"color3\" :nodename \"c\"}]]
     (materialx {:version \"1.38\"} nodegraph surfacematerial…)  ⇒ a full <?xml?> <materialx> document

   ADR-0048 §4 (com-junkawasaki/root) extends this from a bare XML string builder into a library
   that actually knows the MaterialX standard node library:

   - `node-defs` — a curated table of real MaterialX standard nodedefs (real port names / types /
     defaults, sourced from AcademySoftwareFoundation/MaterialX `libraries/bxdf/standard_surface.mtlx`
     + `libraries/stdlib/stdlib_defs.mtlx`), scoped to a game-engine PBR pipeline (uber-shader,
     texture sampling, normal mapping, basic math combinators, geometric inputs) — not the full spec.
   - `parse-xml` / `materialx->node-graph` — a dependency-free XML parser (a real subset: elements,
     attributes, comments, the `<?xml?>` decl; no CDATA/namespaces/DOCTYPE) and a MaterialX-aware
     reader that turns a `.mtlx` document into an EDN node-graph (nodes keyed by name, `:type`
     resolved against `node-defs` when recognized, inputs as literals or connections).
   - `node-graph->materialx` — the inverse: an EDN node-graph → a full `.mtlx` XML document, via the
     `materialx` emitter above (so emission stays node-def-aware hiccup, not raw XML).
   - `materialx-node-graph->render-ir-material` / `render-ir-material->materialx-node-graph` — bridge
     to kami-engine's EDN render-IR `:materials` vocabulary (ADR-0044), `:pbr` model only — see their
     docstrings for exactly what is and isn't covered (MToon has no MaterialX standard-node
     equivalent and is refused, not faked)."
  (:require [xml.core :as xml]
            [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Emission (pre-existing)
;; ---------------------------------------------------------------------------

(defn materialx
  "A MaterialX document: optional {:version …} (defaults 1.38) then top-level elements as hiccup."
  [opts & body]
  (str "<?xml version=\"1.0\"?>\n"
       (xml/xml (into [:materialx (merge {:version "1.38"} opts)] body))))

(defn value
  "Format a MaterialX value attribute: a vector → comma-joined (1, 0, 0); else str."
  [v] (if (vector? v) (str/join ", " (map str v)) (str v)))

;; ---------------------------------------------------------------------------
;; Standard node-definition table (ADR-0048 §4)
;;
;; Real nodedef ids, node names, port names/types/defaults — verified against the actual
;; AcademySoftwareFoundation/MaterialX source (2026-07, `main` branch):
;;   libraries/bxdf/standard_surface.mtlx      (ND_standard_surface_surfaceshader_100)
;;   libraries/stdlib/stdlib_defs.mtlx         (image / normalmap / multiply / add / mix /
;;                                              position / normal / texcoord)
;; This is a curated PBR-relevant subset, not the full spec: overloaded nodes (image, multiply,
;; add, mix, normalmap) ship only the float/color3/vector3 variants most useful to a game-engine
;; material pipeline (color4/vector2/vector4/matrix33/matrix44/integer variants are out of scope —
;; see the README/ADR for the full "not covered" list).
;; ---------------------------------------------------------------------------

(def node-defs
  "nodedef-id (keyword, matches the real MaterialX `ND_*` name) → {:node :output-type :nodegroup
   :doc :inputs [{:name :type :default}] :outputs [{:name :type}]}."
  {:ND_standard_surface_surfaceshader
   {:node "standard_surface" :output-type "surfaceshader" :nodegroup "pbr"
    :doc "Autodesk Standard Surface — the shipped PBR uber-shader (ND_standard_surface_surfaceshader_100)."
    :inputs [{:name "base" :type "float" :default 0.8}
             {:name "base_color" :type "color3" :default [1.0 1.0 1.0]}
             {:name "diffuse_roughness" :type "float" :default 0.0}
             {:name "metalness" :type "float" :default 0.0}
             {:name "specular" :type "float" :default 1.0}
             {:name "specular_color" :type "color3" :default [1.0 1.0 1.0]}
             {:name "specular_roughness" :type "float" :default 0.2}
             {:name "specular_IOR" :type "float" :default 1.5}
             {:name "specular_anisotropy" :type "float" :default 0.0}
             {:name "specular_rotation" :type "float" :default 0.0}
             {:name "transmission" :type "float" :default 0.0}
             {:name "transmission_color" :type "color3" :default [1.0 1.0 1.0]}
             {:name "transmission_depth" :type "float" :default 0.0}
             {:name "transmission_scatter" :type "color3" :default [0.0 0.0 0.0]}
             {:name "transmission_scatter_anisotropy" :type "float" :default 0.0}
             {:name "transmission_dispersion" :type "float" :default 0.0}
             {:name "transmission_extra_roughness" :type "float" :default 0.0}
             {:name "subsurface" :type "float" :default 0.0}
             {:name "subsurface_color" :type "color3" :default [1.0 1.0 1.0]}
             {:name "subsurface_radius" :type "color3" :default [1.0 1.0 1.0]}
             {:name "subsurface_scale" :type "float" :default 1.0}
             {:name "subsurface_anisotropy" :type "float" :default 0.0}
             {:name "sheen" :type "float" :default 0.0}
             {:name "sheen_color" :type "color3" :default [1.0 1.0 1.0]}
             {:name "sheen_roughness" :type "float" :default 0.3}
             {:name "coat" :type "float" :default 0.0}
             {:name "coat_color" :type "color3" :default [1.0 1.0 1.0]}
             {:name "coat_roughness" :type "float" :default 0.1}
             {:name "coat_anisotropy" :type "float" :default 0.0}
             {:name "coat_rotation" :type "float" :default 0.0}
             {:name "coat_IOR" :type "float" :default 1.5}
             {:name "coat_normal" :type "vector3" :defaultgeomprop "Nworld"}
             {:name "coat_affect_color" :type "float" :default 0.0}
             {:name "coat_affect_roughness" :type "float" :default 0.0}
             {:name "thin_film_thickness" :type "float" :default 0.0}
             {:name "thin_film_IOR" :type "float" :default 1.5}
             {:name "emission" :type "float" :default 0.0}
             {:name "emission_color" :type "color3" :default [1.0 1.0 1.0]}
             {:name "opacity" :type "color3" :default [1.0 1.0 1.0]}
             {:name "thin_walled" :type "boolean" :default false}
             {:name "normal" :type "vector3" :defaultgeomprop "Nworld"}
             {:name "tangent" :type "vector3" :defaultgeomprop "Tworld"}]
    :outputs [{:name "out" :type "surfaceshader"}]}

   :ND_image_float
   {:node "image" :output-type "float" :nodegroup "texture2d"
    :doc "Sample a single-channel image (ND_image_float)."
    :inputs [{:name "file" :type "filename" :default ""}
             {:name "layer" :type "string" :default ""}
             {:name "default" :type "float" :default 0.0}
             {:name "texcoord" :type "vector2" :defaultgeomprop "UV0"}
             {:name "uaddressmode" :type "string" :default "periodic"}
             {:name "vaddressmode" :type "string" :default "periodic"}
             {:name "filtertype" :type "string" :default "linear"}]
    :outputs [{:name "out" :type "float"}]}

   :ND_image_color3
   {:node "image" :output-type "color3" :nodegroup "texture2d"
    :doc "Sample a color image (ND_image_color3)."
    :inputs [{:name "file" :type "filename" :default ""}
             {:name "layer" :type "string" :default ""}
             {:name "default" :type "color3" :default [0.0 0.0 0.0]}
             {:name "texcoord" :type "vector2" :defaultgeomprop "UV0"}
             {:name "uaddressmode" :type "string" :default "periodic"}
             {:name "vaddressmode" :type "string" :default "periodic"}
             {:name "filtertype" :type "string" :default "linear"}]
    :outputs [{:name "out" :type "color3"}]}

   :ND_image_vector3
   {:node "image" :output-type "vector3" :nodegroup "texture2d"
    :doc "Sample a 3-channel data image, e.g. a tangent-space normal map (ND_image_vector3)."
    :inputs [{:name "file" :type "filename" :default ""}
             {:name "layer" :type "string" :default ""}
             {:name "default" :type "vector3" :default [0.0 0.0 0.0]}
             {:name "texcoord" :type "vector2" :defaultgeomprop "UV0"}
             {:name "uaddressmode" :type "string" :default "periodic"}
             {:name "vaddressmode" :type "string" :default "periodic"}
             {:name "filtertype" :type "string" :default "linear"}]
    :outputs [{:name "out" :type "vector3"}]}

   :ND_normalmap_float
   {:node "normalmap" :output-type "vector3" :nodegroup "math"
    :doc "Transform a tangent-space normal-map sample into world space (ND_normalmap_float — the
          `scale` input is a float; the real spec also has an ND_normalmap_vector2 variant with a
          per-axis vector2 scale, not implemented here)."
    :inputs [{:name "in" :type "vector3" :default [0.5 0.5 1.0]}
             {:name "scale" :type "float" :default 1.0}
             {:name "normal" :type "vector3" :defaultgeomprop "Nworld"}
             {:name "tangent" :type "vector3" :defaultgeomprop "Tworld"}
             {:name "bitangent" :type "vector3" :defaultgeomprop "Bworld"}]
    :outputs [{:name "out" :type "vector3"}]}

   :ND_multiply_float
   {:node "multiply" :output-type "float" :nodegroup "math"
    :inputs [{:name "in1" :type "float" :default 0.0} {:name "in2" :type "float" :default 1.0}]
    :outputs [{:name "out" :type "float"}]}
   :ND_multiply_color3
   {:node "multiply" :output-type "color3" :nodegroup "math"
    :inputs [{:name "in1" :type "color3" :default [0.0 0.0 0.0]} {:name "in2" :type "color3" :default [1.0 1.0 1.0]}]
    :outputs [{:name "out" :type "color3"}]}
   :ND_multiply_vector3
   {:node "multiply" :output-type "vector3" :nodegroup "math"
    :inputs [{:name "in1" :type "vector3" :default [0.0 0.0 0.0]} {:name "in2" :type "vector3" :default [1.0 1.0 1.0]}]
    :outputs [{:name "out" :type "vector3"}]}
   :ND_multiply_color3FA
   {:node "multiply" :output-type "color3" :nodegroup "math"
    :doc "color3 × float (ND_multiply_color3FA) — e.g. tinting a sampled texture by a scalar."
    :inputs [{:name "in1" :type "color3" :default [0.0 0.0 0.0]} {:name "in2" :type "float" :default 1.0}]
    :outputs [{:name "out" :type "color3"}]}

   :ND_add_float
   {:node "add" :output-type "float" :nodegroup "math"
    :inputs [{:name "in1" :type "float" :default 0.0} {:name "in2" :type "float" :default 0.0}]
    :outputs [{:name "out" :type "float"}]}
   :ND_add_color3
   {:node "add" :output-type "color3" :nodegroup "math"
    :inputs [{:name "in1" :type "color3" :default [0.0 0.0 0.0]} {:name "in2" :type "color3" :default [0.0 0.0 0.0]}]
    :outputs [{:name "out" :type "color3"}]}
   :ND_add_vector3
   {:node "add" :output-type "vector3" :nodegroup "math"
    :inputs [{:name "in1" :type "vector3" :default [0.0 0.0 0.0]} {:name "in2" :type "vector3" :default [0.0 0.0 0.0]}]
    :outputs [{:name "out" :type "vector3"}]}

   :ND_mix_float
   {:node "mix" :output-type "float" :nodegroup "compositing"
    :inputs [{:name "fg" :type "float" :default 0.0} {:name "bg" :type "float" :default 0.0}
             {:name "mix" :type "float" :default 0.0}]
    :outputs [{:name "out" :type "float"}]}
   :ND_mix_color3
   {:node "mix" :output-type "color3" :nodegroup "compositing"
    :inputs [{:name "fg" :type "color3" :default [0.0 0.0 0.0]} {:name "bg" :type "color3" :default [0.0 0.0 0.0]}
             {:name "mix" :type "float" :default 0.0}]
    :outputs [{:name "out" :type "color3"}]}
   :ND_mix_vector3
   {:node "mix" :output-type "vector3" :nodegroup "compositing"
    :inputs [{:name "fg" :type "vector3" :default [0.0 0.0 0.0]} {:name "bg" :type "vector3" :default [0.0 0.0 0.0]}
             {:name "mix" :type "float" :default 0.0}]
    :outputs [{:name "out" :type "vector3"}]}

   :ND_position_vector3
   {:node "position" :output-type "vector3" :nodegroup "geometric"
    :inputs [{:name "space" :type "string" :default "object"}]
    :outputs [{:name "out" :type "vector3"}]}
   :ND_normal_vector3
   {:node "normal" :output-type "vector3" :nodegroup "geometric"
    :inputs [{:name "space" :type "string" :default "object"}]
    :outputs [{:name "out" :type "vector3"}]}
   :ND_texcoord_vector2
   {:node "texcoord" :output-type "vector2" :nodegroup "geometric"
    :inputs [{:name "index" :type "integer" :default 0}]
    :outputs [{:name "out" :type "vector2"}]}})

(def ^:private node-index
  "[node-name output-type] → nodedef-id, for resolving a parsed `<tag type=\"...\">` back to
   `node-defs`. Built once from the table above."
  (into {} (map (fn [[id {:keys [node output-type]}]] [[node output-type] id])) node-defs))

(defn resolve-nodedef
  "Look up the nodedef-id for a MaterialX node instance's tag name + declared output `type`
   attribute. Returns the keyword when recognized (one of `node-defs`'s keys); otherwise returns a
   raw passthrough map `{:node .. :type .. :unresolved? true}` — nodes outside this library's
   curated subset are preserved structurally rather than dropped (this org's \"no silent
   fallback\" convention: callers can see exactly what wasn't understood)."
  [node-name output-type]
  (or (get node-index [node-name output-type])
      {:node node-name :type output-type :unresolved? true}))

(defn- node-shape
  "nodedef (keyword or raw passthrough map) → [xml-tag-keyword output-type-string]."
  [type]
  (if (keyword? type)
    (let [{:keys [node output-type]} (get node-defs type)]
      [(keyword node) output-type])
    [(keyword (:node type)) (:type type)]))

(defn- port-default-type
  "Declared type of `port` on `nodedef-id`, from `node-defs` (used only as a fallback for
   hand-authored input maps that omit `:type`; parsed inputs always carry their own `:type`)."
  [nodedef-id port]
  (when (keyword? nodedef-id)
    (some #(when (= (:name %) port) (:type %)) (get-in node-defs [nodedef-id :inputs]))))

(defn port-default
  "Declared default value (or `:defaultgeomprop`, when the port has no plain default) of `port`
   on `nodedef-id`."
  [nodedef-id port]
  (when (keyword? nodedef-id)
    (some #(when (= (:name %) port) (if (contains? % :default) (:default %) (:defaultgeomprop %)))
          (get-in node-defs [nodedef-id :inputs]))))

;; ---------------------------------------------------------------------------
;; XML parsing — a small, dependency-free subset (ADR-0048 §4)
;;
;; No CDATA / namespaces / DOCTYPE / processing instructions beyond the `<?xml?>` declaration.
;; Real `.mtlx` files (hand-authored or DCC-exported) stay inside this subset in practice — they
;; are plain nested elements with quoted attributes, which is exactly the shape `xml.core/xml`
;; emits, so this parser is `xml.core`'s missing inverse.
;; ---------------------------------------------------------------------------

#?(:clj  (defn- parse-double* [s] (Double/parseDouble s))
   :cljs (defn- parse-double* [s] (js/parseFloat s)))
#?(:clj  (defn- parse-long* [s] (Long/parseLong s))
   :cljs (defn- parse-long* [s] (js/parseInt s 10)))

(defn- unescape-xml [s]
  (-> s
      (str/replace "&lt;" "<")
      (str/replace "&gt;" ">")
      (str/replace "&quot;" "\"")
      (str/replace "&apos;" "'")
      (str/replace "&amp;" "&")))

(defn- tag-name [t]
  (second (re-find #"^</?([A-Za-z_][\w:.\-]*)" t)))

(defn- parse-xml-attrs [t]
  (into {}
        (map (fn [[_ k v]] [(keyword k) (unescape-xml v)]))
        (re-seq #"([A-Za-z_][\w:.\-]*)\s*=\s*\"([^\"]*)\"" t)))

(defn- classify-tag [t]
  (cond (str/starts-with? t "</") :close
        (str/ends-with? t "/>")   :self
        :else                     :open))

(defn parse-xml
  "Parse an XML document string (this library's subset — see namespace doc) into a hiccup form
   `[:tag {attrs} & children]`, the same shape `xml.core/xml` emits. Returns the single root
   element (asserts open/close tag names match)."
  [xml-str]
  (let [stripped (-> xml-str
                      (str/replace #"(?s)<\?.*?\?>" "")
                      (str/replace #"(?s)<!--.*?-->" ""))
        tags (re-seq #"<[^>]+>" stripped)]
    (loop [tags tags
           stack (list {:tag nil :attrs {} :children []})]
      (if (empty? tags)
        (first (:children (first stack)))
        (let [t (first tags)
              nm (tag-name t)]
          (case (classify-tag t)
            :self
            (let [el [(keyword nm) (parse-xml-attrs t)]
                  top (first stack)]
              (recur (rest tags) (cons (update top :children conj el) (rest stack))))
            :open
            (recur (rest tags) (cons {:tag nm :attrs (parse-xml-attrs t) :children []} stack))
            :close
            (let [{:keys [tag attrs children]} (first stack)]
              (assert (= tag nm) (str "materialx.core/parse-xml: mismatched close tag </" nm "> for <" tag ">"))
              (let [el (into [(keyword tag) attrs] children)
                    parent (second stack)]
                (recur (rest tags) (cons (update parent :children conj el) (drop 2 stack)))))))))))

;; ---------------------------------------------------------------------------
;; XML hiccup ⇄ node-graph EDN (ADR-0048 §4)
;;
;; A node-graph doc: {:version .. :nodegraphs {name {:nodes {..} :outputs {..}}} :nodes {name node}
;; :materials {name {:surfaceshader node-name}}}
;; A node: {:type nodedef-id-or-raw :inputs {port-name input}}
;; An input: {:type "<materialx type string>" :value literal} | {:type .. :connect {:node name}} |
;;           {:type .. :connect {:nodegraph name :output name}}
;; ---------------------------------------------------------------------------

(defn- vector-type? [t] (contains? #{"color3" "color4" "vector2" "vector3" "vector4"} t))

(defn parse-mtlx-value
  "Parse a MaterialX attribute-value string per its declared `type` (\"1, 0, 0\" `color3` → [1.0
   0.0 0.0], \"true\" `boolean` → true, …). Unrecognized/string types pass through as text."
  [type-str s]
  (cond
    (nil? s) nil
    (vector-type? type-str) (mapv #(parse-double* (str/trim %)) (str/split s #","))
    (= type-str "boolean") (= s "true")
    (= type-str "integer") (parse-long* s)
    (= type-str "float") (parse-double* s)
    :else s))

(defn- parse-input-el [[_ attrs]]
  (let [{:keys [name type value nodename nodegraph output]} attrs]
    [name (cond-> {:type type}
            nodegraph (assoc :connect {:nodegraph nodegraph :output output})
            (and nodename (not nodegraph)) (assoc :connect {:node nodename})
            (and (some? value) (not nodename) (not nodegraph)) (assoc :value (parse-mtlx-value type value)))]))

(defn- parse-node-el [[tag attrs & children]]
  (let [node-name (name tag)
        out-type (:type attrs)
        nd-id (resolve-nodedef node-name out-type)
        inputs (into {} (map parse-input-el) (filter #(= :input (first %)) children))]
    [(:name attrs) {:type nd-id :inputs inputs}]))

(defn- parse-output-el [[_ attrs]]
  (let [{:keys [name type nodename nodegraph output]} attrs]
    [name {:type type
           :connect (if nodegraph {:nodegraph nodegraph :output output} {:node nodename})}]))

(defn- parse-nodegraph-el [[_ attrs & children]]
  (let [outs (filter #(= :output (first %)) children)
        nodes (remove #(= :output (first %)) children)]
    [(:name attrs) {:nodes (into {} (map parse-node-el) nodes)
                     :outputs (into {} (map parse-output-el) outs)}]))

(defn- parse-material-el [[_ attrs & children]]
  (let [ss-in (some #(when (and (= :input (first %)) (= "surfaceshader" (:name (second %)))) (second %)) children)]
    [(:name attrs) {:surfaceshader (:nodename ss-in)}]))

(defn materialx->node-graph
  "Parse a MaterialX XML document string into an EDN node-graph doc (see namespace doc for the
   shape). `:type` on each node is resolved against `node-defs` when recognized; nodes outside
   this library's curated subset (e.g. `<tiledimage>`, `<place2d>`) still parse structurally —
   they just carry a raw `{:node .. :type .. :unresolved? true}` in place of an `ND_*` keyword,
   so nothing outside this library's scope is silently dropped."
  [xml-str]
  (let [[tag attrs & children] (parse-xml xml-str)]
    (assert (= :materialx tag) "materialx.core/materialx->node-graph: not a <materialx> document")
    (reduce (fn [doc [ctag :as el]]
              (case ctag
                :nodegraph (let [[k v] (parse-nodegraph-el el)] (assoc-in doc [:nodegraphs k] v))
                :surfacematerial (let [[k v] (parse-material-el el)] (assoc-in doc [:materials k] v))
                (let [[k v] (parse-node-el el)] (assoc-in doc [:nodes k] v))))
            {:version (:version attrs) :nodegraphs {} :nodes {} :materials {}}
            children)))

(defn- input-hiccup [nodedef-id [port {v :value input-type :type input-connect :connect}]]
  (let [t (or input-type (port-default-type nodedef-id port))]
    [:input (merge {:name port :type t}
                    (cond
                      (:nodegraph input-connect) (select-keys input-connect [:nodegraph :output])
                      (:node input-connect) {:nodename (:node input-connect)}
                      :else {:value (value v)}))]))

(defn- node-hiccup [node-name {:keys [type inputs]}]
  (let [[tag out-type] (node-shape type)]
    (into [tag {:name node-name :type out-type}]
          (map #(input-hiccup type %) inputs))))

(defn- output-hiccup [out-name {:keys [type connect]}]
  (let [{:keys [node nodegraph output]} connect]
    [:output (merge {:name out-name :type type}
                     (if nodegraph {:nodegraph nodegraph :output output} {:nodename node}))]))

(defn- nodegraph-hiccup [ng-name {:keys [nodes outputs]}]
  (into [:nodegraph {:name ng-name}]
        (concat (map (fn [[n v]] (node-hiccup n v)) nodes)
                (map (fn [[o v]] (output-hiccup o v)) outputs))))

(defn- material-hiccup [mat-name {:keys [surfaceshader]}]
  [:surfacematerial {:name mat-name :type "material"}
   [:input {:name "surfaceshader" :type "surfaceshader" :nodename surfaceshader}]])

(defn node-graph->materialx
  "Emit a node-graph EDN doc (see namespace doc / `materialx->node-graph`) as a full MaterialX XML
   document, via the existing `materialx` hiccup emitter — this is the node-def-aware API the
   docstring above promises: callers build graphs from data (real port names/types, connections)
   instead of writing raw hiccup by hand."
  [{:keys [version nodegraphs nodes materials]}]
  (apply materialx (cond-> {} version (assoc :version version))
         (concat (map (fn [[n v]] (nodegraph-hiccup n v)) nodegraphs)
                 (map (fn [[n v]] (node-hiccup n v)) nodes)
                 (map (fn [[n v]] (material-hiccup n v)) materials))))

;; ---------------------------------------------------------------------------
;; render-IR bridge (ADR-0048 §4 ⇄ ADR-0044 EDN render-IR `:materials`)
;;
;; Covers **`:model :pbr` only**. VRM's MToon (`:model :mtoon` — shade color, outline, rim,
;; matcap) has no MaterialX standard-node equivalent; `render-ir-material->materialx-node-graph`
;; refuses non-`:pbr` inputs rather than fabricating a lossy MToon→standard_surface approximation.
;;
;; Texture recognition is pattern-based, not general dataflow analysis: a render-IR `-tex` field
;; round-trips only when the corresponding standard_surface input connects (directly, or via one
;; `nodegraph`/`output` hop) to a plain `ND_image_*` node (or, for `normal-tex`, to an
;; `ND_normalmap_float` whose own `in` connects to an `ND_image_*`). Graphs with intermediate
;; `mix`/`multiply`/`add` nodes between the texture and the shader input are not resolved to a URL
;; — the shader input's literal/default value is used instead. This is an explicit, documented
;; scope boundary, not a bug.
;; ---------------------------------------------------------------------------

(defn- find-node
  "Look up a node instance by name across the doc's top-level `:nodes` and every `:nodegraphs`
   scope (MaterialX name lookup for direct `nodename=` connections isn't a full scoping rule —
   this is the practical subset: unique names across the document)."
  [doc node-name]
  (or (get-in doc [:nodes node-name])
      (some #(get-in % [:nodes node-name]) (vals (:nodegraphs doc)))))

(defn- resolve-connect
  "Follow one `:connect` (direct node, or nodegraph+output — which itself may point at a further
   connection) down to the node instance it ultimately names."
  [doc connect]
  (cond
    (:node connect) (find-node doc (:node connect))
    (:nodegraph connect)
    (let [out (get-in doc [:nodegraphs (:nodegraph connect) :outputs (:output connect)])]
      (resolve-connect doc (:connect out)))))

(def ^:private image-nodedefs #{:ND_image_float :ND_image_color3 :ND_image_vector3})

(defn- image-file [node]
  (when (and node (image-nodedefs (:type node)))
    (get-in node [:inputs "file" :value])))

(defn- input-value
  "Literal value of `ss`'s `port` input, or (if it connects to a recognized `ND_image_*`) the
   texture file URL as a string, else the nodedef's declared default."
  [doc ss port]
  (if-let [in (get-in ss [:inputs port])]
    (cond
      (contains? in :value) (:value in)
      (:connect in) (or (image-file (resolve-connect doc (:connect in)))
                         (port-default (:type ss) port)))
    (port-default (:type ss) port)))

(defn- normal-tex-url
  "The one recognized normal-map pattern: standard_surface.normal → ND_normalmap_float.in →
   ND_image_*.file. Anything else (direct vector input, missing normalmap wrapper, …) → nil."
  [doc ss]
  (when-let [normal-in (get-in ss [:inputs "normal"])]
    (when-let [nm-node (resolve-connect doc (:connect normal-in))]
      (when (= :ND_normalmap_float (:type nm-node))
        (image-file (resolve-connect doc (:connect (get-in nm-node [:inputs "in"]))))))))

(defn materialx-node-graph->render-ir-material
  "Convert a parsed MaterialX node-graph doc (`materialx->node-graph`) into an ADR-0044 render-IR
   `:materials` entry — the `ND_standard_surface_surfaceshader` → `:pbr` path only (see namespace
   doc for exactly what's recognized). `material-name` is the `<surfacematerial>` name in `doc`;
   `id` is the render-IR material id (keyword) to assign the result."
  [doc material-name id]
  (let [{:keys [surfaceshader]} (get-in doc [:materials material-name])
        ss (find-node doc surfaceshader)]
    (when (nil? ss)
      (throw (ex-info "materialx.core/materialx-node-graph->render-ir-material: surfaceshader not found"
                       {:material material-name :surfaceshader surfaceshader})))
    (when (not= :ND_standard_surface_surfaceshader (:type ss))
      (throw (ex-info "materialx.core/materialx-node-graph->render-ir-material: only ND_standard_surface_surfaceshader converts to :pbr — no MaterialX standard-node equivalent exists for VRM MToon"
                       {:surfaceshader-type (:type ss)})))
    (let [in #(input-value doc ss %)
          base-color (in "base_color")
          emission (in "emission")
          emission-color (in "emission_color")
          normal-tex (normal-tex-url doc ss)]
      (cond-> {:id id :model :pbr}
        (string? base-color)      (assoc :base-tex base-color)
        (not (string? base-color)) (assoc :base base-color)
        true                      (assoc :metallic (in "metalness")
                                          :roughness (in "specular_roughness"))
        (string? emission-color)  (assoc :emissive-tex emission-color)
        (and (not (string? emission-color)) (number? emission) (pos? emission))
        (assoc :emissive (mapv #(* % emission) emission-color))
        normal-tex                (assoc :normal-tex normal-tex)
        (pos? (in "coat"))        (assoc :clearcoat (in "coat") :clearcoat-roughness (in "coat_roughness"))
        (pos? (in "transmission")) (assoc :transmission (in "transmission") :ior (in "specular_IOR"))
        (pos? (in "sheen"))       (assoc :sheen (in "sheen"))))))

(defn render-ir-material->materialx-node-graph
  "Inverse of `materialx-node-graph->render-ir-material`: an ADR-0044 render-IR `:materials` entry
   (`:model :pbr` only) → a MaterialX node-graph doc, emittable via `node-graph->materialx`.
   Throws on any other `:model` (`:mtoon`/`:unlit`) — VRM MToon's toon-shading inputs (shade
   color, outline, rim, matcap) have no MaterialX standard-node equivalent, and this function
   refuses to fabricate a lossy approximation rather than silently guessing one."
  [{:keys [id model base base-tex metallic roughness emissive emissive-tex normal-tex
           clearcoat clearcoat-roughness transmission ior sheen]
    :as mat}]
  (when (not= :pbr model)
    (throw (ex-info "materialx.core/render-ir-material->materialx-node-graph: only :pbr render-IR materials convert to MaterialX — MToon/unlit have no MaterialX standard-node equivalent"
                     {:material mat})))
  (let [id-str (name id)
        ss-name (str id-str "_SR")
        mat-name (str id-str "_Mat")
        ng-name (str id-str "_NG")
        tex-nodes (cond-> {}
                    base-tex (assoc "img_base" {:type :ND_image_color3 :inputs {"file" {:type "filename" :value base-tex}}})
                    normal-tex (-> (assoc "img_normal" {:type :ND_image_vector3 :inputs {"file" {:type "filename" :value normal-tex}}})
                                   (assoc "nm_normal" {:type :ND_normalmap_float :inputs {"in" {:type "vector3" :connect {:node "img_normal"}}}}))
                    emissive-tex (assoc "img_emissive" {:type :ND_image_color3 :inputs {"file" {:type "filename" :value emissive-tex}}}))
        outputs (cond-> {}
                  base-tex (assoc "out_base" {:type "color3" :connect {:node "img_base"}})
                  normal-tex (assoc "out_normal" {:type "vector3" :connect {:node "nm_normal"}})
                  emissive-tex (assoc "out_emissive" {:type "color3" :connect {:node "img_emissive"}}))
        ss-inputs (cond-> {}
                    (and base (not base-tex)) (assoc "base_color" {:type "color3" :value base})
                    base-tex (assoc "base_color" {:type "color3" :connect {:nodegraph ng-name :output "out_base"}})
                    metallic (assoc "metalness" {:type "float" :value metallic})
                    roughness (assoc "specular_roughness" {:type "float" :value roughness})
                    (and emissive (not emissive-tex))
                    (assoc "emission_color" {:type "color3" :value emissive} "emission" {:type "float" :value 1.0})
                    emissive-tex
                    (assoc "emission_color" {:type "color3" :connect {:nodegraph ng-name :output "out_emissive"}}
                           "emission" {:type "float" :value 1.0})
                    normal-tex (assoc "normal" {:type "vector3" :connect {:nodegraph ng-name :output "out_normal"}})
                    clearcoat (assoc "coat" {:type "float" :value clearcoat})
                    clearcoat-roughness (assoc "coat_roughness" {:type "float" :value clearcoat-roughness})
                    transmission (assoc "transmission" {:type "float" :value transmission})
                    ior (assoc "specular_IOR" {:type "float" :value ior})
                    sheen (assoc "sheen" {:type "float" :value sheen}))]
    (cond-> {:nodes {ss-name {:type :ND_standard_surface_surfaceshader :inputs ss-inputs}}
             :materials {mat-name {:surfaceshader ss-name}}}
      (seq tex-nodes) (assoc :nodegraphs {ng-name {:nodes tex-nodes :outputs outputs}}))))
