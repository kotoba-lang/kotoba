(ns browser.browser-use
  "browser-use IBrowser adapter for the kotoba-only browser.

  This namespace is optional: load it with the `:browser-use` alias so
  browser-use remains unchanged and the kotoba browser supplies the host
  capability expected by browseruse.browser/IBrowser."
  (:require [browser.audit :as audit]
            [browser.dom-bridge :as dom-bridge]
            [browser.page-script :as page-script]
            [browser.session :as session]
            [browseruse.actions :as browser-use-actions]
            [browseruse.browser :as browser-use]
            [kotoba.lang.text :as str]
            [kotoba.wasm.host :as host]))

(def interactive-tags #{:a :button :input :textarea :select})

(declare extended-actions first-scrollable-node-id screenshot session)

(defn- attrs
  [node]
  (or (:attrs node) {}))

(defn- truthy?
  "Real HTML boolean-attribute presence: `true` (this repo's own htmldom
  parser's value for a bare attribute like `disabled`), the empty string
  (`disabled=\"\"`), or any other non-blank value that isn't literally
  \"false\" -- this last case is what actually determines a boolean
  attribute written in the common XHTML-compatible explicit form
  (`disabled=\"disabled\"`, `checked=\"checked\"`, `selected=\"selected\"`,
  `hidden=\"hidden\"`), which the previous version of this fn never
  recognized. Mirrors htmldom.core's own private `truthy-attr?`, which
  already gets this right for htmldom's own internal default-value
  computation (e.g. an <option selected=\"selected\">'s selectedness)."
  [value]
  (or (= true value)
      (= "" value)
      (and (string? value)
           (not (str/blank? value))
           (not= "false" (str/lower value)))))

(defn- blankish?
  [s]
  (str/blank? (str s)))

(defn- style-value
  [node k]
  (or (get-in node [:attrs (keyword "style" (name k))])
      (get-in node [:attrs :style k])))

(defn- decorative-image?
  "Ported from org-w3-aria's aria.core/decorative-image? -- per HTML-AAM's
   <img> role-mapping table, an <img alt=\"\"> (alt PRESENT and blank --
   the standard \"decorative image\" idiom, e.g. a spacer/divider graphic)
   computes an implicit role of presentation and must be excluded from
   the tree entirely, same as an explicit role=\"presentation\"/\"none\"
   node already is. An img with NO alt attribute at all is a separate,
   unrelated gap (missing alt text) and must NOT match here -- it still
   gets the ordinary implicit \"img\" role. An explicit `role` attribute
   always wins over this implicit default, matching ARIA precedence.
   hidden-node? was missing this check, unlike aria.core/hidden? --
   confirmed via direct REPL reproduction before touching source: a
   decorative <img alt=\"\"> still appeared in browser-use's own semantic
   tree, inconsistent with the real accessibility tree, which correctly
   excludes it."
  [node]
  (and (= :img (:tag node))
       (not (contains? (attrs node) :role))
       (contains? (attrs node) :alt)
       (blankish? (get (attrs node) :alt))))

(defn- hidden-node?
  [node]
  (or (truthy? (get-in node [:attrs :hidden]))
      (= "true" (str/lower (str (get-in node [:attrs :aria-hidden]))))
      (= "none" (str/lower (str (style-value node :display))))
      (contains? #{"presentation" "none"} (str/lower (str (get-in node [:attrs :role]))))
      (and (= :input (:tag node))
           (= "hidden" (str/lower (str (get-in node [:attrs :type])))))
      (decorative-image? node)))

(defn- text-content
  "This file's own semantic-node (below) already gates on hidden-node? --
   text-content previously did NOT, unlike its sibling of the same name/
   job in org-w3-aria's aria.core (which correctly stops recursing into a
   hidden element). This is the function indexed-elements (further below)
   uses to compute the :text field the browser-use AI agent reads to
   decide what an interactive element actually says before clicking it --
   a hidden descendant (e.g. a <span hidden> aside inside a <button>)
   silently leaked into that text, misrepresenting the element to the
   very agent this text exists to inform. Confirmed via direct REPL
   reproduction before touching source."
  [document node-id]
  (let [node (get-in document [:nodes node-id])]
    (case (:node/type node)
      :text (str (:text node))
      :element (if (hidden-node? node)
                 ""
                 (apply str (map #(text-content document %)
                                 (:children node))))
      "")))

(defn- input-value
  [document node-id node]
  (cond
    (= :textarea (:tag node))
    (or (get-in node [:attrs :value])
        (text-content document node-id))

    (= :select (:tag node))
    (or (get-in node [:attrs :value])
        (some (fn [option-id]
                (let [option (get-in document [:nodes option-id])]
                  (when (and (= :option (:tag option))
                             (truthy? (get-in option [:attrs :selected])))
                    (or (get-in option [:attrs :value])
                        (text-content document option-id)))))
              (dom-bridge/query-selector-all document "option"))
        "")

    :else
    (get-in node [:attrs :value])))

(defn- document-base-uri
  [document]
  (or (:base-uri document)
      (:url document)
      "about:blank"))

(defn- resolved-url-attrs
  [document node]
  (reduce (fn [result attr-name]
            (if-let [value (get-in node [:attrs attr-name])]
              (assoc result attr-name
                     (page-script/resolve-src (document-base-uri document)
                                              value))
              result))
          {}
          [:href :src]))

(defn- browser-use-attrs
  [document node-id node]
  (let [base (->> (attrs node)
                  (map (fn [[k v]] [k (str v)]))
                  (into {}))
        base (merge base (resolved-url-attrs document node))]
    (cond-> base
      (contains? #{:input :textarea :select} (:tag node))
      (assoc :value (str (or (input-value document node-id node) "")))

      (truthy? (get-in node [:attrs :checked]))
      (assoc :checked "true")

      (truthy? (get-in node [:attrs :disabled]))
      (assoc :disabled "true"))))

(defn- ancestor-or-self-hidden?
  "hidden-node? alone only checks the node ITSELF -- a real, common
   pattern (an interactive element nested inside a hidden container,
   e.g. <div hidden><button>Nested</button></div>) still slipped through
   indexed-elements' own self-only check, since a flat element-nodes
   walk has no ancestry awareness at all (unlike semantic-node's own
   recursive tree-walk, which naturally short-circuits at a hidden
   parent and never visits its children in the first place). Confirmed
   via direct REPL reproduction before touching source. `parents` is
   the whole document's parent-index, computed ONCE by the caller and
   threaded through -- recomputing it per-node here would make this
   function's own caller (a filter over every element in the document)
   quadratic."
  [document parents node-id]
  (loop [id node-id]
    (cond
      (nil? id) false
      (hidden-node? (get-in document [:nodes id])) true
      :else (recur (get parents id)))))

(defn indexed-elements
  "Project the current kotoba document into browser-use indexed elements.

   This file's own semantic-node/text-content already gate on hidden-
   node? -- indexed-elements did NOT, unlike those two. A real, common
   pattern (a submit button hidden via style=\"display:none\", a hidden
   token input) was still listed as an actionable indexed element, and
   is actually clickable/typeable: click_node!/type_node! build a
   synthetic event carrying an explicit :node/id, which document-input's
   own target resolution uses directly, completely bypassing real
   hit-testing (which is where visibility would normally be enforced).
   A real user could never see or reach such an element, but the AI
   agent driving this browser via indexed clicks/types could. Confirmed
   via direct REPL reproduction before touching source."
  [document]
  (let [parents (dom-bridge/parent-index document)]
    (->> (dom-bridge/element-nodes document)
         (filter #(and (contains? interactive-tags (:tag %))
                      (not (ancestor-or-self-hidden? document parents (:node/id %)))))
         (map-indexed
          (fn [index node]
            (let [node-id (:node/id node)]
              {:index index
               :node/id node-id
               :tag (name (:tag node))
               :text (text-content document node-id)
               :attrs (browser-use-attrs document node-id node)})))
         vec)))

(def semantic-tags
  #{:main :nav :header :footer :section :article :aside :form :h1 :h2 :h3 :h4
    :h5 :h6 :p :blockquote :pre :code :ul :ol :li :table :thead :tbody :tfoot
    :tr :th :td :img :figure :figcaption :label :a :button :input :textarea
    :select :option})

(defn- semantic-attrs
  [document node-id node]
  (let [attrs (browser-use-attrs document node-id node)]
    (select-keys attrs [:id :class :role :name :type :placeholder :value :checked
                        :disabled :href :src :alt :title :aria-label
                        :aria-labelledby :aria-describedby])))

(defn- semantic-node
  [document node-id]
  (let [node (get-in document [:nodes node-id])]
    (case (:node/type node)
      :text
      (let [text (str/trim (str (:text node)))]
        (when-not (blankish? text)
          {:type "text" :text text}))

      :element
      (when-not (hidden-node? node)
        (let [children (->> (:children node)
                            (keep #(semantic-node document %))
                            vec)
              text (str/trim (text-content document node-id))
              include? (or (contains? semantic-tags (:tag node))
                           (seq children)
                           (not (blankish? text)))]
          (when include?
            (cond-> {:type "element"
                     :node/id node-id
                     :tag (name (:tag node))}
              (seq (semantic-attrs document node-id node))
              (assoc :attrs (semantic-attrs document node-id node))

              (and (not (seq children))
                   (not (blankish? text)))
              (assoc :text text)

              (seq children)
              (assoc :children children)))))

      nil)))

(defn semantic-tree
  "Project a document into an agent-readable semantic DOM outline."
  [document]
  (when-let [root (:root document)]
    (semantic-node document root)))

(defn- semantic-text
  [node]
  (let [own-text (or (:text node)
                     (get-in node [:attrs :aria-label])
                     (get-in node [:attrs :alt]))
        child-texts (keep semantic-text (:children node))]
    (str/trim (str/join " " (remove blankish? (cons own-text child-texts))))))

(defn- tail
  [xs n]
  (let [xs (vec (or xs []))]
    (subvec xs (max 0 (- (count xs) n)))))

(defn- recorded-host-state
  [session]
  (when-let [h (:browser.session/host session)]
    (try
      (host/recorded h)
      (catch #?(:clj Throwable :cljs :default) _
        nil))))

(defn navigation-state
  "Return a compact navigation lifecycle summary for browser-use debugging."
  [session]
  (let [navigation (:browser.session/navigation session)
        error-document (get-in session [:browser.session/error-document
                                        :browser/document])]
    (cond-> {:index (:index navigation)
             :entries (mapv (fn [{:keys [url page]}]
                              {:url url
                               :status (get-in page [:browser/response :status])
                               :error (:browser/error page)})
                            (:entries navigation))
             :redirects (vec (:redirects navigation))
             :error (:browser.session/error session)
             :page-generation (:browser.session/page-generation session)}
      error-document
      (assoc :error-document-text (text-content error-document
                                                (:root error-document))))))

(defn debug-state
  "Return kotoba-specific state useful when a browser-use action mis-targets."
  [session]
  (let [page (:browser.session/page session)
        audit-log (:browser.session/audit session)]
    (cond-> {:page-generation (:browser.session/page-generation session)
             :history-tail (tail (:browser.session/history session) 20)
             :last-batch (:browser.session/last-batch session)
             :draw-ops (:browser/draw-ops page)
             :navigation (navigation-state session)
             :audit-summary (audit/replay-summary audit-log)
             :audit-events-tail (tail (audit/events audit-log) 20)
             :document-input-result (:browser.session/document-input-result session)}
      (:browser.session/host session)
      (assoc :host-recorded (recorded-host-state session))

      (or (:browser.session/page session)
          (:browser.session/surface session))
      (assoc :accessibility-tree (session/accessibility-tree session)))))

(defn browser-state
  [session]
  (let [page (:browser.session/page session)
        document (:browser/document page)]
    {:url (:browser/url page)
     :title (:browser/title page)
     :elements (if document (indexed-elements document) [])
     :semantic-tree (when document (semantic-tree document))
     :debug (debug-state session)}))

(defn- element-at
  [session index]
  (or (nth (:elements (browser-state session)) index nil)
      (throw (ex-info "No browser-use element at index"
                      {:index index
                       :url (get-in session [:browser.session/page :browser/url])}))))

(defn- current-value
  [session node-id]
  (let [document (get-in session [:browser.session/page :browser/document])
        node (get-in document [:nodes node-id])]
    (str (or (input-value document node-id node) ""))))

(defn- node-at-index
  [kotoba-browser index]
  (:node/id (element-at @(:session* kotoba-browser) index)))

(defn- draw-op-for-node
  [session node-id]
  (some #(when (and (= :node (:draw/op %))
                    (= node-id (:id %)))
           %)
        (get-in session [:browser.session/page :browser/draw-ops])))

