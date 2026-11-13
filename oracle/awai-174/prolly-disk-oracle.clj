;; 2026-11-13 local JVM reference measurement only; not a Native execution path.
(require '[clojure.edn :as edn] '[clojure.java.io :as io]
         '[kotobase.engine.prolly :as prolly] '[kotobase.engine.contract :as eng]
         '[datom.source :as source] '[datalog.core :as datalog])
(import '[java.nio.file Files Paths StandardOpenOption OpenOption]
        '[java.security MessageDigest] '[java.util Arrays HexFormat])
(def root (second *command-line-args*))
(defn path [name] (Paths/get root (into-array String [name])))
(defn hex [b] (.formatHex (HexFormat/of) b))
(defn sha [s] (hex (.digest (MessageDigest/getInstance "SHA-256") (.getBytes (str s) "UTF-8"))))
(defn put-block [cid b]
  (when-not (re-matches #"b[a-z2-7]+" cid) (throw (ex-info "bad CID path" {})))
  (let [p (path (str cid ".block"))]
    (if (Files/exists p (make-array java.nio.file.LinkOption 0))
      (when-not (Arrays/equals ^bytes b (Files/readAllBytes p)) (throw (ex-info "collision" {})))
      (Files/write p ^bytes b (into-array OpenOption [StandardOpenOption/CREATE_NEW StandardOpenOption/WRITE])))))
(defn get-block [cid]
  (when-not (re-matches #"b[a-z2-7]+" cid) (throw (ex-info "bad CID path" {})))
  (let [p (path (str cid ".block"))] (when (Files/exists p (make-array java.nio.file.LinkOption 0)) (Files/readAllBytes p))))
(defn engine [] (prolly/prolly-engine {:put! put-block :get-fn get-block :blind-fn #(str "blind-fixture:" %) :encrypt-fn identity :decrypt-fn identity :digest-fn sha}))
(defn datalog-source [engine snapshot]
  (reify source/IPatternSource
    (-scan [_ pattern] (mapv (fn [{:keys [e a v]}] {:s e :p a :o v}) (eng/scan engine snapshot pattern)))))
(def query '{:find [?root ?cid] :where [["file" :file/root ?root] ["file" :file/chunk ?c] [?c :chunk/index 8] [?c :chunk/cid ?cid]]})
(def logical-root "bafyreidqkmghsd65dwq22umpkrqecyamfhevsbq7xemjfe7tb6wnhvxsny")
(def chunk-cid "bafkreidxq3azg4pwxcuurzkrmjha3uuzhstmefbzx6dw6z5bjaqya64mra")
(case (first *command-line-args*)
 "write"
 (do (Files/createDirectory (Paths/get root (make-array String 0)) (make-array java.nio.file.attribute.FileAttribute 0))
     (let [e (engine) s0 (eng/empty-state e "oracle/db")
           r1 (eng/transact e s0 {:database-id "oracle/db" :request-id "tx1" :tx-data [[:db/add "file" :file/root logical-root] [:db/add "file" :file/chunk "chunk-8"] [:db/add "chunk-8" :chunk/index 8] [:db/add "chunk-8" :chunk/cid chunk-cid] [:db/add "file" :file/name "before"]]})
           r2 (eng/transact e (:state r1) {:database-id "oracle/db" :request-id "tx2" :tx-data [[:db/retract "file" :file/name "before"] [:db/add "file" :file/name "after"]]})
           meta {:root1 (get-in r1 [:receipt :physical-root]) :root2 (get-in r2 [:receipt :physical-root])}]
       (spit (str (path "basis.edn")) (pr-str meta))
       (prn {:phase :write :roots meta :block-count (count (filter #(.endsWith (.getName %) ".block") (.listFiles (io/file root))))})))
 "read"
 (let [{:keys [root1 root2]} (edn/read-string (slurp (str (path "basis.edn")))) e (engine)
       s (eng/restore-state e root2) snap (eng/open-snapshot e s) old (eng/open-snapshot e s {:as-of 1})
       rows (datalog/q (datalog-source e snap) query (constantly true))
       hidden (datalog/q (datalog-source e snap) query #(not= (:p %) :chunk/cid))
       before (mapv :v (eng/scan e old ["file" :file/name nil]))
       after (mapv :v (eng/scan e snap ["file" :file/name nil]))]
   (when-not (and (= #{[logical-root chunk-cid]} rows) (empty? hidden) (= ["before"] before) (= ["after"] after))
     (throw (ex-info "incorrect persistent query" {:rows rows :hidden hidden :before before :after after})))
   (prn {:phase :read :basis root2 :query rows :visibility-denial (empty? hidden) :as-of before :current after :pass true}))
 (throw (ex-info "expected write or read" {})))
