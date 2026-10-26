(ns kuro.checkpoint
  "実行中の状態を、プロセスが死んでも読める形にする。

  ## なぜ要るのか

  `kuro.stream` の値は in-memory にしかない。サーバが落ちれば「何が走って
  いたか」も「どこまで出力したか」も消える —— `kobo.agent` の durable loop は
  **checkpoint 無しにはこの上に載らない**（ADR-2606301000 が言う
  lease/tick → checkpoint → budget は、再開できる状態を前提にしている）。

  ## この名前空間の責務は変換だけ

  純 `.cljc`。ファイルにも DB にも書かない —— **書き込みは host の仕事**で、
  ここは `stream ⇄ EDN` の可逆変換と、途中で失われたものの申告を持つ。
  そうしておくと、保存先（ファイル / kotobase / DataLad）を選び直しても
  この層は変わらない。

  ## 復元は「同じ値」ではなく「正直な値」

  `restore` は保存時点の状態を返すが、**保存後に起きたことは知らない**。
  プロセスが死んだ時点で走っていた stream を復元しても、その子プロセスは
  もう居ない —— だから復元された stream は `:kuro/state :orphaned` になり、
  `running?` は偽を返す。`:running` のまま返すと、呼び出し側は生きていない
  プロセスに stdin を送ろうとする。

  `finish` は orphaned な stream にも使える（exit code が分からないので
  host が `{:exit-code 129 :error \"...\"}` のような値を入れる）—— 落ちた実行を
  receipt にして閉じられないと、台帳に開きっぱなしの穴が残る。"
  (:require [kotoba.lang.text :as str]
            [kuro.stream :as stream]))

(def format-version 1)

(defn- chunk->edn [c]
  (select-keys c [:stream :text :kuro/seq]))

(defn- code-point-at
  "位置 i にある**完全な** Unicode コードポイントと、その直後の UTF-16 番地を
  返す (`[cp end]`)。i が末尾を越えていれば nil。

  `.cljc` は文字を UTF-16 コードユニットで数える (`count` / `subs` は
  サロゲートを 1 文字として扱う)。astral 文字（絵文字・Ext-B・数学記号）は
  2 ユニットなので、ユニット単位で足すと途中で裂ける。ここでコードポイント
  単位に進めることで、保存先に孤立サロゲート（壊れたコードポイント）を
  置かない。"
  [s i]
  (when (< i (count s))
    #?(:clj (let [cp (Character/codePointAt s i)]
              [cp (+ i (Character/charCount cp))])
       :cljs (let [cp (.codePointAt s i)]
               [cp (+ i (if (> cp 0xffff) 2 1))]))))

(defn- codepoint-size
  "1 個のコードポイントの UTF-8 バイト長。コードポイント値から直接算定する ——
  `subs` + `stream/byte-count` を**サロゲート片ごとに**呼ぶと、孤立サロゲートを
  JVM は 1 バイト '?'、cljs (TextEncoder) は 3 バイト U+FFFD に符号化するため
  runtime で答えが割れる (実測 2026-09-09)。コードポイント値は両 runtime で同じ
  整数を返すので、この算術は parity 安全。"
  [cp]
  (cond (<= cp 0x7f) 1
        (<= cp 0x7ff) 2
        (<= cp 0xffff) 3
        :else 4))

