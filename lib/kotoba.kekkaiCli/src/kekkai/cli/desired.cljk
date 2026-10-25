(ns kekkai.cli.desired
  "Portable Kekkai desired-state publisher/puller. This is the Node/nbb
  implementation of the JVM envelope and mirror contract; it never shells a
  Clojure runtime."
  (:require [cljs.reader :as reader]
            [kotoba.lang.text :as str]
            [ipns.core :as ipns]
            [kekkai.cli.sign :as sign]
            ["node:child_process" :as child]
            ["node:crypto" :as crypto]
            ["node:fs" :as fs]
            ["node:path" :as path]))

(def schema "kekkai.desired-state/v1")

(defn- canonical-compare [a b] (compare (pr-str a) (pr-str b)))

(defn canonical-value [value]
  (cond
    (map? value) (into (sorted-map-by canonical-compare)
                       (map (fn [[k v]] [(canonical-value k) (canonical-value v)])) value)
    (set? value) (into (sorted-set-by canonical-compare) (map canonical-value) value)
    (vector? value) (mapv canonical-value value)
    (list? value) (apply list (map canonical-value value))
    (sequential? value) (doall (map canonical-value value))
    :else value))

(defn canonical-bytes [value]
  (.from js/Buffer
         (binding [*print-namespace-maps* false]
           (pr-str (canonical-value value)))
         "utf8"))

(defn- base32 [bytes]
  (loop [xs (seq bytes) acc 0 bits 0 out ""]
    (cond
      (>= bits 5)
      (let [remaining (- bits 5)
            digit (bit-and 31 (unsigned-bit-shift-right acc remaining))
            mask (if (zero? remaining) 0 (dec (bit-shift-left 1 remaining)))]
        (recur xs (bit-and acc mask) remaining
               (str out (.charAt "abcdefghijklmnopqrstuvwxyz234567" digit))))
      xs (recur (next xs) (bit-or (bit-shift-left acc 8) (first xs)) (+ bits 8) out)
      (pos? bits) (str out (.charAt "abcdefghijklmnopqrstuvwxyz234567"
                                  (bit-and 31 (bit-shift-left acc (- 5 bits)))))
      :else out)))

(defn cid [bytes]
  (let [digest (.digest (.update (.createHash crypto "sha256") bytes))]
    (str "b" (base32 (concat [1 85 18 32] digest)))))

(defn- public-key [public-b64]
  (.createPublicKey crypto #js {:key (.from js/Buffer public-b64 "base64")
                                :format "der" :type "spki"}))

(defn- ipns-name [public-b64]
  (let [spki (.from js/Buffer public-b64 "base64")
        raw (.subarray spki (- (.-length spki) 32))]
    (ipns/pubkey->name (vec raw))))

(defn seal [{:keys [kind subject epoch previous-cid payload]} identity]
  (when-not (and (keyword? kind) (string? subject) (not (str/blank? subject))
                 (int? epoch) (pos? epoch))
    (throw (ex-info "desired input needs keyword :kind, non-empty :subject, and positive :epoch"
                    {:type :kekkai/invalid-desired-input})))
  (let [payload-bytes (canonical-bytes payload)
        statement {:desired/schema schema :desired/kind kind
                   :desired/subject subject :desired/name (ipns-name (:public-b64 identity))
                   :desired/epoch epoch :desired/previous-cid previous-cid
                   :desired/payload-cid (cid payload-bytes)
                   :desired/payload-b64 (.toString payload-bytes "base64")}
        bytes (canonical-bytes statement)
        signature (.sign crypto nil bytes (sign/private-key (:private-b64 identity)))]
    {:desired/cid (cid bytes)
     :desired/statement-b64 (.toString bytes "base64")
     :desired/signature-b64 (.toString signature "base64")
     :desired/signer-spki-b64 (:public-b64 identity)}))

