(ns kobo.server-test
  "実サーバを立てて実 HTTP で叩く。モックしない —— この面の価値は
  『ブラウザから触れる』ことなので、ブラウザがやることをやって確かめる。"
  (:require [cljs.test :refer [deftest is testing async]]
            [kotoba.lang.text :as str]
            [kobo.server :as server]))

(def node (.-execPath js/process))

(defn- with-server
  "空きポート（0）でサーバを立て、listening してから f に
   {:base :token :srv :state} を渡す。**listen は非同期**なので、待たずに
   `.address` を読むと null を掴む（実測）。"
  [f]
  (-> (server/serve-async {:port 0 :repo-root "."})
      (.then (fn [{:keys [port token state] :as s}]
               (f {:base (str "http://127.0.0.1:" port)
                   :token token :srv s :state state})))))

(defn- POST [{:keys [base token]} path body & [headers]]
  (js/fetch (str base path)
            #js {:method "POST"
                 :headers (clj->js (merge {"content-type" "application/json"
                                           "x-kobo-token" token}
                                          headers))
                 :body (js/JSON.stringify (clj->js (or body {})))}))

(defn- GET [{:keys [base]} path] (js/fetch (str base path)))

(defn- json [^js resp] (.json resp))

;; ---------------------------------------------------------------- serving

(deftest serves-the-console
  (async done
    (with-server
      (fn [ctx]
        (-> (GET ctx "/")
            (.then (fn [r] (.then (.text r) (fn [body] [r body]))))
            (.then (fn [[r body]]
                     (is (= 200 (.-status r)))
                     (is (str/starts-with? body "<!doctype html>"))
                     (testing "the live-swap target and the write surface are present"
                       (is (str/includes? body "id=\"kobo-root\""))
                       (is (str/includes? body "kobo-argv"))
                       (is (str/includes? body "data-act")))
                     (testing "the token is in the page for the glue, not in a URL"
                       (is (str/includes? body (:token ctx)))
                       (is (not (str/includes? body (str "?token=" (:token ctx))))))
                     (server/stop! (:srv ctx))
                     (done))))))))

(deftest health-reports-state
  (async done
    (with-server
      (fn [ctx]
        (-> (GET ctx "/health") (.then json)
            (.then (fn [j]
                     (is (true? (.-ok j)))
                     (is (= "t1" (.-terminal j)))
                     (is (false? (.-running j)))
                     (server/stop! (:srv ctx))
                     (done))))))))

;; ------------------------------------------------------------------- auth

(deftest write-paths-require-the-token
  (async done
    (with-server
      (fn [ctx]
        (-> (POST ctx "/run" {:argv ["echo" "no"]} {"x-kobo-token" "wrong"})
            (.then (fn [r]
                     (is (= 403 (.-status r)) "a wrong token must not start anything")
                     (POST ctx "/run" {:argv ["echo" "no"]} {"x-kobo-token" ""})))
            (.then (fn [r]
                     (is (= 403 (.-status r)) "an absent token must not start anything")
                     (GET ctx "/health")))
            (.then json)
            (.then (fn [j]
                     (is (false? (.-running j)) "nothing ran")
                     (server/stop! (:srv ctx))
                     (done))))))))

(deftest cross-origin-writes-are-refused
  (testing "a page on another origin must not drive this server"
    (async done
      (with-server
        (fn [ctx]
          (-> (POST ctx "/run" {:argv ["echo" "no"]} {"origin" "https://evil.example"})
              (.then (fn [r]
                       (is (= 403 (.-status r)))
                       (server/stop! (:srv ctx))
                       (done)))))))))

(deftest write-paths-refuse-get
  (async done
    (with-server
      (fn [ctx]
        (-> (GET ctx "/run")
            (.then (fn [r]
                     (is (= 405 (.-status r)))
                     (server/stop! (:srv ctx))
                     (done))))))))

