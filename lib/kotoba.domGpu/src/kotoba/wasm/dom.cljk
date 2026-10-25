(ns kotoba.wasm.dom
  "DOM-like substrate for kotoba WASM.
   This does not call browser DOM APIs. It maintains a document model and emits
   host-friendly ops that a WebGL/WebGPU/native host can interpret."
  (:require [kotoba.lang.text :as str]))

(def empty-document
  {:next-id 1
   :root nil
   :nodes {}
   :listeners {}
   :ops []})

(defn- alloc-id [document]
  [(:next-id document) (update document :next-id inc)])

(defn- emit [document op]
  (update document :ops conj op))

(defn consume-ops [document]
  [(:ops document) (assoc document :ops [])])

(defn create-element [document tag]
  (let [[id document] (alloc-id document)
        tag (keyword tag)]
    [id (-> document
            (assoc-in [:nodes id] {:node/id id
                                   :node/type :element
                                   :tag tag
                                   :attrs {}
                                   :children []})
            (emit [:dom/create-element id tag]))]))

(defn create-text-node [document text]
  (let [[id document] (alloc-id document)
        text (str text)]
    [id (-> document
            (assoc-in [:nodes id] {:node/id id
                                   :node/type :text
                                   :text text})
            (emit [:dom/create-text id text]))]))

(defn create-comment-node
  "A real DOM comment node.

   This existed nowhere until 2026-08-04, which is why `htmldom` dropped
   every `<!-- ... -->` on the floor: there was no node type to put one in.
   Three parser conformance cases fail on exactly that, and they fail in a
   way worth keeping visible -- a dropped comment silently MERGES the text
   on either side of it (`a<!--c-->b` becomes one `ab` text node where a
   browser keeps two), so it is not only a missing node but a corrupted
   text structure.

   Comments carry no layout: `tree` omits them (see its own docstring), so
   cssom.layout never sees one and needs no knowledge of them."
  [document text]
  (let [[id document] (alloc-id document)
        text (str text)]
    [id (-> document
            (assoc-in [:nodes id] {:node/id id
                                   :node/type :comment
                                   :text text})
            (emit [:dom/create-comment id text]))]))

(defn set-root [document node-id]
  (-> document
      (assoc :root node-id)
      (emit [:dom/set-root node-id])))

(defn set-attribute [document node-id k v]
  (-> document
      (assoc-in [:nodes node-id :attrs (keyword k)] v)
      (emit [:dom/set-attr node-id (keyword k) v])))

(defn remove-attribute [document node-id k]
  (-> document
      (update-in [:nodes node-id :attrs] dissoc (keyword k))
      (emit [:dom/remove-attr node-id (keyword k)])))

(defn set-style [document node-id style]
  (reduce-kv
   (fn [document k v]
     (set-attribute document node-id (keyword "style" (name k)) v))
   document
   style))

(defn append-child [document parent-id child-id]
  (-> document
      (update-in [:nodes parent-id :children] (fnil conj []) child-id)
      (emit [:dom/append-child parent-id child-id])))

(defn append-content-child
  "Appends into an element's CONTENT fragment rather than its child list.

   This exists for `<template>`, whose parsed contents are not children of
   the element at all: they live in a separate DocumentFragment. Measured in
   Brave -- `template.childNodes.length` is 0 for every shape probed
   (`<template><p>x</p></template>`, a template in a table, a nested
   template, bare text), while `template.content` holds the parsed tree.

   Kept off `:children` on purpose: every consumer of `tree`/`comment-tree`
   treats `:children` as `what is rendered here`, and template content is
   explicitly not rendered. `content-tree` below is how a consumer that
   wants it asks."
  [document parent-id child-id]
  (-> document
      (update-in [:nodes parent-id :content] (fnil conj []) child-id)
      (emit [:dom/append-content parent-id child-id])))

