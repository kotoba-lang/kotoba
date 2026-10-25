(ns kotoba.wasm.abi
  "Canonical ABI encoding for kotoba.wasm.dom ops."
  (:require [kotoba.lang.text :as str]))

(def version 1)

(defn- maybe-name [x]
  (some-> x name))

(defn- split-attr [k]
  (if-let [ns (when k (namespace k))]
    [ns (maybe-name k)]
    [nil (maybe-name k)]))

(defn op->record [op]
  (let [[kind & xs] op]
    (case kind
      :dom/create-element
      (let [[id tag] xs]
        {:op :create-element :id id :tag (maybe-name tag)})

      :dom/create-text
      (let [[id text] xs]
        {:op :create-text :id id :text (str text)})

      :dom/append-content
      (let [[parent child] xs]
        {:op :append-content :parent parent :child child})

      :dom/create-comment
      (let [[id text] xs]
        {:op :create-comment :id id :text (str text)})

      :dom/set-root
      (let [[id] xs]
        {:op :set-root :id id})

      :dom/set-attr
      (let [[id k v] xs
            [attr-ns attr-name] (split-attr k)]
        {:op :set-attr
         :id id
         :namespace attr-ns
         :name attr-name
         :value (str v)})

      :dom/remove-attr
      (let [[id k] xs
            [attr-ns attr-name] (split-attr k)]
        {:op :remove-attr
         :id id
         :namespace attr-ns
         :name attr-name})

      :dom/append-child
      (let [[parent child] xs]
        {:op :append-child :parent parent :child child})

      :dom/remove-children
      (let [[id] xs]
        {:op :remove-children :id id})

      :dom/remove-child
      (let [[parent child] xs]
        {:op :remove-child :parent parent :child child})

      :dom/insert-before
      (let [[parent child before] xs]
        {:op :insert-before :parent parent :child child :before before})

      :dom/add-event-listener
      (let [[id event-name handler-id] xs]
        {:op :add-event-listener
         :id id
         :name (maybe-name event-name)
         :handler handler-id})

      :dom/remove-event-listener
      (let [[id event-name handler-id] xs]
        {:op :remove-event-listener
         :id id
         :name (maybe-name event-name)
         :handler handler-id})

      :dom/dispatch-event
      (let [[handler event] xs]
        {:op :dispatch-event :handler handler :event event})

      :dom/set-text
      (let [[id text] xs]
        {:op :set-text :id id :text (str text)})

      :dom/create-fragment
      (let [[id] xs]
        {:op :create-fragment :id id})

      :dom/focus
      (let [[id] xs]
        {:op :focus :id id})

      :dom/blur
      (let [[id] xs]
        {:op :blur :id id})

      (throw (ex-info "Unknown kotoba DOM op" {:op op})))))

(defn encode-batch [ops]
  {:abi/version version
   :ops (mapv op->record ops)})

