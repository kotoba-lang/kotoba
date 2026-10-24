(ns devtools.inspect
  "Browser-engine DevTools inspection model — pure-data, zero-dep CLJC.

  This is the L1 DevTools surface: pure functions that project plain-data
  engine state (document tree, computed styles, layout draw-ops, console
  messages, audit/network events) into structured inspector *views* and
  human-readable text renderings — the data analogue of a DevTools
  Elements / Styles / Layout / Console / Network / Timeline panel.

  It captures no state itself and does no IO. A host runtime (e.g.
  `browser.devtools`) adapts its live session/page into the input shapes
  documented below and calls these functions. Input shapes are duck-typed
  plain data, matching what `browser.dom-bridge`, `browser.audit`, and the
  QuickJS execution state already produce — no hard dependency on them, so
  this namespace stays zero-dep and portable (same philosophy as the
  sibling `devtools` automation contracts).

  Input shapes (all optional; panels degrade to empty when absent):

    :document  -- `browser.dom-bridge/document-snapshot` shape:
                  {:root node-id :focus node-id :url :base-uri :ready-state
                   :title :nodes {node-id {:node/id :node/type :tag :attrs
                                           :children :text :parent/id
                                           :text-content}}}
                  A node's :attrs carries computed styles as :style/<prop>
                  keywords (namespace \"style\"), plus :style-inline (map)
                  and :style-inline-important (set) for origin annotation.

    :draw-ops  -- `cssom.layout/draw-ops` shape: vector of
                  {:draw/op :node|:rect|:text :id :x :y :w :h ...}.
                  :node ops link a layout box to a document node-id.

    :console   -- QuickJS execution `:console/messages` shape: vector of
                  {:console/level :log|:info|:warn|:error|:debug :args [...]}.

    :audit-events -- `browser.audit/events` shape: vector of
                  {:audit/id :audit/event <type> <event fields>}.

    :navigation -- `browser.browser-use/navigation-state` shape:
                  {:entries [{:url :status :error}] :redirects [...] :error}.

  Levels (L0->L1): L0 was 'absent' — only KAMI automation contracts existed,
  no inspector. L1 is a real, tested, pure-data inspection surface that
  unifies the engine's scattered debug state (document snapshot, audit log,
  console/messages, draw-ops) into a single readable DevTools view. A CDP /
  HTTP transport lives at L2."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------- -- helpers

(defn- display
  "Render any value as a console-style display string."
  [v]
  (cond
    (nil? v)          ""
    (string? v)       v
    (keyword? v)      (name v)
    (boolean? v)      (str v)
    (number? v)       (str v)
    (map? v)          (pr-str v)
    (coll? v)         (str/join " " (map display v))
    :else             (str v)))

(defn- truncate
  [s n]
  (let [s (str s)]
    (if (<= (count s) n)
      s
      (str (subs s 0 (max 0 (- n 1))) "..."))))

(defn- indent [depth] (str/join (repeat depth "  ")))

(defn- kw->str
  "Full string of a keyword incl. namespace (`:page/commit` -> \"page/commit\"),
  unlike `name` which drops the namespace. Non-keywords fall back to `str`."
  [k]
  (if (keyword? k)
    (if-let [ns (namespace k)] (str ns "/" (name k)) (name k))
    (str k)))

(defn- class-selector
  "Turn a class attr value into a .a.b selector suffix."
  [cls]
  (let [s (str/trim (str cls))]
    (when (seq s)
      (str "." (str/replace s #"\s+" ".")))))

;; ---------------------------------------------------------------- -- DOM tree

(defn- dom-node-view
  [document node-id]
  (when-let [node (get-in document [:nodes node-id])]
    (let [t (:node/type node)
          attrs (:attrs node)]
      (cond-> {:node/id node-id :type t}
        (:tag node)           (assoc :tag (:tag node))
        (get attrs :id)       (assoc :id (get attrs :id))
        (get attrs :class)    (assoc :class (get attrs :class))
        (= t :text)           (assoc :text (:text node))
        (seq (:children node)) (assoc :children
                                 (mapv #(dom-node-view document %) (:children node)))))))

(defn dom-tree
  "Project a document-snapshot into a nested DOM tree view rooted at :root."
  [document]
  (when-let [root (get document :root)]
    (dom-node-view document root)))

(defn- render-node
  [node depth]
  (let [pad (indent depth)]
    (if (= :text (:type node))
      (str pad "\"" (truncate (:text node) 80) "\"")
      (let [head (str pad "<" (name (:tag node))
                      (when-let [id (:id node)] (str " #" id))
                      (when-let [cls (:class node)] (class-selector cls))
                      ">")]
        (if-let [kids (seq (:children node))]
          (str head "\n" (str/join "\n" (map #(render-node % (inc depth)) kids)))
          head)))))

(defn render-dom-tree
  "Indented text rendering of a document's DOM tree (Elements-panel style)."
  [document]
  (if-let [tree (dom-tree document)]
    (render-node tree 0)
    "  (no document)"))

;; ------------------------------------------------------ -- computed styles

(defn- style-origin
  [prop inline important]
  (cond
    (contains? important prop) [:inline true]
    (contains? inline prop)    [:inline false]
    :else                      [:stylesheet false]))

(defn computed-styles
  "Project a node's computed style attrs into a sorted vector of
  {:property :value :origin :inline|:stylesheet :important? bool}.

  Computed styles are the node attrs whose keyword namespace is \"style\"
  (the keys cssom's cascade writes, e.g. :style/color); :style-inline (map)
  and :style-inline-important (set) annotate which values came from inline
  style and which were !important. Returns [] for non-element or style-less
  nodes."
  [node]
  (let [attrs (:attrs node)
        inline (or (:style-inline attrs) {})
        important (or (:style-inline-important attrs) #{})]
    (->> attrs
         (keep (fn [[k v]]
                 (when (= "style" (namespace k))
                   (let [prop (keyword (name k))
                         [origin imp?] (style-origin prop inline important)]
                     {:property prop :value v :origin origin :important? imp?}))))
         (sort-by (fn [m] (name (:property m))))
         vec)))

(defn render-computed-styles
  "Text rendering of a node's computed styles (Styles-panel style)."
  [node]
  (let [styles (computed-styles node)]
    (if (empty? styles)
      "  (no computed styles)"
      (str/join "\n"
                (map (fn [{:keys [property value origin important?]}]
                       (str "  " (name property) ": " value
                            (when important? " !important")
                            "    ; " (name origin)))
                     styles)))))

;; ----------------------------------------------------------- -- layout boxes

(defn layout-boxes
  "Project draw-ops into a vector of {:node/id :op :x :y :width :height}.
  Only ops carrying an :id (node-linked boxes) are returned, so each box
  correlates back to a document node. Other draw-ops (:rect/:text without
  :id) are structural paint ops, not element boxes."
  [draw-ops]
  (->> draw-ops
       (keep (fn [op]
               (when-let [id (:id op)]
                 {:node/id id
                  :op (:draw/op op)
                  :x (:x op) :y (:y op)
                  :width (:w op) :height (:h op)})))
       vec))

(defn render-layout-boxes
  "Text rendering of element layout boxes (x,y width×height per node)."
  [draw-ops]
  (let [boxes (layout-boxes draw-ops)]
    (if (empty? boxes)
      "  (no layout boxes)"
      (str/join "\n"
                (map (fn [{:keys [node/id op x y width height]}]
                       (str "  #" id " " (name op)
                            " @ " x "," y "  " width "x" height))
                     boxes)))))

;; ---------------------------------------------------------------- -- console

(defn console-messages
  "Normalize console messages into [{:level :text}]. Each message's :args
  (any shape) is joined into a single display string."
  [messages]
  (->> messages
       (map (fn [m]
              {:level (or (:console/level m) :log)
               :text  (display (:args m))}))
       vec))

(defn render-console
  "Text rendering of console messages (level-prefixed, Console-panel style)."
  [messages]
  (let [msgs (console-messages messages)]
    (if (empty? msgs)
      "  (console empty)"
      (str/join "\n"
                (map (fn [{:keys [level text]}]
                       (str "  [" (name level) "] " (truncate text 200)))
                     msgs)))))

;; --------------------------------------------------------------- -- network

(defn- nav-entry
  [entry]
  (let [status (:status entry)]
    {:url     (:url entry)
     :method  :get
     :status  status
     :ok?     (and status (<= 200 status 299))
     :error   (:error entry)
     :kind    :navigation}))

(defn- fetch-entry
  "A programmatic fetch() surfaces in the audit log as a :compat/request
  event with :capability :net/fetch. The audit summary carries ok?/error
  but not the URL (that lives in the request payload, not the summary), so
  :url is best-effort."
  [event]
  (when (and (= :compat/request (:audit/event event))
             (= :net/fetch (:capability event)))
    {:url    (:url event)
     :method :get
     :status nil
     :ok?    (:request/ok? event)
     :error  (:error event)
     :kind   :fetch}))

(defn network-log
  "Project navigation state + audit events into a chronological request log.
  Each entry: {:url :method :status :ok? :error :kind}. Navigation entries
  (with url+status) are primary; programmatic fetch() entries are appended."
  [{:keys [navigation audit-events]}]
  (let [nav     (mapv nav-entry (or (:entries navigation) []))
        fetches (->> audit-events (keep fetch-entry) vec)]
    (into nav fetches)))

(defn render-network
  "Text rendering of the network request log (Network-panel style)."
  [input]
  (let [entries (network-log input)]
    (if (empty? entries)
      "  (no network requests)"
      (str/join "\n"
                (map (fn [{:keys [url method status ok? error kind]}]
                       (str "  " (str/upper (name method))
                            " " (or url "(no url)")
                            (when status (str " " status))
                            (if (false? ok?) " FAIL" "")
                            (when error (str " " error))
                            "  [" (name kind) "]"))
                     entries)))))

;; ------------------------------------------------------- -- event timeline

(defn- event-summary
  [event]
  (let [t (:audit/event event)]
    (str (kw->str t)
         (cond
           ;; type-specific fields are more meaningful than the ambient :url
           (= :compat/request t)  (str " " (kw->str (:capability event)))
           (= :quickjs/call t)    (str " " (:quickjs/call event))
           (:url event)           (str " " (:url event))
           (:storage/key event)   (str " " (:storage/key event))
           :else ""))))

(defn event-timeline
  "Project audit events into a chronological timeline of
  {:id :event :summary}. Preserves audit order (oldest-first)."
  [audit-events]
  (->> audit-events
       (map (fn [e] {:id      (:audit/id e)
                     :event   (:audit/event e)
                     :summary (event-summary e)}))
       vec))

(defn render-event-timeline
  "Text rendering of the audit event timeline."
  [audit-events]
  (let [tl (event-timeline audit-events)]
    (if (empty? tl)
      "  (no events)"
      (str/join "\n" (map #(str "  " (:summary %)) tl)))))

;; ----------------------------------------------------------- -- node inspect

(defn node-path
  "Ancestry path (root-first) of node-ids from the document root down to
  `node-id`, inclusive. Uses each snapshot node's :parent/id."
  [document node-id]
  (loop [id node-id path []]
    (if-not id
      (vec (reverse path))
      (if-let [node (get-in document [:nodes id])]
        (recur (:parent/id node) (conj path id))
        (vec (reverse path))))))

(defn find-node-by-id
  "Locate a node-id by its :id attribute within a document-snapshot.
  Literal exact match (like getElementById), never selector parsing."
  [document id]
  (->> (:nodes document)
       (some (fn [[nid node]]
               (when (= (str id) (get-in node [:attrs :id])) nid)))))

(defn inspect-node
  "Full per-node inspection, aggregating attrs, computed styles, tree path,
  and (if draw-ops supplied) the element's layout box.

  Options: {:document :draw-ops :node-id}. Returns nil if the node is absent."
  [{:keys [document draw-ops node-id]}]
  (let [node (get-in document [:nodes node-id])
        box  (some #(when (= node-id (:id %)) %) draw-ops)]
    (when node
      (cond-> {:node/id   node-id
               :type      (:node/type node)
               :tag       (:tag node)
               :path      (node-path document node-id)
               :styles    (computed-styles node)}
        (:attrs node)  (assoc :attrs (:attrs node))
        (:text node)   (assoc :text (:text node))
        box            (assoc :layout-box
                              {:x (:x box) :y (:y box)
                               :width (:w box) :height (:h box)})))))

;; ------------------------------------------------------- -- unified snapshot

(defn inspector-snapshot
  "Aggregate every panel from a single engine-state map into a data view:
  {:meta {:url :title :ready-state}
   :dom <tree>
   :styles {node-id [computed-styles]}   ; every element node
   :layout [<box>]
   :console [<msg>]
   :network [<entry>]
   :timeline [<event>]}.

  All inputs optional; absent panels are nil/empty. For programmatic
  assertions; see `render-inspector` for a readable text dump."
  [{:keys [document draw-ops console audit-events navigation]}]
  (let [doc         (or document {})
        nodes       (:nodes doc)
        element-ids (when nodes
                      (for [[id n] nodes :when (= :element (:node/type n))] id))]
    {:meta     {:url (:url doc) :title (:title doc) :ready-state (:ready-state doc)}
     :dom      (dom-tree doc)
     :styles   (into {} (map (fn [id] [id (computed-styles (get nodes id))]) element-ids))
     :layout   (layout-boxes draw-ops)
     :console  (console-messages console)
     :network  (network-log {:navigation navigation :audit-events audit-events})
     :timeline (event-timeline audit-events)}))

(defn render-inspector
  "Produce a multi-section, human-readable text dump of DevTools state.
  Accepts the raw input map ({:document :draw-ops :console :audit-events
  :navigation}); each section is rendered via its panel renderer. Intended
  for REPL/test inspection and debug dumps."
  [{:keys [document draw-ops console audit-events] :as input}]
  (let [doc   (or document {})
        meta  {:url (:url doc) :title (:title doc) :ready-state (:ready-state doc)}]
    (str/join "\n"
              (filter some?
                      ["=== DevTools inspector ==="
                       (str "url:         " (or (:url meta) "(none)"))
                       (str "title:       " (or (:title meta) "(none)"))
                       (str "ready-state: " (or (:ready-state meta) "(none)"))
                       ""
                       "── DOM ──"
                       (render-dom-tree document)
                       ""
                       "── Layout ──"
                       (render-layout-boxes draw-ops)
                       ""
                       "── Console ──"
                       (render-console console)
                       ""
                       "── Network ──"
                       (render-network input)
                       ""
                       "── Event timeline ──"
                       (render-event-timeline audit-events)
                       ""]))))
