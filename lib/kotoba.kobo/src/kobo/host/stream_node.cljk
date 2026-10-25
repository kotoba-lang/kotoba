(ns kobo.host.stream-node
  "実行中のコマンドを workbench の状態として持つ。

  `kobo.host.node/run` は workbench 値を返すが、コマンドが終わるまで返らない。
  ここは **atom に載せた workbench** を逐次更新する: 走っている間は
  `:kobo/running` に `kuro.stream` の現在地が入り、終わったら receipt が
  `:kobo/receipts` に移る。console はどちらの状態でも描ける。

  atom を使うのは、これが**ホスト層**だから —— `kobo.workbench` は純粋なまま
  で、時間とともに変わるのはこの名前空間の中だけ。"
  (:require [kobo.workbench :as wb]
            [kuro.host.stream-node :as sh]
            [kuro.terminal :as t]))

(defn start
  "`argv` を `terminal-id` で開始する。`wb-atom` は workbench 値を持つ atom。

  戻り値は `kuro.host.stream-node/start` のハンドル（`:write` `:kill`
  `:close-stdin` `:stream`）、または capability 不足なら denial。denial の
  ときは workbench の `:kobo/denials` に積んで**何も起動しない**。

  opts は `kuro.host.stream-node/start` と同じ（`:repo-root` `:timeout-ms`
  `:max-output-bytes` `:env` `:kuro/requires`）に加えて `:on-exit`。"
  [wb-atom terminal-id argv opts]
  (let [sess (or (wb/terminal @wb-atom terminal-id)
                 (throw (ex-info "no such terminal in this workbench"
                                 {:terminal-id terminal-id
                                  :open (vec (keys (:kobo/terminals @wb-atom)))})))
        cmd (t/command argv (select-keys opts [:kuro/requires]))
        ;; 呼び出し側のコールバックは **潰さずに合成する**。最初の版は
        ;; `(assoc opts :on-chunk …)` で上書きしていて、呼び出し側が渡した
        ;; :on-chunk が黙って捨てられていた（テストで出た）。黙って消える
        ;; コールバックは、呼ばれない理由を呼び出し側から永遠に説明できない。
        caller-on-exit (:on-exit opts (fn [_]))
        caller-on-chunk (:on-chunk opts (fn [_ _]))
        handle (sh/start sess cmd
                         (assoc opts
                                :on-chunk (fn [st chunk]
                                            (swap! wb-atom wb/set-running terminal-id st)
                                            (caller-on-chunk st chunk))
                                :on-exit (fn [receipt]
                                           (swap! wb-atom
                                                  (fn [w]
                                                    (-> w
                                                        (wb/set-running terminal-id nil)
                                                        (update :kobo/receipts conj receipt))))
                                           (caller-on-exit receipt))))]
    (if (false? (:kuro/allowed? handle))
      (do (swap! wb-atom wb/record-denial (assoc handle :kuro/argv argv))
          handle)
      ;; 最初の chunk が来る前から「走っている」ことを見せる。ここを省くと、
      ;; 出力の無いコマンドは開始から終了まで画面上に一度も現れない。
      (do (swap! wb-atom wb/set-running terminal-id @(:stream handle))
          handle))))