;; ------------------------------------------------------------- run / stdin

(deftest runs-a-command-and-streams-the-result
  (async done
    (with-server
      (fn [ctx]
        (-> (POST ctx "/run" {:argv [node "-e" "process.stdout.write('hello-from-run')"]})
            (.then (fn [r] (is (= 202 (.-status r)))))
            (.then (fn [_]
                     ;; 終了を待つ: receipt が積まれるまで health を見る
                     (js/Promise. (fn [resolve _]
                                    (letfn [(poll []
                                              (if (seq (:kobo/receipts @(:wb-atom (:state ctx))))
                                                (resolve nil)
                                                (js/setTimeout poll 20)))]
                                      (poll))))))
            (.then (fn [_]
                     (let [[r] (:kobo/receipts @(:wb-atom (:state ctx)))]
                       (is (= 0 (:kuro/exit-code r)))
                       (is (= "hello-from-run" (:kuro/stdout r))))
                     (GET ctx "/")))
            (.then (fn [r] (.text r)))
            (.then (fn [body]
                     (is (str/includes? body "hello-from-run")
                         "the result is visible on the page, not only in memory")
                     (server/stop! (:srv ctx))
                     (done))))))))

(deftest a-second-command-is-refused-while-one-runs
  (async done
    (with-server
      (fn [ctx]
        (-> (POST ctx "/run" {:argv [node "-e" "setTimeout(()=>{},300)"]})
            (.then (fn [_] (POST ctx "/run" {:argv [node "-e" "0"]})))
            (.then (fn [r]
                     (is (= 409 (.-status r))
                         "stdin/kill would be ambiguous with two processes on one terminal")
                     (POST ctx "/kill" {})))
            (.then (fn [_] (server/stop! (:srv ctx)) (done))))))))

