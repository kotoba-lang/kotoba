(ns kotobase.server.storage-test
  (:require #?(:clj [clojure.test :refer [deftest is]]
               :cljs [cljs.test :refer [deftest is async] :include-macros true])
            [kotobase.server.runtime :as runtime]
            [kotobase.server.storage :as bridge]
            [kotobase.storage.memory :as memory]))

#?(:clj
   (deftest common-storage-drives-the-server-runtime
     (let [adapter (bridge/runtime-storage (memory/memory-store))
           bytes (byte-array [1 2 3])]
       (runtime/-put-block adapter "tenant-a" "graph-a" "cid-a" bytes)
       (is (= [1 2 3]
              (vec (runtime/-get-block
                    adapter "tenant-a" "graph-a" "cid-a"))))
       (is (= {:head nil :version nil}
              (runtime/-read-head adapter "tenant-a" "graph-a")))
       (is (true? (runtime/-compare-and-set-head
                   adapter "tenant-a" "graph-a" nil "cid-a")))
       (let [{:keys [version] :as current}
             (runtime/-read-head adapter "tenant-a" "graph-a")]
         (is (= "cid-a" (:head current)))
         (is (false? (runtime/-compare-and-set-head
                      adapter "tenant-a" "graph-a" nil "cid-b")))
         (is (true? (runtime/-compare-and-set-head
                     adapter "tenant-a" "graph-a" version "cid-b")))))))

#?(:cljs
   (deftest common-storage-drives-the-async-server-runtime
     (async done
       (let [adapter (bridge/runtime-storage (memory/memory-store))
             bytes (js/Uint8Array. #js [1 2 3])]
         (-> (runtime/-put-block
              adapter "tenant-a" "graph-a" "cid-a" bytes)
             js/Promise.resolve
             (.then
              (fn [_]
                (runtime/-get-block
                 adapter "tenant-a" "graph-a" "cid-a")))
             (.then
              (fn [found]
                (is (= [1 2 3] (vec found)))
                (runtime/-compare-and-set-head
                 adapter "tenant-a" "graph-a" nil "cid-a")))
             (.then
              (fn [published?]
                (is (true? published?))
                (runtime/-read-head adapter "tenant-a" "graph-a")))
             (.then
              (fn [current]
                (is (= "cid-a" (:head current)))
                (done)))
             (.catch
              (fn [error]
                (is false (str error))
                (done))))))))
