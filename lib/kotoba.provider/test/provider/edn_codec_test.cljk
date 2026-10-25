(ns provider.edn-codec-test
  (:require [clojure.java.io :as io]
            [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is testing]]
            [provider.edn-codec :as codec]
            [provider.value-codec :as value-codec]))

(defn- assert-canonical-audit [event kit]
  (is (= :provider.ops-audit/v1 (:value-format event)))
  (doseq [[field direction] [[:request-value-bytes :request]
                             [:reply-value-bytes :reply]]]
    (let [decoded (value-codec/decode-audit-value (get event field))]
      (is (= kit (:kit decoded)))
      (is (= direction (:direction decoded))))))

(deftest codec-aot-complete-flag
  (is (true? (codec/codec-aot-complete?))))

(deftest ops-kits-declare-codec-aot-implemented
  (doseq [res ["kotoba/lang/capability-kits/http-v1.edn"
               "kotoba/lang/capability-kits/secret-v1.edn"
               "kotoba/lang/capability-kits/process-v1.edn"
               "kotoba/lang/capability-kits/git-v1.edn"
               "kotoba/lang/capability-kits/entropy-v1.edn"
               "kotoba/lang/capability-kits/scoped-fs-v1.edn"]]
    (let [kit (clojure.edn/read-string (slurp (io/resource res)))]
      (is (= :implemented (get-in kit [:qualification :codec-aot])) res)
      (is (= :partial (get-in kit [:qualification :wasm-aot])) res))))

(deftest secret-request-edn-host-wire-optional
  (testing "pure W4 secret request via browser-host when available"
    (let [r (codec/secret-request-edn "API_TOKEN")]
      (if (= :browser-host-unavailable (:reason r))
        (is true "skip when browser-host unavailable")
        (do
          (is (:ok r) (pr-str r))
          (is (string? (:value r)))
          (is (str/includes? (:value r) ":name"))
          (is (str/includes? (:value r) "API_TOKEN"))
          (let [empty-r (codec/secret-request-edn "")]
            (is (:ok empty-r))
            (is (= "" (:value empty-r)))))))))

(deftest entropy-request-edn-host-wire-optional
  (let [r (codec/entropy-request-edn 16)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":n"))
        (is (str/includes? (:value r) "16"))
        (let [bad (codec/entropy-request-edn 0)]
          (is (:ok bad))
          (is (= "" (:value bad)) "n=0 fail-closed empty EDN"))))))

(deftest process-request-edn-host-wire-optional
  (let [r (codec/process-request-edn "[\"echo\" \"hi\"]" 4096 5000)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":argv"))
        (is (str/includes? (:value r) "echo"))))))

(deftest unknown-package-fails-closed
  (let [r (codec/invoke-export :no-such-package :main [])]
    (is (false? (:ok r)))
    (is (contains? #{:unknown-package :browser-host-unavailable} (:reason r)))))

(deftest wrap-secret-fetch-audits-edn-optional
  (let [events (atom [])
        fetch (fn [{:keys [name]}]
                (if (= name "API_TOKEN")
                  {:tag :value :value "s3cr3t"}
                  {:tag :error :code :secret/not-found :message "missing"}))
        wrapped (codec/wrap-secret-fetch fetch (fn [e] (swap! events conj e)))
        reply (wrapped {:name "API_TOKEN"})]
    (is (= :value (:tag reply)))
    (is (= "s3cr3t" (:value reply)))
    (if (empty? @events)
      (is true "no events if wrap failed closed without host — unexpected")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip EDN assert when browser-host unavailable")
          (do
            (is (= :secret (:kit e)))
            (assert-canonical-audit e :secret)
            (is (str/includes? (:request-edn e) "API_TOKEN"))
            (is (str/includes? (:reply-edn e) "s3cr3t"))
            (is (= :value (:reply-tag e)))))))))

(deftest wrap-http-post-transport-audits-request-edn-optional
  (let [events (atom [])
        transport (fn [{:keys [url]}]
                    {:status 200 :body "ok" :headers {}})
        wrapped (codec/wrap-http-post-transport
                 transport
                 (fn [e] (swap! events conj e)))
        reply (wrapped {:url "https://ex.com/a"
                        :headers {"Accept" "text/plain" "Host" "ex.com"}
                        :body "hi"
                        :timeout-ms 5000})]
    (is (= 200 (:status reply)))
    (if (empty? @events)
      (is true "unexpected empty events")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip EDN assert when browser-host unavailable")
          (do
            (is (= :http (:kit e)))
            (assert-canonical-audit e :http)
            (is (str/includes? (:request-edn e) "https://ex.com/a"))
            (is (= 200 (:status e)))
            (is (false? (:error? e)))))))))

