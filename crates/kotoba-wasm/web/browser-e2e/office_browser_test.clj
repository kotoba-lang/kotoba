(ns office-browser-test
  "Runs the kotoba office/CACAO flow in a REAL browser (Chromium) via playwright-clj.
   Proves the browser (web-target) WASM works end to end: sovereign identity,
   client-side encryption, CACAO mint, and depth-2 team delegation — in a genuine
   secure-context page (so crypto.subtle / Service Worker are available).

   Serve the web dir on localhost first; pass its URL via KOTOBA_WEB_URL.
     (python3 -m http.server in ../  →) KOTOBA_WEB_URL=http://localhost:8123 clojure -M:run"
  (:require [playwright-clj.core :as pw]))

(def office-flow-js
  "() => {
     const N = window.KotobaNode;
     const acct = new N(); acct.useIdentity('07'.repeat(32));
     const account = acct.accountDid();
     const graph = acct.privateGraphId();
     const env = acct.encrypt('\\u4f1a\\u54e1\\u756a\\u53f7 12345');
     const back = acct.decrypt(env);
     const cacao = acct.mintCacao('did:key:zSrv', graph, ['datom:transact','tx:create'], 'n1','2026-01-01T00:00:00Z','2099-01-01T00:00:00Z');
     const org = new N(); org.useIdentity('b1'.repeat(32));
     const mem = new N(); mem.useIdentity('c2'.repeat(32));
     const orgGraph = org.privateGraphId();
     const root  = org.mintCacao(mem.accountDid(), orgGraph, ['datom:transact','tx:create'],'r1','2026-01-01T00:00:00Z','2099-01-01T00:00:00Z');
     const chain = mem.mintDelegated(root, 'did:key:zSrv', orgGraph, ['datom:transact','tx:create'],'l1','2026-01-01T00:00:00Z','2099-01-01T00:00:00Z');
     return {
       account, graphLen: graph.length,
       encOk: env.startsWith('signal:v1:'), decryptOk: back === '\\u4f1a\\u54e1\\u756a\\u53f7 12345',
       leak: env.includes('12345'),
       cacaoLen: cacao.length, chainLen: chain.length,
       secure: window.isSecureContext, subtle: !!(crypto && crypto.subtle), sw: ('serviceWorker' in navigator)
     };
   }")

(defn -main [& _]
  (let [url   (or (System/getenv "KOTOBA_WEB_URL") "http://localhost:8123")
        fails (atom 0)
        check (fn [n c] (if c (println "  ok  " n)
                            (do (swap! fails inc) (println "  FAIL" n))))]
    (pw/with-page [page {:headless true}]
      (let [logs (pw/capture-console page)]
        (pw/goto page (str url "/office_harness.html") {:wait-until "load"})
        (pw/wait-for-fn page "() => window.__kotobaReady === true || window.__kotobaError"
                        {:timeout 20000})
        (check "wasm initialised (no init error)"
               (nil? (pw/eval-js page "() => window.__kotobaError || null")))
        (let [r (pw/eval-js page office-flow-js)]
          (check "real-browser secure context" (true? (get r "secure")))
          (check "crypto.subtle available (secure ctx)" (true? (get r "subtle")))
          (check "serviceWorker API present" (true? (get r "sw")))
          (check "accountDid is did:key:z6Mk"
                 (clojure.string/starts-with? (str (get r "account")) "did:key:z6Mk"))
          (check "privateGraphId derived" (pos? (long (get r "graphLen"))))
          (check "body encrypted to signal:v1:" (true? (get r "encOk")))
          (check "plaintext not in ciphertext" (false? (get r "leak")))
          (check "decrypt round-trips" (true? (get r "decryptOk")))
          (check "mintCacao produced a CACAO" (pos? (long (get r "cacaoLen"))))
          (check "mintDelegated produced a depth-2 chain"
                 (> (long (get r "chainLen")) (long (get r "cacaoLen")))))
        ;; kotoba passkey identity unlock (doc b): enroll wraps a fresh Ed25519 seed
        ;; under the passkey's WebAuthn-PRF secret; unlock on a FRESH node recovers the
        ;; SAME account. Driven on a CDP virtual authenticator (ctap2 + PRF).
        (pw/add-virtual-authenticator page)
        (let [r (pw/eval-js page
                  "async () => {
                     const k = window.kotoba;
                     const n1 = new window.KotobaNode();
                     const enrolled = await k.enrollPasskey(n1, 'localhost', 'alice');
                     // a brand-new node (fresh 'device/session') recovers via the passkey
                     const n2 = new window.KotobaNode();
                     const recovered = await k.unlockPasskey(n2, 'localhost');
                     // an unrelated random identity must differ
                     const n3 = new window.KotobaNode(); n3.generateIdentity();
                     return { enrolled, recovered, random: n3.accountDid(),
                              flag: k.passkeyEnrolled() };
                   }")]
          (check "passkey PRF unlock recovers the SAME account"
                 (and (clojure.string/starts-with? (str (get r "enrolled")) "did:key:z6Mk")
                      (= (get r "enrolled") (get r "recovered"))))
          (check "recovered identity differs from a random one"
                 (not= (get r "enrolled") (get r "random")))
          (check "passkeyEnrolled flag set" (true? (get r "flag"))))
        (pw/screenshot page "office_harness.png")
        (check "console shows harness ready"
               (some #(re-find #"kotoba wasm ready" (:text %)) @logs))))
    (println (if (zero? @fails) "\nALL OK" (format "\n%d FAILURE(S)" @fails)))
    (System/exit (if (zero? @fails) 0 1))))
