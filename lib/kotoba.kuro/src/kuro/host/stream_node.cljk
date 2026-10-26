(ns kuro.host.stream-node
  "実行中のコマンドを本当に走らせる —— 逐次出力と stdin と kill。

  `kuro.host.node/run` は `spawnSync` で、終わるまで返らず、途中の出力も見えず、
  途中で止める手段も無かった。10 分の build と無限ループが呼び出し側から同じに
  見えるということで、それは端末ではない。

  ここは `spawn`（非同期）で、`kuro.stream` の値を進めながら chunk を渡す:

      (def h (start sess cmd {:repo-root \".\"
                              :on-chunk (fn [st chunk] …)
                              :on-exit  (fn [receipt] …)}))
      ((:write h) \"y\\n\")   ; stdin
      ((:kill h))            ; SIGTERM（既定）

  ## 保証は `kuro.host.node` と同じ

  capability の事前検査・argv（shell 無し）・cwd 拘束・宣言環境・時間上限・
  出力上限 —— 同じ関数を使い回しており、streaming 版だけ緩いということはない。

  ## PTY ではない（重要）

  子プロセスに繋がるのは **pipe** であって疑似端末ではない。したがって:
  `isatty` は偽になり、多くのプログラムは色付けを自分から止め、行バッファに
  切り替わる。`vim` や `top` のような全画面プログラムは動かない。SIGWINCH も
  端末サイズも無い。**本物の PTY には native addon（node-pty 等）が要り、それは
  この repo の依存方針に関わる別の決定**なので、ここでは踏み込まない。
  `TERM=dumb` を宣言環境に入れて、子に嘘をつかないようにしている。"
  (:require ["node:child_process" :as cp]
            [kuro.host.cid :as cid]
            [kuro.host.node :as node]
            [kuro.stream :as stream]
            [kuro.terminal :as t]))

(def default-env
  "streaming 実行の宣言環境。`kuro.host.node/default-env` に `TERM=dumb` を足す。

  pipe で繋いでおきながら `TERM=xterm-256color` と名乗ると、子は cursor 移動や
  代替画面を出してくる —— こちらはそれを解釈できない（`kuro.ansi` は行志向）。
  能力を偽らない方が出力が読める。"
  (assoc node/default-env "TERM" "dumb"))

(def default-timeout-ms
  "The `:timeout-ms` the streaming provider applies when the caller passes
  none - the value the README table names (120 s, same as the sync
  provider's `kuro.host.node/default-timeout-ms`). A def so the table's
  default stays referenceable from tests without poking at the inline
  literal in `start`."
  120000)

(defn deadline-decision
  "A `:timeout-ms` deadline that elapses AFTER the child has already been
  observed to exit must not claim `:timed-out?` - the receipt reports the
  exit code the host actually saw, never a mislabeled 124. `exit-info` is
  the value recorded by the child's `exit` event (nil until a real exit is
  observed): `{:code n :signal s}`.

  Pure fn so the precedence contract can be pinned without spawning a
  process: the deadline claims 124/timed-out ONLY while no exit code is
  known. In practice the 'exit' handler disarms the timer, so this is the
  defensive fallback for the residual window where the events nest.
  Mirrors the 'close' handler's mapping (`some? code` -> real code, else
  128 + signal)."
  [exit-info]
  (if (nil? exit-info)
    {:exit-code 124 :timed-out? true}
    (let [code (:code exit-info) signal (:signal exit-info)]
      (if (some? code)
        {:exit-code code}
        {:exit-code 128 :error (str "terminated by " signal)}))))

