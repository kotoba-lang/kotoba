(ns yoro-ui.state.convo-search-test
  (:require [cljs.test :refer-macros [deftest is]]
            [re-frame.core :as rf]
            [re-frame.db :as db]
            [yoro-ui.interop.signal :as signal]
            [yoro-ui.state.convo-search]))

(defn- seed! [state]
  (rf/clear-subscription-cache!)
  (reset! db/app-db state))

(deftest set-query-writes-under-its-own-db-path-not-the-generic-search-ns
  (seed! {:search {:query "should not be touched"}})
  (rf/dispatch-sync [:convo-search/set-query! "hello"])
  (is (= "hello" @(rf/subscribe [:convo-search/query])))
  (is (= "should not be touched" (get-in @db/app-db [:search :query]))
      "yoro-ui.state.search's own :search/query state is a completely separate feature/path"))

(deftest matching-convos-empty-query-returns-nothing
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query ""}
          :convos {:list [{:id "c1" :title "" :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]}]}})
  (is (empty? @(rf/subscribe [:convo-search/matching-convos]))))

(deftest matching-convos-filters-by-title-and-peer-name-case-insensitively
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query "BOB"}
          :convos {:list [{:id "c1" :title "" :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]}
                          {:id "c2" :title "" :members [{:did "did:web:alice"} {:did "did:web:carol" :displayName "Carol"}]}]}})
  (let [matches @(rf/subscribe [:convo-search/matching-convos])]
    (is (= 1 (count matches)))
    (is (= "c1" (:id (first matches))))))

(deftest matching-convos-matches-group-title
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query "book club"}
          :convos {:list [{:id "c1" :title "Book Club" :kind "group" :members []}]}})
  (is (= 1 (count @(rf/subscribe [:convo-search/matching-convos])))))

(deftest matching-messages-empty-query-returns-nothing
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query ""}
          :convo {:decrypted {} :messages-by-convo {"c1" [{:rkey "m1" :text "hello world"}]}}
          :convos {:list []}})
  (is (empty? @(rf/subscribe [:convo-search/matching-messages]))))

(deftest matching-messages-finds-plaintext-message-content
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query "world"}
          :convo {:decrypted {} :messages-by-convo {"c1" [{:rkey "m1" :text "hello world" :encryption "plaintext"}
                                                          {:rkey "m2" :text "goodbye" :encryption "plaintext"}]}}
          :convos {:list [{:id "c1" :title "" :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]}]}})
  (let [matches @(rf/subscribe [:convo-search/matching-messages])]
    (is (= 1 (count matches)))
    (is (= "m1" (:rkey (first matches))))
    (is (= "hello world" (:snippet (first matches))))
    (is (= "Bob" (:convo-title (first matches))))))

(deftest matching-messages-uses-decrypted-cache-for-e2ee-and-never-searches-raw-ciphertext
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query "secret"}
          :convo {:decrypted {"m1" "the secret plan"}
                  :messages-by-convo {"c1" [{:rkey "m1" :text "opaque-ciphertext-json" :encryption signal/scheme}
                                            ;; m2 has the query string sitting in raw (undecrypted) ciphertext by
                                            ;; sheer coincidence — must NOT match, since it was never really decrypted.
                                            {:rkey "m2" :text "secret-looking-ciphertext" :encryption signal/scheme}]}}
          :convos {:list [{:id "c1" :title "" :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]}]}})
  (let [matches @(rf/subscribe [:convo-search/matching-messages])]
    (is (= 1 (count matches)) "only the genuinely-decrypted message counts")
    (is (= "m1" (:rkey (first matches))))
    (is (= "the secret plan" (:snippet (first matches))))))

(deftest matching-messages-spans-multiple-convos
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query "hi"}
          :convo {:decrypted {}
                  :messages-by-convo {"c1" [{:rkey "m1" :text "hi there" :encryption "plaintext"}]
                                     "c2" [{:rkey "m2" :text "hi again" :encryption "plaintext"}]}}
          :convos {:list [{:id "c1" :title "" :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]}
                          {:id "c2" :title "" :members [{:did "did:web:alice"} {:did "did:web:carol" :displayName "Carol"}]}]}})
  (is (= #{"c1" "c2"} (set (map :convo-id @(rf/subscribe [:convo-search/matching-messages]))))))