(defn verify [envelope authority {:keys [kind subject min-epoch previous-cid]}]
  (let [{:desired/keys [cid statement-b64 signature-b64 signer-spki-b64]} envelope]
    (when-not (= authority signer-spki-b64)
      (throw (ex-info "desired state signer is not the configured authority"
                      {:type :kekkai/untrusted-desired-signer})))
    (let [bytes (.from js/Buffer statement-b64 "base64")]
      (when-not (= cid (kekkai.cli.desired/cid bytes))
        (throw (ex-info "desired state CID mismatch" {:type :kekkai/desired-cid-mismatch})))
      (when-not (.verify crypto nil bytes (public-key signer-spki-b64)
                         (.from js/Buffer signature-b64 "base64"))
        (throw (ex-info "desired state signature invalid"
                        {:type :kekkai/desired-signature-invalid})))
      (let [statement (reader/read-string (.toString bytes "utf8"))
            payload-bytes (.from js/Buffer (:desired/payload-b64 statement) "base64")
            payload (reader/read-string (.toString payload-bytes "utf8"))]
        (when-not (and (= schema (:desired/schema statement))
                       (= (:desired/name statement) (ipns-name signer-spki-b64))
                       (= (:desired/payload-cid statement)
                          (kekkai.cli.desired/cid payload-bytes)))
          (throw (ex-info "desired state derived identity mismatch"
                          {:type :kekkai/desired-integrity-mismatch})))
        (when (and kind (not= kind (:desired/kind statement)))
          (throw (ex-info "desired state kind mismatch" {:type :kekkai/desired-kind-mismatch})))
        (when (and subject (not= subject (:desired/subject statement)))
          (throw (ex-info "desired state subject mismatch" {:type :kekkai/desired-subject-mismatch})))
        (when (and min-epoch (< (:desired/epoch statement) min-epoch))
          (throw (ex-info "desired state epoch rollback" {:type :kekkai/desired-epoch-rollback})))
        (when (and previous-cid (not= previous-cid (:desired/previous-cid statement)))
          (throw (ex-info "desired state chain mismatch" {:type :kekkai/desired-chain-mismatch})))
        (assoc statement :desired/cid cid :desired/payload payload)))))

(defn subject-key [subject] (cid (.from js/Buffer subject "utf8")))
(defn- block-rel [c] (str "blocks/" c ".edn"))
(defn- head-rel [s] (str "heads/" (subject-key s) ".edn"))

