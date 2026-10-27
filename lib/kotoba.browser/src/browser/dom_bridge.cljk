(ns browser.dom-bridge
  "DOM query/mutation bridge used by compat runtimes."
  (:require [cssom.core :as css]
            [htmldom.core :as html]
            [kotoba.wasm.dom :as dom]))

(defn element-nodes
  [document]
  (letfn [(walk [node-id]
            (let [node (get-in document [:nodes node-id])]
              (when node
                (cons node
                      (mapcat walk (:children node))))))]
    (->> (walk (:root document))
         (filter #(= :element (:node/type %)))
         vec)))

(defn query-selector-all
  [document selector]
  (let [selectors (->> (css/split-selector-list selector)
                       (map css/parse-selector)
                       vec)]
    (->> (element-nodes document)
         (filter #(some (fn [selector]
                          (css/matches? document % selector))
                        selectors))
         (mapv :node/id))))

(defn query-selector
  [document selector]
  (first (query-selector-all document selector)))

(defn get-element-by-id
  "Real document.getElementById(id) semantics: a literal, unescaped match
   against the id attribute's exact string value -- never CSS selector
   parsing. Deliberately NOT implemented as (query-selector (str \"#\" id)):
   an id containing any CSS-special character (a period, a colon, a space,
   a leading digit, ...) -- all common in real-world HTML, e.g. id=\"2fa.token\"
   -- would silently fail to match, or worse, match something else entirely,
   once concatenated into a selector string without escaping, exactly the
   real getElementById(id) vs. querySelector('#' + id) gotcha real browsers
   avoid by never parsing id as a selector in the first place."
  [document id]
  (:node/id (first (filter #(= (str id) (get-in % [:attrs :id])) (element-nodes document)))))

(defn title-node-id
  [document]
  (query-selector document "title"))

(defn parent-index
  [document]
  (reduce-kv
   (fn [parents parent-id node]
     (reduce (fn [parents child-id]
               (assoc parents child-id parent-id))
             parents
             (:children node)))
   {}
   (:nodes document)))

(defn- node-text
  [document node-id]
  (letfn [(walk [id]
            (let [node (get-in document [:nodes id])]
              (case (:node/type node)
                :text (:text node)
                :element (apply str (map walk (:children node)))
                "")))]
    (walk node-id)))

(defn document-title
  [document]
  (if-let [title-id (title-node-id document)]
    (node-text document title-id)
    ""))

(defn document-base-href
  [document]
  (when-let [base-id (query-selector document "base")]
    (get-in document [:nodes base-id :attrs :href])))

(defn- ensure-head-node
  [document]
  (if-let [head-id (query-selector document "head")]
    [head-id document]
    (let [[head-id document] (dom/create-element document :head)]
      [head-id (dom/append-child document (:root document) head-id)])))

(defn set-document-title
  [document title]
  (let [title (str title)
        [title-id document] (if-let [title-id (title-node-id document)]
                              [title-id document]
                              (let [[head-id document] (ensure-head-node document)
                                    [title-id document] (dom/create-element document :title)]
                                [title-id (dom/append-child document head-id title-id)]))
        document (dom/remove-children document title-id)
        [text-id document] (dom/create-text-node document title)]
    (-> document
        (dom/append-child title-id text-id)
        (assoc :title title))))

(defn node-snapshot
  ([document node-id]
   (node-snapshot document (parent-index document) node-id))
  ([document parents node-id]
   (when-let [node (get-in document [:nodes node-id])]
     (cond-> (select-keys node [:node/id :node/type :tag :attrs :children :text])
       (contains? parents node-id) (assoc :parent/id (get parents node-id))
       (= :element (:node/type node)) (assoc :text-content (node-text document node-id))))))

(defn document-snapshot
  [document]
  (let [parents (parent-index document)]
    {:root (:root document)
     :focus (:focus document)
     :url (or (:url document) "about:blank")
     :base-uri (or (:base-uri document) (:url document) "about:blank")
     :ready-state (or (:ready-state document) "complete")
     :title (document-title document)
     :nodes (into {}
                  (map (fn [[node-id _]]
                         [node-id (node-snapshot document parents node-id)]))
                  (:nodes document))}))

(defn add-event-listener
  [document node-id event-type handler-id]
  {:document (dom/add-event-listener document node-id event-type handler-id)
   :node/id node-id
   :handler/id handler-id})

(defn remove-event-listener
  [document node-id event-type handler-id]
  {:document (dom/remove-event-listener document node-id event-type handler-id)
   :node/id node-id
   :handler/id handler-id})

(defn dispatch-event
  [document node-id event]
  (let [event-type (or (:event/type event) (:type event))
        before-count (count (:ops document))
        document (dom/dispatch-event document node-id event-type event)]
    {:document document
     :node/id node-id
     :event/dispatched? (< before-count (count (:ops document)))}))

(defn- style-attr?
  [attr]
  (= :style (keyword attr)))

(defn- clear-style-attrs
  [document node-id]
  (update-in document [:nodes node-id :attrs]
             (fn [attrs]
               (into {}
                     (remove (fn [[k _]]
                               (or (= :style k)
                                   (= :style-inline k)
                                   (= :style-inline-important k)
                                   (= "style" (namespace k)))))
                     attrs))))

(defn- set-style-attribute
  "A script mutating `element.style.cssText`/`setAttribute('style', ...)`
   goes through here, not `htmldom.core/parse-style` (that only ever runs
   once, at initial HTML parse time) -- so it needs its OWN `!important`
   handling to stay consistent with a page's initial inline styles (see
   `cssom.core/resolve-style-for`'s docstring). `parse-declarations-with-
   importance` (unlike the plain `parse-declarations` this used before)
   reports real per-property importance, which is split back out into the
   same `:style-inline`/`:style-inline-important` attr pair
   `htmldom.core/apply-attrs` populates, so `cssom.core/inline-style`/
   `inline-style-importance` can't tell the two origins apart."
  [document node-id value]
  (let [parsed (css/parse-declarations-with-importance value)
        style (into {} (map (fn [[k v]] [k (:value v)])) parsed)
        important (into #{} (keep (fn [[k v]] (when (:important? v) k))) parsed)]
    (-> document
        (clear-style-attrs node-id)
        (dom/set-attribute node-id :style value)
        (dom/set-attribute node-id :style-inline style)
        (dom/set-attribute node-id :style-inline-important important)
        (dom/set-style node-id style))))

(defn- style-property-attr?
  "True for a script mutating an INDIVIDUAL `element.style.<prop>` property
   (or `style.setProperty(prop, value)`/`style.removeProperty(prop)`) --
   `browser.compat.quickjs-wasm`'s `__kotobaStyle` shim namespaces these as
   `\"style/<kebab-prop>\"`, e.g. `\"style/color\"`, distinct from the
   literal `\"style\"` attr `style-attr?` matches (a full `cssText`/
   `setAttribute('style', ...)` replace)."
  [attr]
  (= "style" (namespace (keyword attr))))

(defn- set-style-property
  "A script mutating an individual `element.style.<prop>` property goes
   through here -- unlike `set-style-attribute` (a full `cssText` replace
   that re-parses and REPLACES the entire `:style-inline` map), this merges
   just the one changed property into the EXISTING `:style-inline` map, and
   clears any prior `!important` flag on that property (a plain property
   assignment always carries no priority, exactly like
   `setProperty(prop, value)` with no third argument). Without this,
   writing `attr` straight through the generic `dom/set-attribute` path
   (as this used to) only ever touched the derived, cascade-computed
   `:style/<prop>` attr directly -- `cssom.core/apply-cascade`'s
   `style-element` clears and rebuilds every `:style/*` attr from
   `:style-inline` + stylesheet rules on every page commit, silently
   reverting the mutation on the very next commit.

   Runs `value` through the SAME `css/parse-declarations-with-importance`
   pipeline `set-style-attribute` above already uses, by synthesizing a
   one-property `\"<prop>: <value>\"` declaration string -- previously this
   merged whatever raw JS string it received straight into :style-inline
   with ZERO coercion, unlike set-style-attribute's own cssText-replace
   path. Confirmed via direct REPL reproduction before this fix: a script
   doing `el.style.lineHeight = \"24px\"` (setting an ABSOLUTE line-height)
   left the raw string \"24px\" in :style-inline, which cssom.layout's own
   resolve-line-height then mis-parsed as a 24x MULTIPLIER instead (its
   own `(string? raw)` branch assumes a raw string can only ever mean a
   unitless multiplier, an assumption that already held for every OTHER
   producer of this value -- the cssText/inline-style-attribute path
   always pre-coerces a bare px value to a real number first -- except
   this one). This also closes a related, more severe gap for the same
   reason: a script setting a SHORTHAND property individually (e.g.
   `el.style.boxShadow = \"2px 3px 5px red\"`) previously wrote a single,
   unrecognized `:box-shadow` key that cssom.layout/node-style never
   reads at all -- the shorthand was silently DROPPED entirely, not just
   mis-typed, since only parse-declarations-with-importance's own
   expand-box-shadow-shorthand (etc.) ever populates the actual longhand
   keys (:box-shadow-x/:box-shadow-y/...) layout reads, and that only
   ever ran via set-style-attribute before this fix.

   Falls back to the exact pre-existing raw-assoc behavior when the
   synthesized declaration parses to nothing at all (parse-declarations-
   with-importance's own established behavior for a blank/empty value,
   e.g. `el.style.color = \"\"`, a common real-world 'unset this property'
   idiom) -- preserving that edge case byte-for-byte rather than
   incidentally changing it as a side effect of this fix."
  [document node-id attr value]
  (let [prop (keyword (name (keyword attr)))
        node (get-in document [:nodes node-id])
        parsed (css/parse-declarations-with-importance (str (name prop) ": " value))
        additions (into {} (map (fn [[k v]] [k (:value v)])) parsed)
        additions (if (seq additions) additions {prop value})
        style-inline (merge (get-in node [:attrs :style-inline] {}) additions)
        style-important (reduce disj (get-in node [:attrs :style-inline-important] #{}) (keys additions))]
    (-> document
        (dom/set-attribute node-id :style-inline style-inline)
        (dom/set-attribute node-id :style-inline-important style-important)
        (dom/set-attribute node-id (keyword attr) value))))

(defn- remove-style-property
  "`style.removeProperty(prop)`'s counterpart to `set-style-property` above
   -- removes just the one property from `:style-inline` (so the next
   cascade recompute no longer re-applies it), rather than the generic
   attribute-removal path this used to fall through to, which only ever
   touched the derived `:style/<prop>` attr and left the stale value in
   `:style-inline` to keep winning the cascade on every subsequent commit."
  [document node-id attr]
  (let [prop (keyword (name (keyword attr)))
        node (get-in document [:nodes node-id])
        style-inline (dissoc (get-in node [:attrs :style-inline] {}) prop)
        style-important (disj (get-in node [:attrs :style-inline-important] #{}) prop)]
    (-> document
        (dom/set-attribute node-id :style-inline style-inline)
        (dom/set-attribute node-id :style-inline-important style-important)
        (update-in [:nodes node-id :attrs] dissoc (keyword attr)))))

(defn- remove-attribute
  [document node-id attr]
  (cond
    (style-attr? attr) (clear-style-attrs document node-id)
    (style-property-attr? attr) (remove-style-property document node-id attr)
    :else (dom/remove-attribute document node-id attr)))

(defn- create-fragment
  [document]
  (let [id (:next-id document)]
    [id (-> document
            (update :next-id inc)
            (assoc-in [:nodes id] {:node/id id
                                   :node/type :document-fragment
                                   :children []})
            (update :ops conj [:dom/create-fragment id]))]))

(defn- fragment-node?
  [document node-id]
  (= :document-fragment (get-in document [:nodes node-id :node/type])))

(defn- append-child-or-fragment
  [document parent-id child-id]
  (if (fragment-node? document child-id)
    (let [children (vec (get-in document [:nodes child-id :children] []))]
      {:document (assoc-in (reduce #(dom/append-child %1 parent-id %2)
                                   document
                                   children)
                           [:nodes child-id :children]
                           [])
       :node/id child-id})
    {:document (dom/append-child document parent-id child-id)
     :node/id child-id}))

(defn- insert-child-or-fragment-before
  [document parent-id child-id before-id]
  (if (fragment-node? document child-id)
    (let [children (vec (get-in document [:nodes child-id :children] []))]
      {:document (assoc-in (reduce #(dom/insert-before %1 parent-id %2 before-id)
                                   document
                                   children)
                           [:nodes child-id :children]
                           [])
       :node/id child-id})
    {:document (dom/insert-before document parent-id child-id before-id)
     :node/id child-id}))

(defn- clone-node*
  [document source-id deep?]
  (let [source (get-in document [:nodes source-id])]
    (case (:node/type source)
      :text
      (dom/create-text-node document (:text source))

      :element
      (let [[id document] (dom/create-element document (:tag source))
            document (reduce-kv #(dom/set-attribute %1 id %2 %3)
                                document
                                (or (:attrs source) {}))]
        [id (if deep?
              (reduce (fn [document child-id]
                        (let [[cloned-child-id document] (clone-node* document child-id true)]
                          (dom/append-child document id cloned-child-id)))
                      document
                      (:children source))
              document)])

      :document-fragment
      (let [[id document] (create-fragment document)]
        [id (if deep?
              (reduce (fn [document child-id]
                        (let [[cloned-child-id document] (clone-node* document child-id true)]
                          (dom/append-child document id cloned-child-id)))
                      document
                      (:children source))
              document)])

      [nil document])))

(defn- import-node*
  [document source-document source-id]
  (let [source (get-in source-document [:nodes source-id])]
    (case (:node/type source)
      :text
      (dom/create-text-node document (:text source))

      :element
      (let [[id document] (dom/create-element document (:tag source))
            document (reduce-kv #(dom/set-attribute %1 id %2 %3)
                                document
                                (or (:attrs source) {}))]
        [id (reduce (fn [document child-id]
                      (let [[imported-child-id document] (import-node* document source-document child-id)]
                        (dom/append-child document id imported-child-id)))
                    document
                    (:children source))])

      [nil document])))

(defn- set-inner-html
  [document node-id html-text]
  (let [fragment-document (html/parse-into-document html-text)
        fragment-root (:root fragment-document)
        children (vec (get-in fragment-document [:nodes fragment-root :children] []))
        document (dom/remove-children document node-id)]
    {:document (reduce (fn [document child-id]
                         (let [[imported-child-id document] (import-node* document fragment-document child-id)]
                           (dom/append-child document node-id imported-child-id)))
                       document
                       children)
     :node/id node-id}))

(defn- set-outer-html
  [document node-id html-text]
  (if-let [parent-id (get (parent-index document) node-id)]
    (let [fragment-document (html/parse-into-document html-text)
          fragment-root (:root fragment-document)
          children (vec (get-in fragment-document [:nodes fragment-root :children] []))
          document (reduce (fn [document child-id]
                             (let [[imported-child-id document] (import-node* document fragment-document child-id)]
                               (dom/insert-before document parent-id imported-child-id node-id)))
                           document
                           children)]
      {:document (dom/remove-child document parent-id node-id)
       :node/id node-id})
    {:document document
     :node/id node-id}))

(defn- insert-adjacent-html
  "Real `Element.insertAdjacentHTML(position, html)`: parses `html-text` as
   a real HTML fragment (the SAME `html/parse-into-document` +
   `import-node*` machinery `set-inner-html`/`set-outer-html` already use,
   just landing the parsed nodes at one of 4 positions relative to
   `node-id` instead of replacing its content/itself) and inserts its
   top-level nodes, in order, at `position`:

     \"beforebegin\" -- as siblings immediately BEFORE `node-id`, under
                        `node-id`'s own parent (a no-op if `node-id` has
                        no parent, matching real `insertAdjacentHTML` on a
                        detached node -- there's nowhere to insert a
                        sibling).
     \"afterbegin\"  -- as the FIRST children of `node-id`, before
                        whatever its current first child is (or appended
                        if `node-id` currently has none).
     \"beforeend\"   -- as the LAST children of `node-id` (plain append).
     \"afterend\"    -- as siblings immediately AFTER `node-id`, under
                        `node-id`'s own parent (same no-op-if-detached
                        rule as beforebegin).

   Each of the 4 branches inserts every parsed top-level node relative to
   the SAME captured anchor (the original first-child / next-sibling /
   `node-id` itself, computed once before the loop) rather than
   re-deriving it after each insertion -- this is what keeps multiple
   top-level nodes in a single `html` string (e.g. `\"<b>a</b><i>b</i>\"`)
   landing in their own correct relative order instead of reversed."
  [document node-id position html-text]
  (let [fragment-document (html/parse-into-document html-text)
        fragment-root (:root fragment-document)
        children (vec (get-in fragment-document [:nodes fragment-root :children] []))
        import-all (fn [document insert-fn]
                     (reduce (fn [document child-id]
                               (let [[imported-id document] (import-node* document fragment-document child-id)]
                                 (insert-fn document imported-id)))
                             document
                             children))]
    (case position
      "beforebegin"
      (if-let [parent-id (get (parent-index document) node-id)]
        {:document (import-all document #(dom/insert-before %1 parent-id %2 node-id))
         :node/id node-id}
        {:document document :node/id node-id})

      "afterbegin"
      (let [first-child (first (get-in document [:nodes node-id :children] []))]
        {:document (import-all document #(dom/insert-before %1 node-id %2 first-child))
         :node/id node-id})

      "beforeend"
      {:document (import-all document #(dom/append-child %1 node-id %2))
       :node/id node-id}

      "afterend"
      (if-let [parent-id (get (parent-index document) node-id)]
        (let [siblings (vec (get-in document [:nodes parent-id :children] []))
              idx (.indexOf siblings node-id)
              next-id (when (and (<= 0 idx) (< (inc idx) (count siblings)))
                        (nth siblings (inc idx)))]
          {:document (import-all document #(dom/insert-before %1 parent-id %2 next-id))
           :node/id node-id})
        {:document document :node/id node-id})

      {:document document :node/id node-id})))

(defn- split-text-node
  [document node-id offset]
  (let [text (str (get-in document [:nodes node-id :text] ""))
        offset (max 0 (min (count text) (long (or offset 0))))
        before (subs text 0 offset)
        after (subs text offset)
        parents (parent-index document)
        parent-id (get parents node-id)
        parent-children (get-in document [:nodes parent-id :children] [])
        idx (when parent-id (.indexOf (vec parent-children) node-id))
        next-id (when (and idx (not (neg? idx)))
                  (nth parent-children (inc idx) nil))
        document (-> document
                     (assoc-in [:nodes node-id :text] before)
                     (update :ops conj [:dom/set-text node-id before]))
        [new-id document] (dom/create-text-node document after)
        document (if parent-id
                   (dom/insert-before document parent-id new-id next-id)
                   document)]
    {:document document :node/id new-id}))

(defn- normalize-node
  [document node-id]
  (let [children (vec (get-in document [:nodes node-id :children] []))
        document (reduce (fn [document child-id]
                           (if (= :element (get-in document [:nodes child-id :node/type]))
                             (normalize-node document child-id)
                             document))
                         document
                         children)
        children (vec (get-in document [:nodes node-id :children] []))]
    (loop [document document
           result []
           children children
           active-text nil]
      (if-let [child-id (first children)]
        (let [node (get-in document [:nodes child-id])]
          (if (= :text (:node/type node))
            (let [text (str (:text node ""))]
              (cond
                (empty? text)
                (recur (dom/remove-child document node-id child-id)
                       result
                       (rest children)
                       active-text)

                active-text
                (let [merged (str (get-in document [:nodes active-text :text] "") text)]
                  (recur (-> document
                             (assoc-in [:nodes active-text :text] merged)
                             (update :ops conj [:dom/set-text active-text merged])
                             (dom/remove-child node-id child-id))
                         result
                         (rest children)
                         active-text))

                :else
                (recur document (conj result child-id) (rest children) child-id)))
            (recur document (conj result child-id) (rest children) nil)))
        document))))

(defn apply-mutation
  [document {:keys [dom/op tag attrs attr value text title html offset deep? position] :as mutation}]
  (case op
    :create-element
    (let [[id document] (dom/create-element document tag)
          document (reduce-kv #(dom/set-attribute %1 id %2 %3)
                              document
                              (or attrs {}))]
      {:document document :node/id id})

    :create-text
    (let [[id document] (dom/create-text-node document text)]
      {:document document :node/id id})

    :set-text
    (let [node-id (:node/id mutation)]
      {:document (-> document
                     (assoc-in [:nodes node-id :text] (str text))
                     (update :ops conj [:dom/set-text node-id (str text)]))
       :node/id node-id})

    :set-title
    {:document (set-document-title document title)
     :title (str title)}

    :split-text
    (split-text-node document (:node/id mutation) offset)

    :create-fragment
    (let [[id document] (create-fragment document)]
      {:document document :node/id id})

    :clone-node
    (let [[id document] (clone-node* document (:source/id mutation) (boolean deep?))]
      {:document document :node/id id})

    :set-inner-html
    (set-inner-html document (:node/id mutation) html)

    :set-outer-html
    (set-outer-html document (:node/id mutation) html)

    :insert-adjacent-html
    (insert-adjacent-html document (:node/id mutation) position html)

    :normalize
    (let [node-id (:node/id mutation)]
      {:document (normalize-node document node-id)
       :node/id node-id})

    :set-attribute
    (let [node-id (:node/id mutation)]
      {:document (cond
                   (style-attr? attr) (set-style-attribute document node-id value)
                   (style-property-attr? attr) (set-style-property document node-id attr value)
                   :else (dom/set-attribute document node-id attr value))
       :node/id node-id})

    :remove-attribute
    (let [node-id (:node/id mutation)]
      {:document (remove-attribute document node-id attr)
       :node/id node-id})

    :append-child
    (let [parent-id (:parent/id mutation)
          child-id (:child/id mutation)]
      (append-child-or-fragment document parent-id child-id))

    :remove-child
    (let [parent-id (:parent/id mutation)
          child-id (:child/id mutation)]
      {:document (dom/remove-child document parent-id child-id)
       :node/id child-id})

    :insert-before
    (let [parent-id (:parent/id mutation)
          child-id (:child/id mutation)
          before-id (:before/id mutation)]
      (insert-child-or-fragment-before document parent-id child-id before-id))

    :remove-children
    (let [node-id (:node/id mutation)]
      {:document (dom/remove-children document node-id)
       :node/id node-id})

    :focus-node
    (let [node-id (:node/id mutation)]
      {:document (-> document
                     (assoc :focus node-id)
                     (update :ops conj [:dom/focus node-id]))
       :node/id node-id})

    :blur-node
    (let [node-id (:node/id mutation)]
      {:document (cond-> (update document :ops conj [:dom/blur node-id])
                   (= node-id (:focus document)) (assoc :focus nil))
       :node/id node-id})

    {:document document
     :error :dom/unknown-mutation
     :mutation mutation}))

(defn handle-request
  [document request]
  (case (:capability request)
    :dom/query
    (case (:dom/query request)
      :query-selector {:document document
                       :result (query-selector document (:selector request))}
      :query-selector-all {:document document
                           :result (query-selector-all document (:selector request))}
      :get-element-by-id {:document document
                          :result (get-element-by-id document (:id request))}
      :node {:document document
             :result (node-snapshot document (:node/id request))}
      :document {:document document
                 :result (document-snapshot document)}
      {:document document :error :dom/unknown-query})

    :dom/mutate
    (apply-mutation document request)

    :event/listen
    (add-event-listener document
                        (:node/id request)
                        (:event/type request)
                        (:handler/id request))

    :event/remove
    (remove-event-listener document
                           (:node/id request)
                           (:event/type request)
                           (:handler/id request))

    :event/dispatch
    (dispatch-event document
                    (:node/id request)
                    (:event request))

    {:document document :error :dom/unsupported-capability}))
