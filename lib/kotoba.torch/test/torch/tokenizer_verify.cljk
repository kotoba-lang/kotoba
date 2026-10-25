(ns torch.tokenizer-verify
  (:require [torch.generate :as generate]
            [torch.tokenizer :as tokenizer]))

(defn byte-token [n]
  (str "<0x" (.toUpperCase (.padStart (.toString n 16) 2 "0")) ">"))

(defn -main [& _]
  (let [tokens (vec (concat ["<unk>" "<bos>" "<eos>" "h" "e" "l" "o"
                             "he" "ll" "hell" "hello"]
                            (map byte-token (range 256))))
        t (tokenizer/tokenizer
           {:tokens tokens :merges [["h" "e"] ["l" "l"] ["he" "ll"] ["hell" "o"]]
            :unk-id 0 :bos-id 1 :eos-id 2 :add-bos? true})
        fixtures ["hello" "猫🙂" "naïve café"]
        ok? (and (every? #(= % (tokenizer/decode t (tokenizer/encode t %))) fixtures)
                 (= 1 (generate/sample-token [0.1 2.0 1.5] {:temperature 0.0})))]
    (println "CLJS UTF-8 BPE tokenizer:" (if ok? "passed" "failed"))
    (when-not ok? (.exit js/process 1))))

(set! *main-cli-fn* -main)