(defn- cut-to-bytes
  "text を高々 n バイトの UTF-8 に切り詰める。**コードポイント単位**で切る ——
  マルチバイト文字もサロゲートペア (astral 文字) も途中で裂かない。壊れた
  コードポイントを保存先に置かない。戻り [kept cut]: kept は保持した先頭
  (コードポイント境界で切った) 文字列、cut は切り落とした**バイト**数
  (kept+cut = text の全バイト —— バイト会計は常に総和と一致)。

  旧実装は UTF-16 コードユニット単位で足し、`(subs text i (inc i))` のバイト数を
  毎回数えていた。astral 文字は 2 ユニットに見えるため、『切らない』はずの
  cap 境界でサロゲートペアを裂いた (実測: 'a😀b' を cap=4 に切ると cljs =
  実消費者は孤立サロゲート 'a\\uD83D' を保存し、JVM は 6 バイト全部を保持して
  cap を超えた —— 同じ入力・同じ cap で runtime ごとに別の byte 列)。"
  [text n]
  (let [total (stream/byte-count text)]
    (loop [end 0 kept-bytes 0]
      (if (< end (count text))
        (let [[cp end'] (code-point-at text end)
              nb (codepoint-size cp)]
          (if (<= (+ kept-bytes nb) n)
            (recur end' (+ kept-bytes nb))
            [(subs text 0 end) (- total kept-bytes)]))
        [text (- total kept-bytes)]))))

(defn ->edn
  "stream を保存できる EDN 値にする。

  opts `:max-chunk-bytes` を渡すと本文をそこまでに（UTF-8 **byte** で、char 境界を
  裂かない）切り詰め、切った**バイト**数を `:kuro.checkpoint/dropped-bytes` に記録する（**黙って切らない**）。
  既定は切らない —— 切るかどうかは保存先の都合であって、この層の既定では
  ない。"
  ([st] (->edn st {}))
  ([st opts]
   (let [cap (:max-chunk-bytes opts)
         chunks (mapv chunk->edn (:kuro/chunks st))
         [chunks dropped]
        (if-not cap
          [chunks 0]
          ;; 各 chunk ごとに kept 全体の byte 数を**足し直さない** - 旧実装は
          ;; `(reduce + 0 (map byte-count acc))` を毎 chunk 走らせていて、acc が
          ;; 伸びるにつれ O(k^2) に劣化する (k = chunk 数)。chatty な実行は
          ;; 1 MiB 上限内で数万 chunk を積むため、checkpoint 保存 (durability の
          ;; 経路) のたびに 2 次の時間が溶ける (実測: 20k chunk / 40KB で
          ;; ->edn 約 2s)。total (kept の byte 総数) を accumulator に載せて
          ;; 毎回 O(1) にする。切り落としの byte 会計 (`dropped`) は変わらない。
          (let [[chunks dropped _]
                (reduce (fn [[acc dropped total] c]
                          (let [n (stream/byte-count (:text c))
                                room (max 0 (- cap total))]
                            (cond
                              (<= n room) [(conj acc c) dropped (+ total n)]
                              (pos? room) (let [[kept cut] (cut-to-bytes (:text c) room)]
                                            [(conj acc (assoc c :text kept))
                                             (+ dropped cut)
                                             (- (+ total n) cut)])
                              :else [acc (+ dropped n) total])))
                        [[] 0 0] chunks)]
            [chunks dropped]))]
     (cond-> {:kuro.checkpoint/version format-version
              :kuro.checkpoint/state (:kuro/state st)
              :kuro/session (:kuro/session st)
              :kuro/command (:kuro/command st)
              :kuro/session-id (:kuro/session-id st)
              :kuro/chunks chunks
              :kuro/seq (:kuro/seq st)
              :kuro/stdout-bytes (:kuro/stdout-bytes st)
              :kuro/stderr-bytes (:kuro/stderr-bytes st)
              :kuro/dropped-bytes (:kuro/dropped-bytes st)
              :kuro/truncated? (:kuro/truncated? st)
              :kuro/max-output-bytes (:kuro/max-output-bytes st)}
       (pos? dropped) (assoc :kuro.checkpoint/dropped-bytes dropped)))))

(defn restore
  "checkpoint から stream を戻す。

  **`:running` では戻さない。** 保存された実行のプロセスはもう居ないので、
  `:orphaned` にする —— `:running` のまま返すと、呼び出し側は生きていない
  プロセスに stdin を送ろうとする。"
  [cp]
  (when-not (= format-version (:kuro.checkpoint/version cp))
    (throw (ex-info "unknown checkpoint version"
                    {:got (:kuro.checkpoint/version cp) :expected format-version})))
  (let [was (:kuro.checkpoint/state cp)
        cpt-drop (or (:kuro.checkpoint/dropped-bytes cp) 0)
        stream-drop (or (:kuro/dropped-bytes cp) 0)]
    {:kuro/type :kuro/stream
     :kuro/state (if (= :running was) :orphaned was)
     :kuro/restored-from was
     :kuro/session (:kuro/session cp)
     :kuro/command (:kuro/command cp)
     :kuro/session-id (:kuro/session-id cp)
     :kuro/chunks (vec (:kuro/chunks cp))
     :kuro/seq (:kuro/seq cp)
     :kuro/stdout-bytes (:kuro/stdout-bytes cp)
     :kuro/stderr-bytes (:kuro/stderr-bytes cp)
     ;; `->edn` の `:max-chunk-bytes` 切詰めは stream 層と別物: stream 自体は
     ;; 切っていない (`:kuro/truncated? false`, `:kuro/dropped-bytes 0`) のに、
     ;; checkpoint 層だけ保存時に切った。その事実を restore で落とすと、復元
     ;; した orphan を `abandon` した receipt が `:kuro/truncated?` も
     ;; `:kuro/dropped-bytes` も持たない「成功した短い出力」の顔をする ——
     ;; stream 層の「silently-cut receipt は short success と見分けが付かない」
     ;; 禁止と同じ穴が checkpoint 層に漏れている。切った量を stream の
     ;; truncation に載せ、byte カウンタの pre-truncation 真実は保持する。
     :kuro/dropped-bytes (+ stream-drop cpt-drop)
     :kuro/truncated? (or (:kuro/truncated? cp) (pos? cpt-drop))
     :kuro/max-output-bytes (:kuro/max-output-bytes cp)}))

(defn orphaned?
  "保存時に走っていて、復元時にはもうプロセスが居ない stream か。"
  [st]
  (= :orphaned (:kuro/state st)))

(defn abandon
  "orphaned な実行を receipt にして閉じる。

  落ちた実行を閉じられないと台帳に開きっぱなしの穴が残る。exit code は
  **推測しない** —— host が知っている値（既定 129 = SIGHUP 相当）と理由を
  入れる。"
  ([st] (abandon st {}))
  ([st result]
   (when-not (contains? #{:running :orphaned} (:kuro/state st))
     (throw (ex-info "abandon closes a run whose process died — a stream with another state already has a real ending"
                     {:state (:kuro/state st)})))
   (stream/finish (assoc st :kuro/state :running)
                  (merge {:exit-code 129
                          :error "process did not survive its host"
                          :isolation :none}
                         result))))

(defn summary
  "checkpoint を人が読める 1 行に。運用でまず知りたいのはこれ。

  切れた本文があるならどちらの層の切れ方かまで書く —— 黙って切った事実を
  落とすと、`[running] 4B` は「短い成功」の顔をする (stream 層の
  silently-cut 禁止が summary に漏れる)。stream 層 (:kuro/dropped-bytes,
  実行中に上限で切った) と checkpoint 層 (:kuro.checkpoint/dropped-bytes,
  保存時に切った) は別に報告する。"
  [cp]
  (str (:kuro/session-id cp) " "
       (str/join " " (:kuro/argv (:kuro/command cp)))
       " [" (name (:kuro.checkpoint/state cp)) "] "
       (+ (:kuro/stdout-bytes cp 0) (:kuro/stderr-bytes cp 0)) "B"
       (when-let [d (or (:kuro/dropped-bytes cp) 0)]
         (when (pos? d)
           (str " (stream dropped " d "B)")))
       (when-let [d (:kuro.checkpoint/dropped-bytes cp)]
         (str " (checkpoint dropped " d "B)"))))
