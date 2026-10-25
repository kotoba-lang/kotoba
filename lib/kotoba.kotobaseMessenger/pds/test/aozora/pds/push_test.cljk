(ns aozora.pds.push-test
  (:require [cljs.test :refer-macros [deftest is async]]
            [aozora.pds.webpush :as webpush]
            [aozora.pds.repo :as repo]
            [aozora.pds.push :as push]))

;; post-one!/deliver-and-cleanup! chain real RFC 8291/8292 crypto
;; (webpush/encrypt-payload, webpush/vapid-authorization-header) and
;; aozora.pds.repo/delete-record before ever reaching js/fetch — stubbed
;; here so these tests exercise ONLY the new HTTP-status-code branching
;; logic being added, not crypto (already covered by webpush_test.cljc
;; with real key material) or the record-delete plumbing (repo_test.cljc).
;;
;; Deliberately NOT using a nested nested with-X wrapper-around-(f) helper
;; here (the pattern blob_test.cljc's with-fetch uses for a SINGLE stub):
;; stacking 2-3 of those and letting the restore happen in an OUTER .then
;; that runs AFTER the test's own (done) call created a real, reproduced
;; race — cljs.test's async runner started the NEXT deftest (in a
;; different namespace, aozora.pds.repo-test / aozora.pds.webpush-test)
;; before the outer wrapper's trailing restore had actually run, leaking
;; the stub across files. Every test below sets its stubs directly and
;; restores them ITSELF, synchronously, immediately before calling (done)
;; — no queued .then/.finally left to race the next test.
;; NOTE: the destructured key here must NOT be named `fetch` — a local
;; binding named `fetch` shadows the global `js/fetch` within this
;; function's compiled JS scope, so `(set! js/fetch fetch)` would silently
;; reassign the LOCAL variable instead of the real global (a real bug hit
;; while writing this test: post-one! kept hitting the genuine network
;; because the "stub" never actually replaced globalThis.fetch).
(defn- set-stubs! [{:keys [encrypt vapid fetch-stub delete-record]}]
  (when encrypt (set! webpush/encrypt-payload encrypt))
  (when vapid (set! webpush/vapid-authorization-header vapid))
  (when fetch-stub (set! js/fetch fetch-stub))
  (when delete-record (set! repo/delete-record delete-record)))

(def ^:private orig-encrypt webpush/encrypt-payload)
(def ^:private orig-vapid webpush/vapid-authorization-header)
(def ^:private orig-fetch js/fetch)
(def ^:private orig-delete-record repo/delete-record)

(defn- restore! []
  (set! webpush/encrypt-payload orig-encrypt)
  (set! webpush/vapid-authorization-header orig-vapid)
  (set! js/fetch orig-fetch)
  (set! repo/delete-record orig-delete-record))

(def ^:private fake-vapid {:private-jwk {} :public-key "pub" :subject "mailto:ops@aozora.app"})
(def ^:private fake-sub {:did "did:web:alice" :deviceId "device-1"
                         :endpoint "https://push.example/x" :p256dh "p" :auth "a"})

(defn- stub-crypto! []
  (set-stubs! {:encrypt (fn [_ _ _] (js/Promise.resolve (js/Uint8Array. 0)))
               :vapid (fn [_ _ _ _] (js/Promise.resolve "vapid t=x, k=y"))}))

