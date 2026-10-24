(ns kami.mangaka.qa.perception
  "VLM 知覚 — prompt + parser (ADR-2607165100)。I/O ゼロ: VLM 呼び出しは
  `vision-fn` (fn [prompt image-b64] → parsed-map|nil) として注入する
  (langchain-clj の host-capability 方式)。offline / 解析不能は nil =
  no signal — 呼び出し側は罰せず degrade する。

  backend 実測 (fleet gemma4 量子化, 2026-07-16): カウント VQA は正確
  (公開ページ→3 顔 / キャラ不在パネル→0)、bounding-box grounding は弱く
  漫画顔に空配列を返しがち、コマ境界検出は動作 (公開ページ→3 コマ)。
  数だけ要る用途 (facePresence 軸) は count-faces を使うこと。"
  )

(def face-count-prompt
  (str "How many distinct drawn character faces are visible in this manga"
       " image? Count stylized anime faces of any size. Reply ONLY JSON"
       " {\"count\": <integer>}. No prose."))

(def face-boxes-prompt
  (str "This is a manga/anime image. Detect every drawn CHARACTER FACE"
       " (stylized anime faces count, any size). Reply with ONLY a JSON"
       " object {\"faces\": [{\"cx\": <0-1>, \"cy\": <0-1>, \"w\": <0-1>,"
       " \"h\": <0-1>}]} — cx/cy is the face center and w/h its size, all"
       " normalized to the image dimensions. Empty array if no face."
       " No prose."))

(def panel-boxes-prompt
  (str "Detect the manga PANEL boundaries (koma frames) in this page image."
       " Reply with ONLY a JSON object {\"panels\": [{\"x\": <0-1>,"
       " \"y\": <0-1>, \"w\": <0-1>, \"h\": <0-1>}]} — x/y is each panel's"
       " top-left corner, normalized. Order by reading order if apparent."
       " No prose."))

(defn- norm-box? [m ks]
  (every? #(let [v (get m %)] (and (number? v) (<= 0.0 v) (<= v 1.0))) ks))

(defn parse-face-count
  "{:count n} → non-negative long | nil。"
  [out]
  (let [n (:count out)]
    (when (and (number? n) (<= 0 n)) (long n))))

(defn parse-face-boxes
  "{:faces [...]} → 検証済みボックス vector | nil。範囲外/非数値は落とす。"
  [out]
  (let [faces (:faces out)]
    (when (sequential? faces)
      (vec (filter #(norm-box? % [:cx :cy :w :h]) faces)))))

(defn parse-panel-boxes
  [out]
  (let [panels (:panels out)]
    (when (sequential? panels)
      (vec (filter #(norm-box? % [:x :y :w :h]) panels)))))

(defn count-faces
  "顔数 (long) | nil。実測で動く既定経路 — facePresence 軸はこれを使う。"
  [vision-fn image-b64]
  (when (and vision-fn (seq (str image-b64)))
    (parse-face-count (vision-fn face-count-prompt image-b64))))

(defn detect-faces
  "顔ボックス | nil。⚠ backend 依存 (grounding の弱い VLM は空配列を返す)。"
  [vision-fn image-b64]
  (when (and vision-fn (seq (str image-b64)))
    (parse-face-boxes (vision-fn face-boxes-prompt image-b64))))

(defn detect-panels
  "パネルボックス | nil。"
  [vision-fn image-b64]
  (when (and vision-fn (seq (str image-b64)))
    (parse-panel-boxes (vision-fn panel-boxes-prompt image-b64))))
