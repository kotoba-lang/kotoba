(ns nostr.blossom-test
  (:require [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is testing]]
            [kotobase.local :as local]
            [kotobase.store :as st]
            [nostr.blossom :as blossom]
            [nostr.crypto :as crypto]
            [nostr.fixtures :as fx]
            [nostr.json :as json]))

(defn- ctx []
  {:store (local/local-store) :now 1700000000 :base-url "https://blossom.test"})

(defn- auth-header [sk method url created_at]
  (let [ev (fx/nip98-auth-event sk method url {:created_at created_at})
        b64 #?(:clj (.encodeToString (java.util.Base64/getEncoder) (.getBytes (json/encode ev) "UTF-8"))
               :cljs (.toString (js/Buffer.from (json/encode ev) "utf8") "base64"))]
    (str "Nostr " b64)))

(deftest upload-without-auth-succeeds
  (let [c (ctx)
        res (blossom/handle c {:method :put :path "/upload"
                               :headers {"content-type" "text/plain"}
                               :body "hello blossom"})
        expected-sha (crypto/sha256-of-str "hello blossom")]
    (is (= 200 (:status res)))
    (let [descriptor (json/parse (:body res))]
      (is (= expected-sha (get descriptor "sha256")))
      (is (= 13 (get descriptor "size")))
      (is (= "text/plain" (get descriptor "type")))
      (is (= (str "https://blossom.test/" expected-sha) (get descriptor "url"))))))

(deftest get-round-trips-uploaded-blob
  (let [c (ctx)
        put-res (blossom/handle c {:method :put :path "/upload"
                                   :headers {"content-type" "text/plain"}
                                   :body "round trip"})
        sha (get (json/parse (:body put-res)) "sha256")
        get-res (blossom/handle c {:method :get :path (str "/" sha)})]
    (is (= 200 (:status get-res)))
    (is (= "round trip" (:body get-res)))
    (is (= "text/plain" (get-in get-res [:headers "content-type"])))))

(deftest get-missing-blob-404
  (let [c (ctx)
        res (blossom/handle c {:method :get :path "/0000000000000000000000000000000000000000000000000000000000000000"})]
    (is (= 404 (:status res)))))

(deftest upload-with-valid-auth-records-uploader
  (let [c (ctx)
        url "https://blossom.test/upload"
        header (auth-header fx/alice-sk "PUT" url 1700000000)
        res (blossom/handle c {:method :put :path "/upload"
                               :headers {"content-type" "text/plain" "authorization" header}
                               :body "authed upload"})
        sha (get (json/parse (:body res)) "sha256")
        stored (st/-get (:store c) blossom/coll sha)]
    (is (= 200 (:status res)))
    (is (= (fx/pubkey fx/alice-sk) (:uploaded-by stored)))))

(deftest upload-with-invalid-auth-rejected
  (let [c (ctx)
        bad-header "Nostr not-valid-base64-json!!"
        res (blossom/handle c {:method :put :path "/upload"
                               :headers {"authorization" bad-header}
                               :body "should not store"})]
    (is (= 401 (:status res)))))

(deftest delete-requires-valid-nip98-auth
  (let [c (ctx)
        put-res (blossom/handle c {:method :put :path "/upload" :body "to be deleted"})
        sha (get (json/parse (:body put-res)) "sha256")
        no-auth-res (blossom/handle c {:method :delete :path (str "/" sha)})]
    (is (= 401 (:status no-auth-res)))
    (is (some? (st/-get (:store c) blossom/coll sha)) "not deleted without auth")))

(deftest delete-with-valid-auth-succeeds
  (let [c (ctx)
        put-res (blossom/handle c {:method :put :path "/upload" :body "to be deleted 2"})
        sha (get (json/parse (:body put-res)) "sha256")
        url (str "https://blossom.test/" sha)
        header (auth-header fx/alice-sk "DELETE" url 1700000000)
        del-res (blossom/handle c {:method :delete :path (str "/" sha)
                                   :headers {"authorization" header}})]
    (is (= 204 (:status del-res)))
    (is (nil? (st/-get (:store c) blossom/coll sha)))))

(deftest delete-rejects-wrong-method-tag
  (let [c (ctx)
        put-res (blossom/handle c {:method :put :path "/upload" :body "method mismatch"})
        sha (get (json/parse (:body put-res)) "sha256")
        url (str "https://blossom.test/" sha)
        ;; auth event claims PUT, but the actual request is DELETE
        header (auth-header fx/alice-sk "PUT" url 1700000000)
        del-res (blossom/handle c {:method :delete :path (str "/" sha)
                                   :headers {"authorization" header}})]
    (is (= 401 (:status del-res)))))

(deftest delete-rejects-wrong-url
  (let [c (ctx)
        put-res (blossom/handle c {:method :put :path "/upload" :body "url mismatch"})
        sha (get (json/parse (:body put-res)) "sha256")
        header (auth-header fx/alice-sk "DELETE" "https://blossom.test/some-other-sha" 1700000000)
        del-res (blossom/handle c {:method :delete :path (str "/" sha)
                                   :headers {"authorization" header}})]
    (is (= 401 (:status del-res)))))

(deftest delete-rejects-expired-auth
  (let [c (ctx)
        put-res (blossom/handle c {:method :put :path "/upload" :body "expired"})
        sha (get (json/parse (:body put-res)) "sha256")
        url (str "https://blossom.test/" sha)
        ;; ctx :now is 1700000000; sign at a time 1000s earlier -> outside default 60s window
        header (auth-header fx/alice-sk "DELETE" url (- 1700000000 1000))
        del-res (blossom/handle c {:method :delete :path (str "/" sha)
                                   :headers {"authorization" header}})]
    (is (= 401 (:status del-res)))))

(deftest delete-nonexistent-blob-is-idempotent-204
  (let [c (ctx)
        sha "0000000000000000000000000000000000000000000000000000000000000000"
        url (str "https://blossom.test/" sha)
        header (auth-header fx/alice-sk "DELETE" url 1700000000)
        res (blossom/handle c {:method :delete :path (str "/" sha)
                               :headers {"authorization" header}})]
    (is (= 204 (:status res)))))

(deftest audit-trail-records-put-and-delete
  (let [c (ctx)
        put-res (blossom/handle c {:method :put :path "/upload" :body "audited blob"})
        sha (get (json/parse (:body put-res)) "sha256")
        url (str "https://blossom.test/" sha)
        header (auth-header fx/alice-sk "DELETE" url 1700000000)]
    (blossom/handle c {:method :delete :path (str "/" sha) :headers {"authorization" header}})
    (let [events (st/-read (:store c) :nostr.blossom/audit 0)]
      (is (= [:put :delete] (map :op events))))))