(deftest post-one!-ok-on-200-and-not-dead
  (async done
    (stub-crypto!)
    (set-stubs! {:fetch-stub (fn [_ _] (js/Promise.resolve #js {:ok true :status 200}))})
    (-> (#'push/post-one! fake-vapid fake-sub "{}")
        (.then (fn [res] (restore!) (is (= {:ok true :dead? false} res)) (done))))))

(deftest post-one!-dead-on-410-gone
  (async done
    (stub-crypto!)
    (set-stubs! {:fetch-stub (fn [_ _] (js/Promise.resolve #js {:ok false :status 410}))})
    (-> (#'push/post-one! fake-vapid fake-sub "{}")
        (.then (fn [res] (restore!) (is (= {:ok false :dead? true} res)) (done))))))

(deftest post-one!-dead-on-404-not-found
  (async done
    (stub-crypto!)
    (set-stubs! {:fetch-stub (fn [_ _] (js/Promise.resolve #js {:ok false :status 404}))})
    (-> (#'push/post-one! fake-vapid fake-sub "{}")
        (.then (fn [res] (restore!) (is (= {:ok false :dead? true} res)) (done))))))

(deftest post-one!-not-dead-on-transient-5xx
  (async done
    (stub-crypto!)
    (set-stubs! {:fetch-stub (fn [_ _] (js/Promise.resolve #js {:ok false :status 503}))})
    (-> (#'push/post-one! fake-vapid fake-sub "{}")
        (.then (fn [res]
                 (restore!)
                 (is (false? (:ok res)))
                 (is (false? (:dead? res)) "a 5xx is transient — must never trigger subscription cleanup")
                 (done))))))

(deftest post-one!-not-dead-on-network-error-never-rejects
  (async done
    (stub-crypto!)
    (set-stubs! {:fetch-stub (fn [_ _] (js/Promise.reject (js/Error. "network down")))})
    (-> (#'push/post-one! fake-vapid fake-sub "{}")
        (.then (fn [res] (restore!) (is (= {:ok false :dead? false} res)) (done))))))

(deftest cleanup-dead-subscription-deletes-under-the-deterministic-rkey
  (async done
    (let [captured (atom nil)]
      (set-stubs! {:delete-record (fn [_ _ opts] (reset! captured opts) (js/Promise.resolve {:uri "at://x"}))})
      (-> (#'push/cleanup-dead-subscription! nil "yoro-social" fake-sub)
          (.then (fn [_]
                   (restore!)
                   (is (= {:repo "did:web:alice"
                          :collection "app.aozora.push.subscription"
                          :rkey "sub-device-1"}
                         @captured))
                   (done)))))))

(deftest cleanup-dead-subscription-no-ops-without-did-or-deviceId
  (async done
    (let [called? (atom false)]
      (set-stubs! {:delete-record (fn [_ _ _] (reset! called? true) (js/Promise.resolve {}))})
      ;; cleanup-dead-subscription! legitimately returns bare nil (not a
      ;; Promise) for the no-op case — real callers never chain on it
      ;; (deliver-and-cleanup! only calls it inside a .then for its side
      ;; effect) — wrap in Promise.resolve so this assertion can await
      ;; either shape.
      (-> (js/Promise.resolve (#'push/cleanup-dead-subscription! nil "yoro-social" {:endpoint "x"}))
          (.then (fn [_] (restore!) (is (false? @called?)) (done)))))))

(deftest deliver-and-cleanup-triggers-cleanup-only-when-dead
  (async done
    (stub-crypto!)
    (let [deleted (atom nil)]
      (set-stubs! {:fetch-stub (fn [_ _] (js/Promise.resolve #js {:ok false :status 410}))
                   :delete-record (fn [_ _ opts] (reset! deleted opts) (js/Promise.resolve {}))})
      (-> (#'push/deliver-and-cleanup! nil "yoro-social" fake-vapid fake-sub "{}")
          (.then (fn [_]
                   (restore!)
                   (is (= "sub-device-1" (:rkey @deleted)))
                   (done)))))))

(deftest deliver-and-cleanup-does-not-delete-on-successful-delivery
  (async done
    (stub-crypto!)
    (let [deleted? (atom false)]
      (set-stubs! {:fetch-stub (fn [_ _] (js/Promise.resolve #js {:ok true :status 200}))
                   :delete-record (fn [_ _ _] (reset! deleted? true) (js/Promise.resolve {}))})
      (-> (#'push/deliver-and-cleanup! nil "yoro-social" fake-vapid fake-sub "{}")
          (.then (fn [_] (restore!) (is (false? @deleted?)) (done)))))))
