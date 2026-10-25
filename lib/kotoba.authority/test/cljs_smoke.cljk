(ns cljs-smoke
  (:require [authority.scope :as s]
            [authority.grant :as g]
            [authority.chain :as c]))
(def checks
  [["round-trip" (= "kotoba://cap/host/ledger-append/*"
                    (s/render (s/parse "kotoba://cap/host/ledger-append/*")))]
   ["prefix-confusion-closed" (not (s/covers? (s/parse "kotoba://graph/alice")
                                              (s/parse "kotoba://graph/alice-evil")))]
   ["wildcard-still-works" (s/covers? (s/parse "kotoba://graph/*")
                                      (s/parse "kotoba://graph/alice-evil"))]
   ["empty-denies" (false? (s/covered? #{} ["k" "a"]))]
   ["normalize-idempotent" (let [n (s/normalize [["k" "a"] ["k" :*]])]
                             (= n (s/normalize n)))]
   ["meet-glb" (= ["k" "a" "b"] (s/meet ["k" "a" :*] ["k" "a" "b"]))]
   ["unbounded-child-cannot-extend"
    (= "2026-08-01T00:00:00Z"
       (:grant/expires (g/meet (g/grant {:scopes ["k://a"] :expires "2026-08-01T00:00:00Z"})
                               (g/grant {:scopes ["k://a"]}))))]
   ["fold-neutralises-escalation"
    (= #{["k" "graph" :*]}
       (:grant/scopes (:chain/effective
                       (c/fold [(g/grant {:scopes ["k://graph/*"]})
                                (g/grant {:scopes ["k://graph/*" "k://admin/*"]})]))))]
   ["no-clock-is-a-denial"
    (false? (:authority/allowed?
             (c/authorize {:chain [(g/grant {:scopes ["k://a"]})] :requested "k://a"})))]
   ["granted-path-works"
    (true? (:authority/allowed?
            (c/authorize {:chain [(g/grant {:scopes ["k://a"]})] :requested "k://a"
                          :now "2026-08-15T00:00:00Z"})))]])
(doseq [[n ok] checks] (println (if ok "ok  " "FAIL") n))
(println "---" (count (filter second checks)) "/" (count checks) "passed")
(when-not (every? second checks) (js/process.exit 1))
