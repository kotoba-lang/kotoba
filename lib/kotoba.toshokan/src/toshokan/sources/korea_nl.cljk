(ns toshokan.sources.korea-nl
  "National Library of Korea (국립중앙도서관, nl.go.kr) Open API harvester.

  Endpoint: https://www.nl.go.kr/NL/search/openApi/search.do (verified
  live 2026-07-19 -- responds, but REQUIRES a registered API key:
  `{\"errorCode\":\"011\",\"errorMsg\":\"INVALID KEY\"}` confirms the
  service exists and the wire format, without one). Registration is a
  manual, human, per-account approval flow at
  https://www.nl.go.kr/NL/contents/N31101010000.do -- out of scope for
  self-service automation (unverified whether non-Korean applicants can
  register without a Korean resident/business registration number; needs
  a human to actually try). This namespace is fully wired and will work
  once NL_GO_KR_API_KEY is set; until then `search` throws immediately
  with the registration URL rather than silently no-op'ing."
  (:require [toshokan.quad :as quad]))

(def ^:const search-endpoint "https://www.nl.go.kr/NL/search/openApi/search.do")
(def ^:const source-key :korea-nl)

(defn api-key []
  (or (some-> js/process.env .-NL_GO_KR_API_KEY not-empty)
      (throw (ex-info
              "NL_GO_KR_API_KEY not set -- register at https://www.nl.go.kr/NL/contents/N31101010000.do first"
              {:source source-key :status :blocked-on-registration}))))

(defn- entity-id [item]
  (str "korea-nl:" (or (:control_no item) (:recordId item) (:no item))))

(defn parse-item [item]
  {:entity (entity-id item)
   :source-url (:detail_link item)
   :title (:title_info item)
   :creators (some-> (:author_info item) vector)
   :publisher (:pub_info item)
   :date (:pub_year_info item)
   :isbn (:isbn_val item)
   :subject (:kdc_pattern_code item)})

(defn parse-response
  "nl.go.kr search.do JSON response (already keywordized) -> seq of
  field-maps. Field names per https://www.nl.go.kr/NL/contents/N31101010000.do
  -- unverified against a real successful (non-error) response since no key
  is provisioned; adjust on first real run if the schema differs."
  [response]
  (->> (get response :result [])
       (map parse-item)))

(defn search [query & {:keys [count] :or {count 20}}]
  (-> (js/fetch (str search-endpoint "?key=" (api-key)
                     "&kwd=" (js/encodeURIComponent query)
                     "&apiType=json&pageSize=" count)
                #js {:headers #js {"User-Agent" "toshokan-library-harvester/0.1 (kotoba-lang/toshokan; public bibliographic metadata preservation)"}})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.json r)
                 (throw (js/Error. (str "nl.go.kr search HTTP " (.-status r)))))))
      (.then #(js->clj % :keywordize-keys true))
      (.then (fn [resp]
               (when (:errorCode resp)
                 (throw (ex-info (str "nl.go.kr API error: " (:errorMsg resp)) resp)))
               resp))
      (.then parse-response)))

(defn ->quads
  [tx retrieved-at m]
  (quad/record->quads
   (:entity m) tx
   {:library/source source-key
    :library/source-url (:source-url m)
    :library/title (:title m)
    :library/creator (:creators m)
    :library/publisher (:publisher m)
    :library/date (:date m)
    :library/isbn (:isbn m)
    :library/subject (:subject m)
    :library/retrieved-at retrieved-at}))