(deftest stdin-reaches-the-running-command
  (async done
    (with-server
      (fn [ctx]
        (-> (POST ctx "/run"
                  {:argv [node "-e" "process.stdin.once('data',d=>{process.stdout.write('got:'+d.toString().trim());process.exit(0)})"]})
            (.then (fn [_] (js/Promise. (fn [res _] (js/setTimeout #(res nil) 150)))))
            (.then (fn [_] (POST ctx "/stdin" {:text "ping"})))
            (.then (fn [r] (is (= 202 (.-status r)))))
            (.then (fn [_]
                     (js/Promise. (fn [resolve _]
                                    (letfn [(poll []
                                              (if (seq (:kobo/receipts @(:wb-atom (:state ctx))))
                                                (resolve nil)
                                                (js/setTimeout poll 20)))]
                                      (poll))))))
            (.then (fn [_]
                     (is (= "got:ping" (:kuro/stdout (first (:kobo/receipts @(:wb-atom (:state ctx)))))))
                     (server/stop! (:srv ctx))
                     (done))))))))

(deftest stdin-and-kill-without-a-command-are-refused
  (async done
    (with-server
      (fn [ctx]
        (-> (POST ctx "/stdin" {:text "x"})
            (.then (fn [r] (is (= 409 (.-status r))) (POST ctx "/kill" {})))
            (.then (fn [r]
                     (is (= 409 (.-status r)))
                     (server/stop! (:srv ctx))
                     (done))))))))

(deftest empty-argv-is-refused
  (async done
    (with-server
      (fn [ctx]
        (-> (POST ctx "/run" {:argv []})
            (.then (fn [r]
                     (is (= 400 (.-status r)))
                     (server/stop! (:srv ctx))
                     (done))))))))

(deftest a-denied-command-is-reported-not-run
  (async done
    (with-server
      (fn [ctx]
        ;; grant を空にして、どのコマンドも repo/read を満たせない状態にする
        (swap! (:wb-atom (:state ctx)) assoc-in
               [:kobo/terminals "t1" :kuro/grant :capabilities] #{})
        (-> (POST ctx "/run" {:argv [node "-e" "process.stdout.write('NO')"]})
            (.then (fn [r] (is (= 403 (.-status r))) (json r)))
            (.then (fn [j]
                     (is (true? (.-denied j)))
                     (is (= ["repo/read"] (js->clj (.-missing j))))
                     (is (empty? (:kobo/receipts @(:wb-atom (:state ctx))))
                         "nothing executed")
                     (server/stop! (:srv ctx))
                     (done))))))))

;; ------------------------------------------------------------------- SSE

(deftest events-push-the-rendered-fragment
  (async done
    (with-server
      (fn [ctx]
        (-> (GET ctx "/events")
            (.then (fn [^js r]
                     (is (= 200 (.-status r)))
                     (is (str/includes? (.get (.-headers r) "content-type") "text/event-stream"))
                     (let [reader (.getReader (.-body r))
                           decoder (js/TextDecoder.)]
                       (-> (.read reader)
                           (.then (fn [^js chunk]
                                    (let [s (.decode decoder (.-value chunk))]
                                      (testing "the first frame is the current state, not an empty ping"
                                        (is (str/starts-with? s "data: "))
                                        (is (str/includes? s "No command has run")))
                                      (.cancel reader)
                                      (server/stop! (:srv ctx))
                                      (done)))))))))))))

(deftest binds-loopback-only
  (testing "the address must never widen — this endpoint starts processes"
    (async done
      (-> (server/serve-async {:port 0 :repo-root "."})
          (.then (fn [{:keys [server] :as s}]
                   (is (= "127.0.0.1" (.-address (.address server))))
                   (server/stop! s)
                   (done)))))))

(deftest coloured-output-becomes-classes-on-the-served-page
  ;; この面は cljs（nbb）で動く。`kuro.ansi` は 1 日だけ JVM 緑 / cljs 死で、
  ;; JVM の kobo.ui テストは通っていたのにブラウザでは色が 1 つも出なかった。
  ;; **実際に配信されるページを、実際に走るランタイムで確かめる。**
  (async done
    (with-server
      (fn [ctx]
        (-> (POST ctx "/run"
                  {:argv [node "-e" "process.stdout.write('\\u001b[32mPASS\\u001b[0m done')"]})
            (.then (fn [_]
                     (js/Promise. (fn [resolve _]
                                    (letfn [(poll []
                                              (if (seq (:kobo/receipts @(:wb-atom (:state ctx))))
                                                (resolve nil)
                                                (js/setTimeout poll 20)))]
                                      (poll))))))
            (.then (fn [_] (GET ctx "/")))
            (.then (fn [r] (.text r)))
            (.then (fn [body]
                     (is (str/includes? body "t-fg-green") "the colour survived as a class")
                     (is (str/includes? body "PASS"))
                     ;; `[32m` そのものは argv の表示に出てよい（コマンド文字列を
                     ;; そのまま見せているので）。禁じたいのは **ESC バイト**が
                     ;; 生で出ること。最初の版はこれを取り違えて落ちた。
                     (is (not (str/includes? body (str (char 27))))
                         "no raw ESC byte on the page")
                     (server/stop! (:srv ctx))
                     (done))))))))

(deftest port-in-use-explains-itself
  ;; 実測 2026-08-04: 2 本目を同じポートで起動したら node の unhandled 'error'
  ;; として 15 行の stack trace が出た。理由も次の一手もその中に無い。
  ;; **使い方の誤りに stack trace を返すのは、答えを持っていて黙るのと同じ。**
  (async done
    (with-server
      (fn [ctx]
        (let [port (js/parseInt (last (str/split (:base ctx) #":")) 10)]
          (server/serve
           {:port port :repo-root "."
            :on-error (fn [^js err]
                        (is (= "EADDRINUSE" (.-code err))
                            "the second listen fails, and we get told which way")
                        (server/stop! (:srv ctx))
                        (done))}))))))