(defn- remote-root [root]
  (when (str/starts-with? root "ssh://")
    (let [[_ host p] (re-matches #"ssh://([^/]+)(/.*)" root)]
      (when-not (and host p
                     (re-matches #"(?:[A-Za-z0-9._-]+@)?[A-Za-z0-9._-]+" host)
                     (re-matches #"[A-Za-z0-9._/-]+" p)
                     (not (str/includes? p "..")))
        (throw (ex-info "invalid ssh desired-state mirror root"
                        {:type :kekkai/invalid-ssh-mirror :root root})))
      {:host host :base (str/replace p #"/+$" "")})))

(defn- ssh! [host command input]
  (let [result (.spawnSync child "ssh" #js [host command]
                           #js {:input input :encoding "utf8"})]
    (when-not (zero? (.-status result))
      (throw (ex-info "ssh desired-state mirror operation failed"
                      {:type :kekkai/ssh-mirror-failed :host host
                       :exit (.-status result) :stderr (.-stderr result)})))
    (.-stdout result)))

(defn read-root [root rel]
  (if-let [{:keys [host base]} (remote-root root)]
    (ssh! host (str "cat " base "/" rel) nil)
    (.readFileSync fs (.join path root rel) "utf8")))

(defn write-root! [root rel text]
  (if-let [{:keys [host base]} (remote-root root)]
    (let [target (str base "/" rel) parent (.dirname path target)
          tmp (str target ".tmp-" (.randomUUID crypto))]
      (ssh! host (str "mkdir -p " parent " && cat > " tmp " && mv " tmp " " target) text))
    (let [target (.join path root rel) parent (.dirname path target)
          tmp (str target ".tmp-" (.randomUUID crypto))]
      (.mkdirSync fs parent #js {:recursive true})
      (.writeFileSync fs tmp text)
      (.renameSync fs tmp target))))

(defn- maybe-head [root subject]
  (try (reader/read-string (read-root root (head-rel subject)))
       (catch :default _ nil)))

(defn publish! [roots min-copies envelope authority]
  (let [verified (verify envelope authority {})
        head {:desired/cid (:desired/cid verified) :desired/name (:desired/name verified)
              :desired/subject (:desired/subject verified) :desired/epoch (:desired/epoch verified)}
        results (mapv
                 (fn [root]
                   (try
                     (when-let [old (maybe-head root (:desired/subject verified))]
                       (when (or (< (:desired/epoch head) (:desired/epoch old))
                                 (and (= (:desired/epoch head) (:desired/epoch old))
                                      (not= (:desired/cid head) (:desired/cid old))))
                         (throw (ex-info "desired mirror head would rewind or conflict"
                                         {:type :kekkai/desired-head-conflict}))))
                     (write-root! root (block-rel (:desired/cid verified))
                                  (binding [*print-namespace-maps* false] (pr-str envelope)))
                     (write-root! root (head-rel (:desired/subject verified))
                                  (.toString (canonical-bytes head) "utf8"))
                     {:root root :ok? true}
                     (catch :default e
                       {:root root :ok? false :error (ex-message e)
                        :error-type (:type (ex-data e))}))) roots)
        copies (count (filter :ok? results))]
    (when (< copies min-copies)
      (throw (ex-info "desired state did not reach mirror quorum"
                      {:type :kekkai/desired-mirror-quorum :required min-copies
                       :copies copies :results results})))
    {:desired/cid (:desired/cid verified) :desired/epoch (:desired/epoch verified)
     :desired/name (:desired/name verified) :desired/copies copies :desired/results results}))

(defn pull [roots subject authority opts]
  (let [heads (keep (fn [root]
                      (try (assoc (reader/read-string (read-root root (head-rel subject)))
                                  :root root)
                           (catch :default _ nil))) roots)]
    (when-not (seq heads)
      (throw (ex-info "no desired state mirror is readable"
                      {:type :kekkai/desired-unavailable})))
    (let [epoch (apply max (map :desired/epoch heads))
          latest (filter #(= epoch (:desired/epoch %)) heads)
          cids (set (map :desired/cid latest))]
      (when-not (= 1 (count cids))
        (throw (ex-info "desired state mirrors disagree at the same epoch"
                        {:type :kekkai/desired-split-brain :epoch epoch :cids cids})))
      (let [c (first cids)
            envelope (some (fn [{:keys [root]}]
                             (try (reader/read-string (read-root root (block-rel c)))
                                  (catch :default _ nil))) latest)]
        (when-not envelope
          (throw (ex-info "desired head has no readable block"
                          {:type :kekkai/desired-block-unavailable})))
        (verify envelope authority (merge {:subject subject :min-epoch epoch} opts))))))

(defn roots [csv]
  (->> (str/split (or csv "") #",") (map str/trim) (remove str/blank?) distinct vec))

(defn authority [value]
  (if (.existsSync fs value)
    (:public-b64 (reader/read-string (.readFileSync fs value "utf8")))
    value))

(defn publish-command [{:keys [input authority-file roots-csv min-copies]}]
  (let [identity (reader/read-string (.readFileSync fs authority-file "utf8"))
        desired-input (reader/read-string (.readFileSync fs input "utf8"))
        rs (roots roots-csv)
        result (publish! rs (or min-copies (count rs)) (seal desired-input identity)
                         (:public-b64 identity))]
    (println (binding [*print-namespace-maps* false]
               (pr-str (assoc result :desired/authority-spki-b64 (:public-b64 identity)))))
    result))

(defn pull-command [{:keys [subject authority-value roots-csv min-epoch kind]}]
  (let [result (pull (roots roots-csv) subject (authority authority-value)
                     (cond-> {} min-epoch (assoc :min-epoch min-epoch)
                       kind (assoc :kind (keyword kind))))]
    (println (binding [*print-namespace-maps* false] (pr-str result)))
    result))
