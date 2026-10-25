(ns kobo.ui
  "The workbench console — the screen ADR-2606301000 describes, at the size it
  can honestly be built today.

  The ADR's target layout is a five-pane workbench (file tree, editor tabs,
  graph/audit, terminal tabs). This renders the read-only half of it: what the
  workbench *knows* — terminal sessions and their effective grants, command
  receipts, open buffers, diagnostics. Editing and command entry are not here,
  because `kobo` has no event wiring and `kuro.host.node` has no PTY; a text
  box that cannot send anywhere is worse than an absent one.

  So this follows the operator-console convention used across kotoba-lang
  (`dtn`, `card`, `ekyc`, `securities`, …): pure data → markup, and **no write
  surface** — no `<form>`, no `<button>`. Every value shown comes from a
  receipt that already happened.

  Pure `.cljc` hiccup on the kotoba-ui stack (single require point, layout
  from shell, colors from the theme map)."
  (:require [appkit.core :as appkit]
            [kotoba.lang.text :as str]
            [kotoba-ui.core :as ui]
            [kuro.ansi :as ansi]
            [kuro.stream :as kstream]))

(def theme
  "One map, per the design-system contract — the only place a hex belongs.

  `:auto` rather than a forced dark: the console is read at a desk in the
  morning and at 2am, and the tokens already carry both schemes."
  {:accent "#3C7DD9" :appearance :auto})

(def ^:private mode-labels
  "画面に出す mode 名。**`kuro` の `:kuro/label` と同じ語にする** ——
  keyword を `:terminal-repo` に改名したとき、ここのラベル文字列だけ \"safe\" の
  まま残っていて、画面には隔離を主張する語が出続けていた（kotoba-browser の
  render gate が drawn text の中に見つけた）。**改名は keyword ではなく、
  読む人が見る語に対して行うもの。**"
  {:terminal-repo "repo"
   :terminal-build "build"
   :terminal-agent "agent"
   :terminal-host "host"})

(defn short-cid
  "First 12 characters of a CID for display. The full value stays in the
  row's title attribute — a truncated hash that cannot be recovered is
  decoration, not evidence."
  [cid]
  (let [s (str cid)]
    (if (> (count s) 12) (str (subs s 0 12) "…") s)))