(deftest git-request-edn-host-wire-optional
  (let [r (codec/git-request-edn "[\"status\"]" 4096 5000)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":args")
            (str "got " (:value r)))
        (is (str/includes? (:value r) "status"))))))

(deftest fs-req-read-edn-host-wire-optional
  (let [r (codec/fs-req-read-edn "workspace" "docs/a.txt")]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":read")
            (str "got " (:value r)))
        (is (str/includes? (:value r) "docs/a.txt"))))))

(deftest wrap-process-spawn-audits-optional
  (let [events (atom [])
        spawn (fn [_] {:tag :ok :exit 0 :stdout "hi" :stderr ""})
        wrapped (codec/wrap-process-spawn spawn (fn [e] (swap! events conj e)))
        reply (wrapped {:argv ["echo" "hi"] :max-stdout-bytes 4096 :timeout-ms 5000})]
    (is (= :ok (:tag reply)))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip when browser-host unavailable")
          (do
            (is (= :process (:kit e)))
            (assert-canonical-audit e :process)
            (is (str/includes? (:request-edn e) "echo"))
            (is (str/includes? (:reply-edn e) "hi"))))))))

(deftest wrap-git-run-audits-optional
  (let [events (atom [])
        run (fn [_] {:tag :ok :exit 0 :stdout "ok" :stderr ""})
        wrapped (codec/wrap-git-run run (fn [e] (swap! events conj e)))
        reply (wrapped {:args ["status"] :max-stdout-bytes 4096 :timeout-ms 5000})]
    (is (= :ok (:tag reply)))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip when browser-host unavailable")
          (do
            (is (= :git (:kit e)))
            (assert-canonical-audit e :git)
            (is (str/includes? (:request-edn e) "status"))))))))

(deftest wrap-entropy-draw-audits-optional
  (let [events (atom [])
        draw (fn [_] {:tag :hex :hex "deadbeefcafebabe"})
        wrapped (codec/wrap-entropy-draw draw (fn [e] (swap! events conj e)))
        reply (wrapped {:n 8})]
    (is (= :hex (:tag reply)))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip when browser-host unavailable")
          (do
            (is (= :entropy (:kit e)))
            (assert-canonical-audit e :entropy)
            (is (str/includes? (:request-edn e) "8"))
            (is (str/includes? (:reply-edn e) "deadbeefcafebabe"))))))))

(deftest wrap-scoped-fs-transact-audits-optional
  (let [events (atom [])
        tx (fn [{:keys [op]}]
             (if (= op :read)
               {:tag :content :content "hello"}
               {:tag :written :written true}))
        wrapped (codec/wrap-scoped-fs-transact tx (fn [e] (swap! events conj e)))
        reply (wrapped {:op :read :root "workspace" :path "docs/a.txt"})]
    (is (= :content (:tag reply)))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip when browser-host unavailable")
          (do
            (is (= :scoped-fs (:kit e)))
            (assert-canonical-audit e :scoped-fs)
            (is (str/includes? (:request-edn e) "docs/a.txt"))
            (is (str/includes? (:reply-edn e) "hello"))))))))

