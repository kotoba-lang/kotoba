(ns browser.compat.quickjs-abort-controller-smoke-test
  "Real page-script round-trip proof that AbortController/AbortSignal exist
  and that fetch() honors a signal, evaluated through the actual webapi
  shim string inside real QuickJS WASM, not a JVM stand-in.

  Before this cycle's fix, `new AbortController()` threw a bare
  ReferenceError -- every other commonly-paired webapi class (e.g.
  MutationObserver/Notification/WebSocket) was defined, but not this one
  -- and fetch() never read a `signal` field at all even if a caller
  hand-rolled a signal-shaped object.

  __kotobaMakeDeferred (the hand-rolled thenable every async-shaped
  capability in this shim uses instead of native Promise, since this
  engine's real QuickJS VM job queue is never pumped) settles its
  reactions SYNCHRONOUSLY, so both the pre-abort and mid-flight-abort
  cases below resolve entirely within ONE script tag -- no second
  script tag or real network round trip needed, unlike
  quickjs_fetch_smoke_test.cljs's real-delivery proof."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- canned-fetch-fn
  [pages]
  (fn [{:keys [url]}]
    (if-let [html (get pages url)]
      {:status 200 :headers {} :body html}
      {:status 404 :headers {} :body (str "<main>not found: " url "</main>")})))

(defn- run-page-and-read-title!
  [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/abort-controller"
           fetch-fn (canned-fetch-fn {url html})
           h (host/recording-host)
           base-session (session/new-session
                         (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [after (session/navigate! ready-session url)
                      title (get-in after [:browser.session/page :browser/title])]
                  (dispose-engine! ready-session)
                  (resolve title))
                (catch :default e
                  (dispose-engine! ready-session)
                  (reject e)))))
           (.catch (fn [err]
                     (dispose-engine! base-session)
                     (reject err))))))))

(def ^:private script
  "var r = [];

   var c1 = new AbortController();
   r.push(c1.signal.aborted === false ? 1 : 'fresh-signal-should-not-be-aborted:' + c1.signal.aborted);

   var abortEventFired = false;
   c1.signal.addEventListener('abort', function() { abortEventFired = true; });
   c1.abort('reason-one');
   r.push(c1.signal.aborted === true ? 1 : 'abort-should-set-aborted-true');
   r.push(c1.signal.reason === 'reason-one' ? 1 : 'abort-reason-mismatch:' + c1.signal.reason);
   r.push(abortEventFired === true ? 1 : 'abort-event-listener-should-have-fired');

   var c2 = new AbortController();
   c2.abort();
   r.push(String(c2.signal.reason).indexOf('AbortError') !== -1 ? 1 : 'default-abort-reason-should-be-AbortError:' + c2.signal.reason);

   var preAborted = AbortSignal.abort('static-reason');
   r.push(preAborted.aborted === true ? 1 : 'static-abort-should-be-aborted');

   var c3 = new AbortController();
   c3.abort('pre-abort');
   var preAbortCaught = null;
   fetch('https://example.test/pre-aborted', { signal: c3.signal })
     .then(function() { preAbortCaught = 'should-not-resolve'; })
     .catch(function(err) { preAbortCaught = err; });
   r.push(preAbortCaught === 'pre-abort' ? 1 : 'pre-aborted-fetch-should-reject-synchronously:' + preAbortCaught);

   var c4 = new AbortController();
   var midFlightCaught = null;
   fetch('https://example.test/mid-flight', { signal: c4.signal })
     .then(function() { midFlightCaught = 'should-not-resolve'; })
     .catch(function(err) { midFlightCaught = err; });
   r.push(midFlightCaught === null ? 1 : 'fetch-should-still-be-pending-before-abort:' + midFlightCaught);
   c4.abort('mid-flight-reason');
   r.push(midFlightCaught === 'mid-flight-reason' ? 1 : 'mid-flight-abort-should-reject-synchronously:' + midFlightCaught);

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-abort-controller-and-signal-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real AbortController/AbortSignal round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected AbortController/AbortSignal to exist and fetch() to honor "
                          "a signal on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs AbortController smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
