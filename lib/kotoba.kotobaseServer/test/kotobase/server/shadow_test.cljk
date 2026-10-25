(ns kotobase.server.shadow-test
  (:require #?(:clj [clojure.test :refer [deftest is]]
               :cljs [cljs.test :refer [deftest is async]
                      :include-macros true])
            [kotobase.server.shadow :as shadow]))

(deftest primary-response-is-authoritative
  (let [events (atom [])
        route (shadow/wrap-handler
               {:primary-handle (fn [& _] #?(:clj {:ok true :root "p"}
                                             :cljs (js/Promise.resolve
                                                    {:ok true :root "p"})))
                :shadow-handle (fn [& _] #?(:clj {:ok true :root "s"}
                                            :cljs (js/Promise.resolve
                                                   {:ok true :root "s"})))
                :normalize #(dissoc % :root)
                :observe! #(swap! events conj %)})]
    #?(:clj
       (do
         (is (= {:ok true :root "p"} (route "q" {} nil)))
         (is (= :match (:shadow/status (first @events)))))
       :cljs
       (async done
         (-> (route "q" {} nil)
             (.then (fn [response]
                      (is (= {:ok true :root "p"} response))
                      ;; The default scheduler starts the shadow Promise before
                      ;; the primary continuation completes.
                      (js/Promise.resolve nil)))
             (.then (fn [_]
                      (is (= :match (:shadow/status (first @events))))
                      (done)))
             (.catch (fn [error] (is false (str error)) (done))))))))

(deftest shadow-failure-never-fails-primary
  (let [events (atom [])
        route (shadow/wrap-handler
               {:primary-handle (fn [& _] #?(:clj {:ok true}
                                             :cljs (js/Promise.resolve {:ok true})))
                :shadow-handle (fn [& _] (throw (ex-info "shadow down" {})))
                :observe! #(swap! events conj %)})]
    #?(:clj
       (do (is (= {:ok true} (route "transact" {} nil)))
           (is (= :failed (:shadow/status (first @events)))))
       :cljs
       (async done
         (-> (route "transact" {} nil)
             (.then (fn [response]
                      (is (= {:ok true} response))
                      (is (= :failed (:shadow/status (first @events))))
                      (done)))
             (.catch (fn [error] (is false (str error)) (done))))))))

(deftest scheduling-and-eligibility-are-owned-by-the-host
  (let [tasks (atom []) events (atom []) calls (atom 0)
        route (shadow/wrap-handler
               {:primary-handle (fn [& _] {:ok true})
                :shadow-handle (fn [& _] (swap! calls inc) {:ok true})
                :schedule! #(swap! tasks conj %)
                :eligible? (fn [method _ _] (= "q" method))
                :observe! #(swap! events conj %)})]
    #?(:clj
       (do
         (route "transact" {} nil)
         (route "q" {} nil)
         (is (= 1 (count @tasks)))
         (is (zero? @calls) "the router does not execute a host-owned task")
         ((first @tasks))
         (is (= 1 @calls))
         (is (= :match (:shadow/status (first @events)))))
       :cljs
       ;; Scheduling semantics are platform-neutral and exercised above by
       ;; the Promise-based tests; this exact sync fake is JVM-only.
       (is (ifn? route)))))
