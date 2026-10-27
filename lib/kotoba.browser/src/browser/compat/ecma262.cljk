(ns browser.compat.ecma262
  "The host side of the Kotoba ECMA-262 engine's DOM bridge.

  That engine (`kotoba-lang/org-ecma-international-262`) is pure: it has no
  capabilities and cannot touch a document. It reads from a SNAPSHOT the host
  injects and returns an EFFECT LOG the host replays. This namespace is the
  host half of that exchange -- build the snapshot, read the log, apply it.

      document ──snapshot──> engine ──effect log──> apply-effects ──> document'

  Nothing here evaluates JavaScript. That is the point: the authority to
  change the document never leaves this side of the line, which is why
  `browser.runtime/ecma262` declares `:imports #{}` while `quickjs` needs
  twelve.

  ## The wire format

  Both directions use the length-prefixed entry format the engine uses for its
  own environment, so neither side needs escaping:

      snapshot   <id>=o<len>:<node>       repeated, newest first
      node       textContent=s<len>:<text> then @<attr>=s<len>:<value>
      effect     <len>:<op><len>:<id><len>:<value>   repeated, in order

  An attribute is stored under `@name` so an element carrying one literally
  called `textContent` cannot shadow the property of that name.

  Two effects nest one more level, because they carry two values:

      16:addEventListener3:btn10:5:click1:0
      └ op ────────────┘└ id ┘└ 5:click1:0 ┘
                               └ type ┘└ n ┘

      12:setAttribute1:a11:5:class2:on"
  (:require [browser.dom-bridge :as dom-bridge]
            [kotoba.lang.text :as str]))

(defn- entry
  "One `<name>=<type><len>:<body>` entry, prepended -- the engine reads
  newest-first and both sides must agree on that."
  [region name type body]
  (str name "=" type (count body) ":" body region))

(defn- node-region
  "What one element looks like to the engine: its text, then its attributes
  under `@name`. `:id` is left out -- the engine already knows it, since that
  is how it addressed the element."
  [document node]
  (reduce-kv (fn [r k v]
               (if (= k :id) r (entry r (str "@" (name k)) "s" (str v))))
             (entry "" "textContent" "s"
                    (or (:text-content (dom-bridge/node-snapshot document (:node/id node))) ""))
             (or (:attrs node) {})))

(defn snapshot
  "Element id -> its readable state, in the format the engine reads.

  Only elements WITH an id are included: the engine addresses nodes by id and
  has no other handle, so an element without one is not reachable from a page
  script anyway."
  [document]
  (reduce (fn [region node]
            (if-let [id (get-in node [:attrs :id])]
              (entry region (str id) "o" (node-region document node))
              region))
          ""
          (dom-bridge/element-nodes document)))

(defn- read-field
  "One `<len>:<text>` field. Returns [text next-index], or nil if `s` does not
  hold a well-formed field at `i` -- a truncated log must not be read as an
  empty one."
  [s i]
  (let [colon (str/index-of s ":" i)]
    (when colon
      (when-let [n (parse-long (subs s i colon))]
        (let [start (inc colon)
              end (+ start n)]
          (when (<= end (count s))
            [(subs s start end) end]))))))

