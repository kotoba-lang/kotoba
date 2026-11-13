(ns awai-oracle.snapshot
  (:require [arrangement.source :as source]
            [ipld.core :as ipld]))
(defn -main []
  (let [good (ipld/node->block {"schema-version" 2 "index-roots" {}})
        bad (:bytes (ipld/node->block {"schema-version" 2 "index-roots" {} "prev" nil}))
        cid (:cid good)
        check (fn [bytes expected]
                (-> (source/snapshot-roots-async #(js/Promise.resolve bytes) cid)
                    (.then (fn [_] (throw (js/Error. "unexpected acceptance")))
                           (fn [e] (when-not (= expected (:type (ex-data e))) (throw e))))))]
    (-> (js/Promise.all #js [(-> (source/snapshot-roots-async #(js/Promise.resolve (:bytes good)) cid) (.then (fn [roots] (when-not (= {} roots) (throw (js/Error. "invalid roots"))))))
                            (check nil :arrangement/block-not-found)
                            (check bad :ipld/cid-mismatch)])
        (.then (fn [_] (println "async snapshot valid accepted; missing and mismatch rejected")))
        (.catch (fn [e] (.error js/console e) (set! (.-exitCode js/process) 1))))))
(set! *main-cli-fn* -main)