(defn start
  "`cmd` を非同期に開始する。戻り値は
  `{:stream <atom of kuro.stream> :write fn :kill fn :pid n}`、
  capability 不足なら `kuro.terminal/denial`（**spawn しない**）。

  opts: `:repo-root` `:env` `:timeout-ms` `:max-output-bytes` `:now`
        `:on-chunk` `(fn [stream-state chunk])`
        `:on-exit`  `(fn [receipt])`"
  [sess cmd opts]
  (when (= :terminal-host (:kuro/mode sess))
    (throw (ex-info "kuro.host.stream-node has no host-shell backing"
                    {:mode :terminal-host :reason :unsupported-mode})))
  (let [cwd (or (node/confine (:repo-root opts ".") (:kuro/cwd sess))
                (throw (ex-info "terminal cwd escapes the repo root"
                                {:reason :cwd-escape :cwd (:kuro/cwd sess)})))
        required (node/required-capabilities cmd)]
    (or (t/denial sess required)
        (let [now (:now opts #(js/Date.now))
              max-bytes (:max-output-bytes opts stream/default-max-output-bytes)
              st (atom (stream/open sess cmd {:max-output-bytes max-bytes}))
              started (now)
              argv (:kuro/argv cmd)
              on-chunk (:on-chunk opts (fn [_ _]))
              on-exit (:on-exit opts (fn [_]))
              done? (atom false)
              ;; The child's real exit result, recorded by the 'exit' event
              ;; (which fires with the OS exit code as soon as the process
              ;; terminates, BEFORE 'close'). The deadline timer consults it
              ;; so a deadline that elapses after an exit was observed never
              ;; relabels the run timed-out.
              exit-info (atom nil)
              ;; 期限 timer のハンドルを、後に繋がれる take-chunk!からも読めるようにする。
              ;; let は後続の繋びを先行の fn 本文には見せないが、
              ;; take-chunk! は spawn 後にしか走らないので、実行時には必ず設定済みの値が見える。
              timer-ref (atom nil)
              proc (cp/spawn (first argv) (clj->js (vec (rest argv)))
                             #js {:cwd cwd
                                  :env (clj->js (:env opts default-env))
                                  :shell false
                                  :stdio #js ["pipe" "pipe" "pipe"]})
              take-chunk!
              (fn [stream-kw]
                (fn [buf]
                  (when (stream/running? @st)
                    ;; `finish!`（timeout / error / close 経由）が既に走った
                    ;; （=state が `:exited` になった）**後**に届いた data は黙って捨てる。
                    ;; ここで `append-chunk` を呼ぶと throw し、その例外は stdout の
                    ;; EventEmitter の data ハンドラ内の uncaught になって **host が
                    ;; 落ちる**（実機: 期限に出力を吐き続ける子 + SIGKILL から
                    ;; close までの窓）。遅い write が「黙って無視」に落ち着くのと
                    ;; 同じ哲学 —— 1 回の遅い data で host が死なない。
                    (let [chunk {:stream stream-kw :text (.toString buf "utf8")}]
                      (swap! st stream/append-chunk chunk)
                      (on-chunk @st chunk)
                      ;; 上限に達したら**こちらから止める**。spawn の maxBuffer と
                      ;; 違い非同期版は勝手に殺してくれないので、無限に吐く子が
                      ;; あるとメモリではなく時間だけが溶ける。
                      (when (and (:kuro/truncated? @st) (not @done?))
                        ;; close/error と同じく timer も外してから殺す。外さないと
                        ;; SIGKILL から close までの窓で timeout が先に発火し、実際の
                        ;; 停止理由は出力上限なのに receipt が exit 124 / timed-out?
                        ;; を名乗ってしまう。
                        (when-let [t @timer-ref] (js/clearTimeout t))
                        (.kill proc "SIGKILL"))))))
              finish!
              (fn [result]
                (when-not @done?
                  (reset! done? true)
                  (let [finished (now)
                        ;; README「content-addressed output」は sync 側だけの
                        ;; 保証にしない: streaming の receipt も sync と同じ
                        ;; CIDv1/raw/sha2-256 を持つ。text-of は UTF-8 文字列を
                        ;; 返し、text-cid はその UTF-8 byte 列にハッシュする ——
                        ;; sync 側が Buffer にハッシュするのと同じ byte 列。
                        stdout-cid (cid/text-cid (stream/text-of @st :stdout))
                        stderr-cid (cid/text-cid (stream/text-of @st :stderr))
                        receipt (stream/finish @st (merge {:started-at started
                                                           :finished-at finished
                                                           :duration-ms (- finished started)
                                                           :stdout-cid stdout-cid
                                                           :stderr-cid stderr-cid}
                                                          result))]
                    (swap! st stream/mark-finished)
                    (on-exit receipt)
                    receipt)))
              timer (when-let [ms (:timeout-ms opts default-timeout-ms)]
                      (js/setTimeout
                       (fn []
                         (when-not @done?
                           (let [decision (deadline-decision @exit-info)]
                             ;; once the child's real exit is known the deadline
                             ;; is moot - report the truth, never a mislabeled
                             ;; timeout (#113).
                             (when (:timed-out? decision)
                               (.kill proc "SIGKILL"))
                             (finish! decision))))
                       ms))]
          ;; Publish the deadline handle so take-chunk! can actually disarm it
          ;; when the output cap stops the run. Prior to this, `timer-ref` was
          ;; never written -- the `(when-let [t @timer-ref] (js/clearTimeout t))`
          ;; in take-chunk! was dead code, so the #97 "disarm on truncation" fix
          ;; never actually ran: only the close/error handlers cleared the timer,
          ;; and the SIGKILL -> close window could still let a firing deadline
          ;; relabel a capped run as timed-out (exit 124). take-chunk! only runs
          ;; after spawn emits 'data', by which time this reset has happened.
          (reset! timer-ref timer)
          ;; Node's spawned stdout/stderr emit `'data'` as raw Buffers whose
          ;; boundaries are OS **pipe bytes, not character-aligned**. A real
          ;; build can let a multibyte (CJK) char straddle two read chunks;
          ;; decoding each Buffer independently (.toString "utf8") turns the
          ;; partial bytes into U+FFFD replacement chars, so the streaming
          ;; stdout text, the byte count, and the CID (hashed over the
          ;; corrupted text) all silently diverge from what the child wrote.
          ;; setEncoding installs a StringDecoder that holds partial code
          ;; points across chunks -- take-chunk! then only ever sees whole
          ;; characters (chunk: text stays a decoded string).
          (.setEncoding (.-stdout proc) "utf8")
          (.setEncoding (.-stderr proc) "utf8")
          (.on (.-stdout proc) "data" (take-chunk! :stdout))
          (.on (.-stderr proc) "data" (take-chunk! :stderr))
          ;; 子の stdin に error リスナを張っておく。close-stdin (`.end`) のあとに
          ;; `(:write …)` されると Node は stdin socket 上で
          ;; ERR_STREAM_WRITE_AFTER_END の 'error' を**非同期で** emit する。
          ;; 誰も listen していなければ unhandled 'error' -> 未捕捉例外で host
          ;; （kobo サーバ）ごと落ちる（実測）。空のリスナが受けることで遅い write は
          ;; 「黙って無視」に落ち着く —— write 1 回の失敗で host が死ぬのは、
          ;; `on-chunk` の EventEmitter 例外と同じ類の壊れ方。
          (when-let [stdin (.-stdin proc)]
            (.on stdin "error" (fn [_] nil)))
          (.on proc "error"
               (fn [err]
                 (when timer (js/clearTimeout timer))
                 (finish! {:exit-code (if (= "ENOENT" (.-code err)) 127 126)
                           :error (if (= "ENOENT" (.-code err))
                                    (str "command not found: " (first argv))
                                    (str (.-code err)))})))
          (.on proc "close"
               (fn [code signal]
                 (when timer (js/clearTimeout timer))
                 (finish!
                  (cond
                    (:kuro/truncated? @st) {:exit-code 125 :truncated? true}
                    (some? code) {:exit-code code}
                    ;; kill されたら signal 名を残す。exit code だけだと
                    ;; 「誰が止めたのか」が receipt から消える。
                    :else {:exit-code 128 :error (str "terminated by " signal)}))))
          ;; Node emits 'exit' (the OS process terminated; real code+signal
          ;; known) BEFORE 'close' (stdio fully drained). A grandchild that
          ;; inherited the pipe keeps close delayed well past exit - if the
          ;; :timeout-ms deadline elapses in that window and finish!s first, the
          ;; done? guard makes the real close a no-op and the receipt lies: a run
          ;; that actually exit(0)'d gets reported 124/:timed-out? (#113). Record
          ;; the real exit and disarm the deadline: with the child already gone
          ;; there is no process left to enforce a timeout on.
          (.on proc "exit"
               (fn [code signal]
                 (when timer (js/clearTimeout timer))
                 (reset! exit-info {:code code :signal signal})))
          {:stream st
           :pid (.-pid proc)
           :write (fn [s]
                    (when-let [stdin (.-stdin proc)]
                      (.write stdin s)))
           :close-stdin (fn [] (some-> (.-stdin proc) (.end)))
           :kill (fn
                   ([] (.kill proc "SIGTERM"))
                   ([sig] (.kill proc sig)))}))))

(defn run-async
  "`start` を Promise で包む。receipt に解決する（denial は即座に解決）。"
  [sess cmd opts]
  (js/Promise.
   (fn [resolve _reject]
     (let [h (start sess cmd (assoc opts :on-exit resolve))]
       (when (false? (:kuro/allowed? h)) (resolve h))))))