(defn parse-effects
  "The engine's log -> a vector of effects, in the order the script asked.

  Throws on a malformed log rather than returning what it managed to read: a
  half-read log and an empty one must not look the same, or a script whose
  effects were truncated would replay as a script that asked for nothing."
  [log]
  (loop [i 0 out []]
    (if (>= i (count log))
      out
      (let [[op i1] (or (read-field log i)
                        (throw (ex-info "malformed effect log: bad op field"
                                        {:log log :at i})))
            [id i2] (or (read-field log i1)
                        (throw (ex-info "malformed effect log: bad id field"
                                        {:log log :at i1 :op op})))
            [value i3] (or (read-field log i2)
                           (throw (ex-info "malformed effect log: bad value field"
                                           {:log log :at i2 :op op :id id})))]
        (recur i3
               (conj out
                     (cond
                       (= op "setAttribute")
                       (let [[attr j] (or (read-field value 0)
                                          (throw (ex-info "malformed setAttribute: bad name"
                                                          {:value value})))
                             [v _] (or (read-field value j)
                                       (throw (ex-info "malformed setAttribute: bad value"
                                                       {:value value})))]
                         {:effect/op :set-attribute
                          :element/id id
                          :attribute/name attr
                          :effect/value v})

                       (= op "fetch")
                       (let [[url j] (or (read-field value 0)
                                         (throw (ex-info "malformed fetch: bad url"
                                                         {:value value})))
                             [n _] (or (read-field value j)
                                       (throw (ex-info "malformed fetch: bad request number"
                                                       {:value value})))]
                         {:effect/op :fetch
                          :element/id id
                          :request/url url
                          :handler/n (parse-long n)})

                       (= op "setTimeout")
                       (let [[ms j] (or (read-field value 0)
                                        (throw (ex-info "malformed setTimeout: bad delay"
                                                        {:value value})))
                             [n _] (or (read-field value j)
                                       (throw (ex-info "malformed setTimeout: bad handler number"
                                                       {:value value})))]
                         {:effect/op :set-timeout
                          :element/id id
                          :timeout/ms (parse-long ms)
                          :handler/n (parse-long n)})

                       (= op "addEventListener")
                       (let [[type j] (or (read-field value 0)
                                          (throw (ex-info "malformed registration: bad type"
                                                          {:value value})))
                             [n _] (or (read-field value j)
                                       (throw (ex-info "malformed registration: bad handler number"
                                                       {:value value})))]
                         {:effect/op :add-event-listener
                          :element/id id
                          :event/type type
                          :handler/n (parse-long n)})

                       :else
                       {:effect/op (case op
                                     "textContent" :set-text-content
                                     "title" :set-title
                                     "log" :console-log
                                     (keyword op))
                        :element/id id
                        :effect/value value})))))))

(defn- set-text-content
  "What a real `textContent` setter does: drop the children, then add one text
  node. `:set-text` alone would write an element's own `:text`, which
  `node-text` does not read for an element."
  [document node-id text]
  (let [document (:document (dom-bridge/apply-mutation
                             document {:dom/op :remove-children :node/id node-id}))
        {:keys [document node/id]} (dom-bridge/apply-mutation
                                    document {:dom/op :create-text :text text})]
    (:document (dom-bridge/apply-mutation
                document {:dom/op :append-child :parent/id node-id :child/id id}))))

(defn apply-effects
  "Replay the log against a real document.

  Returns {:document d :listeners [...] :timers [...] :requests [...] :logs [...]
  :unknown [...]}. An effect
  this host does not implement is REPORTED, never dropped: a log the host
  silently ignored is indistinguishable from a script that did nothing, which
  is the failure this codebase keeps finding in its own gates."
  [document effects]
  (reduce
   (fn [acc {:keys [effect/op element/id effect/value] :as fx}]
     (cond
       ;; `#document` and `#console` are not elements. They are the two
       ;; reserved ids the engine uses for the page itself and for its log,
       ;; and no HTML id can spell either, so looking them up as elements
       ;; would report them as missing rather than as what they are.
       (= op :set-title)
       (update acc :document
               (fn [d] (:document (dom-bridge/apply-mutation
                                   d {:dom/op :set-title :title value}))))

       (= op :console-log)
       (update acc :logs conj value)

       ;; A timer, like a listener, is COLLECTED. Firing it is this side's
       ;; decision -- the guest has no clock -- and it fires through the same
       ;; `eval-dom-event` the listeners use, because they share one registry.
       (= op :set-timeout)
       (update acc :timers conj fx)

       ;; A request, like a timer, is COLLECTED. The guest cannot reach the
       ;; network; this side performs it and then fires the handler with the
       ;; response through `eval-dom-event-arg`.
       (= op :fetch)
       (update acc :requests conj fx)

       :else
       (if-let [node-id (dom-bridge/get-element-by-id (:document acc) id)]
       (case op
         :set-text-content
         (update acc :document set-text-content node-id value)

         :set-attribute
         (update acc :document
                 (fn [d] (:document (dom-bridge/apply-mutation
                                     d {:dom/op :set-attribute :node/id node-id
                                        :attr (:attribute/name fx) :value value}))))

         :add-event-listener
         (update acc :listeners conj (assoc fx :node/id node-id))

         (update acc :unknown conj fx))
         (update acc :unknown conj (assoc fx :reason :no-such-element)))))
   {:document document :listeners [] :timers [] :requests [] :logs [] :unknown []}
   effects))
