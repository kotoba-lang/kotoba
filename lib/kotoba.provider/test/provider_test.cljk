(ns provider-test
  (:require [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is]]
            [kotoba.kir.value :as value]
            [provider.conformance :as conformance]
            [provider.clock]
            [provider.clock-transport]
            [provider.http]
            [provider.http-ingress]
            [provider.http-transport]
            [provider.llm]
            [provider.llm-transport]
            [provider.log]
            [provider.object :as object]
            [provider.object-transport :as object-transport]
            [provider.state :as state]
            [provider.storage :as storage]
            [provider.storage-transport :as storage-transport]
            [provider.ui]
            [provider.scoped-fs :as scoped-fs]
            [provider.scoped-fs-transport :as scoped-fs-transport]
            [provider.process :as process]
            [provider.process-transport :as process-transport]
            [provider.secret :as secret]
            [provider.secret-transport :as secret-transport]
            [provider.git :as git]
            [provider.git-transport :as git-transport]
            [provider.entropy :as entropy]
            [provider.entropy-transport :as entropy-transport]
            [provider.dataspace]
            [provider.dataspace-match]))

;; Load gate: the split must not break namespace resolution. Each extracted
;; namespace must load standalone from this repo's own dependency closure.
(deftest every-extracted-namespace-loads
  (is (some? (find-ns 'provider.conformance)) "provider.conformance must load")
  (is (some? (find-ns 'provider.clock)) "provider.clock must load")
  (is (some? (find-ns 'provider.clock-transport)) "provider.clock-transport must load")
  (is (some? (find-ns 'provider.http)) "provider.http must load")
  (is (some? (find-ns 'provider.http-ingress)) "provider.http-ingress must load")
  (is (some? (find-ns 'provider.http-transport)) "provider.http-transport must load")
  (is (some? (find-ns 'provider.llm)) "provider.llm must load")
  (is (some? (find-ns 'provider.llm-transport)) "provider.llm-transport must load")
  (is (some? (find-ns 'provider.log)) "provider.log must load")
  (is (some? (find-ns 'provider.object)) "provider.object must load")
  (is (some? (find-ns 'provider.object-transport)) "provider.object-transport must load")
  (is (some? (find-ns 'provider.state)) "provider.state must load")
  (is (some? (find-ns 'provider.storage)) "provider.storage must load")
  (is (some? (find-ns 'provider.storage-transport)) "provider.storage-transport must load")
  (is (some? (find-ns 'provider.ui)) "provider.ui must load")
  (is (some? (find-ns 'provider.scoped-fs)) "provider.scoped-fs must load")
  (is (some? (find-ns 'provider.scoped-fs-transport)) "provider.scoped-fs-transport must load")
  (is (some? (find-ns 'provider.process)) "provider.process must load")
  (is (some? (find-ns 'provider.process-transport)) "provider.process-transport must load")
  (is (some? (find-ns 'provider.secret)) "provider.secret must load")
  (is (some? (find-ns 'provider.secret-transport)) "provider.secret-transport must load")
  (is (some? (find-ns 'provider.git)) "provider.git must load")
  (is (some? (find-ns 'provider.git-transport)) "provider.git-transport must load")
  (is (some? (find-ns 'provider.entropy)) "provider.entropy must load")
  (is (some? (find-ns 'provider.entropy-transport)) "provider.entropy-transport must load")
  (is (some? (find-ns 'provider.dataspace)) "provider.dataspace must load")
  (is (some? (find-ns 'provider.dataspace-match)) "provider.dataspace-match must load"))

(deftest state-provider-and-conformance-are-owned-here
  (let [provider (state/provider {:message "one"})
        put [state/request-type :put [state/put-type :message "two"]]
        get [state/request-type :get [state/get-type :message]]
        written ((:invoke provider) put)
        found ((:invoke provider) get)
        receipt (conformance/validate-suite!
                 {:state/transact state/capability-id}
                 [{:name :state/transact :id state/capability-id
                   :provider provider}])]
    (is (= :written (second written)))
    (is (= :found (second found)))
    (is (= "two" (get-in found [2 2])))
    (is (= [{:name :state/transact :id state/capability-id}]
           (:capabilities receipt)))))

(deftest object-get-stream-chunk-queue-yields-discrete-chunks
  "ADR 0125: {:chunk-queue [...]} is not pre-joined (unlike :chunks)."
  (let [a (byte-array [1 2])
        b (byte-array [3])
        ps (:providers (object/create-providers
                        {:allowed-bindings #{:example/blocks}
                         :transport (fn [_] {:chunk-queue [a b]})}))
        p (get ps object/get-stream-capability-id)
        task ((:invoke p) [object/get-stream-request-type :example/blocks "k"])
        stream (:stream (value/task-poll task))
        c1 (value/stream-read! stream 100)
        c2 (value/stream-read! stream 100)]
    (is (false? (:done? c1)))
    (is (= [1 2] (vec (:bytes c1))))
    (is (true? (:done? c2)))
    (is (= [3] (vec (:bytes c2))))))

(deftest object-get-stream-open-stream-progressive-push
  "ADR 0126: {:open-stream true}; host enqueues then closes."
  (let [ps (:providers (object/create-providers
                        {:allowed-bindings #{:example/blocks}
                         :transport (fn [_] {:open-stream true})}))
        p (get ps object/get-stream-capability-id)
        task ((:invoke p) [object/get-stream-request-type :example/blocks "k"])
        stream (:stream (value/task-poll task))
        p0 (value/stream-read! stream 100)
        a (byte-array [10 11])
        _ (value/stream-enqueue! stream a)
        c1 (value/stream-read! stream 100)
        _ (value/stream-close! stream)
        done (value/stream-read! stream 100)]
    (is (true? (:pending? p0)))
    (is (= [10 11] (vec (:bytes c1))))
    (is (false? (:done? c1)))
    (is (true? (:done? done)))))

(deftest object-transport-resolve-endpoint-requires-host-config
  (is (thrown-with-msg? clojure.lang.ExceptionInfo #":endpoint"
                        (object-transport/resolve-endpoint {})))
  (is (= "https://obj.example.test"
         (object-transport/resolve-endpoint {:endpoint "https://obj.example.test"}))))

(deftest object-transport-request-body-shapes
  (is (= {"operation" "get-stream" "binding" "example/blocks" "key" "k1"}
         (#'object-transport/request-body
          {:operation :get-stream :binding :example/blocks :key "k1"})))
  (let [body (#'object-transport/request-body
              {:operation :put-block
               :binding :example/blocks
               :digest "sha256:abc"
               :bytes (byte-array [1 2 3])})]
    (is (= "put-block" (get body "operation")))
    (is (string? (get body "bytes_base64")))
    (is (seq (get body "bytes_base64")))))


(deftest scoped-fs-resolve-path-rejects-escapes
  (is (= {:ok "a/b"} (scoped-fs/resolve-path "a/b")))
  (is (= {:ok "a/b"} (scoped-fs/resolve-path "a//b/")))
  (is (= :fs/absolute (:error (scoped-fs/resolve-path "/etc/passwd"))))
  (is (= :fs/home-escape (:error (scoped-fs/resolve-path "~/secret"))))
  (is (= :fs/escape (:error (scoped-fs/resolve-path "a/../b"))))
  (is (= :fs/escape (:error (scoped-fs/resolve-path "a/./b"))))
  (is (= :fs/empty-path (:error (scoped-fs/resolve-path ""))))
  (is (= :fs/backslash (:error (scoped-fs/resolve-path "a\\b")))))

(deftest scoped-fs-mem-store-read-write-roundtrip
  (let [store (scoped-fs/mem-store {:cache/tmp {"hello.txt" "hi"}})
        ps (:providers (scoped-fs/create-providers
                        {:allowed-roots #{:cache/tmp}
                         :store store}))
        p (get ps scoped-fs/capability-id)
        read-req [scoped-fs/request-type :read
                  [scoped-fs/read-request-type :cache/tmp "hello.txt"]]
        write-req [scoped-fs/request-type :write
                   [scoped-fs/write-request-type :cache/tmp "hello.txt" "bye"]]
        found ((:invoke p) read-req)
        written ((:invoke p) write-req)
        found2 ((:invoke p) read-req)
        escape [scoped-fs/request-type :read
                [scoped-fs/read-request-type :cache/tmp "../x"]]]
    (is (= :content (second found)))
    (is (= "hi" (nth found 2)))
    (is (= :written (second written)))
    (is (= "bye" (nth found2 2)))
    (is (= :error (second ((:invoke p) escape))))))

(deftest process-validate-spawn-policy
  (is (nil? (process/validate-spawn ["echo" "hi"] 100 1000 #{"echo"})))
  (is (= :process/empty-argv (process/validate-spawn [] 100 1000 #{"echo"})))
  (is (= :process/not-allowed (process/validate-spawn ["rm" "-rf"] 100 1000 #{"echo"})))
  (is (= :process/path-command (process/validate-spawn ["/bin/echo" "x"] 100 1000 #{"echo"})))
  (is (= :process/bad-max-stdout (process/validate-spawn ["echo"] 0 1000 #{"echo"}))))

(deftest process-echo-transport-roundtrip
  (let [ps (:providers (process/create-providers
                        {:allowed-commands #{"echo"}
                         :spawn (process/echo-transport)}))
        p (get ps process/capability-id)
        reply ((:invoke p) [process/spawn-request-type ["echo" "a" "b"] 1024 5000])]
    (is (= :ok (second reply)))
    (let [[_ _exit stdout _stderr] (nth reply 2)]
      (is (= 0 _exit))
      (is (= "a b" stdout)))))


(deftest process-transport-resolve-binary-no-path-scan
  (is (= "/bin/echo" (process-transport/resolve-binary {"echo" "/bin/echo"} "echo")))
  (is (nil? (process-transport/resolve-binary {"echo" "/bin/echo"} "rm")))
  (is (nil? (process-transport/resolve-binary {} "echo"))))

(deftest process-and-fs-absolute-path-predicate
  (is (true? (process-transport/absolute-path? "/bin/echo")))
  (is (false? (process-transport/absolute-path? "echo")))
  (is (false? (process-transport/absolute-path? "")))
  (is (true? (scoped-fs-transport/absolute-path? "/var/cache")))
  (is (false? (scoped-fs-transport/absolute-path? "relative/path"))))

(deftest process-os-spawn-runs-host-mapped-echo
  (let [echo-bin (let [f (java.io.File. "/bin/echo")]
                   (if (.canExecute f) "/bin/echo" "/usr/bin/echo"))
        spawn (process-transport/os-spawn {:binaries {"echo" echo-bin}})
        ps (:providers (process/create-providers
                        {:allowed-commands #{"echo"}
                         :spawn spawn}))
        p (get ps process/capability-id)
        reply ((:invoke p) [process/spawn-request-type ["echo" "hello-os"] 4096 5000])]
    (is (= :ok (second reply)))
    (let [[_ exit stdout _] (nth reply 2)]
      (is (zero? exit))
      (is (str/includes? stdout "hello-os")))))

(deftest process-os-spawn-rejects-unmapped-binary
  (let [spawn (process-transport/os-spawn {:binaries {"echo" "/bin/echo"}})
        reply (spawn {:argv ["rm" "-rf" "/"] :max-stdout-bytes 100 :timeout-ms 1000})]
    (is (= :error (:tag reply)))
    (is (= :process/no-binary (:code reply)))))

(deftest scoped-fs-under-root-prefix-check
  (is (true? (scoped-fs-transport/under-root? "/var/cache" "/var/cache")))
  (is (true? (scoped-fs-transport/under-root? "/var/cache" "/var/cache/a")))
  (is (false? (scoped-fs-transport/under-root? "/var/cache" "/var/cache2/x")))
  (is (false? (scoped-fs-transport/under-root? "/var/cache" "/etc/passwd"))))

(deftest scoped-fs-os-store-roundtrip-under-temp-root
  (let [dir (doto (java.io.File. (str (System/getProperty "java.io.tmpdir")
                                      "/kotoba-fs-test-"
                                      (System/currentTimeMillis)))
              (.mkdirs))
        store (scoped-fs-transport/os-store {:roots {:cache/tmp dir}})
        ps (:providers (scoped-fs/create-providers
                        {:allowed-roots #{:cache/tmp}
                         :store store}))
        p (get ps scoped-fs/capability-id)
        write-req [scoped-fs/request-type :write
                   [scoped-fs/write-request-type :cache/tmp "nested/hello.txt" "os-hi"]]
        read-req [scoped-fs/request-type :read
                  [scoped-fs/read-request-type :cache/tmp "nested/hello.txt"]]
        escape [scoped-fs/request-type :read
                [scoped-fs/read-request-type :cache/tmp "../outside"]]]
    (is (= :written (second ((:invoke p) write-req))))
    (let [found ((:invoke p) read-req)]
      (is (= :content (second found)))
      (is (= "os-hi" (nth found 2))))
    (is (= :error (second ((:invoke p) escape))))
    ;; cleanup
    (doseq [f (reverse (file-seq dir))]
      (.delete f))))


(deftest secret-validate-name-policy
  (is (nil? (secret/validate-name "cloudflare-api-token")))
  (is (= :secret/empty-name (secret/validate-name "")))
  (is (= :secret/wildcard (secret/validate-name "tok*")))
  (is (= :secret/path-name (secret/validate-name "a/b")))
  (is (= :secret/whitespace (secret/validate-name "a b"))))

(deftest secret-mem-fetch-roundtrip-and-allowlist
  (let [ps (:providers (secret/create-providers
                        {:allowed-names #{"murakumo-token" "cloudflare-api-token"}
                         :fetch (secret/mem-fetch
                                 {"murakumo-token" "s3cr3t"
                                  "cloudflare-api-token" "cf-tok"})}))
        p (get ps secret/capability-id)
        ok ((:invoke p) [secret/get-request-type "murakumo-token"])
        denied ((:invoke p) [secret/get-request-type "other"])
        ps2 (:providers (secret/create-providers
                         {:allowed-names #{"murakumo-token"}
                          :fetch (secret/mem-fetch {})}))
        p2 (get ps2 secret/capability-id)
        missing ((:invoke p2) [secret/get-request-type "murakumo-token"])]
    (is (= :value (second ok)))
    (is (= "s3cr3t" (nth ok 2)))
    (is (= :error (second denied)))
    (is (= :secret/not-allowed (second (nth denied 2))))
    (is (= :error (second missing)))
    (is (= :secret/not-found (second (nth missing 2))))))

(deftest secret-env-fetch-reads-only-mapped-var
  ;; Map a well-known process env var by exact name — never enumerates env.
  (let [fetch (secret-transport/env-fetch {"path-probe" "PATH"})
        ps (:providers (secret/create-providers
                        {:allowed-names #{"path-probe"}
                         :fetch fetch}))
        p (get ps secret/capability-id)
        ok ((:invoke p) [secret/get-request-type "path-probe"])
        unmapped (fetch {:name "other"})
        missing (secret-transport/env-fetch {"gone" "KOTOBA_SECRET_DEFINITELY_UNSET_XYZ"})]
    (is (= :value (second ok)))
    (is (string? (nth ok 2)))
    (is (pos? (count (nth ok 2))))
    (is (= :error (:tag unmapped)))
    (is (= :secret/not-found (:code unmapped)))
    (is (= :error (:tag (missing {:name "gone"}))))
    (is (= :secret/not-found (:code (missing {:name "gone"}))))))

(deftest secret-fn-fetch-wraps-one-shot-getter
  ;; Host/kagi shape: (fn [name] string-or-nil) — no list/dump.
  (let [calls (atom [])
        getter (fn [n]
                 (swap! calls conj n)
                 (get {"murakumo-token" "hmac-secret"
                       "cloudflare-api-token" "cf-tok"} n))
        fetch (secret-transport/fn-fetch getter #{"murakumo-token" "cloudflare-api-token"})
        ps (:providers (secret/create-providers
                        {:allowed-names #{"murakumo-token" "cloudflare-api-token"}
                         :fetch fetch}))
        p (get ps secret/capability-id)
        ok ((:invoke p) [secret/get-request-type "murakumo-token"])]
    (is (= :value (second ok)))
    (is (= "hmac-secret" (nth ok 2)))
    (is (= ["murakumo-token"] @calls))
    (let [cf (fetch {:name "cloudflare-api-token"})]
      (is (= :value (:tag cf)))
      (is (= "cf-tok" (:value cf))))
    (is (= :secret/not-found
           (:code ((secret-transport/fn-fetch (fn [_] nil)) {:name "x"}))))
    (is (= :secret/fetch
           (:code ((secret-transport/fn-fetch
                    (fn [_] (throw (ex-info "locked" {}))))
                   {:name "x"}))))
    (let [deny (secret-transport/fn-fetch getter #{"murakumo-token"})]
      (is (= :error (:tag (deny {:name "cloudflare-api-token"}))))
      (is (= :secret/not-allowed (:code (deny {:name "cloudflare-api-token"})))))))

(deftest secret-keychain-fetch-single-item-only
  ;; Inject sh-fn — never call real security; prove argv is get-one -w only.
  (let [argv (atom nil)
        sh-fn (fn [& args]
                (reset! argv (vec args))
                {:exit 0 :out "kc-secret\n" :err ""})
        fetch (secret-transport/keychain-fetch
               {"murakumo-token" {:service "murakumo" :account "token"}}
               {:sh-fn sh-fn})
        ps (:providers (secret/create-providers
                        {:allowed-names #{"murakumo-token"}
                         :fetch fetch}))
        p (get ps secret/capability-id)
        ok ((:invoke p) [secret/get-request-type "murakumo-token"])
        unmapped (fetch {:name "other"})
        miss-sh (fn [& _] {:exit 44 :out "" :err "could not be found"})
        miss ((secret-transport/keychain-fetch
               {"murakumo-token" {:service "murakumo" :account "token"}}
               {:sh-fn miss-sh})
              {:name "murakumo-token"})]
    (is (= :value (second ok)))
    (is (= "kc-secret" (nth ok 2)))
    (is (= ["security" "find-generic-password" "-s" "murakumo" "-a" "token" "-w"]
           @argv)
        "must use -w single-item read, never -g dump")
    (is (not (some #{"-g" "dump-keychain" "dump"} @argv)))
    (is (= :secret/not-found (:code unmapped)))
    (is (= :secret/not-found (:code miss)))
    (is (thrown-with-msg? Exception #"name→\{:service :account\}"
          (secret-transport/keychain-fetch {"x" {:service "s"}})))
    (is (thrown-with-msg? Exception #"name→\{:service :account\}"
          (secret-transport/keychain-fetch
           {"x" {:service "s*" :account "a"}})))))


(deftest git-validate-run-policy
  (is (nil? (git/validate-run ["status" "--porcelain"] 100 1000)))
  (is (nil? (git/validate-run ["rev-parse" "HEAD"] 100 1000)))
  (is (= :git/subcommand-not-allowed
         (git/validate-run ["push" "origin" "main"] 100 1000)))
  (is (= :git/path-escape
         (git/validate-run ["show" "/etc/passwd"] 100 1000)))
  (is (= :git/path-escape
         (git/validate-run ["log" "../x"] 100 1000)))
  (is (= :git/empty-args (git/validate-run [] 100 1000))))

(deftest git-echo-transport-roundtrip
  (let [ps (:providers (git/create-providers
                        {:run (git/echo-transport)
                         :allowed-subcommands git/default-allowed-subcommands}))
        p (get ps git/capability-id)
        req [git/run-request-type ["status" "--short"] 1024 5000]
        reply ((:invoke p) req)]
    (is (= git/reply-type (first reply)))
    (is (= :ok (second reply)))
    (let [[_ exit stdout stderr] (nth reply 2)]
      (is (zero? exit))
      (is (= "status --short" stdout))
      (is (= "" stderr)))))

(deftest git-os-run-status-on-this-repo
  (let [root (java.io.File. ".")
        git-dir (java.io.File. root ".git")
        git-bin (cond (.canExecute (java.io.File. "/usr/bin/git")) "/usr/bin/git"
                      (.canExecute (java.io.File. "/bin/git")) "/bin/git"
                      :else nil)]
    (if (and (.exists git-dir) git-bin)
      (let [run (git-transport/os-run {:git-bin git-bin
                                       :worktree (.getCanonicalPath root)})
            ps (:providers (git/create-providers {:run run}))
            p (get ps git/capability-id)
            reply ((:invoke p) [git/run-request-type
                                ["rev-parse" "--abbrev-ref" "HEAD"]
                                4096 5000])]
        (is (= :ok (second reply)) (str reply))
        (let [[_ exit stdout _] (nth reply 2)]
          (is (zero? exit))
          (is (pos? (count (str/trim stdout))))))
      (is true "skip when no .git or git binary"))))

(deftest git-os-run-rejects-relative-paths
  (is (thrown-with-msg? Exception #"absolute :git-bin"
        (git-transport/os-run {:git-bin "git" :worktree "/tmp"})))
  (is (thrown-with-msg? Exception #"absolute :worktree"
        (git-transport/os-run {:git-bin "/usr/bin/git" :worktree "relative"}))))

(deftest entropy-validate-n-and-hex
  (is (nil? (entropy/validate-n 16)))
  (is (= :entropy/bad-n (entropy/validate-n 0)))
  (is (= :entropy/too-large (entropy/validate-n 65)))
  (is (= "0001ff" (entropy/bytes->hex [0 1 255])))
  (is (= [0 1 255] (entropy/hex->bytes "0001ff"))))

(deftest entropy-mem-draw-roundtrip
  (let [draw (entropy/mem-draw [0xab 0xcd])
        ps (:providers (entropy/create-providers {:draw draw}))
        p (get ps entropy/capability-id)
        ok ((:invoke p) [entropy/draw-request-type 4])
        bad ((:invoke p) [entropy/draw-request-type 0])]
    (is (= :hex (second ok)))
    (is (= "abcdabcd" (nth ok 2)))
    (is (= :error (second bad)))
    (is (= :entropy/bad-n (second (nth bad 2))))))

(deftest entropy-os-draw-produces-hex
  (let [draw (entropy-transport/os-draw)
        ps (:providers (entropy/create-providers {:draw draw}))
        p (get ps entropy/capability-id)
        a ((:invoke p) [entropy/draw-request-type 16])
        b ((:invoke p) [entropy/draw-request-type 16])]
    (is (= :hex (second a)))
    (is (= 32 (count (nth a 2))))
    (is (re-matches #"[0-9a-f]{32}" (nth a 2)))
    ;; cryptographic draws should almost never collide
    (is (not= (nth a 2) (nth b 2)))))

(deftest storage-mem-transport-audits-on-call
  "ADR 0271: mem-transport fires optional on-call audit events."
  (let [events (atom [])
        t (storage-transport/mem-transport
           {:on-call (fn [e] (swap! events conj e))})
        p (storage/provider {:storage-namespace :test/ns :transport t})
        put ((:invoke p) [storage/request-type :put
                          [storage/put-type :k "v" [storage/expected-version-type false]]])
        get ((:invoke p) [storage/request-type :get
                          [storage/get-type :k]])]
    (is (= :written (second put)))
    (is (= :found (second get)))
    (is (= 2 (count @events)))
    (is (= :storage (:kit (first @events))))
    (is (= :put (:operation (first @events))))
    (is (= :written (:reply-tag (first @events))))
    (is (= :get (:operation (second @events))))
    (is (= :found (:reply-tag (second @events))))))

(deftest object-mem-transport-audits-on-call
  "ADR 0271: object mem-transport fires optional on-call audit events."
  (let [events (atom [])
        payload (value/utf8-string->bytes "hi")
        t (object-transport/mem-transport
           {:on-call (fn [e] (swap! events conj e))})
        ps (:providers (object/create-providers
                        {:allowed-bindings #{:example/blocks}
                         :transport t}))
        put-p (get ps object/put-block-capability-id)
        get-p (get ps object/get-stream-capability-id)
        won ((:invoke put-p)
             [object/put-block-request-type :example/blocks "sha256:ab" payload])
        task ((:invoke get-p)
              [object/get-stream-request-type :example/blocks "sha256:ab"])]
    (is (true? won))
    (is (some? task))
    (is (= 2 (count @events)))
    (is (= :object (:kit (first @events))))
    (is (= :put-block (:operation (first @events))))
    (is (= :ok (:reply-tag (first @events))))
    (is (= :get-stream (:operation (second @events))))))

;; --- ADR 0272: object pure deny fixtures ---

(deftest object-validate-pure-deny-fixtures
  (let [allowed #{:example/blocks}]
    (is (nil? (object/validate-get-stream allowed :example/blocks "k")))
    (is (= :object/binding-not-allowed
           (object/validate-get-stream allowed :other/ns "k")))
    (is (= :object/empty-key
           (object/validate-get-stream allowed :example/blocks "")))
    (is (= :object/empty-key
           (object/validate-get-stream allowed :example/blocks "   ")))
    (is (nil? (object/validate-put-block allowed :example/blocks "sha256:ab"
                                         (byte-array [1]))))
    (is (= :object/binding-not-allowed
           (object/validate-put-block allowed :evil/ns "d" (byte-array [1]))))
    (is (= :object/empty-digest
           (object/validate-put-block allowed :example/blocks "" (byte-array [1]))))
    (is (nil? (object/validate-cas allowed :example/blocks "k" nil "next")))
    (is (= :object/empty-next-etag
           (object/validate-cas allowed :example/blocks "k" nil "")))
    (is (= :object/empty-expected-etag
           (object/validate-cas allowed :example/blocks "k" "" "next")))))

(deftest object-invoke-deny-codes
  (let [ps (:providers (object/create-providers
                        {:allowed-bindings #{:example/blocks}
                         :transport (fn [_] (byte-array [1]))}))
        get-p (get ps object/get-stream-capability-id)
        put-p (get ps object/put-block-capability-id)]
    (try
      ((:invoke get-p) [object/get-stream-request-type :nope/x "k"])
      (is false "expected deny")
      (catch clojure.lang.ExceptionInfo e
        (is (= :object/binding-not-allowed (:code (ex-data e))))
        (is (re-find #"denied" (ex-message e)))))
    (try
      ((:invoke get-p) [object/get-stream-request-type :example/blocks ""])
      (is false "expected deny")
      (catch clojure.lang.ExceptionInfo e
        (is (= :object/empty-key (:code (ex-data e))))))
    (try
      ((:invoke put-p)
       [object/put-block-request-type :example/blocks "" (byte-array [1])])
      (is false "expected deny")
      (catch clojure.lang.ExceptionInfo e
        (is (= :object/empty-digest (:code (ex-data e))))))))

;; --- ADR 0273: storage pure deny fixtures ---

(deftest storage-validate-pure-deny-fixtures
  (is (nil? (storage/validate-get :k)))
  (is (= :storage/bad-key (storage/validate-get "not-a-keyword")))
  (is (nil? (storage/validate-put-value "ok")))
  (is (= :storage/value-too-large
         (storage/validate-put-value (apply str (repeat (inc storage/max-value-bytes) "a")))))
  (is (nil? (storage/validate-expected-version false nil)))
  (is (nil? (storage/validate-expected-version true 1)))
  (is (= :storage/invalid-version (storage/validate-expected-version true 0)))
  (is (= :storage/invalid-version (storage/validate-expected-version true -1)))
  (is (nil? (storage/validate-put :k "v" false nil)))
  (is (= :storage/value-too-large
         (storage/validate-put :k (apply str (repeat (inc storage/max-value-bytes) "x")) false nil))))

(deftest storage-invoke-deny-codes
  (let [t (storage-transport/mem-transport)
        p (storage/provider {:storage-namespace :test/ns :transport t})
        huge (apply str (repeat (inc storage/max-value-bytes) "z"))]
    (try
      ((:invoke p) [storage/request-type :put
                    [storage/put-type :k huge [storage/expected-version-type false]]])
      (is false "expected deny")
      (catch clojure.lang.ExceptionInfo e
        (is (= :storage/value-too-large (:code (ex-data e))))))
    (try
      ((:invoke p) [storage/request-type :put
                    [storage/put-type :k "v" [storage/expected-version-type true 0]]])
      (is false "expected deny")
      (catch clojure.lang.ExceptionInfo e
        (is (= :storage/invalid-version (:code (ex-data e))))))))
