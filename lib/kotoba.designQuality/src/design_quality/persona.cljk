(ns design-quality.persona
  "persona-conditioned visual / user test — the :persona-visual scoring layer
  (ADR-2607141550, com-junkawasaki/root).

  The existing layers score design-system conformance (:lint, deterministic),
  library craft (:llm-judge) and rendered samples (:sample-visual). This layer
  answers a different question: *would this page's target customer trust it and
  act?* An LLM judge role-plays a concrete persona against page screenshots and
  returns 1-5 scores on six axes plus free-text feedback.

  Contract:
  - Personas and target pages are PRODUCT data — they live in the consumer repo
    (e.g. ai-gftd-itad/resources/personas.edn), not here. This ns only defines
    the schema, the rubric, prompt rendering and ledger-event builders.
  - Score events append to the consumer's ledger in the same :eval/* event shape
    as design-quality-ledger.edn, with two extra keys: :eval/persona :eval/page.
    Append-only; never hand-edit existing lines.
  - The panel is a DISCOVERY tool, not a gate. The deploy gate stays the
    deterministic audit (coscientist principle: ranking must be reproducible,
    never an LLM debate).
  - Honesty invariant: feedback that asks for fabricated social proof (invented
    track records, certifications, testimonials) must NOT be applied by Evolve.

  Pure cljc, no I/O — capture/judging/appending are the runner's job."
  (:require [kotoba.lang.text :as str]))

;; --- axes --------------------------------------------------------------------

(def axes
  "Six 1-5 axes for persona visual tests. :question is what the judge answers
  *as the persona*."
  [{:id :first-view-comprehension
    :label "ファーストビュー理解"
    :question "最初の1画面(5秒)で、何のサービスで自分に関係あるか分かったか?"}
   {:id :trust
    :label "信頼感"
    :question "この会社に自社の機密が入った機器を預けてよいと感じるか?"}
   {:id :cta-findability
    :label "CTA発見性"
    :question "次に何をすればよいか(申込/相談)が迷わず見つかるか?"}
   {:id :anxiety-resolution
    :label "不安解消"
    :question "あなたが最も恐れていることに、このページは答えているか?"}
   {:id :readability
    :label "読みやすさ"
    :question "あなたのITリテラシー・デバイスで、文章と構成は負担なく読めるか?"}
   {:id :form-intent
    :label "フォーム送信意欲"
    :question "実際にこのフォームを送信する(または問い合わせる)気になったか?"}])

(def scale
  {1 "全く当てはまらない / 離脱する"
   2 "弱い"
   3 "どちらとも言えない"
   4 "概ね良い"
   5 "強く当てはまる / 迷いなく行動する"})

;; --- persona schema -----------------------------------------------------------

(def persona-keys
  "Required keys for a persona map in a consumer repo's personas.edn."
  [:persona/id      ; keyword, unique in catalog
   :persona/name    ; display name (ja)
   :persona/role    ; job/situation
   :persona/age     ; int
   :persona/it-literacy ; :low :mid :high
   :persona/context ; why they landed on this page (1-3 sentences)
   :persona/goals   ; vector of strings
   :persona/fears   ; vector of strings — anxiety-resolution scores against these
   :persona/device]); :desktop :mobile

(defn valid-persona? [p]
  (every? #(contains? p %) persona-keys))

;; --- judge prompt --------------------------------------------------------------

(defn judge-prompt
  "Render the panel prompt for one persona × one page. The runner attaches the
  screenshot(s) and asks for the EDN result shape below."
  [{:persona/keys [name role age it-literacy context goals fears device]}
   {:page/keys [id url] :as _page}]
  (str
   "あなたはこれから1人の見込み客として日本語のWebページを評価します。演じるペルソナ:\n"
   "- 名前/立場: " name "(" role ", " age "歳)\n"
   "- ITリテラシー: " (clojure.core/name it-literacy)
   " / 閲覧デバイス: " (clojure.core/name device) "\n"
   "- 状況: " context "\n"
   "- 目的: " (str/join " / " goals) "\n"
   "- 恐れていること: " (str/join " / " fears) "\n\n"
   "対象ページ: " url " (page id: " (clojure.core/name id) ")\n"
   "添付のスクリーンショットだけを根拠に(想像で補完しない)、このペルソナとして"
   "以下の6軸を1-5で採点し、軸ごとに1-2文の理由を書いてください。"
   "スケール: 1=全く当てはまらない/離脱する … 5=強く当てはまる/迷いなく行動する\n\n"
   (str/join "\n" (map-indexed (fn [i {:keys [id question]}]
                                 (str (inc i) ". " (clojure.core/name id) " — " question))
                               axes))
   "\n\n最後に、このペルソナとして感じた改善要望を影響の大きい順に最大3件、"
   "具体的に(ページのどこの何が、なぜ、どうなっていてほしいか)書いてください。"
   "スクリーンショットに写っていないことを事実として書かないでください。"))

;; --- ledger events --------------------------------------------------------------

(defn score-events
  "One judge result -> ledger event maps (one per axis), same :eval/* shape as
  design-quality-ledger.edn plus :eval/persona :eval/page. `scores` is
  {axis-id {:score n :note s}}. seq0 is the first :eval/seq to use; events get
  seq0, seq0+1, ...

  `:theme` (optional, e.g. :light/:dark) adds an :eval/theme key when given --
  follow-up 1 of ADR-2607141550 (light/dark scored as distinct capture
  conditions, not folded together). Omitted entirely when nil, so events built
  without a theme keep the exact pre-existing shape (append-only ledger:
  historical lines never had this key, and never need to)."
  [{:keys [run-id at judge persona-id page-id seq0 theme]} scores]
  (into []
        (map-indexed
         (fn [i {:keys [id]}]
           (let [{:keys [score note]} (get scores id)
                 base {:eval/layer :persona-visual
                       :eval/persona persona-id
                       :eval/page page-id
                       :eval/axis (keyword "axis" (clojure.core/name id))
                       :eval/score (double score)
                       :eval/judge judge
                       :eval/run-id run-id
                       :eval/at at
                       :eval/seq (+ seq0 i)
                       :eval/note note}]
             (if (some? theme)
               (assoc base :eval/theme theme)
               base)))
         axes)))

(defn feedback-event
  "Free-text feedback items -> one ledger event. `items` is a vector of strings
  ordered by impact. `:theme` -- see score-events."
  [{:keys [run-id at judge persona-id page-id seq0 theme]} items]
  (cond-> {:eval/layer :persona-visual
           :eval/persona persona-id
           :eval/page page-id
           :eval/axis :axis/feedback
           :eval/score 0.0
           :eval/judge judge
           :eval/run-id run-id
           :eval/at at
           :eval/seq seq0
           :eval/note (str/join " | " items)}
    (some? theme) (assoc :eval/theme theme)))

(defn mean-by-axis
  "events (:persona-visual score events) -> {axis-id {:mean m :n n :stdev s}}.
  Use to compare runs and detect judge disagreement (stdev) — a single judge
  hides weak consensus (ADR-2607132300 measured stdev 0.50 disagreements)."
  [events]
  (let [score-evs (filter #(and (= :persona-visual (:eval/layer %))
                                (not= :axis/feedback (:eval/axis %)))
                          events)]
    (into {}
          (map (fn [[axis evs]]
                 (let [xs (map :eval/score evs)
                       n (count xs)
                       m (/ (reduce + xs) n)
                       var (/ (reduce + (map #(let [d (- % m)] (* d d)) xs)) n)]
                   [axis {:mean (double m) :n n :stdev (double (Math/sqrt var))}])))
          (group-by :eval/axis score-evs))))
