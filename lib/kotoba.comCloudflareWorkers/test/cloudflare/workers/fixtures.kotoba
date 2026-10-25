(ns cloudflare.workers.fixtures
  "One policy shared by the conformance suites, written to exercise every
  interesting authority shape at once:

  - `SESSIONS` -- read+write KV, narrow key scope, small value ceiling, TTL band
  - `READONLY` -- read-only KV (the `capability-not-granted` case for writes)
  - `WIDE`     -- KV with `:any` key scope (the `wildcard-forbidden` case)
  - `APP_DB`   -- D1 granted **read only**, but with a write statement
                  registered. A guest naming `insert-order` is denied on the
                  capability derived from the statement's mode, which is the
                  property that makes statement-id addressing worth having.
  - `ASSETS`   -- read+write R2

  Quotas are deliberately tiny so the quota fixtures do not need bulk data.")

(def policy
  {:policy/quota {:max-commands 4
                  :max-write-bytes 150
                  :max-d1-statements 2
                  :max-reads 4}
   :policy/bindings
   {"SESSIONS" {:kind :kv
                :caps #{:cf/kv-read :cf/kv-write}
                :key-prefixes #{"user:"}
                :max-value-bytes 64
                :min-ttl 60
                :max-ttl 3600}

    "READONLY" {:kind :kv
                :caps #{:cf/kv-read}
                :key-prefixes #{"pub:"}}

    "WIDE"     {:kind :kv
                :caps #{:cf/kv-read}
                :key-prefixes :any}

    "APP_DB"   {:kind :d1
                :caps #{:cf/d1-read}
                :statements
                {"order-by-id"  {:sql "select id, qty from orders where id = ?1"
                                 :arity 1
                                 :mode :read}
                 "insert-order" {:sql "insert into orders (id, qty) values (?1, ?2)"
                                 :arity 2
                                 :mode :write}}}

    "ASSETS"   {:kind :r2
                :caps #{:cf/r2-read :cf/r2-write}
                :key-prefixes #{"img/"}
                :max-value-bytes 1024}}})

(def now "2026-07-25T00:00:00Z")

(def session-read
  {:cmd :cf.kv/get :binding "SESSIONS" :key "user:42"})

(def session-write
  {:cmd :cf.kv/put :binding "SESSIONS" :key "user:42" :value "ok" :ttl 300})

(def order-query
  {:cmd :cf.d1/exec :binding "APP_DB" :statement "order-by-id" :params ["o-1"]})

(def asset-write
  {:cmd :cf.r2/put :binding "ASSETS" :key "img/logo.png" :body {:b64 "AAAA"}
   :content-type "image/png"})
