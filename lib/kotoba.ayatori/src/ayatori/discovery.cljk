(ns ayatori.discovery
  "IPNI provider discovery for Ayatori.

  Discovery answers *where a CID may be fetched*. It does not fetch IPLD
  blocks, verify their CIDs, traverse a graph, or evaluate a query. Keeping
  those effects separate prevents an indexer response from being mistaken
  for content or query evidence. HTTP transport and JSON parsing are injected
  by the caller through `ipni.find`."
  (:require #?(:cljs [kotoba.lang.text :as str])
            [ipni.find :as ipni]))

(def default-indexers ipni/default-indexers)
(def default-routers ipni/default-routers)

(defn find-providers
  "Discover providers for `cid` through Delegated Routing V1/IPNI.

  Returns `ipni.find/find-providers`'s structured result and never rewrites
  the content CID. `http-fn` owns transport; `opts` may supply `:routers`,
  `:quorum`, and `:parse-fn`."
  [http-fn cid opts]
  (ipni/find-providers http-fn cid opts))

#?(:cljs
   (defn find-providers-async
     "Promise-native Delegated Routing/IPNI discovery for Workers.

     `http-fn` returns a Promise of the same `{:status :body}` response used
     by `find-providers`. Requests are concurrent across routers; each settled
     response is parsed by io-ipni-specs' existing conformance path, then the
     ordinary quorum/provider scorer combines them. Transport rejection is a
     failed router response, not a rejected aggregate Promise."
     [http-fn cid {:keys [routers quorum]
                   :or {routers default-routers quorum 1}
                   :as opts}]
     (-> (js/Promise.all
          (into-array
           (map (fn [router]
                  (-> (js/Promise.resolve
                       (http-fn {:method :get
                                 :url (str (str/replace router #"/$" "")
                                           "/providers/" cid)
                                 :headers {"Accept" "application/json"}}))
                      (.then (fn [response]
                               (ipni/get-providers (constantly response)
                                                   router cid opts)))
                      (.catch (fn [e]
                                {:ok? false :router router :cid cid
                                 :reason :transport-error
                                 :detail (or (.-message e) (str e))}))))
                routers)))
         (.then (fn [responses]
                  (ipni/score-providers cid (vec (js->clj responses :keywordize-keys true))
                                        {:quorum quorum}))))))

(defn get-cid
  "Query one IPNI-native `/cid/{cid}` endpoint when ContextID or Metadata is
  needed. Provider discovery alone is not proof that the IPLD block exists or
  hashes to `cid`; the retrieval layer must still verify it."
  ([http-fn indexer cid]
   (ipni/get-cid http-fn indexer cid))
  ([http-fn indexer cid opts]
   (ipni/get-cid http-fn indexer cid opts)))
