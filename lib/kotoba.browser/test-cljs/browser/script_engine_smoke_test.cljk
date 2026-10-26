(ns browser.script-engine-smoke-test
  "Real Promise-rejection proof for browser.session/ensure-script-engine!.

  browser.script-engine/ensure! (what ensure-script-engine! calls) is
  documented as returning \"a Promise of the updated session\" when the
  engine-factory returns a Promise -- but until this fix, its own `.then`
  call only ever wired a resolve handler, never a reject one. A real
  engine-factory rejection (a real, reachable case -- e.g. the WASM binary
  fails to load) would then propagate as an unhandled rejection on the
  Promise ensure! itself returns, and -- independent of whether a caller's
  own code happened to catch that -- browser.script-engine/fail-start!
  would never run, permanently stranding the session at
  :script-engine/status :pending (ensure!'s own :pending case is a no-op,
  so no future call could ever attempt a new start again, even after the
  caller noticed the failure and wanted to retry).

  This test uses a synthetic, rejecting :engine-factory (a real
  js/Promise.reject, not a mock of ensure!/fail-start! themselves) -- no
  real QuickJS WASM engine is needed to prove this fix, since the bug and
  its fix live entirely in browser.session/browser.script-engine's own
  Promise-handling, not in anything QuickJS-specific.

  ensure! is polymorphic: when the factory returns a Promise, ensure!
  ITSELF returns a Promise (of the eventually-updated session), not a
  plain session map -- so every assertion below deliberately waits on that
  Promise via .then rather than inspecting its return value synchronously."
  (:require [cljs.test :refer [deftest is async]]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(deftest ensure-script-engine-rejection-marks-session-error-not-stuck-pending-test
  (async done
    (let [rejecting-factory (fn [_session] (js/Promise.reject (js/Error. "real WASM load failure")))
          s (session/new-session {:host (host/recording-host)
                                  :engine-factory rejecting-factory})]
      (-> (session/ensure-script-engine! s)
          (.then (fn [after-reject]
                   (is (= :error (get-in after-reject [:browser.session/script-engine :script-engine/status]))
                       (str "expected fail-start! to have transitioned the session to :error after the "
                            "real Promise rejected, not left it stranded at :pending -- got "
                            (pr-str (get-in after-reject [:browser.session/script-engine :script-engine/status]))))
                   (is (= "real WASM load failure"
                          (get-in after-reject [:browser.session/script-engine :script-engine/error]))
                       "expected the real rejection's message to be recorded as the session's error")
                   ;; Proves the fix's whole point: retrying after a failure must actually attempt a
                   ;; NEW start, not silently no-op the way it would if status stayed stuck at :pending.
                   ;; The retry uses the SAME rejecting factory, so it also returns a Promise -- await
                   ;; it too, rather than inspecting its own return value synchronously.
                   (-> (session/ensure-script-engine! after-reject)
                       (.then (fn [after-second-reject]
                                (is (= :error (get-in after-second-reject
                                                      [:browser.session/script-engine :script-engine/status]))
                                    "a retry after :error must attempt a genuinely new start (and can itself fail again), not silently no-op the way a permanently-:pending session would")))
                       (.catch (fn [err]
                                 (is false (str "the retry's own Promise must resolve too, never reject -- got: "
                                                (or (.-message err) err))))))))
          (.catch (fn [err]
                    (is false (str "ensure-script-engine!'s own returned Promise must resolve (with an "
                                   ":error-status session), never itself reject -- got: "
                                   (or (.-message err) err)))))
          (.finally done)))))