(defn validate-batch [batch]
  (when-not (= version (:abi/version batch))
    (throw (ex-info "Unsupported kotoba DOM ABI version" {:batch batch :expected version})))
  (doseq [{:keys [op id parent child before handler name tag text value]} (:ops batch)]
    (case op
      :create-element (when-not (and (int? id) (seq tag)) (throw (ex-info "Invalid create-element op" {:op op :id id :tag tag})))
      :create-text (when-not (and (int? id) (string? text)) (throw (ex-info "Invalid create-text op" {:op op :id id :text text})))
      ;; :append-content and :create-comment were BOTH emitted by op->record
      ;; above and BOTH applied by kotoba.wasm.host.retained/apply-op, and
      ;; neither had a case here -- so every batch carrying one fell through
      ;; to the "Invalid ABI op kind" default and crashed the WHOLE commit,
      ;; including every legitimate mutation queued alongside it. Measured
      ;; 2026-08-29: this is exactly what made `browser`'s two real
      ;; browser.demo smoke tests fail with `{:op :append-content}` -- CSS
      ;; generated content (::before/::after, which is what
      ;; kotoba.wasm.dom/append-content-child exists for) could never reach
      ;; a real host at all. `abi-op-kinds-agree-test` now asserts the three
      ;; sets agree, so a fourth drift of this shape fails instead of
      ;; waiting for a page to hit it.
      :append-content (when-not (and (int? parent) (int? child)) (throw (ex-info "Invalid append-content op" {:op op :parent parent :child child})))
      :create-comment (when-not (and (int? id) (string? text)) (throw (ex-info "Invalid create-comment op" {:op op :id id :text text})))
      :set-root (when-not (int? id) (throw (ex-info "Invalid set-root op" {:op op :id id})))
      :set-attr (when-not (and (int? id) (seq name) (string? value)) (throw (ex-info "Invalid set-attr op" {:op op :id id :name name :value value})))
      ;; Previously entirely unhandled here (and in op->record above): a
      ;; real removeAttribute()/boolean-attribute-off setter had no op at
      ;; all emitted for it (browser.dom-bridge's own remove-attribute
      ;; just dissoc'd the JS-facing document's :attrs map, never
      ;; `update :ops conj [...]`) -- so the real GPU-rendered host's own
      ;; retained tree (kotoba.wasm.host.retained/apply-op, replayed from
      ;; :ops by webgl.cljs/webgpu.cljs's render!) kept a removed
      ;; attribute stale forever, even though the JS-facing document
      ;; model's getAttribute/queries looked correct immediately.
      :remove-attr (when-not (and (int? id) (seq name)) (throw (ex-info "Invalid remove-attr op" {:op op :id id :name name})))
      :append-child (when-not (and (int? parent) (int? child)) (throw (ex-info "Invalid append-child op" {:op op :parent parent :child child})))
      :remove-children (when-not (int? id) (throw (ex-info "Invalid remove-children op" {:op op :id id})))
      :remove-child (when-not (and (int? parent) (int? child)) (throw (ex-info "Invalid remove-child op" {:op op :parent parent :child child})))
      :insert-before (when-not (and (int? parent) (int? child) (or (nil? before) (int? before))) (throw (ex-info "Invalid insert-before op" {:op op :parent parent :child child :before before})))
      ;; `handler` is an OPAQUE identifier, not necessarily numeric -- the
      ;; real QuickJS webapi shim's own `__kotobaHandlerId()` (quickjs_wasm.cljc)
      ;; generates STRING ids ("handler-1", "handler-2", ...), and the
      ;; window/document global-listener path uses its own string scheme
      ;; ("global-" + target + "-" + eventType). The old `(int? handler)`
      ;; check rejected every real script-registered listener outright --
      ;; a pre-existing, previously-latent bug (nothing before this exercised
      ;; a real addEventListener() call all the way through this real
      ;; validate-batch/commit! pipeline) confirmed via live-Chrome
      ;; verification: any real page calling addEventListener() crashed the
      ;; whole commit with "Invalid add-event-listener op" the instant this
      ;; ABI layer's own validation ran.
      :add-event-listener (when-not (and (int? id) (seq name) (some? handler)) (throw (ex-info "Invalid add-event-listener op" {:op op :id id :name name :handler handler})))
      ;; Same opaque, non-numeric `handler` shape as :add-event-listener
      ;; above -- previously missing entirely, so encode-batch itself threw
      ;; "Unknown kotoba DOM op" on any real remove-event-listener call
      ;; before validate-batch ever ran, confirmed via direct REPL
      ;; reproduction (the sibling bug this file's :add-event-listener/
      ;; :insert-before/:remove-child fixes already covered was simply
      ;; missed for this op).
      :remove-event-listener (when-not (and (int? id) (seq name) (some? handler)) (throw (ex-info "Invalid remove-event-listener op" {:op op :id id :name name :handler handler})))
      :dispatch-event (when-not (some? handler) (throw (ex-info "Invalid dispatch-event op" {:op op :handler handler})))
      ;; The exact same "Unknown kotoba DOM op" crash class as
      ;; :remove-event-listener above, for four MORE real, common,
      ;; JS-reachable ops browser.dom-bridge already emits
      ;; (element.focus()/.blur(), a Text node's .data/.nodeValue
      ;; setter, document.createDocumentFragment()) -- op->record had no
      ;; case for any of them either, so encode-batch itself crashed the
      ;; ENTIRE host/commit! batch (every other legitimate mutation
      ;; queued alongside it too) the instant a real page ever exercised
      ;; one, confirmed via direct REPL reproduction before touching
      ;; source.
      :set-text (when-not (and (int? id) (string? text)) (throw (ex-info "Invalid set-text op" {:op op :id id :text text})))
      :create-fragment (when-not (int? id) (throw (ex-info "Invalid create-fragment op" {:op op :id id})))
      :focus (when-not (int? id) (throw (ex-info "Invalid focus op" {:op op :id id})))
      :blur (when-not (int? id) (throw (ex-info "Invalid blur op" {:op op :id id})))
      (throw (ex-info "Invalid ABI op kind" {:op op}))))
  batch)

(defn host-event
  "Normalize host input into the WIT-level input-event record shape."
  [{:keys [target name x y value key] :as event}]
  {:target target
   :name (clojure.core/name name)
   :x (double (or x 0.0))
   :y (double (or y 0.0))
   :value (some-> value str)
   :key (cond
          (keyword? key) (clojure.core/name key)
          (some? key) (str key)
          :else nil)})

(defn event-handler-id [event]
  (or (:handler event) (:handler-id event)))

(defn css-style-attr? [op]
  (and (= :set-attr (:op op))
       (= "style" (:namespace op))))

(defn style-map [ops node-id]
  (into {}
        (for [{:keys [id namespace name value]} ops
              :when (and (= id node-id)
                         (= "style" namespace))]
          [(keyword (str/replace name #"_" "-")) value])))
