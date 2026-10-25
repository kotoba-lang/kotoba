(ns hata.call-test
  "D5: call API は形と admission の継ぎ目だけで、判定しない。
  形の拒否（未知 kind / interface pin なし / from・to・method なし）は fail closed、
  判定は注入した judge-fn に委ねられ、明示的な allow 以外は通さない。
  署名 entry は hata.ito に :commit として載る。"
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])
            [hata.call :as call]
            [hata.ito :as ito]))

(def cell-call
  {:hata.call/kind :cell-call
   :hata.call/from "did:key:z6Mkfrom"
   :hata.call/to "did:key:z6Mkto"
   :hata.call/interface-cid "bafyreiginterface000000000000000000000000000000000000"
   :hata.call/method "app/do-thing"
   :hata.call/params {:x 1}})

(deftest a-prepared-call-is-the-cell-cell-op
  (let [r (call/prepare cell-call)]
    (is (= :call (:ok r)))
    (is (= cell-call (:call r)))
    (is (empty? (call/problems cell-call)))
    (testing "only the declared keys ride the op"
      (is (= (set call/call-op-keys) (set (keys (:call r))))))))

(deftest bad-shapes-are-refused-and-named
  (doseq [[why op] [[:unknown-call-kind (assoc cell-call :hata.call/kind :fax)]
                    [:no-interface-pin (dissoc cell-call :hata.call/interface-cid)]
                    [:no-from-cell (dissoc cell-call :hata.call/from)]
                    [:no-to-cell (dissoc cell-call :hata.call/to)]
                    [:no-method (dissoc cell-call :hata.call/method)]
                    [:params-not-a-map (assoc cell-call :hata.call/params [1 2])]
                    [:call-op-not-a-map :not-a-map]]]
    (testing (str why)
      (let [probs (call/problems op)]
        (is (some #(= why (:problem %)) probs))
        (is (seq (:problems (call/prepare op))))
        (is (vector? (:problems (call/prepare op))))))))

(deftest the-api-decides-nothing
  (testing "no judge: refused (fail closed), never silently allowed"
    (let [r (call/admit (:call (call/prepare cell-call)) nil)]
      (is (false? (:ok? r)))
      (is (= :no-judgment (:reason r)))))
  (testing "the judge decides; anything but an explicit :allow is refused"
    (is (true? (:ok? (call/admit cell-call (constantly :allow)))))
    (let [r (call/admit cell-call (constantly :deny))]
      (is (false? (:ok? r)))
      (is (= :denied (:reason r)))
      (is (= :deny (:decision r)))))
  (testing "a bad shape never reaches the judge"
    (let [r (call/admit (dissoc cell-call :hata.call/interface-cid)
                        (constantly :allow))]
      (is (false? (:ok? r)))
      (is (= :bad-shape (:reason r))))))

(deftest an-admitted-call-rides-the-source-chain-as-a-commit
  (let [cid-fn (fn [action] (str "cid:" (:hata.action/kind action) ":" (:hata.action/prev action)))
        sign-fn (fn [author action] (str "sig:" author ":" (:hata.action/kind action)))
        seams {:cid-fn cid-fn :verify-fn (constantly true)}
        open-action {:hata.action/kind :open :hata.action/prev nil}
        open-entry {:author "did:key:z6Mkfrom" :signature "sig:did:key:z6Mkfrom::open"
                    :hata.action/action open-action}
        prev (ito/entry-cid cid-fn open-entry)
        entry (call/entry {:sign-fn sign-fn :cid-fn cid-fn} cell-call "did:key:z6Mkfrom" prev)
        opened (ito/append seams [] open-entry)
        chain (:ok opened)]
    (is (vector? chain))
    (is (= :commit (-> entry :hata.action/action :hata.action/kind)))
    (is (= cell-call (-> entry :hata.action/action :hata.action/op))
        "the op rides unmodified: the call API adds no judgment of its own")
    (testing "hata.ito accepts the entry on the chain"
      (is (empty? (ito/problems seams chain entry)))
      (is (vector? (:ok (ito/append seams chain entry)))))))
