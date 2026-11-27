(ns kotoba.ontology-viz.svg
  "Pure, zero-dependency, offline-safe standalone SVG generator for normalized
  `ontology.graph/v1` and Yataverse `yataverse.ontology.graph/v1` graphs.

  Security & portability invariants:
  - Always validates caller-supplied graphs via `validate/validate-graph!` (no unchecked bypass).
  - Formats all coordinates with `escape/fmt-num` for byte-identical output across JVM, Babashka, and nbb.
  - Standalone SVGs (`:interactive? false`, default) never emit focusable `role=\"button\"` on static graphics."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.escape :as esc]
            [kotoba.ontology-viz.graph :as g]
            [kotoba.ontology-viz.validate :as v]
            [kotoba.ontology-viz.yataverse :as yv]))

(def ^:private kind-palette
  {:connector    {:stroke "#0f766e" :fill "#f0fdfa" :badge "#0f766e" :tag "CONNECTOR"}
   :object-type  {:stroke "#1d4ed8" :fill "#eff6ff" :badge "#1d4ed8" :tag "TYPE"}
   :attribute    {:stroke "#6d28d9" :fill "#f5f3ff" :badge "#6d28d9" :tag "ATTR"}
   :entity       {:stroke "#b45309" :fill "#fffbeb" :badge "#b45309" :tag "ENTITY"}
   :rdf-resource {:stroke "#0369a1" :fill "#f0f9ff" :badge "#0369a1" :tag "RDF"}
   :rdf-blank    {:stroke "#0284c7" :fill "#f8fafc" :badge "#475569" :tag "BNODE"}
   :ipld-node    {:stroke "#be123c" :fill "#fff1f2" :badge "#be123c" :tag "IPLD"}})

(def ^:private edge-style
  {:produces      {:stroke "#0f766e" :dash nil   :marker "ov-arrow-teal"}
   :provenance    {:stroke "#0f766e" :dash "4 3" :marker "ov-arrow-teal"}
   :has-attribute {:stroke "#6d28d9" :dash nil   :marker "ov-arrow-slate"}
   :instance-of   {:stroke "#b45309" :dash "5 3" :marker "ov-arrow-amber"}
   :datom-ref     {:stroke "#b45309" :dash nil   :marker "ov-arrow-amber"}
   :rdf-predicate {:stroke "#0369a1" :dash nil   :marker "ov-arrow-blue"}
   :join          {:stroke "#1d4ed8" :dash "6 4" :marker "ov-arrow-blue"}
   :join-instance {:stroke "#1d4ed8" :dash "3 3" :marker "ov-arrow-blue"}
   :ipld-link     {:stroke "#be123c" :dash "2 3" :marker "ov-arrow-rose"}})

(defn normalize-and-validate-graph
  "Accept a Kotoba `ontology.graph/v1` (re-validated fail-closed!), a Yataverse
  `yataverse.ontology.graph/v1` graph (validated & adapted), or a raw projection
  input map. Guarantees every returned graph has been validated and laid out."
  [graph-or-input]
  (cond
    (yv/yataverse-graph? graph-or-input)
    (yv/<-yataverse-graph graph-or-input)

    (and (map? graph-or-input)
         (or (contains? graph-or-input :schema/kind)
             (contains? graph-or-input :schema/version)))
    (do
      (v/validate-graph! graph-or-input {:verify-graph-cid-fn yv/verify-normalized-graph-cid!})
      (if (and (:layout graph-or-input)
               (every? :layout (:nodes graph-or-input)))
        graph-or-input
        (g/layout-graph graph-or-input {} {:verify-graph-cid-fn yv/verify-normalized-graph-cid!})))

    :else
    (g/project-graph graph-or-input)))

