(ns hata.rebuild-test
  "P3 合否条件 (4) — bundle CID から再構築。実 digest と実 CAR で測る。

    kbb --backend sci --classpath \\
      src:test:../io-ipld-car/src:../io-ipld/src:../io-multiformats/src:../bytes/src:../coll/src:../edn/src:../error/src:../hash/src:../io/src:../pprint/src:../text/src \\
      test/hata/rebuild_runner.cljk

  この ns は codec が classpath に無いと読めない — それでよい。CID と CAR の
  ない「再構築できた」は、この repo が測ってはいけない種類の主張だから。"
  (:require [cljs.test :refer [deftest is testing]]
            [hata.bundle :as bundle]
            [hata.conductor :as conductor]
            [ipld.car.v2 :as car]
            [ipld.core :as ipld]))

;; ------------------------------------------------------- real artifacts
;;
;; IPLD map keys are strings — the wire form is string-keyed, and the parse
;; seam below keywordizes exactly the manifest keys hata reads.

(def mon-node
  "A real 紋 in the abi schema shape (ADR-2610082200 §3), wire form."
  {"rules" ["bafkreib76wmaln52547xmqh3f3qonsxuzujvhctwppvjxegwfyvavesgli"]
   "entry-types" {"greeting" "bafkreicawgyinhnv7dh6bgvubcbx32vls4l6z7zxegh7oyxkebzkuuaymu"}
   "properties" {"title-limit" 256}
   "network-seed" "hello-net"
   "membrane" "bafkreib76wmaln52547xmqh3f3qonsxuzujvhctwppvjxegwfyvavesgli"})

(def logic-node {"kind" "entry" "entry" "greeting" "pure" true})
(def ui-node {"entry" "index.html" "html" "<html><body>itonami hello</body></html>"})

(def mon-block (ipld/node->block mon-node))
(def logic-block (ipld/node->block logic-node))
(def ui-block (ipld/node->block ui-node))

(def manifest-node
  {"kotoba.app/id" "itonami-hello"
   "kotoba.app/kind" "app"
   "kotoba.app/did" "did:key:z6MkApp"
   "kotoba.app/roles" [{"role" "hello"
                        "mon" (:cid mon-block)
                        "logic" [(:cid logic-block)]
                        "clone-limit" 0}]
   "kotoba.app/ui" {"bundle" (:cid ui-block) "entry" "index.html"}})

(def manifest-block (ipld/node->block manifest-node))
(def all-blocks [mon-block logic-block ui-block manifest-block])

(def packed (car/pack {:roots [(:cid manifest-block)] :blocks all-blocks}))

;; ------------------------------------------------------------- real seams

(defn- kw-manifest
  "Wire → in-memory: keywordize exactly the manifest keys hata reads."
  [m]
  {:kotoba.app/id (get m "kotoba.app/id")
   :kotoba.app/kind (get m "kotoba.app/kind")
   :kotoba.app/did (get m "kotoba.app/did")
   :kotoba.app/bundle-cid (get m "kotoba.app/bundle-cid")
   :kotoba.app/roles (mapv (fn [r] {:role (get r "role")
                                    :mon (get r "mon")
                                    :logic (get r "logic")
                                    :clone-limit (get r "clone-limit")})
                           (get m "kotoba.app/roles"))
   :kotoba.app/ui {:bundle (get-in m ["kotoba.app/ui" "bundle"])
                   :entry (get-in m ["kotoba.app/ui" "entry"])}})

(defn car->bundle
  "The parse seam, for real: CAR bytes → the logical bundle. The CAR root
  must be the manifest's own CID — that is what 'opened from the bundle CID'
  means."
  [bytes]
  (let [{:keys [roots blocks]} (car/read-all bytes)
        entries (into {} blocks)
        manifest-block (get entries (first roots))]
    (when manifest-block
      {:bundle/cid (first roots)
       :bundle/manifest (kw-manifest (ipld/decode manifest-block))
       :bundle/entries entries})))