(defn- node-center
  [session node-id]
  (if-let [{:keys [x y w h]} (draw-op-for-node session node-id)]
    {:x (+ x (/ (or w 0) 2))
     :y (+ y (/ (or h 0) 2))}
    {:x 0 :y 0}))

(defn- node-attrs
  [session node-id]
  (get-in session [:browser.session/page :browser/document :nodes node-id :attrs]))

(defn- document
  [session]
  (get-in session [:browser.session/page :browser/document]))

(defn- node-at-selector
  [session selector]
  (or (some-> (document session)
              (dom-bridge/query-selector selector))
      (throw (ex-info "No element matches selector"
                      {:selector selector
                       :url (get-in session [:browser.session/page :browser/url])}))))

(defn- click-node!
  [kotoba-browser node-id]
  (let [{:keys [x y]} (node-center @(:session* kotoba-browser) node-id)]
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :pointer/click
            :node/id node-id
            :x x
            :y y})
    (browser-use/-state kotoba-browser)))

(defn- type-node!
  [kotoba-browser node-id text]
  (let [value (current-value @(:session* kotoba-browser) node-id)
        {:keys [x y]} (node-center @(:session* kotoba-browser) node-id)]
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :pointer/click
            :node/id node-id
            :x x
            :y y})
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :text/selection
            :node/id node-id
            :start 0
            :end (count value)})
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :text/input
            :node/id node-id
            :text text})
    (browser-use/-state kotoba-browser)))