(defn- edge-path [src-node tgt-node direction]
  (let [{sx :x sy :y sw :width sh :height} (:layout src-node)
        {tx :x ty :y tw :width th :height} (:layout tgt-node)]
    (if (= direction :vertical)
      (let [x1 (+ sx (/ sw 2.0))
            y1 (+ sy sh)
            x2 (+ tx (/ tw 2.0))
            y2 ty
            cy (/ (+ y1 y2) 2.0)]
        {:d (str "M " (esc/fmt-num x1) " " (esc/fmt-num y1)
                 " C " (esc/fmt-num x1) " " (esc/fmt-num cy)
                 ", " (esc/fmt-num x2) " " (esc/fmt-num cy)
                 ", " (esc/fmt-num x2) " " (esc/fmt-num y2))
         :mx (/ (+ x1 x2) 2.0)
         :my (/ (+ y1 y2) 2.0)})
      (let [same-col? (= sx tx)
            x1 (if same-col? (+ sx sw) (if (<= sx tx) (+ sx sw) sx))
            y1 (+ sy (/ sh 2.0))
            x2 (if same-col? (+ tx tw) (if (<= sx tx) tx (+ tx tw)))
            y2 (+ ty (/ th 2.0))
            abs-dx #?(:clj (Math/abs (double (- x2 x1)))
                      :cljs (js/Math.abs (- x2 x1)))
            dx (if same-col? 54.0 (max 42.0 (/ abs-dx 2.0)))
            cx1 (if same-col? (+ x1 dx) (if (<= sx tx) (+ x1 dx) (- x1 dx)))
            cx2 (if same-col? (+ x2 dx) (if (<= sx tx) (- x2 dx) (+ x2 dx)))]
        {:d (str "M " (esc/fmt-num x1) " " (esc/fmt-num y1)
                 " C " (esc/fmt-num cx1) " " (esc/fmt-num y1)
                 ", " (esc/fmt-num cx2) " " (esc/fmt-num y2)
                 ", " (esc/fmt-num x2) " " (esc/fmt-num y2))
         :mx (if same-col? (+ x1 (* dx 0.72)) (/ (+ x1 x2) 2.0))
         :my (/ (+ y1 y2) 2.0)}))))

(defn- render-layer-bands [layers layout]
  (let [{:keys [direction node-width node-height col-gap pad-x pad-y height width]} layout]
    (str/join
     "\n"
     (map-indexed
      (fn [idx layer]
        (let [color (if (v/safe-hex-color? (:color layer)) (:color layer) "#475569")
              bg (if (v/safe-hex-color? (:bg layer)) (:bg layer) "#f8fafc")
              label (esc/escape-xml (:label layer))
              cnt (esc/fmt-num (or (:node-count layer) 0))]
          (if (= direction :vertical)
            (let [band-y (- (+ pad-y (* idx (+ node-height col-gap))) 18)
                  band-h (+ node-height 36)]
              (str "  <g class=\"ov-layer-band\" data-layer=\"" (esc/escape-attr (:id layer)) "\">"
                   "<rect x=\"16\" y=\"" (esc/fmt-num band-y) "\" width=\"" (esc/fmt-num (- width 32))
                   "\" height=\"" (esc/fmt-num band-h) "\" rx=\"10\" fill=\"" bg
                   "\" stroke=\"#e2e8f0\" stroke-width=\"1\"/>"
                   "<text x=\"28\" y=\"" (esc/fmt-num (+ band-y 14))
                   "\" font-size=\"11\" font-weight=\"600\" fill=\"" color "\">"
                   label " (" cnt ")</text></g>"))
            (let [band-x (- (+ pad-x (* idx (+ node-width col-gap))) 14)
                  band-w (+ node-width 28)
                  band-h (max 120 (- height 100))]
              (str "  <g class=\"ov-layer-band\" data-layer=\"" (esc/escape-attr (:id layer)) "\">"
                   "<rect x=\"" (esc/fmt-num band-x) "\" y=\"48\" width=\"" (esc/fmt-num band-w)
                   "\" height=\"" (esc/fmt-num band-h) "\" rx=\"10\" fill=\"" bg
                   "\" stroke=\"#e2e8f0\" stroke-width=\"1\"/>"
                   "<text x=\"" (esc/fmt-num (+ band-x 12)) "\" y=\"68\" font-size=\"11\" font-weight=\"700\" letter-spacing=\"0.04em\" fill=\""
                   color "\">" label " (" cnt ")</text></g>")))))
      layers))))

