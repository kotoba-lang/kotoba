(ns kuro.session
  "session を terminal (tmux/Zellij 相当) から切り離して保持する。

  ## なぜ要るのか

  `kuro.stream` は 1 実行の値で、`kuro.checkpoint` はそれを死なせる。
  しかし「強制終了しても session に戻る」という要求は、1 実行の保存では
  足りない —— 複数の実行が走ったまま、見ている窓 (attachment) だけが
  死ぬ。terminal emulator が死んでも shell が生きているのは、
  **実行の寿命と窓の寿命が別**だから。この名前空間はその分離を値で持つ:

      registry = sessions (実行の集合) + attachments (見ている窓の集合)

  ## モデル

  stream は実行の寿命。attachment は窓の寿命。attach/detach は
  **stream を一切書き換えない** —— 窓が外れても出力は溜まり続ける
  (tmux で detach してもコマンドが走り続けるのと同じ)。

  ## 復元は「生きていないことを正直に」

  checkpoint から戻した stream は `:orphaned` (`kuro.checkpoint/restore`
  の規約)。registry も同じ規約を踏む —— 復元された attachment は
  stream が running でも**生きている窓ではない** (`:suspended`)。

  ## 純粋

  `.cljc`、IO・時計・PRNG 無し。pid / cwd / 時刻は host が値として渡す。"
  (:require [kotoba.lang.text :as str]
            [kuro.checkpoint :as cp]
            [kuro.stream :as stream]))

(defn- no-self-name [name]
  (when (str/blank? (str name))
    (throw (ex-info "session name must not be blank" {:name name}))))

(defn- no-self-dup [m k kind]
  (when (contains? m k)
    (throw (ex-info (str kind " already exists: " k) {kind k}))))

(defn registry
  "空の registry。opts `:sessions` / `:attachments` で初期値を足せる
  (checkpoint 復元用)。"
  ([] (registry {}))
  ([opts]
   {:kuro.registry/sessions (or (:sessions opts) {})
    :kuro.registry/attachments (or (:attachments opts) {})}))

(defn spawn
  "registry に実行を登録する。`stream` は `kuro.stream/open` の戻り値
  (`:running` であること)。

  spawn は実行を登録するだけで、stream の書き込みは `kuro.stream` の
  既存手順 (`append-chunk` / `finish`) のまま —— registry は stream を
  包むだけで奪わない。"
  [reg name stream]
  (no-self-name name)
  (no-self-dup (:kuro.registry/sessions reg) name :session)
  (when-not (stream/running? stream)
    (throw (ex-info "spawn requires a :running stream"
                    {:name name :state (:kuro/state stream)})))
  (assoc-in reg [:kuro.registry/sessions name]
            {:kuro.session/name name
             :kuro.session/stream stream}))

(defn attach
  "窓を session に付ける。窓は「どこまで読んだか」を持つ —
  read は `:kuro/seq` の単調増加を使って 1 回だけ同じ chunk を渡す。"
  [reg window-id name]
  (no-self-name window-id)
  (no-self-dup (:kuro.registry/attachments reg) window-id :attachment)
  (let [s (get (:kuro.registry/sessions reg) name ::absent)]
    (when (= s ::absent)
      (throw (ex-info (str "no such session: " name) {:session name})))
    (assoc-in reg [:kuro.registry/attachments window-id]
              {:kuro.attachment/id window-id
               :kuro.attachment/session name
               :kuro.attachment/state :attached
               :kuro.attachment/seq (dec (get-in s [:kuro.session/stream :kuro/seq]))})))

(defn detach
  "窓を外す。**stream は書き換えない** — 実行は走り続ける。"
  [reg window-id]
  (let [a (get (:kuro.registry/attachments reg) window-id ::absent)]
    (when (= a ::absent)
      (throw (ex-info (str "no such attachment: " window-id) {:attachment window-id})))
    (assoc-in reg [:kuro.registry/attachments window-id :kuro.attachment/state] :detached)))

