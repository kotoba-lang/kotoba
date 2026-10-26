(ns kuro.host.supervisor
  "running stream を窓 (attachment) から切り離して生かす監督者 — tmux server 相当。

  二重持と同期: kuro.session は閉じた値 (state in/out)。registry は kuro.session
  registry を atom に持ち、子の生きた本体 (stream / pid / stdin) は stream-node
  の handle が持つ。子の出力は各 chunk ごとに registry の stream へコピーする —
  detach 中の窓が読めるのはそのコピーで、再 attach した窓は cursor で溜まった分を
  読む。終了時は registry の stream を finished にし、receipt を保存する。

永続は呼び出し側: snapshot / restore! は kuro.session の edn 変換を渡す。restore
後の stream は orphaned、窓は suspended (kuro.session/restore の規約) — 死んだ窓
を attached のまま返さない。この層は PTY を提供しない (kuro.stream と同じ
pipe / TERM=dumb)。"
  (:require [kuro.host.stream-node :as sh]
            [kuro.session :as sess]
            [kuro.stream :as stream]))

(defn new-supervisor
  "空の supervisor。registry (値) と live handle (子) を atom で持つ。"
  []
  {:kuro.sup/registry  (atom (sess/registry))
   :kuro.sup/handles   (atom {})
   :kuro.sup/receipts  (atom {})})

(defn registry [sup] @(:kuro.sup/registry sup))
(defn handle-of [sup name] (get @(:kuro.sup/handles sup) name))
(defn receipt-of [sup name] (get @(:kuro.sup/receipts sup) name))

(defn- update-stream!
  "registry の name の stream コピーに関数 f を当てる。"
  [sup name f]
  (swap! (:kuro.sup/registry sup)
         (fn [reg]
           (update-in reg [:kuro.registry/sessions name :kuro.session/stream] f))))

(defn start!
  "sess で cmd を spawn し、registry に name で登録、窓 :window-id (既定 name) を
  付ける。opts は stream-node/start へ渡す (:repo-root :env :timeout-ms
  :max-output-bytes :now :on-chunk :on-exit)。

  - capability 不足 → kuro.terminal/denial (spawn しない / registry に触れない)。
  - 子の出力は各 chunk で registry の stream へ流す (detach 中も更新)。
  - 終了時、registry の stream を finished にし receipt を保存。
  - return: stream-node の handle、denial なら denial map。"
  [sup name sess cmd opts]
  (let [wire (or (:window-id opts) name)
        prev-chunk (:on-chunk opts)
        prev-exit  (:on-exit opts)
        clean-opts (dissoc opts :window-id)
        h (sh/start sess cmd
                    (merge clean-opts
                           {:on-chunk (fn [st chunk]
                                        (update-stream! sup name (constantly st))
                                        (when prev-chunk (prev-chunk st chunk)))
                            :on-exit (fn [receipt]
                                       (update-stream! sup name stream/mark-finished)
                                       (swap! (:kuro.sup/receipts sup) assoc name receipt)
                                       (when prev-exit (prev-exit receipt)))}))]
    (if (false? (:kuro/allowed? h))
      h
      (do (let [st @(:stream h)]
            (swap! (:kuro.sup/registry sup)
                   (fn [reg]
                     (-> reg
                         (sess/spawn name st)
                         (sess/attach wire name)))))
          (swap! (:kuro.sup/handles sup) assoc name h)
          h))))

(defn attach-window!
  "窓 window-id を session name に付ける。"
  [sup window-id name]
  (swap! (:kuro.sup/registry sup) #(sess/attach % window-id name)))

(defn detach-window!
  "窓 window-id を外す。子プロセスは走り続ける — registry への流し込みは続き、
  再 attach した窓は溜まった分を読める。"
  [sup window-id]
  (swap! (:kuro.sup/registry sup) #(sess/detach % window-id)))

(defn reattach-window!
  "外した窓 old-id の cursor を引き継ぐ新窓 new-id を作る — detach 中の未読は
  新窓の最初の read で届く。"
  [sup old-id new-id]
  (swap! (:kuro.sup/registry sup) #(sess/reattach % old-id new-id)))

(defn read-window
  "窓 window-id の未読 chunk を返し、その窓の読み位置を進める。
  (tmux と同じ — 読んだ分は次に重複して来ない。)"
  [sup window-id]
  (let [[adv chunks] (sess/read-out (registry sup) window-id)]
    (swap! (:kuro.sup/registry sup)
           (fn [reg] (assoc-in reg [:kuro.registry/attachments window-id] adv)))
    chunks))

(defn kill!
  "live な子 (name) を止める (SIGTERM)。子が終わると on-exit が registry の
  stream を finished にし、receipt を保存。restored (handle 無し) なら registry
  の stream を finished にするだけ。"
  [sup name]
  (if-let [h (handle-of sup name)]
    ((:kill h))
    (update-stream! sup name stream/mark-finished)))

(defn session-states
  "name → stream state。監査・snapshot の対象選び。"
  [sup]
  (sess/session-states (registry sup)))

(defn snapshot
  "registry を保存可能な EDN 値にする (kuro.session/->edn)。"
  [sup]
  (sess/->edn (registry sup)))

(defn restore!
  "EDN から registry を戻す。stream は orphaned、窓 は suspended (kuro.session/
  restore)。handle には登録しない (子は死んでいる)。"
  [sup edn]
  (reset! (:kuro.sup/registry sup) (sess/restore edn))
  (reset! (:kuro.sup/receipts sup) {})
  (reset! (:kuro.sup/handles sup) {})
  :restored)