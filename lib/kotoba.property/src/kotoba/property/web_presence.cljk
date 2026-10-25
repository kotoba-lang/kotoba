(ns kotoba.property.web-presence
  "法人番号に紐づく**公開面**（サイト URL とフィード）の可搬コントラクト。

   ## 出所を 2 段に分ける

   - `:web/url` は gBizINFO 由来 —— **その会社が経済産業省に自分で登録した URL**
     なので、出所は authority 経由の自己申告である。
   - `:press/feed-url` は**こちらが探しに行って、実際に取得できたもの**。
     autodiscovery か既知のパスで見つけ、**取得して中身を数えるまで載せない**
     （newsfeed の `resources/sources.edn` が守っている規律と同じ:
     「listed される feed は全部、載る前に fetch された」）。

   混ぜないのは、前者が「この会社はこう名乗っている」で、後者が「この URL は
   この日、これだけの記事を返した」だからである。press item そのものは
   **自己公表**であって registry fact ではない —— `dossier.commoncrawl` が
   web crawl の hit を registry fact に混ぜないのと同じ線を引く。

   出典：gBizINFO（経済産業省）https://info.gbiz.go.jp/ を加工して作成 +
   各社の自己公表フィード（`:press/feed-url` に URL、`:source/observed-at` に取得時刻）"
  (:require [kotoba.lang.text :as str]))

(def dataset "web-presence")
(def authority-id "JP/METI-gBizINFO+self-published")
(def attribution
  "出典：gBizINFO（経済産業省）https://info.gbiz.go.jp/ を加工して作成。フィードは各社の自己公表。")

(defn- put [m k v] (if (or (nil? v) (str/blank? (str v))) m (assoc m k v)))