(defn read-out
  "attachment に届いた出力の未読分を返す。`[attachment' chunks]`。
  attachment' は cursor (`:kuro.attachment/seq`) を進めた値 — **これを次の
  registry に使うのは呼び出し側** (state in/out 規約。read は reg を
  書き換えない)。同じ chunk は二度渡さない。"
  [reg window-id]
  (let [a (get (:kuro.registry/attachments reg) window-id ::absent)]
    (when (= a ::absent)
      (throw (ex-info (str "no such attachment: " window-id)
                      {:attachment window-id})))
    (let [session (get a :kuro.attachment/session)
          cursor (get a :kuro.attachment/seq 0)
          entry (get (:kuro.registry/sessions reg) session ::absent)]
      (when (= entry ::absent)
        (throw (ex-info (str "attachment points at no session: " session)
                        {:attachment window-id :session session})))
      (let [st (get entry :kuro.session/stream)
            fresh (filter #(> (:kuro/seq %) cursor) (:kuro/chunks st))
            next-seq (if (seq fresh) (:kuro/seq (last fresh)) cursor)]
        [(assoc a :kuro.attachment/seq next-seq) fresh]))))

(defn reattach
  "dead な窓を新しい窓として同じ session に付け直す。
  cursor は前の窓の読み取り位置を引き継ぐ — detach 中に溜まった出力は
  新しい窓の最初の read で届く。元の窓は消さない —
  「前の窓がここまで読んだ」という証跡は残す。"
  [reg old-window-id new-window-id]
  (let [a (get (:kuro.registry/attachments reg) old-window-id ::absent)]
    (when (= a ::absent)
      (throw (ex-info (str "no such attachment: " old-window-id)
                      {:attachment old-window-id})))
    (-> (attach reg new-window-id (:kuro.attachment/session a))
        (assoc-in [:kuro.registry/attachments new-window-id :kuro.attachment/seq]
                  (:kuro.attachment/seq a)))))

(defn kill
  "session を落とす。`result` は host が測った終了値。内部の stream を
  `kuro.stream/finish` で閉じ、receipt を返す。**registry から消さない** —
  終わった実行の receipt は台帳の一部。"
  [reg name result]
  (let [s (get (:kuro.registry/sessions reg) name ::absent)]
    (when (= s ::absent)
      (throw (ex-info (str "no such session: " name) {:session name})))
    (let [receipt (stream/finish (:kuro.session/stream s) result)]
      [(assoc-in reg [:kuro.registry/sessions name :kuro.session/stream]
                 (stream/mark-finished (:kuro.session/stream s)))
       receipt])))

(defn session-states
  "name → stream state の一覧。監査と checkpoint の対象選びに使う。
  (plain map — キー型を混ぜないための sorted は呼び出し側の関心)"
  [reg]
  (into {}
        (map (fn [[n s]] [n (get-in s [:kuro.session/stream :kuro/state])]))
        (:kuro.registry/sessions reg)))

(defn ->edn
  "registry を保存できる EDN 値にする。stream 部分は `kuro.checkpoint/->edn`
  の形に委譲する — 保存形式を二重に持たない。"
  [reg]
  {::version 1
   ::sessions
   (into {}
         (map (fn [[n s]]
                [n (update s :kuro.session/stream cp/->edn)]))
         (:kuro.registry/sessions reg))
   ::attachments (:kuro.registry/attachments reg)})

(defn restore
  "checkpoint から registry を戻す。**生きていないことは正直に**:
  stream は `kuro.checkpoint/restore` 経由で `:orphaned` になり、
  attachment は `:suspended` になる — 前のプロセスを知らない窓を
  attached のまま返すと、呼び出し側は死んだ窓に入力を送る。"
  [edn]
  (when-not (= 1 (::version edn))
    (throw (ex-info "unsupported registry checkpoint version"
                    {:version (::version edn)})))
  (let [sessions (into {}
                       (map (fn [[n s]]
                              [n (update s :kuro.session/stream cp/restore)]))
                       (::sessions edn))
        attachments (into {}
                          (map (fn [[id a]]
                                 [id (assoc a :kuro.attachment/state :suspended)]))
                          (::attachments edn))]
    (registry {:sessions sessions :attachments attachments})))
