(ns kotoba.signal.sealed-test
  (:require [cljs.test :refer-macros [deftest is testing async]]
            [kotoba.protocol.sealed :as proto]
            [kotoba.signal.ratchet :as ratchet]
            [kotoba.signal.sealed :as sealed]
            [kotoba.signal.x3dh :as x3dh]))

(def ipns (str "k51qzi5uqu5d" (apply str (repeat 50 "a"))))
(def file-cid "bafkreibm6jg3ux5qumhcn2b3flc3tyu6dmlb4xa7u5bf44yegnrjhc4yeq")

(defn- shape-cid
  "Injected hasher: shape-valid CID, not a real multihash. Walks the whole
   pr-str so two messages that differ only in :ciphertext still diverge."
  [x]
  (let [s (pr-str x)
        alphabet "abcdefghijklmnopqrstuvwxyz234567"
        n (count s)
        chars (map (fn [i]
                     (nth alphabet
                          (mod (+ n i (* 7 (.charCodeAt s (mod (* i 13) n))))
                               32)))
                   (range 32))]
    (str "bafkrei" (apply str chars))))

(defn- alice-roles [alice]
  {:ipns "k-ipns" :peer "k-peer"
   :signal (str "sig-" (.-length ^js (:pub (:ik alice))))})

(defn- step [p f]
  (.then p f))

(deftest published-bundle-is-public-and-pq-absent
  (let [bob (x3dh/generate-identity)
        {:keys [public remaining]} (sealed/publish bob)]
    (is (true? (proto/bundle? public)))
    (is (false? (:confidential? public)))
    (is (nil? (:pq-prekey public))
        "missing PQ prekey is absence, not a silent hybrid upgrade")
    (is (= (dec (count (:opks bob))) (count (:opks remaining))))
    (is (false? (proto/opk-once-on-content-addressed?)))))

(deftest colliding-key-roles-are-refused
  (let [bob (x3dh/generate-identity)]
    (is (= :key-role-collision
           (:error (sealed/publish bob {:ipns "same" :peer "same" :signal "other"}))))
    (async done
      (-> (sealed/initiate (x3dh/generate-identity)
                           (:public (sealed/publish bob))
                           {:ipns "a" :peer "b" :signal "a"})
          (step (fn [out]
                  (is (= :key-role-collision (:error out)))
                  (done)))))))

