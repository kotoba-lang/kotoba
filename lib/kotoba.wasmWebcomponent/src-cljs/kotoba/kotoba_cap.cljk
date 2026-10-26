(ns kotoba.kotoba-cap
  "Browser/Node host for amu wasm32-kotoba-v1 `kotoba:cap`/`call`.

  This is the HOST, not a guest. Date.now, Error, a WebAssembly import
  object, and BigInt i64 live here. Authored in ClojureScript (this
  workspace's next runtime after kotoba-wasm / clojurewasm) and compiled
  once via shadow-cljs `:kotoba-cap` to `src/kotoba-cap.js`. New host
  surface is cljs; `actor-host.js` remains the legacy hand-JS `actor:host`
  plane. The host itself is not a `.kotoba` module — `.kotoba` /
  `:js-kotoba-v1` is what this module instantiates.

  Semantics match kototama.tender's always-linked cap-call-host-fn:
  capability id 7 + grant `clock-monotonic` → BigInt(Date.now());
  missing grant or any other id throws
  `kototama.tender: host import denied`.")

(def kotoba-cap-module "kotoba:cap")

(def clock-now-capability-id (js/BigInt 7))

(def denied-message "kototama.tender: host import denied")

(defn- grant-set [caps]
  (js/Set. (or (when (some? caps) (aget caps "grants")) #js [])))

(defn- as-bigint [id]
  (if (number? id) (js/BigInt id) id))

(defn- denied!
  [reason info]
  (let [err (js/Error. denied-message)
        payload (js/Object.assign #js {:import "cap-call" :reason reason} info)]
    (set! (.-kototamaDenied err) payload)
    (throw err)))

(defn kotoba-cap-imports
  "Return the `{call(id, seed)}` import object for module `kotoba:cap`.
  `caps` is typically `hostCaps({grants:[...]})` from actor-host.js; a
  `{grants: Iterable}` object is also accepted so this ns does not import
  the actor:host plane."
  [caps]
  (let [grants (grant-set caps)]
    #js {:call (fn [id _seed]
                 (let [cap-id (as-bigint id)]
                   (if (= (str cap-id) "7")
                     (if (.has grants "clock-monotonic")
                       (js/BigInt (js/Date.now))
                       (denied! "grant/missing"
                                #js {:grant "clock-monotonic"
                                     :capability-id (js/Number cap-id)}))
                     (denied! "grant/unknown-capability"
                              #js {:capability-id (js/Number cap-id)}))))}))

(defn amu-compile-imports
  "Compose actor:host + kotoba:cap. `actor-host-imports` is injected so
  this ns stays loadable from nbb without pulling the 1500-line
  actor:host plane into the cljs compile."
  [requested-ids caps memory-box opts actor-host-imports]
  (let [obj #js {}]
    (aset obj "kotoba" (actor-host-imports requested-ids caps memory-box (or opts #js {})))
    (aset obj kotoba-cap-module (kotoba-cap-imports caps))
    obj))
