(ns etzhayyim.social.publication
  "Shared, actor-neutral social publication membrane.

  Actor identity and prose are configuration. Provenance, non-adjudication,
  no-server-key, and dry-run-only behavior are library invariants."
  (:require [kotoba.lang.text :as str]))

(def disclaimer-prefix
  "【観測ミラー / accountability map — NOT a verdict, NOT advice, 非断定】")

(def phase-init "init")
(def phase-drafted "drafted")
(def phase-refused "refused")

(defn- require-config
  [{:keys [actor-id display-name] :as config}]
  (when (str/blank? (str actor-id))
    (throw (ex-info "social publication config requires :actor-id" {:config config})))
  (when (str/blank? (str display-name))
    (throw (ex-info "social publication config requires :display-name" {:config config})))
  config)

(defn disclaimer
  [config]
  (let [{:keys [display-name]} (require-config config)]
    (str disclaimer-prefix " " display-name " が既知の観測から編んだ事実の要約です。")))

(defn distinct-citations
  "provenance の実体。空白だけの出典を落とし、**同じ出典の重複を 1 件に畳む**。

  ≥ 2 という閾値は「ひとつの主張が複数の出所に支えられている」ことを言う
  ために在る。同じ出典を 2 回引いた投稿は出所が 1 つなので、裏付けは何も増えて
  いないのに閾値を数の上でだけ満たし、本文で『出典 2 件』と名乗れてしまう ——
  空白出典と同じ形で、**数が合っているように見えるぶん外から気づけない**。

  畳む単位は trim 後の文字列。前後の空白だけが違う 2 つは同じ出所であって、
  空白は provenance ではない。記録に残すのは最初に現れた形（呼び手が渡した形）。

  **この関数が provenance 規則の唯一の実装であること。** `enough-sources`（例外で
  拒む経路）と `transition-to-drafted`（拒否 cell を返す経路）の両方がここを
  呼ぶ—— 規則を 2 箇所に書くと、片方だけを直したときもう一方が黙って古いまま残る。"
  [sources]
  (->> (or sources [])
       (filter #(seq (str/trim (str %))))
       (reduce (fn [acc s]
                 (let [k (str/trim (str s))]
                   (if (contains? (:seen acc) k)
                     acc
                     (-> acc (update :seen conj k) (update :out conj s)))))
               {:seen #{} :out []})
       :out
       vec))

(defn enough-sources
  [sources]
  (let [citations (distinct-citations sources)]
    (when (< (count citations) 2)
      (throw (ex-info "source-provenance: a post needs ≥ 2 distinct citations"
                      {:citations citations})))
    citations))

(defn draft-observation-post
  ([config subject body sources]
   (draft-observation-post config subject body sources ""))
  ([config subject body sources author]
   (let [citations (enough-sources sources)]
     {":post/subject" subject
      ":post/body" (str (disclaimer config) "\n\n" body
                        " 出典 " (count citations) " 件。")
      ":post/status" ":dry-run"
      ":post/is-mirror" true
      ":post/non-adjudicating-notice" true
      ":post/server-held-key" false
      ":post/author" author
      ":post/sources" citations})))

(defn build-live
  [config & _args]
  (let [{:keys [actor-id]} (require-config config)]
    (throw
     (ex-info
      (str actor-id
           " R0: live social posting is Council Lv6+ + operator + "
           "member/actor-signature gated. Only dry-run posts are producible "
           "offline; signing happens actor-side, never with a server key.")
      {:actor-id actor-id :status :refused}))))

(def state-defaults
  {"phase" phase-init
   "subject" ""
   "sources" []
   "requested_status" "dry-run"
   "server_held_key" false
   "payload" {}
   "refusal" ""})

(defn- cell-state [state]
  (merge state-defaults (get state "cell_state" {})))

(defn- without-leading-colon [value]
  (str/replace (str value) #"^:+" ""))

(defn- server-key-claimed?
  "no-server-key の判定。**真理値 `true` だけを鍵とみなさない。**

  `state` はキーが全部文字列の wire 形で届くので、値も文字列で届きうる ——
  `\"true\"` を `true?` で見ると素通りする。nil/false 以外はすべて鍵の主張と
  みなして拒否側に倒す。"
  [value]
  (boolean value))

(defn transition-to-drafted
  [config state]
  (let [current (cell-state state)
        next-state
        (assoc current
               "subject" (get state "subject" (get current "subject"))
               "sources" (get state "sources" (get current "sources"))
               "requested_status"
               (without-leading-colon
                (get state "requested_status" (get current "requested_status")))
               "server_held_key"
               (server-key-claimed?
                (get state "server_held_key" (get current "server_held_key"))))
        ;; payload を落とすのは「拒否とは作らなかったことである」から。
        ;; next-state は渡された cell_state を引き継ぐので、前回 drafted で
        ;; 作った payload がそのまま残る —— phase を見ない呼び手は、いま
        ;; 拒否されたはずの下書きをそこから publish できてしまう。
        refuse (fn [message]
                 {"cell_state"
                  (assoc next-state
                         "refusal" message
                         "payload" {}
                         "phase" phase-refused)})]
    (cond
      (< (count (distinct-citations (get next-state "sources"))) 2)
      (refuse "source-provenance: a post needs ≥ 2 distinct citations")

      (get next-state "server_held_key")
      (refuse "no-server-key: server-held-key must be false")

      (not= "dry-run" (get next-state "requested_status"))
      (refuse "R0-gate: only dry-run posts")

      :else
      {"cell_state"
       (assoc next-state
              "payload"
              (draft-observation-post
               config
               (get next-state "subject")
               ""
               (get next-state "sources"))
              "refusal" ""
              "phase" phase-drafted)})))