(defn- capability-chips [caps]
  (map #(ui/chip %) (sort caps)))

(defn- outcome-label
  "How a command ended, in words. An exit code alone does not distinguish
  \"returned 124\" from \"the deadline killed it\"."
  [r]
  (cond
    (:kuro/timed-out? r) "timed out"
    (:kuro/truncated? r) "output capped"
    (:kuro/error r) (:kuro/error r)
    (zero? (:kuro/exit-code r)) "ok"
    :else (str "exit " (:kuro/exit-code r))))

(defn terminal-row [[id sess]]
  (ui/list-row
   [:span
    [:span {:class "hig-headline"} (str id)]
    [:span {:class "hig-caption1"} " " (:kuro/cwd sess)]
    [:div (capability-chips (get-in sess [:kuro/grant :capabilities] #{}))]]
   {:trailing (ui/badge (mode-labels (:kuro/mode sess) "?"))}))

;; ------------------------------------------------------- terminal output

(def ^:private ansi-class
  "SGR の色名 → CSS クラス。**ここで生の色値を書かない** —— 端末の 16 色を
  勝手な hex に割り当てると、light/dark の切り替えとコントラスト保証を
  design system の外に持ち出すことになる。クラスだけ振り、実際の値は
  `output-css` が HIG のセマンティックカラー変数から取る。"
  {"black" "t-fg-black"     "red" "t-fg-red"       "green" "t-fg-green"
   "yellow" "t-fg-yellow"   "blue" "t-fg-blue"     "magenta" "t-fg-magenta"
   "cyan" "t-fg-cyan"       "white" "t-fg-white"})

(def output-css
  "端末出力の見た目。**生の色値をひとつも書かない** —— すべて HIG のトークンで、
  light/dark の切り替えとコントラストは design system の保証をそのまま使う。

  意図的な不忠実が 2 つある。端末の `black` と `white` は「その端末の背景の
  反対側」を意味していて、絶対色ではない —— light テーマで literal な white を
  出すと文字が消える。どちらも `--hig-color-label`（＝読める既定の前景）に
  寄せる。**読めない忠実さより、読める近似。**

  app CSS は unlayered なのでライブラリの `@layer` に常に勝つ。詳細度で
  戦う必要はない（compound selector を書かない）。"
  (str
   ".t-output pre{font-family:var(--hig-font-mono);"
   "font-size:var(--hig-text-footnote-font-size);"
   "line-height:1.45;margin:var(--hig-spacing-2) 0 0;padding:var(--hig-spacing-3);"
   "white-space:pre-wrap;overflow-wrap:anywhere;overflow-x:auto;"
   "background:var(--hig-color-secondary-system-background);"
   "border-radius:var(--hig-radius-xs);color:var(--hig-color-label);}"
   ;; 端末 16 色 → HIG system palette
   ".t-fg-black{color:var(--hig-color-label);}"
   ".t-fg-white{color:var(--hig-color-label);}"
   ".t-fg-red{color:var(--hig-palette-red);}"
   ".t-fg-green{color:var(--hig-palette-green);}"
   ".t-fg-yellow{color:var(--hig-palette-orange);}"   ; yellow は本文だと薄すぎる
   ".t-fg-blue{color:var(--hig-palette-blue);}"
   ".t-fg-magenta{color:var(--hig-palette-purple);}"
   ".t-fg-cyan{color:var(--hig-palette-teal);}"
   ".t-bold{font-weight:600;}.t-dim{opacity:.65;}"
   ".t-italic{font-style:italic;}.t-underline{text-decoration:underline;}"
   ".t-strike{text-decoration:line-through;}"
   ".t-bright{filter:brightness(1.15);}"
   ".t-inverse{background:var(--hig-color-label);color:var(--hig-color-system-background);}"))

(defn- span-classes [{:keys [fg bold dim italic underline strike inverse]}]
  (->> [(when (string? fg) (ansi-class (str/replace fg "bright-" "")))
        (when (and (string? fg) (str/starts-with? fg "bright-")) "t-bright")
        (when bold "t-bold") (when dim "t-dim") (when italic "t-italic")
        (when underline "t-underline") (when strike "t-strike")
        (when inverse "t-inverse")]
       (remove nil?)
       (str/join " ")))

(def max-output-lines
  "画面に出す行数の上限。receipt の stdout は 1 MiB まで許されるので、
  そのまま流すとページが数万行になる。切ったら必ず件数を出す。"
  200)

(defn output-block
  "コマンド出力を、ANSI を解釈した行として描く。

  `kuro.ansi` は 256 色 / truecolor も返すが、ここでは**名前付きの 8 色 +
  bright だけ**をクラスにする。任意の RGB を span の style に流し込むと、
  design system が保証しているコントラストの外に出る（背景が dark のときに
  `rgb(20,20,20)` の前景が来たら読めない）。捨てるのではなく、色を落として
  文字は残す —— 読めない色より、色の無い読める文字。"
  [text]
  (when (seq (str text))
    (let [[ls dropped] (ansi/truncate-lines (ansi/lines text) max-output-lines)]
      [:div {:class "t-output"}
       [:pre
        (for [[i line] (map-indexed vector ls)]
          [:span {:key i}
           (for [[j {:keys [text style]}] (map-indexed vector line)]
             (let [c (span-classes style)]
               (if (seq c)
                 [:span {:key j :class c} text]
                 [:span {:key j} text])))
           "\n"])]
       (when (pos? dropped)
         [:p {:class "hig-caption2"} (str "… " dropped " 行を省略しました")])])))

(defn receipt-row [r]
  (ui/list-row
   [:span
    [:code (str/join " " (:kuro/argv r))]
    [:span {:class "hig-caption1"}
     " " (outcome-label r)
     (when-let [ms (:kuro/duration-ms r)] (str " · " ms " ms"))
     (when-let [n (:kuro/dropped-bytes r)] (str " · " n " B 切り捨て"))
     (when-let [cid (:kuro/stdout-cid r)]
       [:span {:title cid} (str " · stdout " (short-cid cid))])]
    (output-block (:kuro/stdout r))
    (output-block (:kuro/stderr r))]
   {:trailing (ui/badge (str (:kuro/exit-code r)))}))

(defn running-row
  "実行中の command。`kuro.stream` の値をそのまま読む。

  終わった receipt と同じ列に混ぜない —— 「まだ終わっていない」と
  「終わって exit 0」は別の事実で、同じ行に見せると読み手が取り違える。"
  [st]
  (ui/list-row
   [:span
    [:code (str/join " " (get-in st [:kuro/command :kuro/argv]))]
    [:span {:class "hig-caption1"}
     (str " 実行中 · " (kstream/total-bytes st) " B")]
    (output-block (kstream/text-of st :stdout))
    (output-block (kstream/text-of st :stderr))]
   {:trailing (ui/badge "running")}))

(defn buffer-row [[path buf]]
  (ui/list-row
   [:span {:class "hig-body"} (str path)]
   {:trailing (ui/badge (str (count (str/split-lines (str (:kobo.buffer/text buf ""))))
                             " lines"))}))

(defn denial-row [d]
  (ui/list-row
   [:span
    [:code (str/join " " (:kuro/argv d))]
    [:span {:class "hig-caption1"}
     " needs " (str/join ", " (:kuro/missing d))]]
   {:trailing (ui/badge "denied")}))

(defn diagnostic-row [d]
  (ui/list-row
   [:span
    [:span {:class "hig-headline"} (str (:kobo.diagnostic/path d))]
    [:span {:class "hig-caption1"} " " (str (:kobo.diagnostic/message d))]]
   {:trailing (ui/badge (name (:kobo.diagnostic/severity d :info)))}))

(defn- empty-note [text]
  [:p {:class "hig-footnote"} text])

(defn- listing
  "A section holding a list, or an explicit note when there is nothing.

  An empty section that renders nothing reads as a broken page; an empty
  section that says why reads as a true one."
  [title rows empty-text]
  (ui/section {:title title}
    (if (seq rows)
      (appkit/list-view rows)
      (empty-note empty-text))))

(defn command-bar
  "コマンド入力・stdin・停止。**`:write-surface? true` のときだけ描く。**

  ここまで console は `<form>` も `<button>` も出さなかった。理由は
  「どこにも送れない入力欄は無い方がまし」で、当時は正しかった —— 送り先が
  無かったので。`kuro.host.stream-node` に `:write`（stdin）と `:kill` が
  入った今、**前提が変わった**ので規約側を見直す。

  read-only の運用ダッシュボードとして使う経路（`kotoba-lang` の 23 repo と
  同じ用途）は既定のまま残す —— write surface は明示的に要求した人だけが得る。

  操作は `data-act` に載る（design system の `:act` 契約）。値の読み取りは
  `id` から行う。ここに JS は書かない —— 配線は `kobo.server` が入れる。"
  [terminal-id]
  (ui/section {:title "Command"}
    (ui/stack {:gap :3}
      (ui/stack {:direction :horizontal :gap :3}
        (ui/text-field {:id "kobo-argv"
                        :placeholder "git status --short"
                        :aria-label "実行するコマンド（argv、シェル解釈なし）"})
        (ui/button "Run" {:act [:run terminal-id]}))
      [:p {:class "hig-caption2"}
       "シェルは通しません。空白で区切った argv としてそのまま渡します。"]
      (ui/stack {:direction :horizontal :gap :3}
        (ui/text-field {:id "kobo-stdin"
                        :placeholder "stdin に送る行"
                        :aria-label "実行中のコマンドへの標準入力"})
        (ui/button "Send" {:act [:stdin terminal-id]})
        (ui/button "Kill" {:act [:kill terminal-id]})))))

(defn view
  "The workbench console as hiccup — mountable as-is, or wrapped by `console`.

  opts: `:write-surface?`（既定 false）・`:terminal-id`（既定 \"t1\"）。"
  ([wb] (view wb {}))
  ([wb opts]
   (ui/app-shell
    {:nav (ui/nav-bar "kobo"
                      {:trailing [(ui/badge (short-cid (:kobo/repo-root-cid wb)))]})}
    (when (:write-surface? opts) (command-bar (:terminal-id opts "t1")))
    (listing "Terminals" (map terminal-row (sort-by key (:kobo/terminals wb)))
            "No terminal session open.")
   (listing "Running" (map running-row (vals (:kobo/running wb)))
            "No command is running.")
   (listing "Receipts" (map receipt-row (:kobo/receipts wb))
            "No command has run in this workbench yet.")
   (listing "Denied" (map denial-row (:kobo/denials wb))
            "No command was refused.")
   (listing "Buffers" (map buffer-row (sort-by key (:kobo/buffers wb)))
            "No buffer open.")
   (listing "Diagnostics" (map diagnostic-row (:kobo/diagnostics wb))
            "No diagnostics."))))

(defn console
  "The complete HTML document for a workbench. opts: `:theme` (defaults to
  `theme`), plus anything `kotoba-ui.core/->page` takes."
  ([wb] (console wb {}))
  ([wb opts]
   (ui/->page (merge {:title "kobo — workbench console"
                      :description "Terminal sessions, grants, and command receipts."
                      :theme theme
                      :head [:style [:hiccup/raw output-css]]}
                     (dissoc opts :write-surface? :terminal-id :body-attrs))
              ;; live 更新はこの 1 要素を差し替える。id を view の外（console）で
              ;; 付けるのは、view を別の枠に埋め込む使い方を塞がないため。
              [:div (merge {:id "kobo-root"} (:body-attrs opts))
               (view wb opts)])))
