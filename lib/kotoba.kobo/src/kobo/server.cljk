(ns kobo.server
  "workbench を実際に見て触れるようにする、ローカル専用の HTTP 入口。

  ここまで `kobo` は library でしかなく、**entry point が一つも無かった**ので
  console を見るには自分でハーネスを書く必要があった。実装できていることと
  使えることは別で、この名前空間がその差を埋める。

  ## なぜ Cloudflare Worker ではないのか

  workbench は開発者のマシンでプロセスを起こす。Worker はプロセスを起こせない
  ので、そもそも候補にならない。**これはローカルの開発ツール**であって、
  デプロイする面ではない。

  ## 経路

      GET  /            SSR した console（write surface あり）
      GET  /events      SSE。状態が変わるたびに描き直した fragment を送る
      POST /run         コマンド開始   {argv: [...]}
      POST /stdin       標準入力       {text: \"...\"}
      POST /kill        停止           {}
      GET  /health      {ok, session}

  ## 安全側の作り（ここは飾りではない）

  任意コマンドを起こす HTTP 面は、開いた瞬間に遠隔実行そのものになる。

  1. **127.0.0.1 にしか bind しない。** `--host` は受け取らない —— 「あとで
     0.0.0.0 にできる」形にしておくと、いつか誰かがそうする。
  2. **書き込み経路は起動ごとのトークン必須**（`X-Kobo-Token` ヘッダ）。
     ヘッダ必須にするのは CSRF 対策でもある: カスタムヘッダは
     preflight を強制するので、他所のページから黙って POST できない。
     token は起動時に stdout に出す（URL に載せない —— 履歴に残る）。
  3. **`Origin` を検査する。** localhost 以外からのブラウザ経由の書き込みは拒否。
  4. 実行そのものの制約は `kuro` 側のまま —— capability の事前検査、shell 無しの
     argv、cwd 拘束、宣言環境、期限、出力上限。**サーバはそれを緩めない。**

  それでも**これは隔離ではない**。`kuro.host.node` の docstring どおり
  capability は intent record であって kernel ではないので、走ったコマンドは
  ディスクにもネットワークにも触れる。ローカルの自分のマシンで、自分の repo に
  対して使う道具である。"
  (:require ["node:crypto" :as crypto]
            ["node:http" :as http]
            [kotoba.lang.text :as str]
            [kobo.host.stream-node :as sh]
            [kobo.ui :as ui]
            [kobo.workbench :as wb]
            [kotoba-ui.core :as kui]))

(def default-port 7777)

(defn new-token []
  (.toString (crypto/randomBytes 24) "hex"))

;; ---------------------------------------------------------------- clients

(defn- render-fragment
  "live 更新で差し替える中身。全文書ではなく `#kobo-root` の中身だけを送る。"
  [wb opts]
  (kui/->html (ui/view wb opts)))

(defn- broadcast! [state]
  (let [{:keys [wb-atom clients view-opts]} state
        html (render-fragment @wb-atom view-opts)
        payload (str "data: " (js/JSON.stringify #js {:html html}) "\n\n")]
    (doseq [res @clients]
      (try (.write res payload) (catch :default _ nil)))))

;; ------------------------------------------------------------------ auth

(defn- local-origin?
  "ブラウザが付けた Origin が localhost か。Origin が無い（curl 等）のは通す
   —— CSRF はブラウザ経由の攻撃であり、Origin を送らない client は最初から
   token を持っていなければ何もできない。"
  [origin]
  (or (str/blank? origin)
      (some #(str/starts-with? origin %)
            ["http://127.0.0.1" "http://localhost" "http://[::1]"])))

(defn- authorized? [state req]
  (let [h (.-headers req)]
    (and (= (:token state) (aget h "x-kobo-token"))
         (local-origin? (aget h "origin")))))

;; --------------------------------------------------------------- handlers

(defn- json! [res status body]
  (.writeHead res status #js {"content-type" "application/json; charset=utf-8"})
  (.end res (js/JSON.stringify (clj->js body))))

(defn- read-body [req]
  (js/Promise.
   (fn [resolve _]
     (let [chunks (atom "")]
       (.on req "data" (fn [d] (swap! chunks str d)))
       (.on req "end" (fn [] (resolve (try (js->clj (js/JSON.parse @chunks) :keywordize-keys true)
                                           (catch :default _ {})))))))))

(defn- handle-run [state res body]
  (let [argv (vec (map str (:argv body)))]
    (cond
      (empty? argv) (json! res 400 {:error "argv is empty"})

      ;; 同じ terminal で二重に走らせない。走行中の stdin/kill がどちらの
      ;; プロセスに届くのか曖昧になる方が、待たせるより悪い。
      (get (:kobo/running @(:wb-atom state)) (:terminal-id state))
      (json! res 409 {:error "a command is already running in this terminal"})

      :else
      (let [h (sh/start (:wb-atom state) (:terminal-id state) argv
                        (assoc (:run-opts state)
                               :on-chunk (fn [_ _] (broadcast! state))
                               :on-exit (fn [_]
                                          (reset! (:handle state) nil)
                                          (broadcast! state))))]
        (if (false? (:kuro/allowed? h))
          (do (broadcast! state)
              (json! res 403 {:denied true :missing (:kuro/missing h)}))
          (do (reset! (:handle state) h)
              (broadcast! state)
              (json! res 202 {:started argv})))))))

(defn- handle-stdin [state res body]
  (if-let [h @(:handle state)]
    (do ((:write h) (str (:text body) "\n"))
        (json! res 202 {:sent true}))
    (json! res 409 {:error "nothing is running"})))

(defn- handle-kill [state res]
  (if-let [h @(:handle state)]
    (do ((:kill h)) (json! res 202 {:killed true}))
    (json! res 409 {:error "nothing is running"})))

(defn- handle-events [state req res]
  (.writeHead res 200 #js {"content-type" "text/event-stream"
                           "cache-control" "no-cache"
                           "connection" "keep-alive"})
  (.write res (str "data: " (js/JSON.stringify
                             #js {:html (render-fragment @(:wb-atom state) (:view-opts state))})
                   "\n\n"))
  (swap! (:clients state) conj res)
  (.on req "close" (fn [] (swap! (:clients state) #(remove #{res} %)))))

;; browser glue。**ここだけ生の JavaScript**。
;;
;; kobo には cljs のビルド経路が無い（nbb は Node 用で browser に出せない）ので、
;; 25 行の配線のために shadow-cljs を持ち込むかどうかという別の決定になる。
;; 当面は inline に留め、**非正典**として扱う: ここにロジックを足さない
;; （分岐が要るようになったら、それが cljs ビルドを入れる合図）。
;; 撤去条件: kobo が browser 向け cljs ビルドを持ったとき。
(def ^:private browser-glue
  (str "(function(){"
       "var t=document.currentScript.dataset.token;"
       "function post(p,b){return fetch(p,{method:'POST',"
       "headers:{'content-type':'application/json','x-kobo-token':t},"
       "body:JSON.stringify(b||{})});}"
       "function val(id){var e=document.getElementById(id);return e?e.value:'';}"
       "document.addEventListener('click',function(ev){"
       "var el=ev.target.closest('[data-act]');if(!el)return;"
       "var a=el.dataset.act;"
       "if(a.indexOf('run')===0){var v=val('kobo-argv').trim();"
       "if(v)post('/run',{argv:v.split(/\\s+/)});}"
       "else if(a.indexOf('stdin')===0){post('/stdin',{text:val('kobo-stdin')});}"
       "else if(a.indexOf('kill')===0){post('/kill',{});}});"
       "new EventSource('/events').onmessage=function(m){"
       "var d=JSON.parse(m.data),r=document.getElementById('kobo-root');"
       "if(r)r.innerHTML=d.html;};"
       "})();"))

(defn- handle-page [state res]
  (.writeHead res 200 #js {"content-type" "text/html; charset=utf-8"})
  (.end res (ui/console @(:wb-atom state)
                        (assoc (:view-opts state)
                               :head [:script {:data-token (:token state)
                                               :defer true}
                                      [:hiccup/raw browser-glue]]))))

(defn- route [state req res]
  (let [url (.-url req) method (.-method req)
        write? (#{"/run" "/stdin" "/kill"} url)]
    (cond
      (and write? (not= "POST" method)) (json! res 405 {:error "POST only"})
      (and write? (not (authorized? state req))) (json! res 403 {:error "bad or missing X-Kobo-Token"})

      (= "/run" url) (-> (read-body req) (.then #(handle-run state res %)))
      (= "/stdin" url) (-> (read-body req) (.then #(handle-stdin state res %)))
      (= "/kill" url) (handle-kill state res)
      (= "/events" url) (handle-events state req res)
      (= "/health" url) (json! res 200 {:ok true
                                        :terminal (:terminal-id state)
                                        :running (boolean @(:handle state))})
      (= "/" url) (handle-page state res)
      :else (json! res 404 {:error "not found"}))))

(defn serve
  "サーバを起動して `{:server :state :token :port}` を返す。

  opts: `:port`（既定 7777、0 で任意の空きポート）・`:repo-root`（既定 \".\"）・
  `:mode`（既定 `:terminal-repo`）・`:terminal-id`（既定 \"t1\"）・`:token`・
  `:timeout-ms` `:max-output-bytes`（`kuro` に渡す）。"
  ([] (serve {}))
  ([opts]
   (let [terminal-id (:terminal-id opts "t1")
         repo-root (:repo-root opts ".")
         wb-atom (atom (-> (wb/workbench (str "local:" repo-root))
                           (wb/open-terminal terminal-id (:mode opts :terminal-repo))))
         state {:wb-atom wb-atom
                :clients (atom [])
                :handle (atom nil)
                :terminal-id terminal-id
                :token (or (:token opts) (new-token))
                :view-opts {:write-surface? true :terminal-id terminal-id}
                :run-opts (merge {:repo-root repo-root}
                                 (select-keys opts [:timeout-ms :max-output-bytes]))}
         srv (http/createServer (fn [req res] (route state req res)))
         result {:server srv :state state :token (:token state)}]
     ;; listen が失敗したときに **何が悪いのかを言う**。
     ;;
     ;; 既定では node は "error" イベントに listener が無いと unhandled として
     ;; 生の stack trace で落ちる。実測 2026-08-04、2 本目を同じポートで起動して
     ;; `Error: listen EADDRINUSE` が 15 行のトレースで出た —— 起動に失敗した
     ;; 理由（ポートが埋まっている）も、次にどうすればよいか（`--port`）も
     ;; その中に無い。**使い方の誤りに stack trace を返すのは、答えを持って
     ;; いるのに黙っているのと同じ。**
     (.on srv "error"
          (fn [^js err]
            (if-let [f (:on-error opts)]
              (f err)
              (do (js/console.error
                   (case (.-code err)
                     "EADDRINUSE"
                     (str "kobo: ポート " (:port opts default-port) " は既に使用中です。\n"
                          "  別のポートで起動: npm run console -- --port 7778\n"
                          "  使用中のプロセス: lsof -ti :" (:port opts default-port))
                     "EACCES"
                     (str "kobo: ポート " (:port opts default-port) " を開く権限がありません"
                          "（1024 未満は root が要ります）。--port で 1024 以上を指定してください。")
                     (str "kobo: 起動できませんでした: " (.-message err))))
                  (set! (.-exitCode js/process) 1)))))
     ;; **第 2 引数の "127.0.0.1" を外さないこと。** 外した瞬間、これは
     ;; LAN に対する遠隔実行になる。
     ;;
     ;; listen は非同期。`:port 0`（任意の空きポート）のとき、実際のポートは
     ;; listening まで確定しない —— 戻り値の :port を同期で読ませる API は、
     ;; 呼び出し側に null を掴ませる。確定値は :on-listen で渡す。
     (.listen srv (:port opts default-port) "127.0.0.1"
              (fn [] (when-let [f (:on-listen opts)]
                       (f (assoc result :port (.-port (.address srv)))))))
     result)))

(defn serve-async
  "`serve` を Promise で包む。listening 後の `{:server :state :token :port}`。"
  [opts]
  (js/Promise. (fn [resolve _] (serve (assoc opts :on-listen resolve)))))

(defn stop! [{:keys [server state]}]
  (doseq [res @(:clients state)] (try (.end res) (catch :default _ nil)))
  (.close server))

(defn -main [& args]
  (let [port (if-let [p (second (drop-while #(not= "--port" %) args))]
               (js/parseInt p 10) default-port)
        repo-root (or (second (drop-while #(not= "--repo-root" %) args)) ".")]
    (serve {:port port
            :repo-root repo-root
            :on-listen (fn [{:keys [token port]}]
                         (println (str "kobo workbench console\n"
                                       "  http://127.0.0.1:" port "/\n"
                                       "  repo-root: " repo-root "\n"
                                       "  token: " token "\n"
                                       "\n  127.0.0.1 のみ。書き込み経路は X-Kobo-Token 必須。"
                                       "\n  隔離ではありません —— 走らせたコマンドはこのマシンに触れます。")))})
    nil))
