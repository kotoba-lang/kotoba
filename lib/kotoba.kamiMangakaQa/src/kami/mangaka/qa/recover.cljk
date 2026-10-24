(ns kami.mangaka.qa.recover
  "Storyboard 逆抽出 — 完成ページ画像 (PNG しか残っていない旧世代の公開物)
  から storyboard 相当の構造 (コマ矩形 + ショット + 登場キャラ + 台詞/SFX)
  を VLM で復元するための prompt + parser (ADR-2607165100 addendum 4)。

  退役 Python 世代の作品は最終 PNG しか残らず EDN 正本を失っている —
  この ns は「PNG → EDN 正本化」の可搬部分。I/O ゼロ、vision-fn 注入
  (perception ns と同じ host-capability 方式)。コマ矩形は既存の
  detect-panels (perception) を先に当て、本 ns の page-script 抽出は
  台詞・構図・キャラ同定を担う。

  復元は**推定**であり原本ではない — 呼び出し側は :recovered? true を
  データに焼き、原本 storyboard と混同させないこと。"
  (:require [kotoba.lang.text :as str]))

(defn page-script-prompt
  "ページ全体から per-panel の脚本情報を JSON で抽出させる prompt。
  `cast` (既知キャラ名の列) を与えると名前が ground される — 未知の顔を
  勝手に命名させない (キャラ以外は \"unknown\")。`n-panels` は
  detect-panels の結果 (読み順) と突き合わせるための期待コマ数。

  3-arity: `appearance` (name → 外見記述 の map) を与えると各キャラの見た目
  ガイドを prompt 先頭に足す。同定戦略の co-scientist (ADR-2607165100
  addendum 5) の勝者 — cast 名のみだと grounding がほぼ 0 になる量子化
  gemma4 で、外見記述の添付が grounding を確実に上げた (0→5 顔/ページ、
  精度 0.0→0.2)。記述が無いキャラは黙って飛ばす。"
  ([cast n-panels] (page-script-prompt cast n-panels nil))
  ([cast n-panels appearance]
   (str (when (seq appearance)
          (str "Character appearance guide (use to identify who appears):\n"
               (str/join "\n" (keep (fn [c] (when-let [d (get appearance c)]
                                              (str "- " c ": " d)))
                                    cast))
               "\n\n"))
        "This is a finished manga page. Read it in Japanese manga order"
        " (right-to-left, top-to-bottom). It has approximately " n-panels
        " panels. For EACH panel, extract: the shot type, which of the known"
        " characters appear, and any dialogue or SFX text visible."
        " Known characters: " (str/join ", " cast) "."
        " Reply with ONLY a JSON object {\"panels\": [{\"index\": <0-based"
        " reading order>, \"shot\": \"<wide|close|two-shot|splash|over-shoulder"
        "|establishing>\", \"characters\": [\"<known name or unknown>\"],"
        " \"dialogue\": [\"<verbatim Japanese text>\"], \"sfx\":"
        " [\"<sfx text>\"]}], \"synopsis\": \"<one sentence: what happens on"
        " this page>\"}. Use empty arrays when a panel has no dialogue/sfx."
        " No prose outside the JSON.")))

(def shot-vocab #{"wide" "close" "two-shot" "splash" "over-shoulder" "establishing"})

(defn parse-page-script
  "VLM 出力 → {:panels [{:index :shot :characters :dialogue :sfx}] :synopsis}
  | nil。index は 0..n に正規化 (欠番は出現順で振り直し)、shot は語彙外を
  \"wide\" に丸め、characters は cast 照合 (未知は落とさず \"unknown\")。"
  [out cast]
  (let [panels (:panels out)
        known (into {} (map (fn [c] [(str/lower (str c)) (str c)])) cast)]
    (when (sequential? panels)
      {:panels
       (vec (map-indexed
             (fn [i p]
               {:index i
                :shot (let [s (str/lower (str (:shot p)))]
                        (if (shot-vocab s) s "wide"))
                :characters (vec (keep (fn [c]
                                         (let [lc (str/lower (str c))]
                                           (or (known lc)
                                               (some (fn [[k v]]
                                                       (when (str/includes? lc k) v))
                                                     known)
                                               "unknown")))
                                       (:characters p)))
                :dialogue (vec (filter #(and (string? %) (seq %)) (:dialogue p)))
                :sfx (vec (filter #(and (string? %) (seq %)) (:sfx p)))})
             panels))
       :synopsis (when (string? (:synopsis out)) (:synopsis out))})))

(defn panel-box->rect
  "detect-panels の {:x :y :w :h} (0..1) → storyboard の :panel/rect
  [x y w h] (0..1 正規化 vector、mangaka.domain の規約)。"
  [{:keys [x y w h]}]
  [x y w h])

(defn merge-boxes-and-script
  "コマ矩形列 (読み順) と page-script の panels を index で züip して
  storyboard パネル列に合成する。数が食い違う場合は短い方に切り詰め、
  :mismatch にその事実を残す (silent truncation にしない)。"
  [boxes script-panels]
  (let [n (min (count boxes) (count script-panels))]
    {:panels
     (vec (for [i (range n)]
            (let [b (nth boxes i) sp (nth script-panels i)]
              (merge {:index i :rect (panel-box->rect b)} (dissoc sp :index)))))
     :mismatch (when (not= (count boxes) (count script-panels))
                 {:boxes (count boxes) :script (count script-panels)})}))
