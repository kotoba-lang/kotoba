(ns office-editor-test
  "Production-shaped E2E: the Hiccup CLJS editor served SAME-ORIGIN by `kotoba serve`
   (KOTOBA_STATIC_DIR) — no CORS, no --disable-web-security. Drives the real UI via
   playwright-clj:
     1. first load → passkey ENROLL → sovereign identity
     2. edit title/body → 保存+同期 → encrypted, synced same-origin
     3. RELOAD → passkey UNLOCK → pull → content restored
     4. OFFLINE edit → queued (Service-Worker-style sync queue) → RECONNECT → auto-flush
   One server (KOTOBA_API_URL) serves both the app and /xrpc."
  (:require [playwright-clj.core :as pw]
            [clojure.string :as str]))

(defn -main [& _]
  (let [base  (or (System/getenv "KOTOBA_API_URL") "http://localhost:8099")
        url   (str base "/editor.html")
        fails (atom 0)
        check (fn [n c] (if c (println "  ok  " n)
                            (do (swap! fails inc) (println "  FAIL" n))))]
    (pw/with-page [page {:headless true}]            ; NO --disable-web-security
      (pw/add-virtual-authenticator page)            ; passkey (ctap2 + PRF)
      (pw/capture-console page)
      ;; 1. first load → passkey enroll
      (pw/goto page url {:wait-until "load"})
      (pw/wait-for-fn page "() => window.__editorReady === true || window.__editorError"
                      {:timeout 25000})
      (check "editor booted same-origin (no error)"
             (nil? (pw/eval-js page "() => window.__editorError || null")))
      (check "passkey enrolled a sovereign account"
             (str/starts-with? (str (pw/eval-js page "() => document.getElementById('account').textContent"))
                               "did:key:z6Mk"))
      ;; 2. edit + save + sync (same-origin)
      (pw/fill page "#title" "四半期メモ")
      (pw/fill page "#body" "本文は端末で暗号化される")
      (pw/click page "#save")
      (pw/wait-for-fn page "() => document.getElementById('sync').textContent.includes('synced')"
                      {:timeout 30000 :polling 250})
      (check "save synced same-origin"
             (str/includes? (str (pw/eval-js page "() => document.getElementById('sync').textContent")) "synced"))
      ;; 3. reload → passkey unlock → pull restores content
      (pw/goto page url {:wait-until "load"})
      (pw/wait-for-fn page "() => window.__editorReady === true" {:timeout 25000})
      (pw/wait-for-fn page "() => document.getElementById('title').value === '四半期メモ'" {:timeout 30000 :polling 250})
      (check "reload → passkey unlock → pull restored title"
             (= "四半期メモ" (pw/eval-js page "() => document.getElementById('title').value")))
      (check "pulled body decrypted client-side"
             (= "本文は端末で暗号化される" (pw/eval-js page "() => document.getElementById('body').value")))
      ;; 4. offline edit → queued → reconnect → auto-flush
      (pw/set-offline page true)
      (pw/fill page "#body" "オフライン編集")
      (pw/click page "#save")
      (pw/wait-for-fn page "() => document.getElementById('sync').textContent.includes('pending 1')"
                      {:timeout 30000 :polling 250})
      (check "offline edit is queued (pending 1)"
             (str/includes? (str (pw/eval-js page "() => document.getElementById('sync').textContent")) "pending 1"))
      (pw/set-offline page false)                    ; fires 'online' → editor auto-flushes
      (pw/wait-for-fn page "() => document.getElementById('sync').textContent.includes('pending 0')"
                      {:timeout 30000 :polling 250})
      (check "reconnect auto-flushed the queue (pending 0)"
             (str/includes? (str (pw/eval-js page "() => document.getElementById('sync').textContent")) "pending 0"))
      ;; 5. final reload proves the offline edit reached the server
      (pw/goto page url {:wait-until "load"})
      (pw/wait-for-fn page "() => window.__editorReady === true" {:timeout 25000})
      (pw/wait-for-fn page "() => document.getElementById('body').value === 'オフライン編集'" {:timeout 30000 :polling 250})
      (check "offline edit persisted to server after reconnect"
             (= "オフライン編集" (pw/eval-js page "() => document.getElementById('body').value")))
      (pw/screenshot page "office_editor.png"))
    (println (if (zero? @fails) "\nALL OK" (format "\n%d FAILURE(S)" @fails)))
    (System/exit (if (zero? @fails) 0 1))))
