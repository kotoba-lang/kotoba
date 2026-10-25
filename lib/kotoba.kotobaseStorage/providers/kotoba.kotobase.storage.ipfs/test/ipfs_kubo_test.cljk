(ns ipfs-kubo-test
  "Qualification for `kotobase.storage.ipfs-kubo` -- the real, independently
  operated Kubo RPC/gateway client (superproject ADR-2608281000 Decision 2).

  Uses an injected fake `kubo/IHttp` rather than a real socket: `open` takes
  an explicit `:http` seam for exactly this reason (see its docstring), which
  sidesteps the `js/fetch`-global-reassignment hazard `ipfs-kotobase-test.cljs`
  documents without needing a real HTTP double."
  (:require [kotoba.lang.text :as str]
            [kotoba.lang.ipfs :as kubo]
            [kotobase.storage.core :as storage]
            [kotobase.storage.ipfs :as ipfs]
            [kotobase.storage.ipfs-kubo :as k]))

(def ^:private failures (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

;; NDJSON body shape Kubo's `/api/v0/add` returns -- see
;; `kotoba.lang.ipfs/parse-add-response`.
(defn- add-response-body [hash size]
  (.encode (js/TextEncoder.)
           (str "{\"Name\":\"file\",\"Hash\":\"" hash "\",\"Size\":" size "}\n")))

(defrecord ^:private FakeHttp [calls add-hash gateway-store gateway-status]
  kubo/IHttp
  (-get [_ url]
    (swap! calls conj {:op :get :url url})
    (let [cid (last (str/split url #"/"))
          status (get @gateway-status cid 200)
          body (get @gateway-store cid (js/Uint8Array. 0))]
      (js/Promise.resolve {:status status :body body})))
  (-post [_ url]
    (swap! calls conj {:op :post :url url})
    (js/Promise.resolve {:status 200 :body (js/Uint8Array. 0)}))
  (-post-file [_ url content]
    (swap! calls conj {:op :post-file :url url :content content})
    (js/Promise.resolve {:status 200 :body (add-response-body @add-hash (.-byteLength content))})))

(defn- fake-http
  ([] (fake-http {}))
  ([{:keys [add-hash gateway-store gateway-status]}]
   (->FakeHttp (atom []) (atom (or add-hash "unset")) (atom (or gateway-store {})) (atom (or gateway-status {})))))

(defn- test-missing-config-rejected []
  (try
    (k/open {:gateway-url "https://gw.example"})
    (expect false "missing :api-url is rejected")
    (catch :default e
      (expect (= :api-url (:missing (ex-data e))) "missing :api-url identifies itself")))
  (try
    (k/open {:api-url "https://rpc.example"})
    (expect false "missing :gateway-url is rejected")
    (catch :default e
      (expect (= :gateway-url (:missing (ex-data e))) "missing :gateway-url identifies itself"))))

(defn- test-put-block-matching-cid []
  (let [cid "bafkreimatching"
        http (fake-http {:add-hash cid})
        client (k/open {:api-url "https://rpc.example" :gateway-url "https://gw.example" :http http})
        bytes (js/Uint8Array.from #js [1 2 3])]
    (-> ((:put-block! client) cid bytes)
        (.then (fn [stored]
                 (expect (= cid stored) "put-block! resolves to the identity cid when kubo's hash matches")
                 (expect (empty? @(:location-index client))
                         "no location entry is recorded when kubo's hash matches the identity cid"))))))

(defn- test-put-block-mismatched-cid-records-location []
  (let [identity-cid "bafkreiidentity"
        kubo-hash "bafkreikuboechoedback"
        http (fake-http {:add-hash kubo-hash})
        client (k/open {:api-url "https://rpc.example" :gateway-url "https://gw.example" :http http})
        bytes (js/Uint8Array.from #js [4 5 6])]
    (-> ((:put-block! client) identity-cid bytes)
        (.then (fn [stored]
                 (expect (= identity-cid stored)
                         "put-block! STILL resolves to the identity cid even when kubo's hash differs")
                 (expect (= kubo-hash (get @(:location-index client) identity-cid))
                         "the identity->location mapping records kubo's own hash")
                 (expect (= kubo-hash ((:location-of client) identity-cid))
                         "location-of resolves the identity cid to kubo's hash"))))))

(defn- test-get-block-uses-location []
  (let [identity-cid "bafkreineedslocation"
        kubo-hash "bafkreiactuallocation"
        bytes (js/Uint8Array.from #js [7 8 9])
        http (fake-http {:add-hash kubo-hash :gateway-store {kubo-hash bytes}})
        client (k/open {:api-url "https://rpc.example" :gateway-url "https://gw.example" :http http})]
    (-> ((:put-block! client) identity-cid bytes)
        (.then (fn [_] ((:get-block client) identity-cid)))
        (.then (fn [got]
                 (expect (some? got) "get-block finds the block via its recorded location")
                 (expect (= (vec bytes) (vec got)) "the fetched bytes match what was stored")
                 (expect (some #(str/ends-with? (:url %) kubo-hash) @(:calls http))
                         "the GET was issued against the LOCATION cid, not the identity cid"))))))

(defn- test-get-block-404-is-nil []
  (let [http (fake-http {:gateway-status {"bafkreinever" 404}})
        client (k/open {:api-url "https://rpc.example" :gateway-url "https://gw.example" :http http})]
    (-> ((:get-block client) "bafkreinever")
        (.then (fn [got] (expect (nil? got) "get-block on a 404 resolves to nil, not an error"))))))

(defn- test-get-block-other-status-throws []
  (let [http (fake-http {:gateway-status {"bafkreibroken" 503}})
        client (k/open {:api-url "https://rpc.example" :gateway-url "https://gw.example" :http http})]
    (-> ((:get-block client) "bafkreibroken")
        (.then (fn [_] (expect false "a non-200/404 gateway status should reject, not resolve")))
        (.catch (fn [e]
                  ;; nbb/SCI re-wraps ex-info thrown across a Promise boundary
                  ;; (its own :sci/error data replaces the original ex-data),
                  ;; so this asserts on the message rather than `(ex-data e)`.
                  (expect (str/includes? (or (.-message e) (str e)) "kubo gateway fetch failed")
                          "a non-200/404 gateway status rejects with the expected error"))))))

(defn- test-composes-as-a-block-store []
  (let [http (fake-http {:add-hash "bafkreicomposed"})
        client (k/open {:api-url "https://rpc.example" :gateway-url "https://gw.example" :http http})
        adapter (ipfs/open {:client client})]
    (expect (storage/block-store? adapter)
            "wrapped in kotobase.storage.ipfs/open, the kubo client is a valid IBlockStore")
    (expect (not (storage/ref-store? adapter))
            "the composed adapter still declares no ref capability -- blocks and refs stay separate planes")))

(defn -main [& _]
  (-> (js/Promise.all
       #js [(test-put-block-matching-cid)
            (test-put-block-mismatched-cid-records-location)
            (test-get-block-uses-location)
            (test-get-block-404-is-nil)
            (test-get-block-other-status-throws)])
      (.then
       (fn [_]
         (test-missing-config-rejected)
         (test-composes-as-a-block-store)
         (if (zero? @failures)
           (println "ipfs-kubo-test: all green")
           (println (str "ipfs-kubo-test: " @failures " FAILURE(S) above")))
         (.exit js/process (if (zero? @failures) 0 1))))
      (.catch (fn [e]
                (js/console.error (str "FAIL (uncaught): " (or (.-message e) (str e))))
                (when-let [d (ex-data e)] (js/console.error (pr-str d)))
                (.exit js/process 1)))))

(-main)
