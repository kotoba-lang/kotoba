(ns hata.test-runner
  (:require #?(:clj [clojure.test :as t] :cljs [cljs.test :as t])
            [hata.bundle-test]
            [hata.call-test]
            [hata.core-test]
            [hata.p3-test]
            [hata.receipt-test]
            [hata.ui-test]))

#?(:cljs
   (defmethod t/report [:cljs.test/default :end-run-tests] [m]
     (println (str "\nhata: " (:test m) " tests, " (:pass m) " passed, "
                   (:fail m) " failed, " (:error m) " errors"))
     (when (pos? (+ (or (:fail m) 0) (or (:error m) 0)))
       (set! (.-exitCode js/process) 1))))

(defn -main [& _]
  #?(:clj (let [result (t/run-tests 'hata.bundle-test 'hata.call-test 'hata.core-test 'hata.p3-test 'hata.receipt-test 'hata.ui-test)]
            (when (pos? (+ (:fail result) (:error result)))
              (System/exit 1)))
     :cljs (t/run-tests 'hata.bundle-test 'hata.call-test 'hata.core-test 'hata.p3-test 'hata.receipt-test 'hata.ui-test)))