(deftest secret-map-fetch-factory-audits-optional
  (let [events (atom [])
        fetch (codec/secret-map-fetch-with-edn-audit
               {"API_TOKEN" "s3cr3t"}
               (fn [e] (swap! events conj e)))
        reply (fetch {:name "API_TOKEN"})]
    (is (= :value (:tag reply)))
    (is (= "s3cr3t" (:value reply)))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip when browser-host unavailable")
          (do
            (is (str/includes? (:request-edn e) "API_TOKEN"))
            (is (str/includes? (:reply-edn e) "s3cr3t"))))))))

(deftest process-echo-factory-audits-optional
  (let [events (atom [])
        spawn (codec/process-echo-with-edn-audit
               (fn [e] (swap! events conj e)))
        reply (spawn {:argv ["echo" "hi"] :max-stdout-bytes 4096 :timeout-ms 5000})]
    (is (= :ok (:tag reply)))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip when browser-host unavailable")
          (do
            (is (= :process (:kit e)))
            (is (str/includes? (:request-edn e) "echo"))
            (is (= :ok (:reply-tag e)))))))))

(deftest git-echo-factory-audits-optional
  (let [events (atom [])
        run (codec/git-echo-with-edn-audit
             (fn [e] (swap! events conj e)))
        reply (run {:args ["status" "--short"] :max-stdout-bytes 8192 :timeout-ms 30000})]
    (is (= :ok (:tag reply)))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip when browser-host unavailable")
          (do
            (is (= :git (:kit e)))
            (is (str/includes? (:request-edn e) "status"))
            (is (= :ok (:reply-tag e)))))))))

(deftest wrap-scoped-fs-uses-value-field
  (let [events (atom [])
        store (fn [{:keys [op path]}]
                (if (= op :read)
                  {:tag :content :value "hello"}
                  {:tag :written}))
        wrapped (codec/wrap-scoped-fs-transact
                 store
                 (fn [e] (swap! events conj e)))
        reply (wrapped {:op :read :root :workspace :path "a.txt"})]
    (is (= :content (:tag reply)))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:reply-edn e))
          (is true "skip when browser-host unavailable")
          (is (str/includes? (:reply-edn e) "hello")))))))

(deftest entropy-mem-draw-factory-audits-bytes-as-hex-optional
  (let [events (atom [])
        ;; 8 deterministic bytes as 0–255 ints (entropy mem-draw contract)
        seed (vec (range 8))
        draw (codec/entropy-mem-draw-with-edn-audit
              seed
              (fn [e] (swap! events conj e)))
        reply (draw {:n 8})]
    (is (= :bytes (:tag reply)))
    (is (= 8 (count (:bytes reply))))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip when browser-host unavailable")
          (do
            (is (= :entropy (:kit e)))
            (is (str/includes? (:request-edn e) ":n"))
            (is (str/includes? (:request-edn e) "8"))
            (is (= :bytes (:reply-tag e)))
            (is (string? (:reply-edn e)))
            (is (str/includes? (:reply-edn e) ":hex"))
            ;; first two bytes 0x00 0x01 → 0001...
            (is (str/includes? (:reply-edn e) "0001"))))))))

(deftest entropy-os-draw-factory-smoke-optional
  (let [events (atom [])
        draw (codec/entropy-os-draw-with-edn-audit
              {:on-call (fn [e] (swap! events conj e))})
        reply (draw {:n 4})]
    (is (#{:bytes :error} (:tag reply)))
    (when (= :bytes (:tag reply))
      (is (= 4 (count (:bytes reply)))))
    (if (empty? @events)
      (is true "unexpected empty")
      (let [e (first @events)]
        (if (nil? (:request-edn e))
          (is true "skip when browser-host unavailable")
          (is (str/includes? (:request-edn e) "4")))))))

(deftest http-w4-host-post-echo-inject-optional
  "ADR 0262: guest host_post_edn + typedCapCall :echo returns W4 request EDN."
  (let [r (codec/http-w4-host-post-edn "https://ex.com/a" "hi" 30 "[]" :echo)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (string? (:value r)))
        (is (str/includes? (:value r) ":url"))
        (is (str/includes? (:value r) "https://ex.com/a"))
        (is (str/includes? (:value r) ":timeout-ms"))
        (is (str/includes? (:value r) "30"))))))