(defn- clear-node!
  [kotoba-browser node-id]
  (type-node! kotoba-browser node-id ""))

(defn- append-node!
  [kotoba-browser node-id text]
  (let [value (current-value @(:session* kotoba-browser) node-id)
        {:keys [x y]} (node-center @(:session* kotoba-browser) node-id)
        caret (count value)]
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :pointer/click
            :node/id node-id
            :x x
            :y y})
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :text/selection
            :node/id node-id
            :start caret
            :end caret})
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :text/input
            :node/id node-id
            :text text})
    (browser-use/-state kotoba-browser)))

(defn- check-node!
  [kotoba-browser node-id]
  (let [checked? (truthy? (:checked (node-attrs @(:session* kotoba-browser) node-id)))]
    (when-not checked?
      (click-node! kotoba-browser node-id)))
  (browser-use/-state kotoba-browser))

(defn- uncheck-node!
  [kotoba-browser node-id]
  (let [checked? (truthy? (:checked (node-attrs @(:session* kotoba-browser) node-id)))]
    (when checked?
      (click-node! kotoba-browser node-id)))
  (browser-use/-state kotoba-browser))

(defn- select-node!
  [kotoba-browser node-id value]
  (swap! (:session* kotoba-browser)
         session/apply-document-input-event!
         {:event/type :select/change
          :node/id node-id
          :value value})
  (browser-use/-state kotoba-browser))

(defn check!
  "Recipe host capability for browseruse.recipe `:check` steps."
  [kotoba-browser index]
  (check-node! kotoba-browser (node-at-index kotoba-browser index)))

(defn uncheck!
  "Uncheck the indexed checkbox-like element when it is currently checked."
  [kotoba-browser index]
  (uncheck-node! kotoba-browser (node-at-index kotoba-browser index)))