(deftest file-key-travels-inside-ratchet-plaintext
  (async done
    (let [bob (x3dh/generate-identity)
          alice (x3dh/generate-identity)
          {:keys [public]} (sealed/publish bob)
          body {:text "hello bob"
                :attachments [{:cid file-cid
                               :file-key "the-real-file-key"
                               :size 12
                               :digest "abc"}]}]
      (-> (sealed/initiate alice public (alice-roles alice))
          (step (fn [alice-s]
                  (is (true? (:ok? alice-s)))
                  (sealed/encrypt alice-s body)))
          (step (fn [pair]
                  (let [msg (nth pair 1)]
                    (.then (sealed/accept bob msg)
                           (fn [acc]
                             {:alice1 (nth pair 0)
                              :msg msg
                              :bob-s (nth acc 0)
                              :opened (nth acc 1)})))))
          (step (fn [w]
                  (let [msg (:msg w)
                        stored (sealed/store-msg msg shape-cid)]
                    (is (true? (proto/message? msg)))
                    (is (= :session (:construction msg)))
                    (is (= sealed/in-session-wrap
                           (get-in msg [:attachments 0 :wrapped-key])))
                    (is (nil? (get-in msg [:attachments 0 :file-key])))
                    (is (not (re-find #"the-real-file-key" (pr-str msg))))
                    (is (= :object (:construction stored)))
                    (is (= :session-ciphertext (:body-is stored)))
                    (is (some? (:alice1 w)))
                    (is (= "hello bob" (:text (:opened w))))
                    (is (= "the-real-file-key"
                           (get-in w [:opened :attachments 0 :file-key])))
                    (is (= file-cid (get-in w [:opened :attachments 0 :cid])))
                    (is (some? (:bob-s w)))
                    (done))))))))

(deftest full-session-then-mailbox-then-reply
  (async done
    (let [bob (x3dh/generate-identity)
          alice (x3dh/generate-identity)
          {:keys [public]} (sealed/publish bob)]
      (-> (sealed/initiate alice public)
          (step (fn [alice0]
                  (sealed/encrypt alice0 {:text "m1"})))
          (step (fn [pair]
                  (.then (sealed/accept bob (nth pair 1))
                         (fn [acc]
                           {:alice1 (nth pair 0)
                            :msg1 (nth pair 1)
                            :bob1 (nth acc 0)
                            :opened1 (nth acc 1)}))))
          (step (fn [w]
                  (.then (sealed/encrypt (:bob1 w) {:text "m2"})
                         (fn [pair]
                           (assoc w :msg2 (nth pair 1))))))
          (step (fn [w]
                  (.then (sealed/decrypt (:alice1 w) (:msg2 w))
                         (fn [pair]
                           (assoc w :alice2 (nth pair 0) :opened2 (nth pair 1))))))
          (step (fn [w]
                  (let [stored1 (sealed/store-msg (:msg1 w) shape-cid)
                        stored2 (sealed/store-msg (:msg2 w) shape-cid)
                        mb0 (proto/mailbox)
                        mb1 (sealed/put-in-mailbox mb0 stored1 shape-cid)
                        mb2 (sealed/put-in-mailbox mb1 stored2 shape-cid)
                        head (sealed/publish-head ipns (:head mb2))]
                    (is (= "m1" (:text (:opened1 w))))
                    (is (= "m2" (:text (:opened2 w))))
                    (is (true? (proto/entries-prefix? mb1 mb2)))
                    (is (= 2 (count (:entries mb2))))
                    (is (not= (:cid stored1) (:cid stored2)))
                    (is (false? (:confidential? head)))
                    (is (false? (:mutates-name? head)))
                    (is (= :naming (:plane head)))
                    (is (some? (:alice2 w)))
                    (done))))))))

(deftest identical-plaintext-does-not-imply-identical-cid
  (testing "ratchet IVs / chain keys advance — convergent encryption is forbidden"
    (async done
      (let [bob (x3dh/generate-identity)
            alice (x3dh/generate-identity)
            {:keys [public]} (sealed/publish bob)]
        (-> (js/Promise.all
             #js [(.then (sealed/initiate alice public)
                         (fn [s] (sealed/encrypt s {:text "same"})))
                  (.then (sealed/initiate alice public)
                         (fn [s] (sealed/encrypt s {:text "same"})))])
            (step (fn [pair]
                    (let [msg-a (nth (aget pair 0) 1)
                          msg-b (nth (aget pair 1) 1)]
                      (is (not= (:ciphertext msg-a) (:ciphertext msg-b)))
                      (is (not= (shape-cid msg-a) (shape-cid msg-b)))
                      (is (false? (proto/convergent-allowed?)))
                      (done)))))))))

(deftest plaintext-on-attachment-is-rejected
  (async done
    (let [bob (x3dh/generate-identity)
          alice (x3dh/generate-identity)]
      (-> (sealed/initiate alice (:public (sealed/publish bob)))
          (step (fn [alice-s]
                  (sealed/encrypt alice-s {:text "x"
                                           :attachments [{:cid file-cid
                                                          :file-key "k"
                                                          :plaintext "no"}]})))
          (step (fn [pair]
                  (is (= :plaintext-in-attachment (:error (nth pair 1))))
                  (done)))))))

(deftest receiver-cannot-send-before-first-decrypt
  (async done
    (let [bob (x3dh/generate-identity)]
      (-> (ratchet/init-receiver (js/Uint8Array. 32) (:spk bob))
          (step (fn [r]
                  (sealed/encrypt {:ok? true :role :responder :ratchet r}
                                  {:text "too soon"})))
          (step (fn [pair]
                  (is (= :cannot-send-before-receive (:error (nth pair 1))))
                  (done)))))))

(deftest tampered-header-n-is-rejected
  (async done
    (let [bob (x3dh/generate-identity)
          alice (x3dh/generate-identity)]
      (-> (sealed/initiate alice (:public (sealed/publish bob)))
          (step (fn [alice-s] (sealed/encrypt alice-s {:text "hello"})))
          (step (fn [pair]
                  (let [tampered (update-in (nth pair 1) [:header :n] inc)]
                    (-> (sealed/accept bob tampered)
                        (step (fn [_] (is false "tampered header :n must reject")))
                        (.catch (fn [_] (is true "tampered header :n correctly rejected")))))))
          (step (fn [_] (done)))))))

(deftest hop-is-not-this-construction
  (is (false? (proto/hop-is-e2ee?)))
  (is (false? (proto/dag-jose-is-ratchet?)))
  (is (true? (proto/e2ee-is-not-session-plane?))))
