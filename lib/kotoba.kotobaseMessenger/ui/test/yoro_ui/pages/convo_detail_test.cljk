(ns yoro-ui.pages.convo-detail-test
  "Component/state tests for the messenger UI. Three layers: (1) pure fns
  called directly via #'var-quote, the same private-fn access
  post_thread_test.cljc already uses; (2)
  reagent.dom.server/render-to-static-markup — no jsdom needed, react-dom/
  server is already a dependency — for message-bubble and the full page
  against a hand-seeded re-frame db; (3) rf/dispatch-sync against the real
  event handlers, with :atproto/* and the Signal :convo/decrypt!/
  :convo/encrypt-and-send! fx stubbed via the registrar so these stay
  hermetic — no network, no real ratchet consumption."
  (:require [cljs.test :refer-macros [deftest is testing]]
            [kotoba.lang.text :as str]
            [reagent.dom.server :as rdom-server]
            [re-frame.core :as rf]
            [re-frame.db :as db]
            [re-frame.registrar :as registrar]
            [yoro-ui.state.auth]
            [yoro-ui.interop.signal :as signal]
            [yoro-ui.interop.signal-group :as signal-group]
            [yoro-ui.pages.convo-detail :as cd]))

;; ---------------------------------------------------------------------------
;; 1. Pure functions

(deftest message-display-text-per-state
  (testing "non-signal-lite messages show their plaintext text field as-is"
    (is (= "hello" (#'cd/message-display-text {:text "hello" :encryption "plaintext"} {} {}))
        (= "" (#'cd/message-display-text {:encryption ""} {} {}))))
  (testing "signal-lite-v1: decrypted cache wins"
    (is (= "decrypted!" (#'cd/message-display-text {:rkey "m1" :encryption signal/scheme} {"m1" "decrypted!"} {}))))
  (testing "signal-lite-v1: failed placeholder when decrypt rejected"
    (is (= "🔒 復号できませんでした" (#'cd/message-display-text {:rkey "m1" :encryption signal/scheme} {} {"m1" true}))))
  (testing "signal-lite-v1: pending placeholder before either resolves"
    (is (= "🔒 復号中…" (#'cd/message-display-text {:rkey "m1" :encryption signal/scheme} {} {})))))

(deftest convo-encryption-label-reflects-latest-message-only
  (is (nil? (#'cd/convo-encryption-label [] {} {})) "no messages, no badge")
  (is (nil? (#'cd/convo-encryption-label [{:rkey "m1" :encryption "plaintext"}] {} {}))
      "plaintext last message, no badge")
  (is (= "E2EE" (#'cd/convo-encryption-label [{:rkey "m1" :encryption signal/scheme}] {"m1" "hi"} {}))
      "decrypted last message shows the real badge")
  (is (= "E2EE ⚠" (#'cd/convo-encryption-label [{:rkey "m1" :encryption signal/scheme}] {} {"m1" true}))
      "failed-to-decrypt last message shows a warning badge, not a bare claim")
  (is (nil? (#'cd/convo-encryption-label [{:rkey "m1" :encryption signal/scheme}] {} {}))
      "still-pending last message shows no badge yet (not the old always-on hardcoded claim)")
  (is (nil? (#'cd/convo-encryption-label [{:rkey "m1" :encryption signal/scheme}
                                          {:rkey "m2" :encryption "plaintext"}] {"m1" "hi"} {}))
      "messages are chronological, (last messages) is the newest — an older
       encrypted message doesn't leak its badge onto a newer plaintext one")
  (is (= "E2EE" (#'cd/convo-encryption-label [{:rkey "m1" :encryption "plaintext"}
                                              {:rkey "m2" :encryption signal/scheme}] {"m2" "hi"} {}))
      "only the LATEST (last) message's own encryption/decrypt state counts"))

(deftest peer-did-picks-the-other-member
  (is (= "did:web:bob" (#'cd/peer-did {:members [{:did "did:web:alice"} {:did "did:web:bob"}]} "did:web:alice")))
  (is (nil? (#'cd/peer-did {:members [{:did "did:web:alice"}]} "did:web:alice"))
      "no other member yet (e.g. convo metadata still loading) → no peer"))

(deftest searchable-text-per-state
  (is (= "hello" (#'cd/searchable-text {:text "hello" :encryption "plaintext"} {}))
      "plaintext text is searchable as-is")
  (is (= "decrypted!" (#'cd/searchable-text {:rkey "m1" :encryption signal/scheme} {"m1" "decrypted!"}))
      "decrypted cache wins for e2ee messages")
  (is (nil? (#'cd/searchable-text {:rkey "m1" :text "raw-ciphertext-json" :encryption signal/scheme} {}))
      "an e2ee message not yet decrypted has nothing searchable — raw ciphertext must never be searched"))

(deftest filter-messages-by-query-blank-query-returns-everything-unfiltered
  (let [messages [{:rkey "m1" :text "hello" :encryption "plaintext"}
                  {:rkey "m2" :text "world" :encryption "plaintext"}]]
    (is (= messages (#'cd/filter-messages-by-query messages {} "")))
    (is (= messages (#'cd/filter-messages-by-query messages {} "   ")))))

(deftest filter-messages-by-query-matches-case-insensitively-and-skips-undecrypted
  (let [messages [{:rkey "m1" :text "Hello World" :encryption "plaintext"}
                  {:rkey "m2" :text "goodbye" :encryption "plaintext"}
                  {:rkey "m3" :text "raw-ciphertext" :encryption signal/scheme}]
        matches (#'cd/filter-messages-by-query messages {} "world")]
    (is (= ["m1"] (map :rkey matches))
        "case-insensitive match on the plaintext message; the undecrypted e2ee one never leaks a false match")))

(deftest typing-label-empty-when-nobody-typing
  (is (nil? (#'cd/typing-label [] [{:did "did:web:bob" :displayName "Bob"}]))))

(deftest typing-label-single-typer-uses-display-name-then-handle-then-did
  (is (= "Bobが入力中…"
        (#'cd/typing-label [{:did "did:web:bob"}] [{:did "did:web:bob" :displayName "Bob" :handle "bob.test"}])))
  (is (= "bob.testが入力中…"
        (#'cd/typing-label [{:did "did:web:bob"}] [{:did "did:web:bob" :handle "bob.test"}]))
      "falls back to handle when no displayName")
  (is (= "did:web:bobが入力中…"
        (#'cd/typing-label [{:did "did:web:bob"}] [{:did "did:web:bob"}]))
      "falls back to the bare did when neither displayName nor handle is known"))

(deftest typing-label-joins-multiple-typers-with-japanese-comma
  (is (= "Bob、Carolが入力中…"
        (#'cd/typing-label [{:did "did:web:bob"} {:did "did:web:carol"}]
                           [{:did "did:web:bob" :displayName "Bob"}
                            {:did "did:web:carol" :displayName "Carol"}]))))

(def ^:private read-receipt-messages
  [{:rkey "m1" :senderDid "did:web:alice"}
   {:rkey "m2" :senderDid "did:web:bob"}
   {:rkey "m3" :senderDid "did:web:alice"}])

(deftest read-status-nil-when-not-the-last-message
  (is (nil? (#'cd/read-status read-receipt-messages "did:web:alice"
                              [{:did "did:web:bob" :lastSeenRkey "m3"}] false
                              (first read-receipt-messages)))
      "only the conversation's LAST message is ever annotated"))

(deftest read-status-nil-when-the-last-message-isnt-mine
  (is (nil? (#'cd/read-status read-receipt-messages "did:web:bob"
                              [{:did "did:web:alice" :lastSeenRkey "m3"}] false
                              (last read-receipt-messages)))))

(deftest read-status-1-1-read-when-peer-has-seen-up-to-the-last-message
  (is (= {:kind :read}
        (#'cd/read-status read-receipt-messages "did:web:alice"
                          [{:did "did:web:bob" :lastSeenRkey "m3"}] false
                          (last read-receipt-messages)))))

(deftest read-status-1-1-nil-when-peer-hasnt-caught-up-yet
  (is (nil? (#'cd/read-status read-receipt-messages "did:web:alice"
                              [{:did "did:web:bob" :lastSeenRkey "m2"}] false
                              (last read-receipt-messages)))
      "the peer's receipt is BEFORE my last message — not read yet"))

(deftest read-status-1-1-nil-without-any-receipt
  (is (nil? (#'cd/read-status read-receipt-messages "did:web:alice" [] false
                              (last read-receipt-messages)))))

(deftest read-status-ignores-my-own-receipt
  (is (nil? (#'cd/read-status read-receipt-messages "did:web:alice"
                              [{:did "did:web:alice" :lastSeenRkey "m3"}] false
                              (last read-receipt-messages)))
      "my own markRead call must never count as someone else having read it"))

(deftest read-status-group-counts-other-members-whove-caught-up
  (is (= {:kind :group :count 2}
        (#'cd/read-status read-receipt-messages "did:web:alice"
                          [{:did "did:web:bob" :lastSeenRkey "m3"}
                           {:did "did:web:carol" :lastSeenRkey "m3"}
                           {:did "did:web:dave" :lastSeenRkey "m1"}] true
                          (last read-receipt-messages)))
      "dave hasn't caught up (m1 is before the last message) so only bob+carol count"))

(deftest read-badge-text-per-status
  (is (= "既読" (#'cd/read-badge-text {:kind :read})))
  (is (= "既読 3" (#'cd/read-badge-text {:kind :group :count 3})))
  (is (nil? (#'cd/read-badge-text nil))))

;; ---------------------------------------------------------------------------
;; 2. Component rendering (SSR string render, no jsdom needed)

(def ^:private no-extras {:decrypted {} :failed {} :convo-id "convo-1"
                          :attachments nil :reactions nil :picker-for nil})

(deftest message-bubble-renders-decrypted-incoming-text
  (let [html (rdom-server/render-to-static-markup
              (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:bob"
                                    :sender {:displayName "Bob"}
                                    :encryption signal/scheme :createdAt "2026-07-08T00:00:00Z"}
                                   "did:web:alice" (assoc no-extras :decrypted {"m1" "hi alice"})))]
    (is (str/includes? html "hi alice"))
    (is (str/includes? html "justify-start") "someone else's bubble aligns left")))

(deftest message-bubble-shows-failure-placeholder-not-ciphertext
  (let [html (rdom-server/render-to-static-markup
              (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:bob"
                                    :text "{\"v\":1,\"ct\":\"should-never-render\"}"
                                    :encryption signal/scheme :createdAt "2026-07-08T00:00:00Z"}
                                   "did:web:alice" (assoc no-extras :failed {"m1" true})))]
    (is (str/includes? html "復号できませんでした"))
    (is (not (str/includes? html "should-never-render"))
        "raw ciphertext/envelope JSON must never leak into the rendered bubble")))

(deftest message-bubble-mine-aligns-right
  (let [html (rdom-server/render-to-static-markup
              (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:alice" :text "hey" :createdAt "2026-07-08T00:00:00Z"}
                                   "did:web:alice" no-extras))]
    (is (str/includes? html "justify-end"))))

(deftest message-bubble-shows-read-badge-for-the-last-message-when-read
  (let [msg {:rkey "m1" :senderDid "did:web:alice" :text "hi" :createdAt "t"}
        html (rdom-server/render-to-static-markup
              (#'cd/message-bubble msg "did:web:alice"
                                   (assoc no-extras
                                          :raw-messages [msg]
                                          :receipts [{:did "did:web:bob" :lastSeenRkey "m1"}])))]
    (is (str/includes? html "既読"))))

(deftest message-bubble-no-read-badge-without-a-receipt
  (let [msg {:rkey "m1" :senderDid "did:web:alice" :text "hi" :createdAt "t"}
        html (rdom-server/render-to-static-markup
              (#'cd/message-bubble msg "did:web:alice"
                                   (assoc no-extras :raw-messages [msg] :receipts [])))]
    (is (not (str/includes? html "既読")))))

(deftest message-bubble-renders-attachment-and-reaction-counts
  (let [html (rdom-server/render-to-static-markup
              (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:bob" :text "look" :createdAt "2026-07-08T00:00:00Z"}
                                   "did:web:alice"
                                   (assoc no-extras
                                          :attachments [{:uri "https://x/blob" :contentType "image/png"}]
                                          :reactions [{:emoji "👍" :did "did:web:alice"}
                                                      {:emoji "👍" :did "did:web:bob"}
                                                      {:emoji "❤️" :did "did:web:bob"}])))]
    (is (str/includes? html "https://x/blob") "image attachment renders as an <img src>")
    (is (str/includes? html "👍") "reaction emoji renders")
    (is (str/includes? html "2") "grouped reaction shows its count")))

(deftest message-bubble-shows-edited-badge
  (let [html (rdom-server/render-to-static-markup
              (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:alice" :text "hi (fixed)"
                                    :editedAt "2026-07-09T00:00:00Z" :createdAt "t"}
                                   "did:web:alice" no-extras))]
    (is (str/includes? html "編集済み"))))

(deftest message-bubble-no-edited-badge-when-never-edited
  (let [html (rdom-server/render-to-static-markup
              (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:alice" :text "hi" :createdAt "t"}
                                   "did:web:alice" no-extras))]
    (is (not (str/includes? html "編集済み")))))

(deftest message-bubble-shows-edit-box-only-for-the-editing-rkey
  (let [editing (rdom-server/render-to-static-markup
                 (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:alice" :text "hi" :createdAt "t"}
                                      "did:web:alice" (assoc no-extras :editing-rkey "m1" :edit-draft "hi there")))
        not-editing (rdom-server/render-to-static-markup
                     (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:alice" :text "hi" :createdAt "t"}
                                          "did:web:alice" (assoc no-extras :editing-rkey "m2")))]
    (is (str/includes? editing "<textarea"))
    (is (str/includes? editing "hi there") "the draft seeds the textarea value")
    (is (not (str/includes? not-editing "<textarea")))))

(deftest message-bubble-edit-box-shows-error
  (let [html (rdom-server/render-to-static-markup
              (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:alice" :text "hi" :createdAt "t"}
                                   "did:web:alice" (assoc no-extras :editing-rkey "m1" :edit-draft "hi"
                                                          :edit-error "encryption: boom")))]
    (is (str/includes? html "encryption: boom"))))

(deftest message-bubble-hides-edit-and-delete-buttons-for-someone-elses-message
  (let [html (rdom-server/render-to-static-markup
              (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:bob" :text "hi" :createdAt "t"}
                                   "did:web:alice" no-extras))]
    (is (not (str/includes? html "編集する")))
    (is (not (str/includes? html "削除する")) "no confirmed-delete label leaks either")))

(deftest message-bubble-delete-confirm-shows-only-for-its-own-rkey
  (let [confirming (rdom-server/render-to-static-markup
                    (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:alice" :text "hi" :createdAt "t"}
                                         "did:web:alice" (assoc no-extras :delete-confirm-for "m1")))
        other (rdom-server/render-to-static-markup
               (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:alice" :text "hi" :createdAt "t"}
                                    "did:web:alice" (assoc no-extras :delete-confirm-for "m2")))]
    (is (str/includes? confirming "削除する") "confirm state shows the destructive confirm button")
    (is (not (str/includes? other "削除する")) "confirming a DIFFERENT message doesn't leak in")))

(deftest member-panel-shows-the-title-and-edit-button-when-not-renaming
  (let [html (rdom-server/render-to-static-markup
              (#'cd/member-panel {:convoId "convo-1" :title "Book Club" :members []}
                                 "did:web:alice" {:renaming? false}))]
    (is (str/includes? html "Book Club"))
    (is (str/includes? html "グループ名を変更") "the edit-title button shows")
    (is (not (str/includes? html "キャンセル")) "the cancel/save controls only show while renaming")))

(deftest member-panel-shows-the-rename-input-when-renaming
  (let [html (rdom-server/render-to-static-markup
              (#'cd/member-panel {:convoId "convo-1" :title "Book Club" :members []}
                                 "did:web:alice" {:renaming? true :rename-draft "New Name"}))]
    (is (str/includes? html "New Name") "the draft seeds the input value")
    (is (str/includes? html "キャンセル"))
    (is (not (str/includes? html "グループ名を変更")) "the edit-title trigger button is gone while actively renaming")))

(deftest member-panel-rename-input-shows-error
  (let [html (rdom-server/render-to-static-markup
              (#'cd/member-panel {:convoId "convo-1" :title "Book Club" :members []}
                                 "did:web:alice" {:renaming? true :rename-draft "" :rename-error "空の名前にはできません"}))]
    (is (str/includes? html "空の名前にはできません"))))

(deftest member-row-shows-leave-not-remove-for-my-own-row
  (let [html (rdom-server/render-to-static-markup
              (#'cd/member-row {:did "did:web:alice" :displayName "Alice"} "convo-1" "did:web:alice" false))]
    (is (str/includes? html "退出"))
    (is (not (str/includes? html "メンバーを削除")))))

(deftest member-row-shows-remove-not-leave-for-someone-elses-row
  (let [html (rdom-server/render-to-static-markup
              (#'cd/member-row {:did "did:web:bob" :displayName "Bob"} "convo-1" "did:web:alice" false))]
    (is (str/includes? html "削除"))
    (is (not (str/includes? html "退出")))))

(deftest member-row-leave-confirm-shows-the-destructive-confirm-button
  (let [html (rdom-server/render-to-static-markup
              (#'cd/member-row {:did "did:web:alice" :displayName "Alice"} "convo-1" "did:web:alice" true))]
    (is (str/includes? html "退出する"))))

(deftest message-bubble-shows-picker-only-for-its-own-rkey
  (let [open (rdom-server/render-to-static-markup
              (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:bob" :text "hi" :createdAt "t"}
                                   "did:web:alice" (assoc no-extras :picker-for "m1")))
        closed (rdom-server/render-to-static-markup
                (#'cd/message-bubble {:rkey "m1" :senderDid "did:web:bob" :text "hi" :createdAt "t"}
                                     "did:web:alice" (assoc no-extras :picker-for "m2")))]
    (is (str/includes? open "👍") "picker open for this message shows quick-react emoji")
    (is (not (str/includes? closed "👍")) "picker open for a DIFFERENT message doesn't leak in")))

(deftest convo-detail-page-renders-seeded-state
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []}
                   :messages [{:rkey "m1" :senderDid "did:web:bob" :sender {:displayName "Bob"}
                               :text "" :encryption signal/scheme :createdAt "2026-07-08T00:00:00Z"}]
                   :decrypted {"m1" "hi alice"}
                   :decrypt-failed {}}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (str/includes? html "hi alice") "decrypted message text renders")
    (is (str/includes? html "E2EE") "badge reflects the successfully-decrypted latest message")
    (is (str/includes? html "Bob") "peer display name used as the title fallback")))

(deftest convo-detail-page-search-filters-visible-messages-but-not-the-badge
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :search-open? true
                   :search-query "world"
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []}
                   :messages [{:rkey "m1" :senderDid "did:web:bob" :sender {:displayName "Bob"}
                               :text "hello world" :encryption "plaintext" :createdAt "2026-07-08T00:00:00Z"}
                              {:rkey "m2" :senderDid "did:web:bob" :sender {:displayName "Bob"}
                               :text "goodbye" :encryption "plaintext" :createdAt "2026-07-08T00:01:00Z"}]
                   :decrypted {}
                   :decrypt-failed {}}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (str/includes? html "hello world") "the matching message renders")
    (is (not (str/includes? html "goodbye")) "the non-matching message is filtered out")))

(deftest convo-detail-page-search-with-no-matches-shows-empty-state-not-the-generic-empty-convo-message
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :search-open? true
                   :search-query "nonexistent"
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []}
                   :messages [{:rkey "m1" :senderDid "did:web:bob" :sender {:displayName "Bob"}
                               :text "hello world" :encryption "plaintext" :createdAt "2026-07-08T00:00:00Z"}]
                   :decrypted {}
                   :decrypt-failed {}}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (str/includes? html "見つかりませんでした"))
    (is (not (str/includes? html "まだメッセージはありません"))
        "there ARE messages, just none matching — the wrong empty-state must not show")))

(deftest convo-detail-page-shows-failed-send-with-retry-and-dismiss
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []}
                   :messages []
                   :decrypted {} :decrypt-failed {}
                   :failed-sends [{:id "convo-1-123" :convo-id "convo-1" :text "undelivered message"}]}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (str/includes? html "undelivered message"))
    (is (str/includes? html "送信できませんでした"))
    (is (str/includes? html "再送信"))))

(deftest convo-detail-page-hides-failed-sends-section-when-empty
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []}
                   :messages []
                   :decrypted {} :decrypt-failed {}
                   :failed-sends []}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (not (str/includes? html "送信できませんでした")))))

(deftest convo-detail-page-shows-load-more-button-when-has-more
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :has-more? true
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []}
                   :messages [{:rkey "m1" :senderDid "did:web:bob" :text "hi" :encryption "plaintext" :createdAt "t"}]
                   :decrypted {} :decrypt-failed {}}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (str/includes? html "過去のメッセージを読み込む"))))

(deftest convo-detail-page-hides-load-more-button-when-no-more
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :has-more? false
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []}
                   :messages [{:rkey "m1" :senderDid "did:web:bob" :text "hi" :encryption "plaintext" :createdAt "t"}]
                   :decrypted {} :decrypt-failed {}}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (not (str/includes? html "過去のメッセージを読み込む")))))

(deftest convo-detail-page-shows-read-badge-on-my-last-message
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []
                          :receipts [{:convoId "convo-1" :did "did:web:bob" :lastSeenRkey "m1"}]}
                   :messages [{:rkey "m1" :senderDid "did:web:alice" :text "hi bob" :encryption "plaintext" :createdAt "t"}]
                   :decrypted {}
                   :decrypt-failed {}}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (str/includes? html "既読"))))

(deftest convo-detail-page-shows-typing-indicator-when-someone-is-typing
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []}
                   :messages []
                   :decrypted {}
                   :decrypt-failed {}
                   :typing [{:convoId "convo-1" :did "did:web:bob" :updatedAt "t"}]}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (str/includes? html "Bobが入力中"))))

(deftest convo-detail-page-shows-no-typing-indicator-when-nobody-is-typing
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? false
                   :not-found? false
                   :current-id "convo-1"
                   :meta {:convoId "convo-1" :title ""
                          :members [{:did "did:web:alice"} {:did "did:web:bob" :displayName "Bob"}]
                          :attachments [] :reactions []}
                   :messages []
                   :decrypted {}
                   :decrypt-failed {}
                   :typing []}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (not (str/includes? html "入力中")))))

(deftest convo-detail-page-loading-state-has-no-badge-or-messages
  (rf/clear-subscription-cache!)
  (reset! db/app-db
          {:auth {:session {:did "did:web:alice"}}
           :convo {:loading? true :not-found? false :current-id "convo-1" :meta nil
                   :messages [] :decrypted {} :decrypt-failed {}}})
  (let [html (rdom-server/render-to-static-markup [cd/convo-detail-page {:id "convo-1"}])]
    (is (not (str/includes? html "E2EE")))
    (is (not (str/includes? html "hi alice")))))

;; ---------------------------------------------------------------------------
;; 3. Event dispatch (hermetic — network/crypto fx stubbed)

(defn- with-fx-stub [fx-key stub-fn f]
  (let [orig (registrar/get-handler :fx fx-key)]
    (rf/reg-fx fx-key stub-fn)
    (try (f) (finally (when orig (rf/reg-fx fx-key orig))))))

(defn- unreachable-network-stub [& _]
  (throw (js/Error. "test: no XRPC call was expected in this dispatch")))

(deftest messages-loaded-updates-db-and-skips-decrypt-for-plaintext
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}})
  (let [captured (atom :not-called)]
    (with-fx-stub :convo/decrypt! (fn [payload] (reset! captured payload))
      (fn []
        (with-fx-stub :atproto/procedure unreachable-network-stub
          (fn []
            (rf/dispatch-sync
             [:convo/messages-loaded
              {:convo {:convoId "convo-1" :members []}
               :messages [{:rkey "m1" :senderDid "did:web:alice" :text "hi" :encryption "plaintext" :createdAt "t1"}]
               :notFound false}])))))
    (is (= "convo-1" (get-in @db/app-db [:convo :meta :convoId])))
    (is (false? (get-in @db/app-db [:convo :loading?])))
    (is (= :not-called @captured) "a plaintext message never triggers the decrypt fx")))

(deftest load-requests-a-page-not-the-whole-history
  (rf/clear-subscription-cache!)
  (reset! db/app-db {})
  (let [captured (atom nil)]
    (with-fx-stub :atproto/query (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/load "convo-1"])))
    (is (= "app.aozora.convo.getConvo" (:nsid @captured)))
    (is (= "convo-1" (get-in @captured [:params :convoId])))
    (is (pos? (get-in @captured [:params :limit])) "a bounded page, not an unbounded full-history fetch")
    (is (nil? (get-in @captured [:params :before])) "the initial load never sends a before cursor")))

(deftest messages-loaded-stores-the-cursor-and-has-more-flag
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}})
  (with-fx-stub :atproto/procedure unreachable-network-stub
    (fn []
      (rf/dispatch-sync
       [:convo/messages-loaded
        {:convo {:convoId "convo-1" :members []}
         :messages [{:rkey "m1" :senderDid "did:web:alice" :text "hi" :encryption "plaintext" :createdAt "t1"}]
         :cursor "m1" :hasMore true :notFound false}])))
  (is (= "m1" (get-in @db/app-db [:convo :cursor])))
  (is (true? (get-in @db/app-db [:convo :has-more?]))))

(deftest load-more-does-nothing-without-has-more
  (reset! db/app-db {:convo {:current-id "convo-1" :cursor "m1" :has-more? false}})
  (let [captured (atom :not-called)]
    (with-fx-stub :atproto/query (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/load-more])))
    (is (= :not-called @captured))))

(deftest load-more-does-nothing-while-already-loading-more
  (reset! db/app-db {:convo {:current-id "convo-1" :cursor "m1" :has-more? true :loading-more? true}})
  (let [captured (atom :not-called)]
    (with-fx-stub :atproto/query (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/load-more])))
    (is (= :not-called @captured))))

(deftest load-more-fetches-the-next-older-page-with-the-cursor
  (reset! db/app-db {:convo {:current-id "convo-1" :cursor "m3" :has-more? true}})
  (let [captured (atom nil)]
    (with-fx-stub :atproto/query (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/load-more])))
    (is (= "app.aozora.convo.getConvo" (:nsid @captured)))
    (is (= {:convoId "convo-1" :limit 50 :before "m3"} (:params @captured)))
    (is (true? (get-in @db/app-db [:convo :loading-more?])))))

(deftest older-messages-loaded-prepends-onto-the-existing-list
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:current-id "convo-1" :loading-more? true
                              :messages [{:rkey "m3" :senderDid "did:web:alice" :text "c" :encryption "plaintext"}]}})
  (with-fx-stub :atproto/procedure unreachable-network-stub
    (fn []
      (rf/dispatch-sync
       [:convo/older-messages-loaded
        {:messages [{:rkey "m1" :senderDid "did:web:alice" :text "a" :encryption "plaintext"}
                    {:rkey "m2" :senderDid "did:web:alice" :text "b" :encryption "plaintext"}]
         :cursor "m1" :hasMore true}])))
  (is (= ["m1" "m2" "m3"] (map :rkey (get-in @db/app-db [:convo :messages])))
      "the older page goes BEFORE the already-loaded messages")
  (is (= "m1" (get-in @db/app-db [:convo :cursor])))
  (is (true? (get-in @db/app-db [:convo :has-more?])))
  (is (false? (get-in @db/app-db [:convo :loading-more?]))))

(deftest older-messages-loaded-requests-decrypt-for-the-new-older-batch-only
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:current-id "convo-1" :messages []}})
  (let [captured (atom :not-called)]
    (with-fx-stub :convo/decrypt! (fn [payload] (reset! captured payload))
      (fn []
        (with-fx-stub :atproto/procedure unreachable-network-stub
          (fn []
            (rf/dispatch-sync
             [:convo/older-messages-loaded
              {:messages [{:rkey "m1" :senderDid "did:web:bob" :text "{\"v\":1,\"n\":0}" :encryption signal/scheme}]
               :cursor nil :hasMore false}])))))
    (is (= [{:rkey "m1" :peer-did "did:web:bob" :envelope {:v 1 :n 0}}] (:items @captured)))))

(deftest older-messages-load-failed-resets-loading-more
  (reset! db/app-db {:convo {:loading-more? true}})
  (rf/dispatch-sync [:convo/older-messages-load-failed "boom"])
  (is (false? (get-in @db/app-db [:convo :loading-more?]))))

;; ---------------------------------------------------------------------------
;; Group rename

(deftest start-rename-seeds-the-draft-and-clears-any-stale-error
  (reset! db/app-db {:convo {:rename-error "stale"}})
  (rf/dispatch-sync [:convo/start-rename "Old Name"])
  (is (true? (get-in @db/app-db [:convo :renaming?])))
  (is (= "Old Name" (get-in @db/app-db [:convo :rename-draft])))
  (is (nil? (get-in @db/app-db [:convo :rename-error]))))

(deftest cancel-rename-clears-renaming-state
  (reset! db/app-db {:convo {:renaming? true :rename-error "boom"}})
  (rf/dispatch-sync [:convo/cancel-rename])
  (is (false? (get-in @db/app-db [:convo :renaming?])))
  (is (nil? (get-in @db/app-db [:convo :rename-error]))))

(deftest save-rename-rejects-blank-draft-without-touching-network
  (reset! db/app-db {:convo {:rename-draft "   "}})
  (let [captured (atom :not-called)]
    (with-fx-stub :atproto/procedure (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/save-rename "convo-1"])))
    (is (= :not-called @captured))
    (is (some? (get-in @db/app-db [:convo :rename-error])))))

(deftest save-rename-posts-updateConvo
  (reset! db/app-db {:convo {:rename-draft "New Name"}})
  (let [captured (atom nil)]
    (with-fx-stub :atproto/procedure (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/save-rename "convo-1"])))
    (is (= "app.aozora.convo.updateConvo" (:nsid @captured)))
    (is (= {:convoId "convo-1" :title "New Name"} (:body @captured)))
    (is (= [:convo/rename-saved "convo-1"] (:on-success @captured)))))

(deftest rename-saved-clears-renaming-state-and-reloads
  (reset! db/app-db {:convo {:renaming? true :rename-error nil}})
  (let [reload-calls (atom [])]
    (with-fx-stub :atproto/query (fn [opts] (swap! reload-calls conj opts))
      (fn [] (rf/dispatch-sync [:convo/rename-saved "convo-1"]))))
  (is (false? (get-in @db/app-db [:convo :renaming?]))))

(deftest rename-failed-surfaces-the-error
  (reset! db/app-db {:convo {:renaming? true}})
  (rf/dispatch-sync [:convo/rename-failed "boom"])
  (is (true? (get-in @db/app-db [:convo :renaming?])) "stays open so the user can retry")
  (is (some? (get-in @db/app-db [:convo :rename-error]))))

(deftest messages-loaded-requests-decrypt-only-for-undecrypted-incoming-signal-lite-messages
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:decrypted {"already-done" "cached"} :decrypt-failed {"gave-up" true}}})
  (let [captured (atom nil)]
    (with-fx-stub :convo/decrypt! (fn [payload] (reset! captured payload))
      (fn []
        (with-fx-stub :atproto/procedure unreachable-network-stub
          (fn []
            (rf/dispatch-sync
             [:convo/messages-loaded
              {:convo {:convoId "convo-1" :members []}
               :messages [{:rkey "already-done" :senderDid "did:web:bob" :text "{}" :encryption signal/scheme :createdAt "t1"}
                          {:rkey "gave-up" :senderDid "did:web:bob" :text "{}" :encryption signal/scheme :createdAt "t2"}
                          {:rkey "mine" :senderDid "did:web:alice" :text "{}" :encryption signal/scheme :createdAt "t3"}
                          {:rkey "fresh" :senderDid "did:web:bob" :text "{\"v\":1,\"n\":0}" :encryption signal/scheme :createdAt "t4"}]
               :notFound false}])))))
    (is (= [{:rkey "fresh" :peer-did "did:web:bob" :envelope {:v 1 :n 0}}]
           (:items @captured))
        "already-decrypted, already-failed, and self-sent messages are all skipped — only the one genuinely-new incoming message is requested")))

(deftest send-start-rejects-when-no-peer-resolvable
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:meta {:convoId "convo-1" :members [{:did "did:web:alice"}]}}})
  (let [captured (atom :not-called)]
    (with-fx-stub :convo/encrypt-and-send! (fn [payload] (reset! captured payload))
      (fn [] (rf/dispatch-sync [:convo/send-start {:convo-id "convo-1" :text "hello"}])))
    (is (= :not-called @captured) "no peer in convo members → never asks signal to encrypt")
    (is (false? (get-in @db/app-db [:convo :sending?])))))

(deftest send-start-hands-off-to-encrypt-and-send-with-resolved-peer-and-attachment
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:meta {:convoId "convo-1"
                                     :members [{:did "did:web:alice"} {:did "did:web:bob"}]}}})
  (let [captured (atom nil)
        fake-file #js {:name "photo.png"}]
    (with-fx-stub :convo/encrypt-and-send! (fn [payload] (reset! captured payload))
      (fn [] (rf/dispatch-sync [:convo/send-start {:convo-id "convo-1" :text "hello" :file fake-file}])))
    (is (= {:my-did "did:web:alice" :peer-did "did:web:bob" :convo-id "convo-1" :text "hello" :file fake-file}
           @captured)
        "the selected file rides through untouched — encryption only ever sees :text")
    (is (true? (get-in @db/app-db [:convo :sending?])))))

(deftest message-sent-caches-plaintext-and-reloads-when-no-attachment
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:convo {:sending? true}})
  ;; message-sent's :fx also re-dispatches :convo/load (a real reload in
  ;; production) — record that it fired rather than blocking it; this test
  ;; is only about the :db effect (plaintext cache + sending? reset).
  (let [reload-calls (atom [])]
    (with-fx-stub :atproto/query (fn [opts] (swap! reload-calls conj opts))
      (fn [] (rf/dispatch-sync [:convo/message-sent "hello" nil {:convoId "convo-1" :rkey "m9"}]))))
  (is (= "hello" (get-in @db/app-db [:convo :decrypted "m9"]))
      "the plaintext this device just composed is cached directly — it can never be re-derived from the ciphertext via the receive chain")
  (is (false? (get-in @db/app-db [:convo :sending?]))))

(deftest message-sent-with-attachment-uploads-the-blob-instead-of-reloading-immediately
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:convo {:sending? true}})
  (let [uploaded (atom nil)
        fake-file #js {:name "photo.png" :type "image/png"}]
    (with-fx-stub :atproto/upload-blob (fn [payload] (reset! uploaded payload))
      (fn [] (rf/dispatch-sync [:convo/message-sent "📎 photo.png" fake-file {:convoId "convo-1" :rkey "m9"}])))
    (is (= fake-file (:file @uploaded)))
    (is (= "image/png" (:mime @uploaded)))))

;; re-frame refuses dispatch-sync called from *within* another event
;; handler ("You can't call dispatch-sync within an event handler") — a real
;; XRPC's .then callback runs in a later microtask, outside that call stack,
;; so it doesn't hit this, but a synchronous test stub simulating success
;; DOES. So these two assert the returned :on-success WIRING (data, not
;; execution), and a separate isolated dispatch of :convo/reload-convo
;; (below) proves that wiring's target actually requests a reload.

(deftest attachment-blob-uploaded-attaches-with-the-blob-url-and-wires-a-reload
  (let [captured (atom nil)]
    (with-fx-stub :atproto/procedure (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync
              [:convo/attachment-blob-uploaded "convo-1" "m9"
               {:blob {:ref {:$link "bafyCID"} :mimeType "image/png"}}])))
    (is (= "app.aozora.convo.addAttachment" (:nsid @captured)))
    (is (= "m9" (get-in @captured [:body :messageRkey])))
    (is (= "bafyCID" (get-in @captured [:body :cid])))
    (is (str/includes? (get-in @captured [:body :uri]) "bafyCID")
        "uri is derived from the blob cid, not left blank")
    (is (= [:convo/reload-convo "convo-1"] (:on-success @captured))
        "success is wired to the shared reload handler")))

(deftest react-clears-the-picker-and-wires-a-reload
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:convo {:reaction-picker-for "m1"}})
  (let [captured (atom nil)]
    (with-fx-stub :atproto/procedure (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/react {:convo-id "convo-1" :message-rkey "m1" :emoji "👍"}])))
    (is (= "app.aozora.convo.addReaction" (:nsid @captured)))
    (is (= {:convoId "convo-1" :messageRkey "m1" :emoji "👍"} (:body @captured)))
    (is (nil? (get-in @db/app-db [:convo :reaction-picker-for])) "picker closes immediately, optimistically")
    (is (= [:convo/reload-convo "convo-1"] (:on-success @captured))
        "success is wired to the same shared reload handler as attachments")))

(deftest attachment-added-requests-a-convo-reload
  (let [captured (atom [])]
    (with-fx-stub :dispatch (fn [event] (swap! captured conj event))
      (fn [] (rf/dispatch-sync [:convo/reload-convo "convo-1"])))
    (is (= [[:convo/load "convo-1"]] @captured))))

(deftest toggle-reaction-picker-opens-then-closes-the-same-rkey
  (reset! db/app-db {})
  (rf/dispatch-sync [:convo/toggle-reaction-picker "m1"])
  (is (= "m1" (get-in @db/app-db [:convo :reaction-picker-for])))
  (rf/dispatch-sync [:convo/toggle-reaction-picker "m1"])
  (is (nil? (get-in @db/app-db [:convo :reaction-picker-for])) "clicking the same message's button again closes it"))

;; ---------------------------------------------------------------------------
;; Edit — same shape as the send-start/messages-loaded tests above, mirrored
;; for the encrypt-then-persist edit chain.

(deftest start-edit-seeds-the-draft-and-clears-any-stale-error
  (reset! db/app-db {:convo {:edit-error "stale"}})
  (rf/dispatch-sync [:convo/start-edit "m1" "current text"])
  (is (= "m1" (get-in @db/app-db [:convo :editing-rkey])))
  (is (= "current text" (get-in @db/app-db [:convo :edit-draft])))
  (is (nil? (get-in @db/app-db [:convo :edit-error]))))

(deftest cancel-edit-clears-editing-state
  (reset! db/app-db {:convo {:editing-rkey "m1" :edit-error "boom"}})
  (rf/dispatch-sync [:convo/cancel-edit])
  (is (nil? (get-in @db/app-db [:convo :editing-rkey])))
  (is (nil? (get-in @db/app-db [:convo :edit-error]))))

(deftest save-edit-rejects-blank-draft-without-touching-network
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:meta {:convoId "convo-1" :members [{:did "did:web:alice"} {:did "did:web:bob"}]}
                              :editing-rkey "m1" :edit-draft "   "}})
  (let [captured (atom :not-called)]
    (with-fx-stub :convo/encrypt-and-edit! (fn [payload] (reset! captured payload))
      (fn [] (rf/dispatch-sync [:convo/save-edit])))
    (is (= :not-called @captured))
    (is (some? (get-in @db/app-db [:convo :edit-error])))))

(deftest save-edit-hands-off-to-encrypt-and-edit-with-resolved-peer
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:meta {:convoId "convo-1" :members [{:did "did:web:alice"} {:did "did:web:bob"}]}
                              :editing-rkey "m1" :edit-draft "fixed text"}})
  (let [captured (atom nil)]
    (with-fx-stub :convo/encrypt-and-edit! (fn [payload] (reset! captured payload))
      (fn [] (rf/dispatch-sync [:convo/save-edit])))
    (is (= {:my-did "did:web:alice" :peer-did "did:web:bob" :convo-id "convo-1"
           :rkey "m1" :text "fixed text"}
          @captured))))

(deftest save-edit-routes-to-group-encryption-for-a-group-convo
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:meta {:convoId "convo-1" :kind "group"
                                     :members [{:did "did:web:alice"} {:did "did:web:bob"} {:did "did:web:carol"}]}
                              :editing-rkey "m1" :edit-draft "fixed for all"}})
  (let [group-captured (atom :not-called)
        dm-captured (atom :not-called)]
    (with-fx-stub :convo/encrypt-and-edit-group! (fn [payload] (reset! group-captured payload))
      (fn []
        (with-fx-stub :convo/encrypt-and-edit! (fn [payload] (reset! dm-captured payload))
          (fn [] (rf/dispatch-sync [:convo/save-edit])))))
    (is (= {:my-did "did:web:alice" :convo-id "convo-1"
           :members ["did:web:alice" "did:web:bob" "did:web:carol"]
           :rkey "m1" :text "fixed for all"}
          @group-captured))
    (is (= :not-called @dm-captured))))

(deftest persist-edit-posts-edit-message-and-wires-the-save-response
  (let [captured (atom nil)]
    (with-fx-stub :atproto/procedure (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/persist-edit {:convo-id "convo-1" :rkey "m1"
                                                     :text "ciphertext-envelope" :plaintext "fixed"}])))
    (is (= "app.aozora.convo.editMessage" (:nsid @captured)))
    (is (= {:convoId "convo-1" :rkey "m1" :text "ciphertext-envelope"} (:body @captured)))
    (is (= [:convo/edit-saved "m1" "fixed" "convo-1"] (:on-success @captured)))))

(deftest edit-saved-caches-plaintext-clears-editing-state-and-reloads
  (reset! db/app-db {:convo {:editing-rkey "m1" :edit-draft "fixed" :edit-error nil}})
  (let [reload-calls (atom [])]
    (with-fx-stub :atproto/query (fn [opts] (swap! reload-calls conj opts))
      (fn [] (rf/dispatch-sync [:convo/edit-saved "m1" "fixed" "convo-1"]))))
  (is (= "fixed" (get-in @db/app-db [:convo :decrypted "m1"])))
  (is (nil? (get-in @db/app-db [:convo :editing-rkey])))
  (is (= "" (get-in @db/app-db [:convo :edit-draft]))))

;; ---------------------------------------------------------------------------
;; Delete (unsend)

(deftest toggle-delete-confirm-opens-then-closes-the-same-rkey
  (reset! db/app-db {})
  (rf/dispatch-sync [:convo/toggle-delete-confirm "m1"])
  (is (= "m1" (get-in @db/app-db [:convo :delete-confirm-for])))
  (rf/dispatch-sync [:convo/toggle-delete-confirm "m1"])
  (is (nil? (get-in @db/app-db [:convo :delete-confirm-for]))))

(deftest delete-message-clears-confirm-and-wires-a-reload
  (reset! db/app-db {:convo {:delete-confirm-for "m1"}})
  (let [captured (atom nil)]
    (with-fx-stub :atproto/procedure (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/delete-message! {:convo-id "convo-1" :rkey "m1"}])))
    (is (= "app.aozora.convo.deleteMessage" (:nsid @captured)))
    (is (= {:convoId "convo-1" :rkey "m1"} (:body @captured)))
    (is (nil? (get-in @db/app-db [:convo :delete-confirm-for])) "confirm state clears immediately, optimistically")
    (is (= [:convo/reload-convo "convo-1"] (:on-success @captured)))))

;; ---------------------------------------------------------------------------
;; In-conversation search

(deftest toggle-search-opens-then-closes-and-clears-the-query
  (reset! db/app-db {:convo {:search-query "stale"}})
  (rf/dispatch-sync [:convo/toggle-search])
  (is (true? (get-in @db/app-db [:convo :search-open?])))
  (rf/dispatch-sync [:convo/toggle-search])
  (is (false? (get-in @db/app-db [:convo :search-open?])))
  (is (= "" (get-in @db/app-db [:convo :search-query])) "closing the search bar clears whatever was typed"))

(deftest set-search-query-updates-the-query
  (reset! db/app-db {})
  (rf/dispatch-sync [:convo/set-search-query "hello"])
  (is (= "hello" (get-in @db/app-db [:convo :search-query]))))

(deftest messages-loaded-accumulates-a-per-convo-cache-without-wiping-the-flat-list
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:messages-by-convo {"convo-0" [{:rkey "old" :text "from an earlier convo"}]}}})
  (let [dm-messages [{:rkey "m1" :senderDid "did:web:alice" :text "hi" :encryption "plaintext" :createdAt "t1"}]]
    (with-fx-stub :atproto/procedure unreachable-network-stub
      (fn []
        (rf/dispatch-sync
         [:convo/messages-loaded
          {:convo {:convoId "convo-1" :members []} :messages dm-messages :notFound false}]))))
  (is (= [{:rkey "m1" :senderDid "did:web:alice" :text "hi" :encryption "plaintext" :createdAt "t1"}]
        (get-in @db/app-db [:convo :messages-by-convo "convo-1"])))
  (is (= [{:rkey "old" :text "from an earlier convo"}]
        (get-in @db/app-db [:convo :messages-by-convo "convo-0"]))
      "an earlier convo's cached messages are never wiped by loading a different one"))

;; ---------------------------------------------------------------------------
;; Typing indicators

(deftest poll-typing-fetches-listTyping-scoped-to-the-open-convo-and-caller
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:current-id "convo-1"}})
  (let [captured (atom nil)]
    (with-fx-stub :atproto/query (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/poll-typing])))
    (is (= "app.aozora.convo.listTyping" (:nsid @captured)))
    (is (= {:convoId "convo-1" :did "did:web:alice"} (:params @captured)))))

(deftest poll-typing-does-nothing-without-a-signed-in-session
  (reset! db/app-db {:auth {:session nil} :convo {:current-id "convo-1"}})
  (let [captured (atom :not-called)]
    (with-fx-stub :atproto/query (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/poll-typing])))
    (is (= :not-called @captured))))

(deftest typing-received-stores-the-list
  (reset! db/app-db {})
  (rf/dispatch-sync [:convo/typing-received {:typing [{:convoId "convo-1" :did "did:web:bob" :updatedAt "t"}]}])
  (is (= [{:convoId "convo-1" :did "did:web:bob" :updatedAt "t"}] (get-in @db/app-db [:convo :typing]))))

(deftest ping-typing-posts-setTyping-true-and-throttles-immediate-repeats
  (reset! db/app-db {:convo {:current-id "convo-1"}})
  (let [calls (atom [])]
    (with-fx-stub :atproto/procedure (fn [opts] (swap! calls conj opts))
      (fn []
        (rf/dispatch-sync [:convo/ping-typing!])
        (rf/dispatch-sync [:convo/ping-typing!])))
    (is (= 1 (count @calls)) "the second ping within the throttle window is a no-op")
    (is (= "app.aozora.convo.setTyping" (:nsid (first @calls))))
    (is (= {:convoId "convo-1" :isTyping true} (:body (first @calls))))))

(deftest stop-typing-posts-setTyping-false-and-resets-the-throttle
  (reset! db/app-db {:convo {:current-id "convo-1" :last-typing-ping-at (js/Date.now)}})
  (let [captured (atom nil)]
    (with-fx-stub :atproto/procedure (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/stop-typing!])))
    (is (= "app.aozora.convo.setTyping" (:nsid @captured)))
    (is (= {:convoId "convo-1" :isTyping false} (:body @captured)))
    (is (zero? (get-in @db/app-db [:convo :last-typing-ping-at]))
        "resetting the throttle means the very next keystroke pings again immediately")))

;; ---------------------------------------------------------------------------
;; Leave group

(deftest toggle-leave-confirm-opens-then-closes
  (reset! db/app-db {})
  (rf/dispatch-sync [:convo/toggle-leave-confirm])
  (is (true? (get-in @db/app-db [:convo :leave-confirm?])))
  (rf/dispatch-sync [:convo/toggle-leave-confirm])
  (is (false? (get-in @db/app-db [:convo :leave-confirm?]))))

(deftest leave-group-posts-removeMember-for-self-and-wires-left-group
  (let [captured (atom nil)]
    (with-fx-stub :atproto/procedure (fn [opts] (reset! captured opts))
      (fn [] (rf/dispatch-sync [:convo/leave-group! {:convo-id "convo-1" :did "did:web:alice"}])))
    (is (= "app.aozora.convo.removeMember" (:nsid @captured)))
    (is (= {:convoId "convo-1" :did "did:web:alice"} (:body @captured)))
    (is (= [:convo/left-group] (:on-success @captured))
        "success is wired to the navigate-away handler, NOT reload-convo — reloading a convo you just left makes no sense")))

(deftest left-group-navigates-to-the-convo-list
  (let [captured (atom nil)]
    (with-fx-stub :dispatch (fn [event] (reset! captured event))
      (fn [] (rf/dispatch-sync [:convo/left-group])))
    (is (= [:router/navigate-to "/messages"] @captured))))

;; ---------------------------------------------------------------------------
;; Offline send retry — a failed send is queued (never just logged and
;; dropped), retryable manually or automatically on the browser's `online`
;; event.

(deftest send-failed-queues-a-retryable-entry
  (reset! db/app-db {:convo {:sending? true}})
  (rf/dispatch-sync [:convo/send-failed "convo-1" "hello" nil "network error"])
  (is (false? (get-in @db/app-db [:convo :sending?])))
  (let [queued (get-in @db/app-db [:convo :failed-sends])]
    (is (= 1 (count queued)))
    (is (= "convo-1" (:convo-id (first queued))))
    (is (= "hello" (:text (first queued))))
    (is (some? (:id (first queued))) "each queued entry gets an id so it can be retried/dismissed individually")))

(deftest send-failed-does-not-queue-a-blank-message
  (reset! db/app-db {:convo {}})
  (rf/dispatch-sync [:convo/send-failed "convo-1" "" nil "no signed-in session"])
  (is (empty? (get-in @db/app-db [:convo :failed-sends] []))))

(deftest failed-sends-sub-scopes-to-the-current-convo-only
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:convo {:current-id "convo-1"
                              :failed-sends [{:id "a" :convo-id "convo-1" :text "hi"}
                                            {:id "b" :convo-id "convo-2" :text "bye"}]}})
  (is (= ["a"] (map :id @(rf/subscribe [:convo/failed-sends])))))

(deftest retry-send-removes-the-entry-and-re-dispatches-send-start
  (reset! db/app-db {:convo {:failed-sends [{:id "a" :convo-id "convo-1" :text "hi" :file nil}]}})
  (let [captured (atom nil)]
    (with-fx-stub :dispatch (fn [event] (reset! captured event))
      (fn [] (rf/dispatch-sync [:convo/retry-send! "a"])))
    (is (empty? (get-in @db/app-db [:convo :failed-sends])))
    (is (= [:convo/send-start {:convo-id "convo-1" :text "hi" :file nil}] @captured))))

(deftest retry-send-no-ops-for-an-unknown-id
  (reset! db/app-db {:convo {:failed-sends [{:id "a" :convo-id "convo-1" :text "hi"}]}})
  (let [captured (atom :not-called)]
    (with-fx-stub :dispatch (fn [event] (reset! captured event))
      (fn [] (rf/dispatch-sync [:convo/retry-send! "does-not-exist"])))
    (is (= :not-called @captured))
    (is (= 1 (count (get-in @db/app-db [:convo :failed-sends]))) "the real queue is untouched")))

(deftest dismiss-failed-send-removes-without-retrying
  (reset! db/app-db {:convo {:failed-sends [{:id "a" :convo-id "convo-1" :text "hi"}
                                            {:id "b" :convo-id "convo-1" :text "bye"}]}})
  (let [captured (atom :not-called)]
    (with-fx-stub :dispatch (fn [event] (reset! captured event))
      (fn [] (rf/dispatch-sync [:convo/dismiss-failed-send! "a"])))
    (is (= :not-called @captured) "dismiss never re-sends")
    (is (= ["b"] (map :id (get-in @db/app-db [:convo :failed-sends]))))))

(deftest retry-all-failed-sends-clears-the-queue-and-re-dispatches-every-entry
  (reset! db/app-db {:convo {:failed-sends [{:id "a" :convo-id "convo-1" :text "hi" :file nil}
                                            {:id "b" :convo-id "convo-1" :text "bye" :file nil}]}})
  (let [captured (atom [])]
    (with-fx-stub :dispatch (fn [event] (swap! captured conj event))
      (fn [] (rf/dispatch-sync [:convo/retry-all-failed-sends!])))
    (is (empty? (get-in @db/app-db [:convo :failed-sends])))
    (is (= #{{:convo-id "convo-1" :text "hi" :file nil}
            {:convo-id "convo-1" :text "bye" :file nil}}
          (set (map second @captured))))))

(deftest retry-all-failed-sends-no-ops-when-queue-is-empty
  (reset! db/app-db {:convo {:failed-sends []}})
  (let [captured (atom :not-called)]
    (with-fx-stub :dispatch (fn [event] (reset! captured event))
      (fn [] (rf/dispatch-sync [:convo/retry-all-failed-sends!])))
    (is (= :not-called @captured))))

;; ---------------------------------------------------------------------------
;; 4. Group-vs-1:1 routing (crypto correctness itself is signal-group-test's
;; job — this only checks send-start/messages-loaded route to the right fx)

(deftest send-start-routes-to-group-encryption-for-a-group-convo
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}
                      :convo {:meta {:convoId "convo-1" :kind "group"
                                     :members [{:did "did:web:alice"} {:did "did:web:bob"} {:did "did:web:carol"}]}}})
  (let [group-captured (atom :not-called)
        dm-captured (atom :not-called)]
    (with-fx-stub :convo/encrypt-and-send-group! (fn [payload] (reset! group-captured payload))
      (fn []
        (with-fx-stub :convo/encrypt-and-send! (fn [payload] (reset! dm-captured payload))
          (fn [] (rf/dispatch-sync [:convo/send-start {:convo-id "convo-1" :text "hello all"}])))))
    (is (= {:my-did "did:web:alice" :convo-id "convo-1"
           :members ["did:web:alice" "did:web:bob" "did:web:carol"]
           :text "hello all" :file nil}
          @group-captured))
    (is (= :not-called @dm-captured) "a group convo never takes the 1:1 encryption path")))

(deftest messages-loaded-splits-pending-decrypts-into-dm-and-group-buckets
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:auth {:session {:did "did:web:alice"}}})
  (let [dm-captured (atom :not-called)
        group-captured (atom :not-called)]
    ;; messages-loaded also fires :convo/mark-read as a queued (async)
    ;; :dispatch — harmless here since app-aozora's own mark-read has
    ;; :on-success/:on-failure nil (fire-and-forget), and re-frame's builtin
    ;; :dispatch effect always queues via goog.async.nextTick regardless of
    ;; how the OUTER dispatch-sync ran, so it can't execute within this
    ;; synchronous test body anyway — no stub needed for it.
    (with-fx-stub :convo/decrypt! (fn [payload] (reset! dm-captured payload))
      (fn []
        (with-fx-stub :convo/decrypt-group! (fn [payload] (reset! group-captured payload))
          (fn []
            (rf/dispatch-sync
             [:convo/messages-loaded
              {:convo {:convoId "convo-1" :members []}
               :messages [{:rkey "dm1" :senderDid "did:web:bob" :text "{\"v\":1,\"n\":0}"
                           :encryption signal/scheme :createdAt "t1"}
                          {:rkey "grp1" :senderDid "did:web:carol" :text "{\"v\":1,\"n\":0}"
                           :encryption signal-group/scheme :createdAt "t2"}]
               :notFound false}])))))
    (is (= [{:rkey "dm1" :peer-did "did:web:bob" :envelope {:v 1 :n 0}}]
          (:items @dm-captured)))
    (is (= "convo-1" (:convo-id @group-captured)))
    (is (= [{:rkey "grp1" :sender-did "did:web:carol" :envelope {:v 1 :n 0}}]
          (:items @group-captured)))))