(defn insert-before [document parent-id child-id before-id]
  (-> document
      (update-in [:nodes parent-id :children]
                 (fn [children]
                   (let [children (vec (or children []))]
                     (if (and before-id (some #{before-id} children))
                       (let [[before after] (split-with #(not= before-id %) children)]
                         (vec (concat before [child-id] after)))
                       (conj children child-id)))))
      (emit [:dom/insert-before parent-id child-id before-id])))

(defn remove-child [document parent-id child-id]
  (-> document
      (update-in [:nodes parent-id :children]
                 (fn [children] (vec (remove #{child-id} (or children [])))))
      (emit [:dom/remove-child parent-id child-id])))

(defn remove-children [document node-id]
  (-> document
      (assoc-in [:nodes node-id :children] [])
      (emit [:dom/remove-children node-id])))

(defn add-event-listener
  "Registers `handler-id` for `event-name` on `node-id`. Real HTML5
   `addEventListener` supports MULTIPLE independent listeners for the same
   (element, event-type) pair -- e.g. two separate scripts each attaching
   their own click handler to the same button -- so this keeps an ORDERED
   collection of handler-ids per (node-id, event-name), not a single scalar
   (a real, previously-fixed bug: a second `addEventListener` call used to
   silently overwrite the first, confirmed via direct REPL reproduction
   before this fix -- only the most-recently-added listener ever fired).
   Adding the exact same `handler-id` twice is a no-op (idempotent), matching
   real `addEventListener` semantics for a duplicate registration. Mirrors
   `browser.compat.quickjs-execution`'s own pre-existing, already-correct
   `{event-type {handler-id true}}` model for `window`/`document` global
   targets -- this was previously the ONE place multi-listener semantics
   were implemented; ordinary element nodes never got the same fix."
  [document node-id event-name handler-id]
  (-> document
      (update-in [:listeners node-id (keyword event-name)]
                 (fn [ids]
                   (let [ids (or ids [])]
                     (if (some #{handler-id} ids) ids (conj ids handler-id)))))
      (emit [:dom/add-event-listener node-id (keyword event-name) handler-id])))

(defn remove-event-listener
  "Removes ONLY `handler-id` from `node-id`'s listeners for `event-name`,
   leaving every other registered listener for that same (element,
   event-type) pair untouched -- previously the only `remove-event-listener`
   in this codebase lived in `browser.dom-bridge` and `dissoc`'d the WHOLE
   event-type entry, ignoring which `handler-id` was actually asked for, so
   removing ONE listener silently wiped every listener for that event type
   on that node."
  [document node-id event-name handler-id]
  (let [event-name (keyword event-name)
        remaining (vec (remove #{handler-id} (get-in document [:listeners node-id event-name])))]
    (-> document
        (update-in [:listeners node-id]
                   (fn [by-type]
                     (if (seq remaining)
                       (assoc by-type event-name remaining)
                       (dissoc by-type event-name))))
        (emit [:dom/remove-event-listener node-id event-name handler-id]))))

(defn dispatch-event
  "Emits one `:dom/dispatch-event` op per handler-id currently registered
   for `event-name` on `node-id`, in REGISTRATION ORDER -- matching real
   `addEventListener` dispatch order and this codebase's own existing
   convention of one `:dom/dispatch-event` op per handler invocation (see
   `browser.document-input`'s own bubble-phase dispatch, which already
   emits multiple such ops up the ancestor chain for a single logical
   event)."
  [document node-id event-name event]
  (let [ids (seq (get-in document [:listeners node-id (keyword event-name)]))]
    (reduce (fn [document handler-id]
              (emit document [:dom/dispatch-event handler-id event]))
            document
            ids)))

(defn node [document node-id]
  (get-in document [:nodes node-id]))

(defn tree
  "The LAYOUT view of the document: elements as maps, text as bare strings.

   Comment nodes are omitted. They have no box, no text and no effect on
   layout, and every consumer of this fn (cssom.layout above all) treats a
   map child as an element and a string child as text -- so admitting a
   third shape here would push comment-awareness into every layout path to
   no benefit. `comment-tree` is the DOM view that keeps them."
  [document]
  (letfn [(walk [id]
            (let [n (node document id)]
              (case (:node/type n)
                :text (:text n)
                :comment nil
                :element (assoc n
                                :listeners (keys (get-in document [:listeners id]))
                                :children (into [] (comp (map walk) (remove nil?))
                                                (:children n)))
                n)))]
    (some-> (:root document) walk)))

(defn content-tree
  "The tree inside an element's content fragment (see
   `append-content-child`), or nil when it has none. Elements are maps and
   text nodes are bare strings, the same shape `tree` produces."
  [document node-id]
  (when-let [ids (seq (get-in document [:nodes node-id :content]))]
    (letfn [(walk [id]
              (let [n (node document id)]
                (case (:node/type n)
                  :text (:text n)
                  :comment nil
                  :element (assoc n :children (into [] (comp (map walk) (remove nil?))
                                                    (:children n)))
                  n)))]
      (into [] (comp (map walk) (remove nil?)) ids))))

(defn comment-tree
  "`tree`, but keeping comment nodes as `{:node/type :comment :text ...}`.

   For consumers that are looking at the DOM rather than laying it out: a
   parser conformance harness comparing against a real browser's node list,
   a devtools inspector, a serializer. Kept as a separate fn precisely so
   that adding comments to the document cannot change what any existing
   layout caller sees."
  [document]
  (letfn [(walk [id]
            (let [n (node document id)]
              (case (:node/type n)
                :text (:text n)
                :comment (select-keys n [:node/type :text])
                :element (assoc n
                                :listeners (keys (get-in document [:listeners id]))
                                :children (mapv walk (:children n)))
                n)))]
    (some-> (:root document) walk)))

(defn text-content [document]
  (letfn [(walk [id]
            (let [n (node document id)]
              (case (:node/type n)
                :text (:text n)
                ;; a comment contributes nothing to textContent, exactly as
                ;; in a real DOM
                :comment ""
                :element (str/join "" (map walk (:children n)))
                "")))]
    (if-let [root (:root document)] (walk root) "")))