(defn click-selector!
  "Click the first element matching a DOM selector."
  [kotoba-browser selector]
  (click-node! kotoba-browser (node-at-selector @(:session* kotoba-browser)
                                                selector)))

(defn type-selector!
  "Replace the current value of the first input-like element matching a selector."
  [kotoba-browser selector text]
  (type-node! kotoba-browser (node-at-selector @(:session* kotoba-browser)
                                               selector)
              text))

(defn clear-selector!
  "Clear the first input-like element matching a selector."
  [kotoba-browser selector]
  (clear-node! kotoba-browser (node-at-selector @(:session* kotoba-browser)
                                                selector)))

(defn append-selector!
  "Append text to the first input-like element matching a selector."
  [kotoba-browser selector text]
  (append-node! kotoba-browser (node-at-selector @(:session* kotoba-browser)
                                                 selector)
                text))

(defn check-selector!
  "Check the first checkbox/radio-like element matching a selector."
  [kotoba-browser selector]
  (check-node! kotoba-browser (node-at-selector @(:session* kotoba-browser)
                                                selector)))

(defn uncheck-selector!
  "Uncheck the first checkbox-like element matching a selector when checked."
  [kotoba-browser selector]
  (uncheck-node! kotoba-browser (node-at-selector @(:session* kotoba-browser)
                                                  selector)))

(defn select-selector!
  "Select an option value on the first select element matching a selector."
  [kotoba-browser selector value]
  (select-node! kotoba-browser (node-at-selector @(:session* kotoba-browser)
                                                 selector)
                value))

(defn click-at!
  "Click a page coordinate through the session hit-test path."
  [kotoba-browser x y]
  (swap! (:session* kotoba-browser)
         session/apply-document-input-event!
         {:event/type :pointer/click
          :x x
          :y y})
  (browser-use/-state kotoba-browser))

(defn hover-at!
  "Move the pointer to a page coordinate through the session hit-test path."
  [kotoba-browser x y]
  (swap! (:session* kotoba-browser)
         session/apply-document-input-event!
         {:event/type :pointer/move
          :x x
          :y y})
  (browser-use/-state kotoba-browser))

(defn scroll-selector!
  "Scroll the first element matching a selector with a wheel delta."
  ([kotoba-browser selector delta-y]
   (scroll-selector! kotoba-browser selector 0 delta-y))
  ([kotoba-browser selector delta-x delta-y]
   (let [node-id (node-at-selector @(:session* kotoba-browser) selector)
         {:keys [x y]} (node-center @(:session* kotoba-browser) node-id)]
     (swap! (:session* kotoba-browser)
            session/apply-document-input-event!
            {:event/type :pointer/wheel
             :node/id node-id
             :delta-x (or delta-x 0)
             :delta-y (or delta-y 0)
             :x x
             :y y})
     (browser-use/-state kotoba-browser))))

(defn scroll-at!
  "Scroll at a page coordinate using the session hit-test path."
  ([kotoba-browser x y delta-y]
   (scroll-at! kotoba-browser x y 0 delta-y))
  ([kotoba-browser x y delta-x delta-y]
   (swap! (:session* kotoba-browser)
          session/apply-document-input-event!
          {:event/type :pointer/wheel
           :x x
           :y y
           :delta-x (or delta-x 0)
           :delta-y (or delta-y 0)})
   (browser-use/-state kotoba-browser)))

(defn select!
  "Recipe host capability for browseruse.recipe `:select` steps."
  [kotoba-browser index value]
  (select-node! kotoba-browser (node-at-index kotoba-browser index) value))

(defn focus!
  "Focus the indexed element through the same document input reducer as clicks."
  [kotoba-browser index]
  (let [node-id (node-at-index kotoba-browser index)
        {:keys [x y]} (node-center @(:session* kotoba-browser) node-id)]
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :pointer/click
            :node/id node-id
            :x x
            :y y})
    (browser-use/-state kotoba-browser)))

(defn hover!
  "Record a hover-sized pointer move against the indexed element for debugging."
  [kotoba-browser index]
  (let [node-id (node-at-index kotoba-browser index)
        {:keys [x y]} (node-center @(:session* kotoba-browser) node-id)]
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :pointer/move
            :node/id node-id
            :x x
            :y y})
    (browser-use/-state kotoba-browser)))

(defn press-key!
  "Press a key against the currently focused or indexed element."
  ([kotoba-browser key]
   (press-key! kotoba-browser nil key))
  ([kotoba-browser index key]
   (let [node-id (when (some? index)
                   (node-at-index kotoba-browser index))]
     (swap! (:session* kotoba-browser)
            session/apply-document-input-event!
            (cond-> {:event/type :key/down
                     :key key}
              node-id (assoc :node/id node-id)))
     (browser-use/-state kotoba-browser))))

(defn scroll-to!
  "Scroll the nearest scrollable document surface toward the indexed element."
  [kotoba-browser index]
  (let [node-id (node-at-index kotoba-browser index)
        {:keys [y]} (node-center @(:session* kotoba-browser) node-id)
        delta-y (if (> (or y 0) 0) (long y) 0)]
    (swap! (:session* kotoba-browser)
           session/apply-document-input-event!
           {:event/type :pointer/wheel
            :node/id (first-scrollable-node-id @(:session* kotoba-browser))
            :delta-y delta-y
            :delta-x 0
            :x 0
            :y 0})
    (browser-use/-state kotoba-browser)))

