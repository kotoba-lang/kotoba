(ns kotoba.property.jgrants
  "Portable record shape for jGrants — デジタル庁's public subsidy portal API
   (`api.jgrants-portal.go.jp`, no key, no account).

   ## What this dataset is, and what it is not

   It is the **公募** catalogue: which subsidy programmes exist, who runs them,
   what they cap, which prefecture and headcount they target, and when the
   window closes. It is **not** 交付実績 — the API says nothing about which
   company received which grant, and no attribute here joins to 法人番号.

   That distinction matters because the obvious question (\"has this
   counterparty ever taken a subsidy?\") is exactly the one this cannot answer;
   the answer lives in per-programme 採択者一覧 published as scattered
   spreadsheets by each ministry. Recording the boundary here keeps a future
   reader from assuming the join exists because the datasets sit side by side.

   ## Coverage is a union of keyword queries, not an enumeration

   The API requires a `keyword` of at least 2 characters and has no \"all\"
   mode (measured: an empty keyword is HTTP 400). So coverage is whatever the
   keyword set finds, and the manifest records the keywords used — a catalogue
   that did not say how it was gathered would read as complete.

   出典：jGrants（デジタル庁）https://api.jgrants-portal.go.jp/ を加工して作成"
  (:require [kotoba.lang.text :as str]))

(def source-id "jgrants-public-subsidies")
(def authority-id "JP/Digital-Agency-jGrants")
(def dataset "jgrants")
(def licence "公共データ利用規約（第1.0版）(デジタル庁)")
(def attribution "出典：jGrants（デジタル庁）https://api.jgrants-portal.go.jp/ を加工して作成")

(def default-keywords
  "The keyword set the collector unions over. Chosen to span the vocabulary
   Japanese subsidy titles actually use, not to be exhaustive — an exhaustive
   set does not exist, which is why `:corpus/keywords` is written down."
  ["事業" "補助" "助成" "支援" "設備" "投資" "デジタル" "人材" "研究" "環境"
   "省エネ" "創業" "雇用" "観光" "医療" "農業" "輸出" "エネルギー"])

(defn- put [m k v] (if (or (nil? v) (and (string? v) (str/blank? v))) m (assoc m k v)))

(defn list-item->record
  "One `/subsidies` list element -> a portable entity."
  [item]
  (let [id (get item "id")]
    (when-not (str/blank? (str id))
      (-> {:subsidy/id id
           :source/dataset dataset}
          (put :subsidy/title (get item "title"))
          (put :subsidy/code (get item "name"))
          (put :subsidy/institution (get item "institution_name"))
          (put :subsidy/acceptance-start (get item "acceptance_start_datetime"))
          (put :subsidy/acceptance-end (get item "acceptance_end_datetime"))
          (put :subsidy/max-limit-yen (get item "subsidy_max_limit"))
          (put :subsidy/target-area (get item "target_area_search"))
          (put :subsidy/target-employees (get item "target_number_of_employees"))))))

(defn merge-detail
  "Fold a `/subsidies/id/<id>` detail into the list record. Only fetched for
   programmes whose window is open — the detail endpoint is one request per
   programme, and a closed programme's terms cannot be applied for anyway."
  [rec detail]
  (-> rec
      (put :subsidy/rate (get detail "subsidy_rate"))
      (put :subsidy/industry (get detail "industry"))
      (put :subsidy/use-purpose (get detail "use_purpose"))
      (put :subsidy/target-area-detail (get detail "target_area_detail"))
      (put :subsidy/url (get detail "front_subsidy_detail_page_url"))
      (put :subsidy/catch-phrase (get detail "subsidy_catch_phrase"))
      (put :subsidy/project-end-deadline (get detail "project_end_deadline"))
      (assoc :subsidy/detail-fetched? true)))

(defn open-at?
  "Is the application window open at `now` (both ISO-8601 strings)? A record
   with no end date is treated as closed rather than open: an unbounded window
   is much more likely to be a missing field than a subsidy anyone can still
   apply for."
  [rec now]
  (boolean
   (let [s (:subsidy/acceptance-start rec)
         e (:subsidy/acceptance-end rec)]
     (and e (neg? (compare now e))
          (or (nil? s) (not (neg? (compare now s))))))))

(defn corpus-manifest
  [{:keys [observed-at keywords record-count open-count detail-count]}]
  (cond-> {:corpus/manifest true
           :corpus/projection true
           :corpus/format :edn-lines
           :source/dataset dataset
           :source/authority authority-id
           :source/licence licence
           :source/attribution attribution
           :source/observed-at observed-at}
    keywords (assoc :corpus/keywords (vec keywords))
    record-count (assoc :corpus/record-count record-count)
    open-count (assoc :corpus/open-count open-count)
    detail-count (assoc :corpus/detail-count detail-count)))
