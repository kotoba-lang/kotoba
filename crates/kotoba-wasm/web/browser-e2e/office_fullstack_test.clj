(ns office-fullstack-test
  "FULL STACK: real browser → the REAL kotoba office CLJS fns (:advanced ESM) →
   real `kotoba serve` over HTTP. Exercises encrypt-doc → store-doc! → sync-doc!
   → pull-doc end to end (sovereign encryption + CACAO sync + read-back + decrypt +
   :node/lid reconstruction), all in genuine Chromium. This is the definitive check
   that the office cljs layer survives advanced compilation in a real browser.

   Needs TWO servers:
     KOTOBA_WEB_URL — static harness (python3 -m http.server, localhost = secure ctx)
     KOTOBA_API_URL — `kotoba serve` XRPC endpoint
   The browser runs cross-origin (harness:PORT → api:PORT), so we launch with
   --disable-web-security (a TEST-ONLY flag; production serves app + API same-origin)."
  (:require [playwright-clj.core :as pw]
            [clojure.string :as str]))

(defn -main [& _]
  (let [web   (or (System/getenv "KOTOBA_WEB_URL") "http://localhost:8128")
        api   (or (System/getenv "KOTOBA_API_URL") "http://localhost:8099")
        fails (atom 0)
        check (fn [n c] (if c (println "  ok  " n)
                            (do (swap! fails inc) (println "  FAIL" n))))]
    (pw/with-page [page {:headless true
                         :args ["--disable-web-security"
                                "--disable-features=IsolateOrigins,site-per-process"]}]
      (let [logs (pw/capture-console page)]
        (pw/goto page (str web "/office_harness.html") {:wait-until "load"})
        (pw/wait-for-fn page "() => window.__kotobaReady === true || window.__kotobaError"
                        {:timeout 20000})
        (check "wasm + cljs ESM loaded"
               (nil? (pw/eval-js page "() => window.__kotobaError || null")))
        (let [r (pw/eval-js page
                  "async (api) => {
                     const n = new window.KotobaNode();
                     n.useIdentity('07'.repeat(32));
                     try { return await window.kotoba.officeRoundtrip(n, api); }
                     catch (e) { return { error: String(e), stack: (e && e.stack) || '' }; }
                   }"
                  api)]
          (when (get r "error")
            (println "    roundtrip error:" (get r "error"))
            (println "    stack:" (get r "stack")))
          (check "office round-trip synced to server" (true? (get r "synced")))
          (check "title round-trips (structure)" (= "Q3 戦略メモ" (get r "title")))
          (check "encrypted body round-trips + decrypts"
                 (= "原材料費が上昇し…" (get r "text")))
          (check "full doc reconstructs (encrypt→sync→pull→decrypt→:node/lid)"
                 (true? (get r "match"))))
        (check "no browser console errors"
               (not-any? #(= "error" (:type %)) @logs))))
    (println (if (zero? @fails) "\nALL OK" (format "\n%d FAILURE(S)" @fails)))
    (System/exit (if (zero? @fails) 0 1))))
