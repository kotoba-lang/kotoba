(ns kotoba.property.site-probe
  "**URL しか無いところから連絡点を観測する** I/O 層。判断は 1 バイトも持たない
   —— どれが連絡窓口か・どのメールが窓口かは `kotoba.property.contact-point`
   （純 cljc）が決め、ここは fetch と robots.txt と待ち時間だけを持つ。

   ## なぜ registry を要求しない口が要るか

   既存の `collect_contact_points.cljs` は **法人番号を起点にする** ——
   gBizINFO の詳細を引き、そこに載っている `company_url` を見に行く。この経路は
   登記に URL が在る会社にしか効かない。実測 2026-08-26、節税 ICP（届出認定を
   持つ中小製造業）では gBizINFO の URL 保有率が 4% で、**母集団の 96% に対して
   起点が無かった。**

   一方、士業・IT 顧問のような専門サービス業は**自分のサイトを持っていることが
   商売の前提**で、URL の側が先に手に入る。だから起点を裏返した口をここに置く:
   `名前 + URL` から始めて、法人番号を一度も引かない。

   ⚠ **`collect_contact_points.cljs` はこのモジュールに寄せていない。** あちらは
   実測 2,103 社を通した経路で、こちらは今日書いたばかりである。両方を 1 本に
   するのは、この経路が同じだけ走ってからにする（今 refactor すると、動く方を
   動かないかもしれない方に合わせることになる）。**重複していることを承知で
   置いている。**"
  (:require [kotoba.lang.text :as str]
            [kotoba.property.contact-point :as cp]))

(defn now [] (.toISOString (js/Date.)))
(defn sleep [ms] (js/Promise. (fn [res] (js/setTimeout res ms))))

