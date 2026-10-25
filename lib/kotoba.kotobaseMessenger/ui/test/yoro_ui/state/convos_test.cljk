(ns yoro-ui.state.convos-test
  "First coverage for yoro-ui.state.convos (previously untested per the
  messenger coverage audit) — specifically the mute/archive/pin preference
  logic: optimistic update + revert-on-failure, and the list-visible/
  list-archived derived subs."
  (:require [cljs.test :refer-macros [deftest is]]
            [re-frame.core :as rf]
            [re-frame.db :as db]
            [yoro-ui.state.convos :as convos]))

(defn- seed! [convo-list]
  (rf/clear-subscription-cache!)
  (reset! db/app-db {:convos {:list convo-list}}))

(deftest list-visible-excludes-archived
  (seed! [{:id "c1" :archived false} {:id "c2" :archived true} {:id "c3" :archived false}])
  (let [visible @(rf/subscribe [:convos/list-visible])]
    (is (= ["c1" "c3"] (mapv :id visible)))))

(deftest list-archived-includes-only-archived
  (seed! [{:id "c1" :archived false} {:id "c2" :archived true}])
  (let [archived @(rf/subscribe [:convos/list-archived])]
    (is (= ["c2"] (mapv :id archived)))))

(deftest set-preference-optimistically-updates-the-list
  (seed! [{:id "c1" :muted false :pinned false}])
  (rf/dispatch-sync [:convos/set-preference! "c1" :muted true])
  (let [convos @(rf/subscribe [:convos/list])]
    (is (true? (:muted (first convos))))))

(deftest set-preference-does-not-touch-unrelated-convos
  (seed! [{:id "c1" :muted false} {:id "c2" :muted false}])
  (rf/dispatch-sync [:convos/set-preference! "c1" :muted true])
  (let [convos @(rf/subscribe [:convos/list])]
    (is (true? (:muted (first (filter #(= "c1" (:id %)) convos)))))
    (is (false? (:muted (first (filter #(= "c2" (:id %)) convos)))))))

(deftest set-preference-failed-reverts-to-the-previous-value
  (seed! [{:id "c1" :pinned false}])
  (rf/dispatch-sync [:convos/set-preference-failed "c1" :pinned false])
  (let [convos @(rf/subscribe [:convos/list])]
    (is (false? (:pinned (first convos))) "reverting to the value it captured before the optimistic flip")))