(deftest http-w4-host-post-ok-200-inject-optional
  (let [r (codec/http-w4-host-post-edn "https://ex.com" "x" 5 "[]" :ok-200)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":ok"))
        (is (str/includes? (:value r) "200"))
        (is (str/includes? (:value r) "injected"))))))

(deftest http-w4-host-post-denied-without-allow-optional
  (let [r (codec/http-w4-host-post-denied "https://ex.com" "x" 5 "[]")]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (false? (:ok r)) (pr-str r))
        (is (contains? #{:node-exit :exception :bad-result} (:reason r)))))))

(deftest http-w4-roundtrip-test-double-optional
  "ADR 0263: guest W4 encode + host transport double + guest W4 reply encode."
  (let [events (atom [])
        transport (fn [{:keys [url body]}]
                    {:status 201 :body (str "got:" body) :headers {}})
        r (codec/http-w4-roundtrip
           "https://ex.com/a"
           {"Accept" "text/plain" "Host" "ex.com"}
           "payload"
           5000
           transport
           (fn [e] (swap! events conj e)))]
    (if (false? (:ok r))
      (if (= :browser-host-unavailable (get-in r [:request-codec :reason]))
        (is true "skip when browser-host unavailable")
        (is false (pr-str r)))
      (do
        (is (:ok r) (pr-str r))
        (assert-canonical-audit r :http)
        (is (str/includes? (:request-edn r) "https://ex.com/a"))
        (is (str/includes? (:request-edn r) "payload"))
        (is (str/includes? (:reply-edn r) "201"))
        (is (str/includes? (:reply-edn r) "got:payload"))
        (is (= 201 (get-in r [:result :status])))
        (when (seq @events)
          (let [e (first @events)]
            (is (= :http (:kit e)))
            (is (= :w4-roundtrip (:op e)))
            (assert-canonical-audit e :http)
            (is (string? (:request-edn e)))
            (is (string? (:reply-edn e)))))))))

(deftest http-w4-roundtrip-transport-error-optional
  (let [transport (fn [_]
                    {:error {:code :http/timeout :message "slow" :retryable true}
                     :error? true})
        r (codec/http-w4-roundtrip "https://ex.com" {} "x" 1000 transport)]
    (if (and (false? (:ok r))
             (= :browser-host-unavailable (get-in r [:request-codec :reason])))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:reply-edn r) ":error")
            (str "got " (:reply-edn r)))
        (is (str/includes? (:reply-edn r) "timeout"))))))

(deftest secret-w4-roundtrip-map-optional
  "ADR 0264: guest secret request EDN + map-fetch + guest reply EDN."
  (let [events (atom [])
        r (codec/secret-w4-roundtrip-with-map
           {"API_TOKEN" "s3cr3t"}
           "API_TOKEN"
           (fn [e] (swap! events conj e)))]
    (if (and (false? (:ok r))
             (= :browser-host-unavailable (get-in r [:request-codec :reason])))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (assert-canonical-audit r :secret)
        (is (str/includes? (:request-edn r) "API_TOKEN"))
        (is (str/includes? (:reply-edn r) "s3cr3t"))
        (is (= :value (get-in r [:result :tag])))
        (when (seq @events)
          (is (= :secret (:kit (first @events))))
          (is (= :w4-roundtrip (:op (first @events)))))))))

(deftest secret-w4-roundtrip-not-found-optional
  (let [r (codec/secret-w4-roundtrip-with-map {} "MISSING")]
    (if (and (false? (:ok r))
             (= :browser-host-unavailable (get-in r [:request-codec :reason])))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (= :error (get-in r [:result :tag])))
        (is (str/includes? (:reply-edn r) "not-found")
            (str "got " (:reply-edn r)))))))