(defn- render-edges [edges nodes-by-id direction]
  (str/join
   "\n"
   (keep
    (fn [edge]
      (when-let [src (get nodes-by-id (:source edge))]
        (when-let [tgt (get nodes-by-id (:target edge))]
          (let [{:keys [d mx my]} (edge-path src tgt direction)
                st (get edge-style (:kind edge) {:stroke "#64748b" :dash nil :marker "ov-arrow-slate"})
                lbl (esc/truncate-display (or (:label edge) "") 26)
                lbl-w (+ 14.0 (* 6.2 (count lbl)))
                is-join? (contains? #{:join :join-instance} (:kind edge))]
            (str "  <g class=\"ov-edge\" data-edge-id=\"" (esc/escape-attr (:id edge))
                 "\" data-source=\"" (esc/escape-attr (:source edge))
                 "\" data-target=\"" (esc/escape-attr (:target edge))
                 "\" data-kind=\"" (esc/escape-attr (name (or (:kind edge) :edge)))
                 "\" data-layer=\"" (esc/escape-attr (or (:layer edge) "ontology")) "\">\n"
                 "    <path d=\"" d "\" fill=\"none\" stroke=\"" (:stroke st) "\" stroke-width=\""
                 (if is-join? "2.2" "1.5") "\""
                 (when (:dash st) (str " stroke-dasharray=\"" (:dash st) "\""))
                 " marker-end=\"url(#" (:marker st) ")\"/>\n"
                 (when-not (str/blank? lbl)
                   (str "    <rect x=\"" (esc/fmt-num (- mx (/ lbl-w 2.0))) "\" y=\"" (esc/fmt-num (- my 9.0))
                        "\" width=\"" (esc/fmt-num lbl-w) "\" height=\"18\" rx=\"9\" fill=\""
                        (if is-join? "#dbeafe" "#ffffff")
                        "\" stroke=\"" (:stroke st) "\" stroke-width=\"0.9\"/>\n"
                        "    <text x=\"" (esc/fmt-num mx) "\" y=\"" (esc/fmt-num (+ my 3.5))
                        "\" text-anchor=\"middle\" font-size=\"10\" font-weight=\""
                        (if is-join? "700" "500") "\" fill=\"#1e293b\">"
                        (esc/escape-xml lbl) "</text>\n"))
                 "    <title>" (esc/escape-xml (str (:source edge) " -> " (:target edge) " (" (:label edge) ")")) "</title>\n"
                 "  </g>")))))
    edges)))

(defn- render-nodes [nodes interactive?]
  (str/join
   "\n"
   (map
    (fn [node]
      (let [{:keys [x y width height]} (:layout node)
            pal (get kind-palette (:kind node) {:stroke "#475569" :fill "#ffffff" :badge "#475569" :tag "NODE"})
            title (esc/truncate-display (or (:label node) (:id node)) 26)
            sub (cond
                  (:cid node) (str "CID " (esc/short-cid (:cid node)))
                  (seq (:keys node)) (str "key: " (esc/truncate-display (str/join ", " (:keys node)) 24))
                  (seq (:attributes node)) (str (count (:attributes node)) " attr(s)")
                  :else (esc/truncate-display (:id node) 26))
            dom-id (str "ov-node-" (esc/sanitize-id (:id node)))
            a11y-attrs (if interactive?
                         (str " tabindex=\"0\" role=\"button\" aria-label=\""
                              (esc/escape-attr (str (or (:label node) (:id node)) " (" (name (or (:kind node) :node)) ")"))
                              "\"")
                         "")]
        (str "  <g id=\"" (esc/escape-attr dom-id)
             "\" class=\"ov-node\"" a11y-attrs
             " data-node-id=\"" (esc/escape-attr (:id node))
             "\" data-layer=\"" (esc/escape-attr (:layer node))
             "\" data-kind=\"" (esc/escape-attr (name (or (:kind node) :node))) "\">\n"
             "    <rect class=\"ov-node-card\" x=\"" (esc/fmt-num x) "\" y=\"" (esc/fmt-num y)
             "\" width=\"" (esc/fmt-num width) "\" height=\"" (esc/fmt-num height)
             "\" rx=\"8\" fill=\"" (:fill pal) "\" stroke=\"" (:stroke pal) "\" stroke-width=\"1.6\"/>\n"
             "    <rect x=\"" (esc/fmt-num (+ x 8)) "\" y=\"" (esc/fmt-num (+ y 8))
             "\" width=\"64\" height=\"16\" rx=\"4\" fill=\"" (:badge pal) "\"/>\n"
             "    <text x=\"" (esc/fmt-num (+ x 40)) "\" y=\"" (esc/fmt-num (+ y 19.5))
             "\" text-anchor=\"middle\" font-size=\"9\" font-weight=\"700\" fill=\"#ffffff\">"
             (:tag pal) "</text>\n"
             "    <text x=\"" (esc/fmt-num (+ x 10)) "\" y=\"" (esc/fmt-num (+ y 41))
             "\" font-size=\"12.5\" font-weight=\"700\" fill=\"#0f172a\">"
             (esc/escape-xml title) "</text>\n"
             "    <text x=\"" (esc/fmt-num (+ x 10)) "\" y=\"" (esc/fmt-num (+ y 57))
             "\" font-size=\"10\" font-family=\"ui-monospace, SFMono-Regular, Menlo, monospace\" fill=\"#475569\">"
             (esc/escape-xml sub) "</text>\n"
             "    <title>" (esc/escape-xml (str (:label node) " [" (:id node) "]"
                                                (when (:cid node) (str " CID=" (:cid node))))) "</title>\n"
             "  </g>")))
    nodes)))

(defn render-svg
  "Render a validated `ontology.graph/v1`, Yataverse `yataverse.ontology.graph/v1`,
  or raw projection input map as a zero-dependency, offline-safe standalone SVG
  document string.

  Options:
  - `:title` — SVG accessible title and header text
  - `:interactive?` — default `false` (standalone SVG omits focusable
    `role=\"button\"` on non-interactive nodes; set `true` only when hosted
    inside an interactive viewer that wires click/keyboard handlers)."
  ([graph-or-input] (render-svg graph-or-input {}))
  ([graph-or-input {:keys [title interactive?]
                    :or {title "Kotoba IPLD Ontology Graph"
                         interactive? false}}]
   (let [graph (normalize-and-validate-graph graph-or-input)
         limits (or (get-in graph [:basis :bounds]) v/default-limits)
         _ (v/assert-label-length! limits :svg/title title)
         layout (:layout graph)
         width (max 420 (or (:width layout) 640))
         height (max 240 (or (:height layout) 360))
         nodes (:nodes graph)
         edges (:edges graph)
         layers (:layers graph)
         basis (:basis graph)
         nodes-by-id (into {} (map (juxt :id identity) nodes))
         cid-ver (name (or (:basis-cid-verification basis) (:cid-verification basis) :syntax-only))
         graph-cid-ver (some-> (:graph-cid-verification basis) name)
         footer-text (str "schema=" g/schema-version
                          " | codec=" (or (:codec basis) "dag-cbor")
                          " | cid=" cid-ver
                          (when (and graph-cid-ver (not= graph-cid-ver "absent"))
                            (str " | graph-cid=" graph-cid-ver))
                          (when-let [rc (:root-cid basis)]
                            (str " | root=" (esc/short-cid rc)))
                          " | nodes=" (count nodes)
                          " | edges=" (count edges)
                          " | joins=" (count (:joins graph)))]
     (str "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 "
          (esc/fmt-num width) " " (esc/fmt-num height)
          "\" width=\"" (esc/fmt-num width) "\" height=\"" (esc/fmt-num height)
          "\" role=\"img\" aria-label=\"" (esc/escape-attr title)
          "\" font-family=\"system-ui, -apple-system, BlinkMacSystemFont, sans-serif\">\n"
          "  <title>" (esc/escape-xml title) "</title>\n"
          "  <desc>" (esc/escape-xml footer-text) "</desc>\n"
          "  <defs>\n"
          "    <marker id=\"ov-arrow-slate\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"6\" markerHeight=\"6\" orient=\"auto-start-reverse\"><path d=\"M 0 1 L 10 5 L 0 9 z\" fill=\"#64748b\"/></marker>\n"
          "    <marker id=\"ov-arrow-teal\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"6\" markerHeight=\"6\" orient=\"auto-start-reverse\"><path d=\"M 0 1 L 10 5 L 0 9 z\" fill=\"#0f766e\"/></marker>\n"
          "    <marker id=\"ov-arrow-blue\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"6\" markerHeight=\"6\" orient=\"auto-start-reverse\"><path d=\"M 0 1 L 10 5 L 0 9 z\" fill=\"#1d4ed8\"/></marker>\n"
          "    <marker id=\"ov-arrow-amber\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"6\" markerHeight=\"6\" orient=\"auto-start-reverse\"><path d=\"M 0 1 L 10 5 L 0 9 z\" fill=\"#b45309\"/></marker>\n"
          "    <marker id=\"ov-arrow-rose\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"6\" markerHeight=\"6\" orient=\"auto-start-reverse\"><path d=\"M 0 1 L 10 5 L 0 9 z\" fill=\"#be123c\"/></marker>\n"
          "  </defs>\n"
          "  <rect x=\"0\" y=\"0\" width=\"" (esc/fmt-num width) "\" height=\"" (esc/fmt-num height) "\" fill=\"#ffffff\"/>\n"
          "  <text x=\"24\" y=\"30\" font-size=\"16\" font-weight=\"700\" fill=\"#0f172a\">"
          (esc/escape-xml title) "</text>\n"
          (render-layer-bands layers layout) "\n"
          "  <g class=\"ov-edges\">\n"
          (render-edges edges nodes-by-id (:direction layout)) "\n"
          "  </g>\n"
          "  <g class=\"ov-nodes\">\n"
          (render-nodes nodes (boolean interactive?)) "\n"
          "  </g>\n"
          "  <text x=\"24\" y=\"" (esc/fmt-num (- height 16)) "\" font-size=\"11\" font-family=\"ui-monospace, SFMono-Regular, Menlo, monospace\" fill=\"#475569\">"
          (esc/escape-xml footer-text) "</text>\n"
          "</svg>\n"))))
