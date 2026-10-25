(ns toshokan.portable
  "Portable toshokan application slice.

  Planning and response parsing are pure CLJC. HTTP execution is represented
  by a typed, data-only Kotoba ability request and can be dispatched by a JVM,
  CLJS/workerd, or Wasm component host implementing the same provider key."
  (:require [kotoba.lang.text :as str]
            [kotoba.lang.capability-values :as caps]
            [kotoba.lang.portable-effect :as effect]
            [toshokan.sources.ndl-core :as ndl-core]))

(def ndl-resource "library:ndl")
(def ndl-origin "https://ndlsearch.ndl.go.jp")
(def ndl-endpoint (str ndl-origin "/api/sru"))
(def ndl-limits {:max-bytes 2097152 :max-items 20 :deadline-ms 30000})

(defn- encode-query [text]
  #?(:clj
     (-> (java.net.URLEncoder/encode text "UTF-8")
         (str/replace "+" "%20"))
     :cljs
     (js/encodeURIComponent text)))

(defn ndl-url
  [query max-records]
  (str ndl-endpoint
       "?operation=searchRetrieve&version=1.2"
       "&query=" (encode-query query)
       "&recordSchema=dcndl"
       "&maximumRecords=" max-records))

(defn ndl-harvest-effect
  "Create the complete host-independent request for one NDL harvest. The
  ability binds the logical source, provider target, operation, limits, and
  audit identity; the URL alone is never authority."
  [request-id query max-records]
  (effect/request
   {:id request-id
    :call :toshokan/fetch
    :effects #{:host/http}
    :ability
    (caps/make-component-cap
     :host/http ndl-resource
     {:target :toshokan/http
      :operation :get
      :limits (assoc ndl-limits :max-items max-records)
      :audit-id request-id})
    :input
    {:method :get
     :url (ndl-url query max-records)
     :headers
     {"User-Agent"
      "toshokan-library-harvester/0.2 (portable Kotoba ability host)"}}}))

(defn ndl-host-policy
  "Least-privilege grant+policy for a host invocation. Deployments may narrow
  the limits further but cannot broaden the guest request."
  []
  {:cacao-grants
   [{:grant/kind :host/http
     :grant/resources #{ndl-resource}
     :grant/id "toshokan:ndl"
     :grant/target :toshokan/http
     :grant/operations #{:get}
     :grant/limits ndl-limits}]
   :local-policy
   {:policy/allow {:host/http #{ndl-resource}}
    :policy/component
    {:host/http {:targets #{:toshokan/http}
                 :operations #{:get}
                 :limits ndl-limits}}}})

(defn workerd-request
  "Encode the semantic CLJC effect into the closed JSON-shaped workerd wire
  contract. This is a data transformation only; it does not grant authority."
  [effect]
  (let [ability (:effect/ability effect)
        limits (:cap/limits ability)
        input (:effect/input effect)]
    {:format "kotoba.portable-effect/v1"
     :id (:effect/id effect)
     :call (subs (str (:effect/call effect)) 1)
     :effects (mapv #(subs (str %) 1) (sort (:effect/effects effect)))
     :ability
     {:kind (subs (str (:cap/kind ability)) 1)
      :resource (:cap/resource ability)
      :target (subs (str (:cap/target ability)) 1)
      :operation (name (:cap/operation ability))
      :limits {:maxBytes (:max-bytes limits)
               :maxItems (:max-items limits)
               :deadlineMs (:deadline-ms limits)}
      :auditId (:cap/audit-id ability)}
     :input
     {:method (str/upper (name (:method input)))
      :url (:url input)
      :headers (:headers input)}}))

(defn validate-ndl-provider-input
  "Provider-side confused-deputy defense. Revalidates the concrete cap and
  request URL immediately before network I/O."
  [concrete-cap {:keys [method url] :as input}]
  (when-not (and (= ndl-resource (:cap/resource concrete-cap))
                 (= :toshokan/http (:cap/target concrete-cap))
                 (= :get (:cap/operation concrete-cap))
                 (= :get method)
                 (string? url)
                 (str/starts-with? url (str ndl-endpoint "?")))
    (throw (ex-info "NDL provider scope denied"
                    {:toshokan/denied :provider-scope :input input})))
  input)

(defn parse-ndl-response
  "Pure completion step shared by all hosts."
  [response-text]
  (vec (ndl-core/parse-records response-text)))