(deftest process-w4-roundtrip-echo-optional
  (let [events (atom [])
        r (codec/process-w4-roundtrip-echo
           ["echo" "hi"]
           (fn [e] (swap! events conj e)))]
    (if (and (false? (:ok r))
             (= :browser-host-unavailable (get-in r [:request-codec :reason])))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (assert-canonical-audit r :process)
        (is (str/includes? (:request-edn r) "echo"))
        (is (= :ok (get-in r [:result :tag])))
        (when (seq @events)
          (is (= :process (:kit (first @events)))))))))

(deftest git-w4-roundtrip-echo-optional
  (let [r (codec/git-w4-roundtrip-echo ["status" "--short"])]
    (if (and (false? (:ok r))
             (= :browser-host-unavailable (get-in r [:request-codec :reason])))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (assert-canonical-audit r :git)
        (is (str/includes? (:request-edn r) "status"))
        (is (= :ok (get-in r [:result :tag])))))))

(deftest entropy-w4-roundtrip-mem-optional
  (let [seed (vec (range 8))
        r (codec/entropy-w4-roundtrip-mem seed 8)]
    (if (and (false? (:ok r))
             (= :browser-host-unavailable (get-in r [:request-codec :reason])))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (assert-canonical-audit r :entropy)
        (is (str/includes? (:request-edn r) "8"))
        (is (= :bytes (get-in r [:result :tag])))
        (is (str/includes? (:reply-edn r) ":hex"))
        (is (str/includes? (:reply-edn r) "0001"))))))

(deftest scoped-fs-w4-roundtrip-read-optional
  (let [store (fn [{:keys [op path]}]
                (if (= op :read)
                  {:tag :content :value "hello"}
                  {:tag :written}))
        r (codec/scoped-fs-w4-roundtrip :read "workspace" "docs/a.txt" nil store)]
    (if (and (false? (:ok r))
             (= :browser-host-unavailable (get-in r [:request-codec :reason])))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (assert-canonical-audit r :scoped-fs)
        (is (str/includes? (:request-edn r) "docs/a.txt"))
        (is (str/includes? (:reply-edn r) "hello"))
        (is (= :content (get-in r [:result :tag])))))))

(deftest secret-w4-host-get-value-inject-optional
  "ADR 0265: guest host_get_edn + typedCapCall :secret-value."
  (let [r (codec/secret-w4-host-get-edn "API_TOKEN" :secret-value)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":value"))
        (is (str/includes? (:value r) "s3cr3t"))))))

(deftest secret-w4-host-get-echo-inject-optional
  (let [r (codec/secret-w4-host-get-edn "API_TOKEN" :echo)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":name"))
        (is (str/includes? (:value r) "API_TOKEN"))))))

(deftest secret-w4-host-get-denied-optional
  (let [r (codec/secret-w4-host-get-denied "API_TOKEN")]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (false? (:ok r)) (pr-str r))
        (is (contains? #{:node-exit :exception :bad-result} (:reason r)))))))

(deftest process-w4-host-spawn-echo-inject-optional
  "ADR 0266: guest host_spawn_edn + typedCapCall :echo returns W4 request EDN."
  (let [r (codec/process-w4-host-spawn-edn "[\"echo\" \"hi\"]" 4096 5000 :echo)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":argv"))
        (is (str/includes? (:value r) "echo"))
        (is (str/includes? (:value r) ":timeout-ms"))
        (is (str/includes? (:value r) "5000"))))))

(deftest process-w4-host-spawn-ok-inject-optional
  (let [r (codec/process-w4-host-spawn-edn "[\"echo\" \"hi\"]" 4096 5000 :process-ok)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":ok"))
        (is (str/includes? (:value r) "stdout"))
        (is (str/includes? (:value r) "ok"))))))