(defn fetch-text
  "[status body final-url] を返す。取りに行けなかったときは [nil nil nil]。

   **status 0 と status 404 を同じ nil に畳まない** —— 前者は測れなかった、
   後者は測って無かった。`final-url` を返すのは、要求した URL と実際に応答した
   URL が別物だから（リダイレクト先を台帳に載せる）。"
  ([url ms] (fetch-text url ms nil))
  ([url ms headers]
   (let [ctl (js/AbortController.)
         t (js/setTimeout #(.abort ctl) ms)]
     (-> (js/fetch url (clj->js {:signal (.-signal ctl)
                                 :redirect "follow"
                                 :headers (merge {"user-agent" cp/user-agent
                                                  "accept-language" "ja,en;q=0.8"}
                                                 headers)}))
         (.then (fn [^js res]
                  (-> (.text res)
                      (.then (fn [body] [(.-status res) body (.-url res)]))
                      (.catch (fn [_] [(.-status res) nil (.-url res)])))))
         (.catch (fn [_] [nil nil nil]))
         (.finally (fn [] (js/clearTimeout t)))))))

(defn robots-for
  "origin -> robots.txt 本文。**origin ごとに引く。**

   ⚠ 以前は種の origin の robots.txt だけを引いて、候補が別ホストでも同じ本文で
   判定していた（実測 2026-08-26: TKC 会員事務所の窓口は `cms.tkcnf.com` に在り、
   その robots.txt を一度も読まずに fetch していた）。`blocked?` が使う path の
   切り出しも origin 前提なので、別ホストの URL では**パスが URL 丸ごとになり、
   どの Disallow にも前方一致しない** —— つまり判定は常に「許可」に倒れていた。
   **拒否できない検査は、検査していないのと同じ値を返す。**"
  [cache origin]
  (if-let [hit (get @cache origin)]
    (js/Promise.resolve hit)
    (-> (fetch-text (str origin "/robots.txt") 10000)
        (.then (fn [[_ body]]
                 (let [txt (or body "")]
                   (swap! cache assoc origin txt)
                   txt))))))

(defn blocked?*
  "⚠ **公開している。** `collect_contact_points.cljs` / `collect_eu_contact_points.cljs`
   が自前に持っていた同名の判定は、種の origin の robots だけを見ていて
   **cross-origin の候補では常に許可に倒れていた**（2026-08-26 実測）。
   probe 全体を寄せるのは時期尚早でも、**拒否できない検査を残す理由は無い**ので、
   この 1 つだけを共有する。"
  [cache url]
  (let [org (cp/origin url)]
    (if-not org
      (js/Promise.resolve true)
      (-> (robots-for cache org)
          (.then (fn [robots]
                   (let [p (str/replace (str url) (re-pattern (str "^" org)) "")]
                     (cp/robots-disallows? robots cp/user-agent
                                           (if (str/blank? p) "/" p)))))))))

(defn- probe-contact
  "homepage を起点に連絡点を探す。robots.txt に拒まれたパスには行かない。
   候補は fetch する**前**に順位を付ける —— 1 件目が通った時点で止めるので、
   順序が精度そのものになる。"
  [site-url robots-cache delay-ms max-candidates]
  (let [org (cp/origin site-url)]
    (-> (blocked?* robots-cache site-url)
        (.then
         (fn [blocked-seed?]
           (if blocked-seed?
             {:status :robots-disallowed}
             (-> (fetch-text site-url 20000)
                 (.then
                  (fn [[hstatus home]]
                    (if-not (and hstatus home)
                      {:status :fetch-failed :note (str "homepage status=" (or hstatus "none"))}
                      ;; **origin 直下の当て先は、種の URL が origin 直下のときしか使わない。**
                      ;; 実測 2026-08-26: TKC の会員事務所は `https://www.tkcnf.com/<事務所名>`
                      ;; という**パスで区切られた共有ホスト**に載っている。ここで origin に
                      ;; `/contact` を当てると **TKC 自身の窓口**が返り、`contact-page?` を
                      ;; 通り、その事務所の連絡先として台帳に載る —— 別人の連絡先が、他の行と
                      ;; 同じ顔で並ぶ。`resolve-hit` が社名の前方一致を禁じたのと同じ誤りの、
                      ;; URL 側の形である。ページから見つけたリンクは事務所自身が張ったものなので
                      ;; 制限しない。
                      (let [root-seed? (contains? #{"" "/"}
                                                  (str/replace (str site-url)
                                                               (re-pattern (str "^" org)) ""))
                            raw (->> (concat (cp/discover-contact-links home site-url)
                                             (when root-seed?
                                               (map #(str org %) cp/common-contact-paths)))
                                     cp/rank-contact-candidates
                                     (take (* 2 max-candidates))
                                     vec)]
                        (-> (js/Promise.all (clj->js (map #(blocked?* robots-cache %) raw)))
                            (.then (fn [flags]
                                     (vec (take max-candidates
                                                (keep-indexed (fn [i u]
                                                                (when-not (nth (js->clj flags) i) u))
                                                              raw)))))
                            (.then
                             (fn [candidates]
                               (-> (reduce
                                    (fn [p url]
                                      (.then p (fn [found]
                                                 (if found
                                                   found
                                                   (-> (sleep delay-ms)
                                                       (.then (fn [] (fetch-text url 20000)))
                                                       (.then (fn [[st body final-url]]
                                                                ;; ⚠ `normalise-url` を通さない。末尾スラッシュを
                                                                ;; 落とすのが 301 の原因そのものだった。応答した
                                                                ;; URL を一字も変えずに載せる。
                                                                (when (and (= 200 st) body (cp/contact-page? body))
                                                                  {:contact-url (or (not-empty (str final-url)) url)
                                                                   :html body}))))))))
                                    (js/Promise.resolve nil)
                                    candidates)
                                   (.then (fn [found]
                                            (if found
                                              (assoc found :status :ok :home-html home)
                                              {:status :no-contact-point :home-html home
                                               :note (str "probed " (count candidates) " candidate path(s)")}))))))))))))))))))

(defn probe-site
  "`site-url` -> observation map（`cp/->site-record` にそのまま渡せる形）。

   **robots.txt を毎回引く。** 取れなかったときに許可として扱うのは RFC 9309 の
   定め（4xx = full allow）であって、こちらの緩さではない。"
  [site-url {:keys [delay-ms max-candidates] :or {delay-ms 400 max-candidates 8}}]
  (if-not (cp/normalise-url site-url)
    (js/Promise.resolve {:status :no-website :observed-at (now)
                         :note (str "not an absolute http(s) url: " site-url)})
    (-> (probe-contact site-url (atom {}) delay-ms max-candidates)
        (.then (fn [{:keys [status contact-url html home-html note]}]
                 ;; **窓口ページと homepage の両方からメールを拾う。** 窓口ページが
                 ;; フォームだけのことがあり、その場合アドレスは footer に在る。
                 (let [pages (remove nil? [html home-html])
                       emails (->> pages (mapcat cp/extract-emails) distinct vec)
                       ;; 営業お断りは**両方のページ**で見る。footer に書く会社と
                       ;; 窓口ページに書く会社が両方居るため。
                       forbidden? (boolean (some cp/solicitation-forbidden? pages))]
                   (cond-> {:status status :observed-at (now) :note note}
                     contact-url (assoc :contact-url contact-url)
                     (seq emails) (assoc :emails emails)
                     (seq pages) (assoc :solicitation-forbidden? forbidden?
                                        :site-postal-code (cp/extract-site-postal-code
                                                           (first pages))))))))))
