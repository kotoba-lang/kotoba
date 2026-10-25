(ns envelope.passkey-test
  "passkey PRF から envelope 受信者を作る経路のテスト。認証器は呼ばず、PRF 出力
   （同じ credential+salt に対して決定的な 32 bytes）をバイト列として渡す。"
  (:require [cljs.test :refer [deftest is testing async]]
            [envelope.passkey :as pk]
            [envelope.seal :as seal]
            [envelope.model :as m]))

(defn- prf [s]
  ;; 認証器が返す 32 bytes の代役。決定的であることだけが本質。
  (-> (js/require "crypto") (.createHash "sha256") (.update s) (.digest)
      (js/Uint8Array.from)))

(def prf-a (prf "credential-a"))
(def prf-b (prf "credential-b"))

(defn- fails
  "p が reject したら true。**resolve したら false** —— reject を待って
   assert し忘れたテストは黙って通るので、明示的に書く。"
  [p]
  (-> p (.then (fn [_] false)) (.catch (fn [_] true))))

(deftest passkey-identity-roundtrip
  (testing "PRF 出力で封じて、同じ PRF 出力で開く"
    (async done
      (let [id (pk/generate-identity)]
        (-> (pk/seal-identity id prf-a)
            (.then (fn [w]
                     (is (= :symmetric (:wrap/kind w)))
                     (is (string? (:wrap/wrapped w)))
                     (pk/open-identity w prf-a)))
            (.then (fn [priv]
                     (is (= (vec (js/Array.from (:priv id))) (vec (js/Array.from priv)))
                         "同じ秘密鍵が戻る")
                     (done))))))))

(deftest passkey-wrong-prf-does-not-open
  (testing "別 credential の PRF 出力では開かない（黙って別の鍵を返さない）"
    (async done
      (let [id (pk/generate-identity)]
        (-> (pk/seal-identity id prf-a)
            (.then (fn [w] (fails (pk/open-identity w prf-b))))
            (.then (fn [rejected?] (is (true? rejected?)) (done))))))))

(deftest passkey-two-credentials-one-identity
  (testing "**同じ identity を 2 本の passkey がそれぞれ開ける** —— これが
            『PRF から鍵を導出する』設計との差。credential を足しても回しても
            identity は動かない"
    (async done
      (let [id (pk/generate-identity)]
        (-> (js/Promise.all #js [(pk/seal-identity id prf-a)
                                 (pk/seal-identity id prf-b)])
            (.then (fn [[wa wb]]
                     (is (not= (:wrap/wrapped wa) (:wrap/wrapped wb))
                         "wrap は別物")
                     (js/Promise.all #js [(pk/open-identity wa prf-a)
                                          (pk/open-identity wb prf-b)])))
            (.then (fn [[pa pb]]
                     (is (= (vec (js/Array.from pa)) (vec (js/Array.from pb)))
                         "どちらも同じ identity 秘密鍵に開く")
                     (is (= (vec (js/Array.from (:priv id))) (vec (js/Array.from pa))))
                     (done))))))))

(deftest passkey-identity-is-not-derived-from-prf
  (testing "identity はランダムであって PRF の関数ではない"
    (let [a (pk/generate-identity) b (pk/generate-identity)]
      (is (not= (vec (js/Array.from (:priv a))) (vec (js/Array.from (:priv b))))
          "呼ぶたびに違う鍵"))))

(deftest passkey-wrap-is-not-transplantable
  (testing "別 AAD で作った wrap は identity として開かない"
    (async done
      (let [id (pk/generate-identity)]
        (-> (seal/wrap-under-key (:priv id) prf-a nil "some other purpose")
            (.then (fn [w] (fails (pk/open-identity w prf-a))))
            (.then (fn [rejected?] (is (true? rejected?)) (done))))))))

(deftest passkey-salt-separates-purposes
  (testing "同じ PRF 出力でも salt が違えば開かない"
    (async done
      (let [id (pk/generate-identity)
            s1 (js/Uint8Array.from #js [1 2 3 4])
            s2 (js/Uint8Array.from #js [9 9 9 9])]
        (-> (pk/seal-identity id prf-a s1)
            (.then (fn [w] (fails (pk/open-identity (assoc w :wrap/salt (seal/b64url s2))
                                                    prf-a))))
            (.then (fn [rejected?] (is (true? rejected?)) (done))))))))

(deftest passkey-recipient-opens-a-sealed-object
  (testing "passkey identity が envelope の受信者として実際に働く"
    (async done
      (let [id (pk/generate-identity)
            did "did:key:passkey-holder"
            plaintext (js/TextEncoder.)
            pt (.encode plaintext "sealed to a passkey")]
        (-> (seal/seal-object "obj-1" [pt] [(pk/recipient did id)])
            (.then (fn [{:keys [envelope chunks]}]
                     (is (some? (seal/entry-for envelope did)))
                     (seal/open-object envelope (seal/entry-for envelope did)
                                       (:priv id) chunks)))
            (.then (fn [out]
                     (is (= "sealed to a passkey"
                            (.decode (js/TextDecoder.) (first out))))
                     (done))))))))