(def ok-receipt
  "kototama.vm/receipt-v1 の形を満たす最小の receipt（loopback demo 共用）。"
  {:machine-spec "kototama.vm/1" :implementation "loopback-stub" :profile :core/v1
   :message-cid "bafyMsg" :program-cid "bafyProg"
   :state-before "bafyS0" :state-after "bafyS1"
   :outcome :ran :fuel-used 1 :events []
   :authority-decision {:manifest-cid "bafyM" :grant-ids []
                        :policy-id "p1" :world :w :epoch 1}})

(def real-seams
  {:digest-fn ipld/cid
   :cid-fn ipld/cid
   :sign-fn (fn [author action] (str "sig:" author ":" (hash action)))
   :verify-fn (fn [author action signature] (= signature (str "sig:" author ":" (hash action))))
   :device-key "device-1"
   :membrane-check-fn (constantly true)
   :fetch-fn (fn [app-did] (when (= app-did "did:key:z6MkApp") (:bytes packed)))
   :parse-bundle-fn car->bundle
   :host-fn (fn [cell call] {:host :ran :call call})})

;; ------------------------------------------------------------------- P3 (4)

(deftest the-real-cids-hold
  (is (= [] (bundle/problems real-seams (car->bundle (:bytes packed)))))
  (is (= [(:cid manifest-block)] (:roots (car/read-all (:bytes packed))))))

(defn same-bytes?
  "cljs `=` on Uint8Arrays is identity and `seq` is unreliable on typed
  arrays here — go through js/Array.from."
  [a b]
  (= (vec (js/Array.from a)) (vec (js/Array.from b))))

(deftest the-bundle-rebuilds-to-the-same-root
  (let [read (car/read-all (:bytes packed))
        entries (into {} (:blocks read))
        repacked (car/pack {:roots [(:cid manifest-block)]
                            :blocks (mapv (fn [cid] {:cid cid :bytes (get entries cid)})
                                          [(:cid mon-block) (:cid logic-block)
                                           (:cid ui-block) (:cid manifest-block)])})]
    ;; 合否条件 (4): rebuilt from what the CID named, the root is the same
    ;; CID and every artifact is the same bytes.
    (is (= (:roots (car/read-all (:bytes packed)))
           (:roots (car/read-all (:bytes repacked)))))
    (is (same-bytes? (:bytes mon-block) (get entries (:cid mon-block))))
    (is (same-bytes? (:bytes ui-block) (get entries (:cid ui-block))))
    (is (same-bytes? (:bytes logic-block) (get entries (:cid logic-block))))
    (is (same-bytes? (:bytes manifest-block) (get entries (:cid manifest-block))))))

(deftest the-app-opens-from-the-real-bundle
  (let [m (conductor/resident real-seams)
        opened (conductor/open-bundle! m "did:key:z6MkApp")]
    (is (= [(:cid mon-block) "device-1"] (:ok opened)))
    ;; the role's 紋 is the real mon cid
    (is (= (:cid mon-block)
           (get-in opened [:bundle :manifest :kotoba.app/roles 0 :mon])))
    (let [cell (get @(:cells m) (:ok opened))
          genesis (first (:hata.cell/ito cell))]
      (is (= {:app-did "did:key:z6MkApp" :bundle-cid (:cid manifest-block)}
             (get-in genesis [:hata.action/action :hata.action/body]))))))

(deftest a-real-tamper-is-refused
  (let [tampered (car->bundle (:bytes packed))
        ;; swap the 紋's bytes for the UI's: valid bytes, wrong CID mapping
        entries (assoc (:bundle/entries tampered) (:cid mon-block) (:bytes ui-block))
        m (conductor/resident (assoc real-seams
                                     :parse-bundle-fn (constantly
                                                       {:bundle/cid (:cid manifest-block)
                                                        :bundle/manifest (:bundle/manifest tampered)
                                                        :bundle/entries entries})))]
    (is (= [{:problem :digest-mismatch :cid (:cid mon-block)}]
           (:problems (conductor/open-bundle! m "did:key:z6MkApp"))))
    (is (empty? @(:cells m)))))
