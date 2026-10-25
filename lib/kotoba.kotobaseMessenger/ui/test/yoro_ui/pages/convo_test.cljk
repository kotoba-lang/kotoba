(ns yoro-ui.pages.convo-test
  "SSR render tests for the messenger list page's cross-conversation search
  UI — same reagent.dom.server/render-to-static-markup + hand-seeded
  re-frame db approach as yoro-ui.pages.convo-detail-test/settings-test."
  (:require [cljs.test :refer-macros [deftest is]]
            [kotoba.lang.text :as str]
            [reagent.dom.server :as rdom-server]
            [re-frame.core :as rf]
            [re-frame.db :as db]
            [yoro-ui.state.auth]
            [yoro-ui.state.convos]
            [yoro-ui.state.convo-search]
            [yoro-ui.pages.convo :as cp]))

(defn- seed! [state]
  (rf/clear-subscription-cache!)
  (reset! db/app-db state))

(deftest no-query-shows-the-normal-convo-list-not-search-results
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query ""}
          :convos {:list [{:id "c1" :title "" :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                           :muted false :archived false :pinned false :unread-count 0}]}})
  (let [html (rdom-server/render-to-static-markup [cp/convo-list-page])]
    (is (str/includes? html "Bob") "the normal convo row renders")
    (is (not (str/includes? html "見つかりませんでした")))))

(deftest query-with-a-matching-convo-shows-it-under-the-convo-results-section
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query "bob"}
          :convo {:decrypted {} :messages-by-convo {}}
          :convos {:list [{:id "c1" :title "" :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                           :muted false :archived false :pinned false :unread-count 0}
                          {:id "c2" :title "" :members [{:did "did:web:alice"} {:did "did:web:carol" :displayName "Carol"}]
                           :muted false :archived false :pinned false :unread-count 0}]}})
  (let [html (rdom-server/render-to-static-markup [cp/convo-list-page])]
    (is (str/includes? html "Bob"))
    (is (not (str/includes? html "Carol")) "a non-matching convo doesn't leak into the results")))

(deftest query-with-a-matching-message-shows-a-snippet-and-scope-label
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query "hello"}
          :convo {:decrypted {} :messages-by-convo {"c1" [{:rkey "m1" :text "hello there" :encryption "plaintext"}]}}
          :convos {:list [{:id "c1" :title "" :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                           :muted false :archived false :pinned false :unread-count 0}]}})
  (let [html (rdom-server/render-to-static-markup [cp/convo-list-page])]
    (is (str/includes? html "hello there"))
    (is (str/includes? html "このセッションで開いた会話のみ")
        "the honest scope limit is surfaced directly in the UI, not just in code comments")))

(deftest query-with-no-matches-shows-the-empty-state
  (seed! {:auth {:session {:did "did:web:alice"}}
          :convo-search {:query "nonexistent-xyz"}
          :convo {:decrypted {} :messages-by-convo {}}
          :convos {:list [{:id "c1" :title "" :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                           :muted false :archived false :pinned false :unread-count 0}]}})
  (let [html (rdom-server/render-to-static-markup [cp/convo-list-page])]
    (is (str/includes? html "見つかりませんでした"))
    (is (not (str/includes? html "Bob")))))

(deftest signed-out-never-shows-search-results-even-with-a-stale-query
  (seed! {:auth {:session nil}
          :convo-search {:query "bob"}
          :convos {:list []}})
  (let [html (rdom-server/render-to-static-markup [cp/convo-list-page])]
    (is (str/includes? html "サインイン"))
    (is (not (str/includes? html "見つかりませんでした")))))
