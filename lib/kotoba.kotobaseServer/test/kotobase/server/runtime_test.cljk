(ns kotobase.server.runtime-test
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing] :include-macros true])
            [kotobase.server.runtime :as runtime]))

(deftest private-runtime-requires-every-security-port
  (testing "missing authority/KMS/audit/claim services fail closed"
    (try
      (runtime/validate-services :private {:block-store :blocks
                                           :head-store :heads})
      (is false "validation must throw")
      (catch #?(:clj Exception :cljs :default) e
        (is (= :runtime/missing-services (:type (ex-data e))))
        (is (= [:audit-sink :authority-registry :claim-store :key-unwrapper]
               (:missing (ex-data e)))))))
  (is (= 6 (count (runtime/validate-services
                   :sealed
                   {:block-store :blocks :head-store :heads :claim-store :claims
                    :authority-registry :authority :key-unwrapper :kms
                    :audit-sink :audit})))))

(deftest public-runtime-keeps-platform-details-outside-common-config
  (is (= {:block-store :blocks :head-store :heads}
         (runtime/validate-services :public
                                    {:block-store :blocks :head-store :heads})))
  (is (false? (runtime/deployment-values? {:security-mode :private})))
  (is (runtime/deployment-values? {:bucket-name "product-bucket"})))
