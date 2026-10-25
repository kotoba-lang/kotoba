(ns multiformats.sha-bench
  "How much does SHA-256 cost, compiled, and is a host digest identical?

  Ranked by measured wall clock, and the correctness gate comes FIRST: a
  digest that is faster and different is not a faster digest."
  (:require ["node:crypto" :as crypto]
            ["node:os" :as os]
            [multiformats.core :as mf]
            [sha2.core :as sha2]))

(defn- host-sha256 [^js b]
  (js/Uint8Array. (.digest (.update (crypto/createHash "sha256") b))))

(defn- same? [a b]
  (and (= (.-length a) (.-length b))
       (every? #(= (aget a %) (aget b %)) (range (.-length a)))))

(defn- median [xs] (nth (sort xs) (quot (count xs) 2)))

(defn- bench [label n f]
  (f)
  (let [ts (vec (for [_ (range n)]
                  (let [t0 (js/process.hrtime.bigint)]
                    (f)
                    (/ (js/Number (- (js/process.hrtime.bigint) t0)) 1e6))))]
    (println (str "  " label "  " (.toFixed (median ts) 4) " ms"))
    (median ts)))

(defn -main [& _]
  (println "compiled ClojureScript, node" (.-version js/process)
           "| load" (.toFixed (first (os/loadavg)) 1))
  (doseq [size [4795 384843]]
    (let [b (js/Uint8Array. size)]
      (dotimes [i size] (aset b i (bit-and (* i 7) 0xff)))
      (println (str "\n-- " size " bytes --"))
      ;; GATE. Ranking a digest that disagrees would be ranking a different
      ;; function, which is the easiest lie this kind of loop can tell.
      ;; `mf/sha256`, not `sha2/sha256`. multiformats converts with `byte-seq`
      ;; before it hands anything to the digest, so calling the inner function
      ;; with a typed array measures a path no caller takes -- the first
      ;; version of this file did exactly that and reported a defect that was
      ;; the harness's.
      (let [pure (mf/sha256 b) host (host-sha256 b)]
        (println (str "  identical to the host digest: " (same? pure host)))
        (when-not (same? pure host)
          (println "  REFUSING to rank: the two do not agree")
          (set! (.-exitCode js/process) 2)))
      (let [n (if (> size 100000) 20 200)
            p (bench "mf/sha256 (byte-seq)   " n #(mf/sha256 b))
            h (bench "node:crypto sha256    " n #(host-sha256 b))]
        (println (str "  ratio " (.toFixed (/ p h) 1) "x"))
        (bench "mf/cidv1-raw (portable)" (if (> size 100000) 20 200) #(mf/cidv1-raw b))
        ;; With the host digest installed -- the number a deployment that calls
        ;; `install-sha256!` actually pays. Installed inside the bench so the
        ;; two rows above are measured against an uninstalled library.
        (mf/install-sha256! host-sha256)
        (bench "mf/cidv1-raw (installed)" (if (> size 100000) 20 200) #(mf/cidv1-raw b))
        (mf/install-sha256! mf/portable-sha256)
        ;; Where does the pure path spend it? A seq materialisation is a small
        ;; fix (take the typed array as it is); a seq-shaped compression loop
        ;; is a rewrite. Ranking a fix before knowing which would be guessing
        ;; at the size of the work.
        (let [sq (vec (array-seq b))]
          (bench "  vec(array-seq b) only" n #(vec (array-seq b)))
          (bench "  sha2/sha256 on a vec " n #(sha2/sha256 sq)))))))
