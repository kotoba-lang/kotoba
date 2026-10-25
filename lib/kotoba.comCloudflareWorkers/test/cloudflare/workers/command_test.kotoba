(ns cloudflare.workers.command-test
  (:require [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is testing]]
            [cloudflare.workers.command :as command]))

(defn- reasons
  [cmd]
  (set (map :reason (command/problems cmd))))

(deftest well-formed-commands-have-no-structural-problems
  (is (command/valid? {:cmd :cf.kv/get :binding "SESSIONS" :key "user:1"}))
  (is (command/valid? {:cmd :cf.kv/put :binding "S" :key "k" :value "v" :ttl 60}))
  (is (command/valid? {:cmd :cf.d1/exec :binding "APP_DB" :statement "order-by-id"
                       :params ["a" 1 true nil]}))
  (is (command/valid? {:cmd :cf.r2/put :binding "ASSETS" :key "img/a.png"
                       :body {:b64 "AAAA"} :content-type "image/png"})))

(deftest raw-sql-is-rejected-by-name
  (testing "the denial an operator most needs to read is not a generic shape error"
    (is (= #{:raw-sql-forbidden}
           (reasons {:cmd :cf.d1/exec :binding "APP_DB" :sql "select 1"})))
    (is (= #{:raw-sql-forbidden}
           (reasons {:cmd :cf.d1/exec :binding "APP_DB" :statement "s"
                     :query "drop table orders"})))
    (testing "and it wins over other problems in the same command"
      (is (= #{:raw-sql-forbidden}
             (reasons {:cmd :nonsense :sql "select 1"}))))))

(deftest command-maps-are-closed
  (is (= #{:unknown-command-key}
         (reasons {:cmd :cf.kv/get :binding "S" :key "k" :consistency :strong})))
  (is (contains? (reasons {:cmd :cf.kv/get :binding "S"}) :missing-required-field))
  (is (= #{:unknown-command} (reasons {:cmd :cf.kv/scan :binding "S"})))
  (is (= #{:malformed-command} (reasons "not-a-map"))))

(deftest field-validation
  (testing "binding names follow the Workers convention"
    (is (= #{:malformed-binding-name}
           (reasons {:cmd :cf.kv/get :binding "sessions" :key "k"})))
    (is (= #{:malformed-binding-name}
           (reasons {:cmd :cf.kv/get :binding "" :key "k"}))))

  (testing "keys reject control characters and oversize"
    (is (= #{:malformed-key} (reasons {:cmd :cf.kv/get :binding "S" :key "a\nb"})))
    (is (= #{:malformed-key} (reasons {:cmd :cf.kv/get :binding "S" :key ""})))
    (is (= #{:key-too-long}
           (reasons {:cmd :cf.kv/get :binding "S"
                     :key (str/join (repeat 513 "x"))}))))

  (testing "ttl has a structural floor independent of policy"
    (is (= #{:ttl-out-of-range}
           (reasons {:cmd :cf.kv/put :binding "S" :key "k" :value "v" :ttl 30})))
    (is (= #{:malformed-ttl}
           (reasons {:cmd :cf.kv/put :binding "S" :key "k" :value "v" :ttl "60"}))))

  (testing "D1 params are scalars only -- no structure smuggling"
    (is (= #{:malformed-params}
           (reasons {:cmd :cf.d1/exec :binding "D" :statement "s" :params [{:a 1}]})))
    (is (= #{:malformed-params}
           (reasons {:cmd :cf.d1/exec :binding "D" :statement "s" :params ["a" ["b"]]})))
    (is (= #{:malformed-params}
           (reasons {:cmd :cf.d1/exec :binding "D" :statement "s" :params '("a")}))
        "a list is not a vector")
    (is (= #{:too-many-params}
           (reasons {:cmd :cf.d1/exec :binding "D" :statement "s"
                     :params (vec (repeat 33 "x"))}))))

  (testing "statement ids are kebab-case identifiers, not free text"
    (is (= #{:malformed-statement-id}
           (reasons {:cmd :cf.d1/exec :binding "D" :statement "Order By Id"}))))

  (testing "payloads are text or base64, nothing else"
    (is (= #{:malformed-value}
           (reasons {:cmd :cf.kv/put :binding "S" :key "k" :value 42})))
    (is (= #{:malformed-value}
           (reasons {:cmd :cf.r2/put :binding "A" :key "k" :body {:b64 "not base64!"}})))))

(deftest utf8-byte-count-matches-what-cloudflare-measures
  (is (= 3 (command/utf8-byte-count "abc")))
  (is (= 3 (command/utf8-byte-count "あ")))
  (is (= 4 (command/utf8-byte-count "😀")) "surrogate pair counts once, as 4 bytes")
  (is (= 0 (command/utf8-byte-count ""))))

(deftest base64-payloads-are-measured-decoded
  (is (= 3 (command/body-byte-count {:b64 "AAAA"})))
  (is (= 2 (command/body-byte-count {:b64 "AAA="})))
  (is (= 1 (command/body-byte-count {:b64 "AA=="})))
  (is (= 2 (command/body-byte-count "hi"))
      "text payloads are measured in UTF-8 bytes, so one ceiling covers both"))

(deftest payload-accounting-only-charges-writes
  (is (zero? (command/payload-byte-count {:cmd :cf.kv/get :binding "S" :key "k"})))
  (is (zero? (command/payload-byte-count {:cmd :cf.kv/delete :binding "S" :key "k"})))
  (is (= 5 (command/payload-byte-count
            {:cmd :cf.kv/put :binding "S" :key "k" :value "hello"}))))

(deftest resource-strings-are-stable-and-total
  (is (= "kv:SESSIONS/user:1"
         (command/resource {:cmd :cf.kv/get :binding "SESSIONS" :key "user:1"})))
  (is (= "d1:APP_DB#order-by-id"
         (command/resource {:cmd :cf.d1/exec :binding "APP_DB" :statement "order-by-id"})))
  (is (= "r2:ASSETS/img/a.png"
         (command/resource {:cmd :cf.r2/put :binding "ASSETS" :key "img/a.png"})))
  (testing "a malformed command still yields a receipt-safe resource"
    (is (nil? (command/resource {:cmd :nonsense})))
    (is (nil? (command/resource "not-a-map")))))
