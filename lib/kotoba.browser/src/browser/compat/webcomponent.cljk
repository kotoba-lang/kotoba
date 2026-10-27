(ns browser.compat.webcomponent
  "Minimal Custom Elements registry model for compat JS adapters."
  (:require [browser.compat :as compat]
            [kotoba.lang.text :as str]))

(defn empty-registry
  []
  {:custom-elements/definitions {}
   :custom-elements/upgraded []})

(def reserved-names
  "Real HTML Custom Elements names explicitly reserved by the spec (pre-
   existing SVG/MathML element names that happen to contain a hyphen,
   carved out to avoid ambiguity) -- a customElements.define() call for
   any of these must be rejected even though each otherwise satisfies
   the hyphen requirement below."
  #{"annotation-xml" "color-profile" "font-face" "font-face-src"
    "font-face-uri" "font-face-format" "font-face-name" "missing-glyph"})

(defn valid-name?
  [name]
  (and (string? name)
       (str/includes? name "-")
       ;; Real spec (PotentialCustomElementName): the name must START with
       ;; a lowercase ASCII letter and contain NO uppercase ASCII letters
       ;; anywhere -- the PCENChar production explicitly excludes A-Z.
       ;; Deliberately ASCII-only: PCENChar's full grammar also permits a
       ;; long tail of non-ASCII Unicode ranges (middle dot, CJK blocks,
       ;; etc.) that real custom element names almost never use, left
       ;; unimplemented rather than risk a subtly wrong Unicode range
       ;; check for near-zero real-world value.
       (re-matches #"[a-z][^A-Z]*" name)
       ;; Real spec: must not start with an ASCII case-insensitive match
       ;; for "xml" (reserved by the XML specification), not just a
       ;; lowercase-only "xml" prefix.
       (not (str/starts-with? (str/lower name) "xml"))
       (not (contains? reserved-names name))))

(defn define
  "Real spec: a second `customElements.define()` call either reusing an
   already-registered NAME or an already-registered CONSTRUCTOR (a class
   used for one name can never be reused for another) must throw
   NotSupportedError, not silently redefine/overwrite. Mirrors the live JS
   registrar's own `globalThis.customElements.define` (quickjs_wasm.cljc)
   -- keep both in sync if either's rules change."
  [registry name definition]
  (let [constructor-id (:constructor/id definition)
        definitions (:custom-elements/definitions registry)]
    (cond
      (not (valid-name? name))
      (assoc registry :custom-elements/error {:reason :invalid-custom-element-name
                                               :name name})

      (contains? definitions name)
      (assoc registry :custom-elements/error {:reason :already-defined
                                               :name name})

      (and (some? constructor-id)
           (some #(= constructor-id (:constructor/id %)) (vals definitions)))
      (assoc registry :custom-elements/error {:reason :constructor-already-used
                                               :name name})

      :else
      (assoc-in registry [:custom-elements/definitions name]
                (merge {:custom-element/name name
                        :observed-attributes []}
                       definition)))))

(defn definition
  [registry name]
  (get-in registry [:custom-elements/definitions name]))

(defn upgrade-request
  "Real spec: an element is upgraded (constructed, connectedCallback
   fired) EXACTLY ONCE per its lifetime -- re-walking a tree that already
   contains a previously-upgraded custom element (e.g. incremental
   parsing re-processing an overlapping subtree) must not re-fire
   connectedCallback. `empty-registry` has always modeled a
   `:custom-elements/upgraded` set for exactly this purpose, but nothing
   ever read or wrote it -- this permanently-dead bookkeeping field meant
   nothing prevented sending a duplicate connected-callback request for
   the same node. Returns nil (no request) both when the tag has no
   definition (existing behavior) and when the node is already upgraded.
   Read-only with respect to `registry` -- `upgrade-tree` below is
   responsible for threading the updated `:custom-elements/upgraded` set
   forward once a request actually fires."
  [adapter registry node]
  (when (and (definition registry (:tag node))
             (not (contains? (set (:custom-elements/upgraded registry)) (:node/id node))))
    (let [definition (definition registry (:tag node))]
      (compat/request adapter :js/call
                      {:js/call :custom-element/connected-callback
                       :constructor/id (:constructor/id definition)
                       :node/id (:node/id node)
                       :tag (:tag node)}))))

(defn attribute-changed-request
  [adapter registry node attr old-value new-value]
  (when-let [definition (definition registry (:tag node))]
    (when (contains? (set (:observed-attributes definition)) attr)
      (compat/request adapter :js/call
                      {:js/call :custom-element/attribute-changed-callback
                       :constructor/id (:constructor/id definition)
                       :node/id (:node/id node)
                       :tag (:tag node)
                       :attr attr
                       :old-value old-value
                       :new-value new-value}))))

(defn upgrade-tree
  "Real spec (see `upgrade-request`'s own docstring): upgrading is a
   once-per-lifetime, tree-wide operation, so this must thread the
   registry's `:custom-elements/upgraded` set forward as it walks --
   previously `(vec (keep #(upgrade-request adapter registry %) nodes))`
   called `upgrade-request` against the SAME, never-updated `registry` for
   every node, so two nodes sharing a `:node/id` (or two separate
   `upgrade-tree` calls over an overlapping subtree, using the registry
   this fn returns) both fired duplicate connected-callback requests.
   Returns `{:requests [...] :registry registry'}` -- a shape change from
   the previous bare vector, safe since this module has zero external
   callers outside its own tests (confirmed dead code, kept in sync with
   its live JS sibling)."
  [adapter registry nodes]
  (reduce (fn [{:keys [registry requests]} node]
            (if-let [request (upgrade-request adapter registry node)]
              {:registry (update registry :custom-elements/upgraded conj (:node/id node))
               :requests (conj requests request)}
              {:registry registry :requests requests}))
          {:registry registry :requests []}
          nodes))