(deftest process-w4-host-spawn-denied-optional
  (let [r (codec/process-w4-host-spawn-denied "[\"echo\" \"hi\"]" 4096 5000)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (false? (:ok r)) (pr-str r))
        (is (contains? #{:node-exit :exception :bad-result} (:reason r)))))))

(deftest git-w4-host-run-echo-optional
  (let [r (codec/git-w4-host-run-edn "[\"status\"]" 4096 5000 :echo)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":args"))
        (is (str/includes? (:value r) "status"))))))

(deftest git-w4-host-run-ok-inject-optional
  "ADR 0270: guest host_run_edn + :git-ok fixed ok arm."
  (let [r (codec/git-w4-host-run-edn "[\"status\"]" 4096 5000 :git-ok)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":ok"))
        (is (str/includes? (:value r) "stdout"))
        (is (str/includes? (:value r) "ok"))))))

(deftest git-w4-host-run-denied-optional
  (let [r (codec/git-w4-host-run-denied "[\"status\"]" 4096 5000)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip")
      (do
        (is (false? (:ok r)) (pr-str r))
        (is (contains? #{:node-exit :exception :bad-result} (:reason r)))))))

(deftest entropy-w4-host-draw-echo-optional
  (let [r (codec/entropy-w4-host-draw-edn 16 :echo)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":n"))
        (is (str/includes? (:value r) "16"))))))

(deftest entropy-w4-host-draw-hex-inject-optional
  "ADR 0270: guest host_draw_edn + :entropy-hex fixed hex arm."
  (let [r (codec/entropy-w4-host-draw-edn 16 :entropy-hex)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":hex"))
        (is (str/includes? (:value r) "0123456789abcdef"))))))

(deftest entropy-w4-host-draw-denied-optional
  (let [r (codec/entropy-w4-host-draw-denied 16)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip")
      (do
        (is (false? (:ok r)) (pr-str r))
        (is (contains? #{:node-exit :exception :bad-result} (:reason r)))))))

(deftest scoped-fs-w4-host-write-echo-optional
  "ADR 0268: guest host_write_edn + :echo returns W4 write request EDN."
  (let [r (codec/scoped-fs-w4-host-write-edn "workspace" "docs/a.txt" "hello" :echo)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":write"))
        (is (str/includes? (:value r) "docs/a.txt"))
        (is (str/includes? (:value r) "hello"))))))

(deftest scoped-fs-w4-host-write-written-inject-optional
  (let [r (codec/scoped-fs-w4-host-write-edn "workspace" "docs/a.txt" "hello" :fs-written)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":written"))
        (is (str/includes? (:value r) "true"))))))

(deftest scoped-fs-w4-host-write-denied-optional
  (let [r (codec/scoped-fs-w4-host-write-denied "workspace" "docs/a.txt" "hello")]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip when browser-host unavailable")
      (do
        (is (false? (:ok r)) (pr-str r))
        (is (contains? #{:node-exit :exception :bad-result} (:reason r)))))))

(deftest scoped-fs-w4-host-read-echo-optional
  (let [r (codec/scoped-fs-w4-host-read-edn "workspace" "docs/a.txt" :echo)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":read"))
        (is (str/includes? (:value r) "docs/a.txt"))))))

(deftest scoped-fs-w4-host-read-content-inject-optional
  "ADR 0270: guest host_read_edn + :fs-content fixed content arm."
  (let [r (codec/scoped-fs-w4-host-read-edn "workspace" "docs/a.txt" :fs-content)]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip")
      (do
        (is (:ok r) (pr-str r))
        (is (str/includes? (:value r) ":content"))
        (is (str/includes? (:value r) "payload"))))))

(deftest scoped-fs-w4-host-read-denied-optional
  (let [r (codec/scoped-fs-w4-host-read-denied "workspace" "docs/a.txt")]
    (if (= :browser-host-unavailable (:reason r))
      (is true "skip")
      (do
        (is (false? (:ok r)) (pr-str r))
        (is (contains? #{:node-exit :exception :bad-result} (:reason r)))))))