(defn normalise-url
  "末尾スラッシュの有無だけで別 URL にしない。scheme が無いものは弾く（相対 URL を
   絶対のふりで載せない）。"
  [u]
  (when-let [u (some-> u str str/trim)]
    (when (re-find #"^https?://" u)
      (str/replace u #"/+$" ""))))

(defn basic->record
  "gBizINFO の法人基本情報 -> 公開面レコード。URL が無ければ nil（`:web/url` の
   無いレコードを作らない —— 「調べたが無かった」は corpus の集計で数える）。"
  [corporate-number info]
  (when-let [url (normalise-url (get info "company_url"))]
    (-> {:source/dataset dataset
         :company/houjin-bangou corporate-number
         :company/registration-no corporate-number
         :company/jurisdiction "JP"
         :web/url url
         :web/url-source "gbizinfo"}
        (put :company/legal-name (get info "name"))
        (put :company/business-summary (get info "business_summary")))))

(def feed-link-re
  ;; <link rel=\"alternate\" type=\"application/rss+xml\" href=\"...\">
  ;; 属性の順序は固定でないので、link タグを取り出してから中を見る。
  #"(?i)<link\s[^>]*>")

(defn discover-feeds
  "HTML から feed の候補 URL を拾う（autodiscovery）。相対 URL は base で絶対化する。
   **候補であって feed ではない** —— 取得して中身を数えるまでは載せない。"
  [html base]
  (->> (re-seq feed-link-re (str html))
       (filter #(re-find #"(?i)application/(rss|atom)\+xml" %))
       (keep (fn [tag]
               (when-let [m (re-find #"(?i)href\s*=\s*[\"']([^\"']+)[\"']" tag)]
                 (let [href (str/trim (second m))]
                   (cond
                     (re-find #"^https?://" href) href
                     (str/starts-with? href "//") (str "https:" href)
                     (str/starts-with? href "/") (str (str/replace base #"/+$" "") href)
                     :else (str (str/replace base #"/+$" "") "/" href))))))
       distinct
       vec))

(def common-feed-paths
  "autodiscovery が無いサイト用の当て先。**当てただけでは載せない**（fetch して
   中身を数える）。順序は日本企業サイトで実際に当たりやすい順。"
  ["/feed" "/rss" "/rss.xml" "/atom.xml" "/feed.xml" "/news/feed" "/news/rss.xml"
   "/index.xml" "/blog/feed"])

(def ^:private item-re #"(?i)<(item|entry)[\s>]")
(def ^:private title-re #"(?i)<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>")
(def ^:private date-re
  #"(?i)<(pubDate|published|updated|dc:date)[^>]*>([^<]{6,40})</")

(defn feed-measurement
  "取得した本文 -> その fetch が**測ったこと**。newsfeed の sources.edn と同じ考え方:
   件数・要約の有無・最新日付を、載せる前に測る。feed でなければ nil。"
  [body]
  (let [body (str body)
        items (count (re-seq item-re body))]
    (when (and (pos? items)
               (re-find #"(?i)<(rss|feed|rdf:RDF)[\s>]" body))
      {:press/item-count items
       :press/has-summary (boolean (re-find #"(?i)<(description|summary|content)[\s>]" body))
       :press/kind (if (re-find #"(?i)<feed[\s>]" body) "atom" "rss")
       :press/latest (some-> (re-find date-re body) (nth 2) str/trim)
       :press/sample-title (some-> (re-find title-re body) second str/trim (subs 0 (min 120 (count (or (second (re-find title-re body)) "")))))})))

(defn with-feed
  "公開面レコード + 測定結果 -> フィード付きレコード。"
  [record feed-url measurement observed-at]
  (cond-> (assoc record
                 :press/feed-url feed-url
                 :press/feed-source "discovered"
                 :source/observed-at observed-at)
    (:press/item-count measurement) (assoc :press/item-count (:press/item-count measurement))
    (:press/kind measurement) (assoc :press/kind (:press/kind measurement))
    (some? (:press/has-summary measurement)) (assoc :press/has-summary (:press/has-summary measurement))
    (:press/latest measurement) (assoc :press/latest (:press/latest measurement))
    (:press/sample-title measurement) (assoc :press/sample-title (:press/sample-title measurement))))

(defn newsfeed-source
  "newsfeed の `resources/sources.edn` に足せる形（`:news.source/*`）。

   press item の取得は newsfeed が既に持っている —— ここが渡すのは**検証済みの
   feed の在処**だけで、fetcher を 2 つ作らない。

   ⚠ **キー名はあのファイルの実物に合わせる。** ingest は
   `:news.source/status \"active\"` の source しか回さないので、それが無い entry は
   **catalog に入っているのに 1 度も取得されない**（実測 2026-08-19: 41 件を足して
   `--only` で回したら `0 sources` だった）。`:newsfeed/verified-items` も同様に、
   こちらが勝手に `verifiedItemCount` と名付けると誰も読まない列になる。"
  [record]
  (when (:press/feed-url record)
    (let [kind (or (:press/kind record) "rss")]
      (cond-> {:news.source/sourceId (str "jp-" (:company/houjin-bangou record))
               :news.source/class "primary"
               :news.source/name (str (:company/legal-name record))
               :news.source/kind kind
               :news.source/sourceType kind
               :news.source/feedUrl (:press/feed-url record)
               :news.source/url (:web/url record)
               :news.source/lang "ja"
               :news.source/official true
               :news.source/rightsPolicy "fair-use-quote"
               ;; 自己公表は一次情報だが宣伝でもある — credibility はその帯。
               :news.source/credibility 0.6
               :news.source/topics ["company" "press-release"]
               :news.source/status "active"
               :newsfeed/verified (:source/observed-at record)
               :company/houjin-bangou (:company/houjin-bangou record)}
        (some? (:press/has-summary record)) (assoc :newsfeed/has-summary (:press/has-summary record))
        (:press/item-count record) (assoc :newsfeed/verified-items (:press/item-count record))))))

(defn corpus-manifest
  [{:keys [observed-at record-count queried with-url with-feed]}]
  (cond-> {:corpus/manifest true
           :corpus/projection true
           :corpus/format :edn-lines
           :source/dataset dataset
           :source/authority authority-id
           :source/attribution attribution
           :source/observed-at observed-at}
    queried (assoc :projection/queried queried)
    with-url (assoc :projection/with-url with-url)
    with-feed (assoc :projection/with-feed with-feed)
    record-count (assoc :corpus/record-count record-count)))
