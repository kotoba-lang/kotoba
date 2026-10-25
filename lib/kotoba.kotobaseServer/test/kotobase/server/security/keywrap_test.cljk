(ns kotobase.server.security.keywrap-test
  (:require [cljs.test :refer-macros [deftest is async]]
            [kotobase.server.security.keywrap :as keywrap]
            [kotobase.server.security.keyring-admin :as keyring-admin]))

(deftest round-trip-wrap-unwrap
  (async done
    (.then (keywrap/generate-recipient-keypair)
           (fn [{:keys [public-key-b64 private-key-b64]}]
             (let [tenant "tenant-a"
                   keyring {"active" "k1"
                            "keys" {"k1" {"aead" "aa" "blind" "bb"}}}]
               (.then (keywrap/wrap-keyring public-key-b64 keyring tenant)
                      (fn [envelope]
                        (is (= 1 (:version envelope)))
                        (is (= "X25519-HKDF-SHA256-CHACHA20POLY1305" (:suite envelope)))
                        (.then (keywrap/unwrap-keyring private-key-b64 envelope tenant)
                               (fn [decoded]
                                 (is (= keyring decoded))
                                 (done))))))))))

(deftest keyring-admin-rotation-round-trip
  (async done
    (.then (keywrap/generate-recipient-keypair)
           (fn [{:keys [public-key-b64 private-key-b64]}]
             (let [tenant "tenant-b"]
               (.then (keyring-admin/create-wrapped-keyring
                       public-key-b64 tenant "k1")
                      (fn [created]
                        (is (some? (:ciphertext created)))
                        (.then (keyring-admin/rotate-wrapped-keyring
                                private-key-b64 public-key-b64 created tenant "k2")
                               (fn [rotated]
                                 (.then (keywrap/unwrap-keyring private-key-b64 rotated tenant)
                                        (fn [decoded]
                                          (is (= "k2" (get decoded "active")))
                                          (is (contains? (get decoded "keys") "k1"))
                                          (is (contains? (get decoded "keys") "k2"))
                                          (done))))))))))))