(defn recipe-options
  "Options map for browseruse.recipe/run-recipe! over a kotoba browser."
  [kotoba-browser]
  {:check (fn [index] (check! kotoba-browser index))
   :select (fn [index value] (select! kotoba-browser index value))})

(defn- action-result
  [state prefix]
  (str prefix "\n" (browser-use/state->prompt state)))

(defn navigate!
  "Playwright/browser-use-style wrapper around `IBrowser/-navigate!`."
  [kotoba-browser url]
  (browser-use/-navigate! kotoba-browser url))

(defn forward!
  "Move forward in the kotoba navigation history."
  [kotoba-browser]
  (swap! (:session* kotoba-browser) session/forward!)
  (browser-use/-state kotoba-browser))

(defn reload!
  "Reload the current kotoba page through the session navigation lifecycle."
  [kotoba-browser]
  (swap! (:session* kotoba-browser) session/reload!)
  (browser-use/-state kotoba-browser))

(defn get-state
  "Return the current browser-use state without requiring callers to know the protocol."
  [kotoba-browser]
  (browser-use/-state kotoba-browser))

(defn extract
  "Extract page data for browser-use/debug flows.

  `kind` may be `:state`, `:text`, `:semantic`, `:accessibility`, `:draw-ops`,
  or `:snapshot`. String names are accepted for browser-use tool arguments."
  ([kotoba-browser]
   (extract kotoba-browser :semantic))
  ([kotoba-browser kind]
   (let [state (browser-use/-state kotoba-browser)
         kind (keyword (str/replace (name (or kind :semantic)) #"_" "-"))]
     (case kind
       :state state
       :text (semantic-text (:semantic-tree state))
       :semantic (:semantic-tree state)
       :accessibility (get-in state [:debug :accessibility-tree])
       :draw-ops (get-in state [:debug :draw-ops])
       :snapshot (screenshot kotoba-browser)
       (:semantic-tree state)))))

(defn wait-for!
  "Evaluate a browser-use-style wait condition against the current kotoba state.

  This is synchronous because the kotoba-only adapter owns pure session state.
  Hosts that advance time/network/script execution can call this after each
  explicit step and get an auditable result instead of an ambient sleep."
  [kotoba-browser {:keys [selector text url kind] :as condition}]
  (let [state (browser-use/-state kotoba-browser)
        document (document @(:session* kotoba-browser))
        kind (keyword (str/replace (name (or kind :present)) #"_" "-"))
        selector-node (when selector
                        (dom-bridge/query-selector document selector))
        ;; :hidden/:visible previously never consulted hidden-node? at
        ;; all -- both were byte-for-byte dead aliases of :absent/
        ;; :present, checking pure DOM-existence only. A real, common UI
        ;; pattern -- closing a modal, hiding a spinner via
        ;; style="display:none" WITHOUT removing it from the DOM -- left
        ;; :hidden permanently false (the node is still selector-
        ;; matched) and :visible permanently true (a false positive for
        ;; an element that's present but actually hidden). Confirmed via
        ;; direct REPL reproduction before touching source. hidden-node?
        ;; already exists in this same file and is already used for the
        ;; identical purpose in semantic-node above -- wait-for! simply
        ;; never called it.
        selector-hidden? (when selector-node
                            (hidden-node? (get-in document [:nodes selector-node])))
        visible-text (semantic-text (:semantic-tree state))
        url-value (:url state)
        matches (cond-> {}
                  selector (assoc :selector {:ok (boolean selector-node)
                                             :node/id selector-node})
                  text (assoc :text {:ok (str/includes?
                                          (str/lower visible-text)
                                          (str/lower (str text)))
                                     :value visible-text})
                  url (assoc :url {:ok (str/includes?
                                        (str/lower (str url-value))
                                        (str/lower (str url)))
                                   :value url-value}))
        ok? (case kind
              :hidden (and selector (or (not (boolean selector-node)) selector-hidden?))
              :absent (and selector (not (boolean selector-node)))
              :present (and (seq matches) (every? :ok (vals matches)))
              :visible (and (seq matches) (every? :ok (vals matches)) (not selector-hidden?))
              (and (seq matches) (every? :ok (vals matches))))]
    {:ok ok?
     :kind kind
     :condition condition
     :matches matches
     :url url-value}))

(defn diagnose
  "Return non-throwing browser-use targeting diagnostics for the current page."
  ([kotoba-browser]
   (diagnose kotoba-browser {}))
  ([kotoba-browser {:keys [index selector text url] :as request}]
   (let [state (browser-use/-state kotoba-browser)
         document (document @(:session* kotoba-browser))
         elements (:elements state)
         selector-node (when selector
                         (dom-bridge/query-selector document selector))
         index-element (when (some? index)
                         (nth elements index nil))
         visible-text (semantic-text (:semantic-tree state))
         url-value (:url state)
         matches (cond-> {}
                   selector (assoc :selector {:ok (boolean selector-node)
                                              :selector selector
                                              :node/id selector-node})
                   (some? index) (assoc :index {:ok (boolean index-element)
                                                :index index
                                                :element index-element})
                   text (assoc :text {:ok (str/includes?
                                           (str/lower visible-text)
                                           (str/lower (str text)))
                                      :text text
                                      :value visible-text})
                   url (assoc :url {:ok (str/includes?
                                         (str/lower (str url-value))
                                         (str/lower (str url)))
                                    :url url
                                    :value url-value}))
         ok? (if (seq matches)
               (every? :ok (vals matches))
               true)]
     {:ok ok?
      :request request
      :url url-value
      :title (:title state)
      :matches matches
      :candidate-count (count elements)
      :elements (vec (take 20 elements))
      :debug {:history-tail (get-in state [:debug :history-tail])
              :document-input-result (get-in state [:debug :document-input-result])
              :audit-summary (get-in state [:debug :audit-summary])}})))

(defn click!
  "Click an indexed interactive element."
  [kotoba-browser index]
  (click-node! kotoba-browser (node-at-index kotoba-browser index)))

(defn type!
  "Replace the current value of an indexed input-like element."
  [kotoba-browser index text]
  (type-node! kotoba-browser (node-at-index kotoba-browser index) text))

(defn clear!
  "Clear the indexed input-like element."
  [kotoba-browser index]
  (clear-node! kotoba-browser (node-at-index kotoba-browser index)))

(defn append!
  "Append text to the indexed input-like element."
  [kotoba-browser index text]
  (append-node! kotoba-browser (node-at-index kotoba-browser index) text))

(defn press!
  "Press a key against the focused element or an optional indexed element."
  ([kotoba-browser key]
   (press-key! kotoba-browser key))
  ([kotoba-browser index key]
   (press-key! kotoba-browser index key)))

(defn screenshot
  "Return a kotoba-only screenshot snapshot.

  The snapshot is intentionally data-first: it captures the same retained draw
  ops and accessibility projection the WASM renderer consumes. On the JVM, a
  `path` option writes the EDN snapshot so recipe/debug flows can attach an
  artifact without requiring a native PNG backend."
  ([kotoba-browser]
   (screenshot kotoba-browser {}))
  ([kotoba-browser {:keys [path] :as _opts}]
   (let [state (browser-use/-state kotoba-browser)
         debug (:debug state)
         snapshot {:format :kotoba.browser/snapshot
                   :url (:url state)
                   :title (:title state)
                   :elements (:elements state)
                   :semantic-tree (:semantic-tree state)
                   :draw-ops (:draw-ops debug)
                   :accessibility-tree (:accessibility-tree debug)}]
     #?(:clj
        (when path
          (spit path (pr-str snapshot)))
        :cljs nil)
     (cond-> snapshot
       path (assoc :path path)))))

(defn screenshot!
  "Write a kotoba screenshot snapshot to `path` and return the path."
  [kotoba-browser path]
  (:path (screenshot kotoba-browser {:path path})))

(defn browser-use-actions
  "Return the standard browser-use action set plus kotoba compatibility actions."
  [kotoba-browser]
  (vec (concat (browser-use-actions/default-actions kotoba-browser)
               (extended-actions kotoba-browser))))

(defn controller-actions
  "Alias for agents that call the browser-use action registry a controller."
  [kotoba-browser]
  (browser-use-actions kotoba-browser))

(defn extended-actions
  "Additional browser-use-style actions for kotoba-only browser sessions.

  These are intentionally optional so browser-use can remain unchanged while a
  kotoba agent can concatenate them with browseruse.actions/default-actions."
  [kotoba-browser]
  [{:name "get_state"
    :description "Return the current page state."
    :schema {:type "object" :properties {}}
    :fn (fn [_]
          (browser-use/state->prompt (get-state kotoba-browser)))}

   {:name "screenshot"
    :description "Capture the current kotoba retained draw-op snapshot."
    :schema {:type "object"
             :properties {:path {:type "string"}}}
    :fn (fn [{:keys [path]}]
          (let [snapshot (screenshot kotoba-browser (cond-> {}
                                                       path (assoc :path path)))]
            (action-result (get-state kotoba-browser)
                           (str "Captured screenshot snapshot"
                                (when (:path snapshot)
                                  (str " at " (:path snapshot)))))))}

   {:name "extract"
    :description "Extract state, text, semantic tree, accessibility tree, draw ops, or snapshot data."
    :schema {:type "object"
             :properties {:kind {:type "string"
                                 :enum ["semantic" "text" "accessibility"
                                        "draw_ops" "snapshot" "state"]}}}
    :fn (fn [{:keys [kind]}]
          (pr-str (extract kotoba-browser (or kind "semantic"))))}

   {:name "wait_for"
    :description "Check whether selector, text, or URL conditions are satisfied in the current kotoba state."
    :schema {:type "object"
             :properties {:selector {:type "string"}
                          :text {:type "string"}
                          :url {:type "string"}
                          :kind {:type "string"
                                 :enum ["present" "visible" "hidden" "absent"]}}}
   :fn (fn [condition]
          (pr-str (wait-for! kotoba-browser condition)))}

   {:name "diagnose"
    :description "Return non-throwing selector, index, text, and URL targeting diagnostics."
    :schema {:type "object"
             :properties {:selector {:type "string"}
                          :index {:type "integer"}
                          :text {:type "string"}
                          :url {:type "string"}}}
    :fn (fn [request]
          (pr-str (diagnose kotoba-browser request)))}

   {:name "navigation_state"
    :description "Return compact navigation entries, redirects, reload/error state, and error document text."
    :schema {:type "object" :properties {}}
    :fn (fn [_]
          (pr-str (navigation-state @(:session* kotoba-browser))))}

   {:name "go_forward"
    :description "Go forward to the next kotoba navigation entry."
    :schema {:type "object" :properties {}}
    :fn (fn [_]
          (action-result (forward! kotoba-browser) "Went forward"))}

   {:name "reload"
    :description "Reload the current kotoba page."
    :schema {:type "object" :properties {}}
    :fn (fn [_]
          (action-result (reload! kotoba-browser) "Reloaded"))}

   {:name "click"
    :description "Click the interactive element with the given index."
    :schema {:type "object"
             :properties {:index {:type "integer"}}
             :required ["index"]}
    :fn (fn [{:keys [index]}]
          (action-result (click! kotoba-browser index)
                         (str "Clicked [" index "]")))}

   {:name "click_selector"
    :description "Click the first element matching a selector."
    :schema {:type "object"
             :properties {:selector {:type "string"}}
             :required ["selector"]}
    :fn (fn [{:keys [selector]}]
          (action-result (click-selector! kotoba-browser selector)
                         (str "Clicked " selector)))}

   {:name "click_at"
    :description "Click at a page coordinate using kotoba hit testing."
    :schema {:type "object"
             :properties {:x {:type "number"}
                          :y {:type "number"}}
             :required ["x" "y"]}
    :fn (fn [{:keys [x y]}]
          (action-result (click-at! kotoba-browser x y)
                         (str "Clicked at " x "," y)))}

   {:name "type"
    :description "Type text into the input element with the given index."
    :schema {:type "object"
             :properties {:index {:type "integer"}
                          :text {:type "string"}}
             :required ["index" "text"]}
    :fn (fn [{:keys [index text]}]
          (action-result (type! kotoba-browser index text)
                         (str "Typed into [" index "]")))}

   {:name "type_selector"
    :description "Type text into the first input-like element matching a selector."
    :schema {:type "object"
             :properties {:selector {:type "string"}
                          :text {:type "string"}}
             :required ["selector" "text"]}
    :fn (fn [{:keys [selector text]}]
          (action-result (type-selector! kotoba-browser selector text)
                         (str "Typed into " selector)))}

   {:name "clear"
    :description "Clear the indexed input element."
    :schema {:type "object"
             :properties {:index {:type "integer"}}
             :required ["index"]}
    :fn (fn [{:keys [index]}]
          (action-result (clear! kotoba-browser index)
                         (str "Cleared [" index "]")))}

   {:name "clear_selector"
    :description "Clear the first input element matching a selector."
    :schema {:type "object"
             :properties {:selector {:type "string"}}
             :required ["selector"]}
    :fn (fn [{:keys [selector]}]
          (action-result (clear-selector! kotoba-browser selector)
                         (str "Cleared " selector)))}

   {:name "append_text"
    :description "Append text to the indexed input element."
    :schema {:type "object"
             :properties {:index {:type "integer"}
                          :text {:type "string"}}
             :required ["index" "text"]}
    :fn (fn [{:keys [index text]}]
          (action-result (append! kotoba-browser index text)
                         (str "Appended to [" index "]")))}

   {:name "append_text_selector"
    :description "Append text to the first input element matching a selector."
    :schema {:type "object"
             :properties {:selector {:type "string"}
                          :text {:type "string"}}
             :required ["selector" "text"]}
    :fn (fn [{:keys [selector text]}]
          (action-result (append-selector! kotoba-browser selector text)
                         (str "Appended to " selector)))}

   {:name "check_selector"
    :description "Check the first checkbox or radio element matching a selector."
    :schema {:type "object"
             :properties {:selector {:type "string"}}
             :required ["selector"]}
    :fn (fn [{:keys [selector]}]
          (action-result (check-selector! kotoba-browser selector)
                         (str "Checked " selector)))}

   {:name "uncheck"
    :description "Uncheck the indexed checkbox element if it is checked."
    :schema {:type "object"
             :properties {:index {:type "integer"}}
             :required ["index"]}
    :fn (fn [{:keys [index]}]
          (action-result (uncheck! kotoba-browser index)
                         (str "Unchecked [" index "]")))}

   {:name "uncheck_selector"
    :description "Uncheck the first checkbox element matching a selector if it is checked."
    :schema {:type "object"
             :properties {:selector {:type "string"}}
             :required ["selector"]}
    :fn (fn [{:keys [selector]}]
          (action-result (uncheck-selector! kotoba-browser selector)
                         (str "Unchecked " selector)))}

   {:name "select_selector"
    :description "Select an option value in the first select element matching a selector."
    :schema {:type "object"
             :properties {:selector {:type "string"}
                          :value {:type "string"}}
             :required ["selector" "value"]}
    :fn (fn [{:keys [selector value]}]
          (action-result (select-selector! kotoba-browser selector value)
                         (str "Selected " value " in " selector)))}

   {:name "press"
    :description "Press a keyboard key, optionally targeted at an indexed element."
    :schema {:type "object"
             :properties {:key {:type "string"}
                          :index {:type "integer"}}
             :required ["key"]}
    :fn (fn [{:keys [index key]}]
          (action-result (if (some? index)
                           (press! kotoba-browser index key)
                           (press! kotoba-browser key))
                         (str "Pressed " key)))}

   {:name "focus_element"
    :description "Focus the interactive element with the given index."
    :schema {:type "object"
             :properties {:index {:type "integer"}}
             :required ["index"]}
    :fn (fn [{:keys [index]}]
          (action-result (focus! kotoba-browser index)
                         (str "Focused [" index "]")))}

   {:name "hover_element"
    :description "Move the pointer over the interactive element with the given index."
    :schema {:type "object"
             :properties {:index {:type "integer"}}
             :required ["index"]}
    :fn (fn [{:keys [index]}]
          (action-result (hover! kotoba-browser index)
                         (str "Hovered [" index "]")))}

   {:name "hover_at"
    :description "Move the pointer to a page coordinate using kotoba hit testing."
    :schema {:type "object"
             :properties {:x {:type "number"}
                          :y {:type "number"}}
             :required ["x" "y"]}
    :fn (fn [{:keys [x y]}]
          (action-result (hover-at! kotoba-browser x y)
                         (str "Hovered at " x "," y)))}

   {:name "scroll_selector"
    :description "Scroll the first element matching a selector with a wheel delta."
    :schema {:type "object"
             :properties {:selector {:type "string"}
                          :delta_x {:type "number"}
                          :delta_y {:type "number"}}
             :required ["selector" "delta_y"]}
    :fn (fn [{:keys [selector delta_x delta_y]}]
          (action-result (scroll-selector! kotoba-browser selector delta_x delta_y)
                         (str "Scrolled " selector)))}

   {:name "scroll_at"
    :description "Scroll at a page coordinate using kotoba hit testing."
    :schema {:type "object"
             :properties {:x {:type "number"}
                          :y {:type "number"}
                          :delta_x {:type "number"}
                          :delta_y {:type "number"}}
             :required ["x" "y" "delta_y"]}
    :fn (fn [{:keys [x y delta_x delta_y]}]
          (action-result (scroll-at! kotoba-browser x y delta_x delta_y)
                         (str "Scrolled at " x "," y)))}

   {:name "press_key"
    :description "Press a keyboard key, optionally targeted at an indexed element."
    :schema {:type "object"
             :properties {:key {:type "string"}
                          :index {:type "integer"}}
             :required ["key"]}
    :fn (fn [{:keys [index key]}]
          (action-result (if (some? index)
                           (press-key! kotoba-browser index key)
                           (press-key! kotoba-browser key))
                         (str "Pressed " key)))}

   {:name "scroll_to_element"
    :description "Scroll the document toward the interactive element with the given index."
    :schema {:type "object"
             :properties {:index {:type "integer"}}
             :required ["index"]}
    :fn (fn [{:keys [index]}]
          (action-result (scroll-to! kotoba-browser index)
                         (str "Scrolled to [" index "]")))}])

(defn- first-scrollable-node-id
  [session]
  (let [document (get-in session [:browser.session/page :browser/document])]
    (or (some (fn [node]
                (let [overflow (str/lower
                                (str (or (get-in node [:attrs :overflow])
                                         (get-in node [:attrs :style/overflow])
                                         "")))]
                  (when (contains? #{"auto" "scroll"} overflow)
                    (:node/id node))))
              (dom-bridge/element-nodes document))
        (:root document))))

(defrecord KotobaBrowser [session*]
  browser-use/IBrowser
  (-navigate! [this url]
    (swap! session* session/navigate! url)
    (browser-use/-state this))

  (-click! [this index]
    (click-node! this (:node/id (element-at @session* index))))

  (-input-text! [this index text]
    (type-node! this (:node/id (element-at @session* index)) text))

  (-scroll! [this direction]
    (let [node-id (first-scrollable-node-id @session*)
          delta-y (case direction
                    :up -120
                    "up" -120
                    120)]
      (swap! session* session/apply-document-input-event!
             {:event/type :pointer/wheel
              :node/id node-id
              :delta-y delta-y
              :delta-x 0
              :x 0
              :y 0})
      (browser-use/-state this)))

  (-back! [this]
    (swap! session* session/back!)
    (browser-use/-state this))

  (-state [_]
    (browser-state @session*)))

(defn kotoba-browser
  "Create a browser-use IBrowser backed by browser.session.

  opts:
  - `:session` existing kotoba browser session.
  - `:fetch-fn` session fetch capability for navigation.
  - `:start-url` + `:html` load an initial page without fetching.
  - `:start-url` with `:fetch-fn` navigates via the session lifecycle.
  - `:host` defaults to a recording host for debug inspection."
  [{:keys [session host fetch-fn start-url html viewport theme] :as opts}]
  (let [session (or session
                    (session/new-session
                     (cond-> {:host (or host (host/recording-host))}
                       fetch-fn (assoc :fetch-fn fetch-fn)
                       viewport (assoc :viewport viewport)
                       theme (assoc :theme theme))))
        session (cond
                  (and start-url html)
                  (session/load-html! session {:url start-url :html html})

                  (and start-url fetch-fn)
                  (session/navigate! session start-url)

                  :else
                  session)]
    (->KotobaBrowser (atom session))))

(defn kotoba-session
  "Create a browser-use-compatible kotoba session map.

  Mirrors browseruse.playwright-browser/playwright-session's host shape:
  `{:browser <IBrowser> :screenshot (fn [path]) :select ... :check ... :close ...}`.
  The screenshot function writes a kotoba EDN draw-op/accessibility snapshot."
  ([]
   (kotoba-session {}))
  ([opts]
   (let [browser (kotoba-browser opts)]
     {:browser browser
      :screenshot (fn [path] (screenshot! browser path))
      :select (fn [index value] (select! browser index value))
      :check (fn [index] (check! browser index))
      :close (fn [] nil)})))

(defn session
  "Return the current underlying kotoba browser session for debugging."
  [kotoba-browser]
  @(:session* kotoba-browser))
