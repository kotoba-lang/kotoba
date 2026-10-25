(ns gijiroku.google-meet
  "Google Meet MeetingPlatform client (JVM). Google Workspace Meet REST API
  (https://developers.google.com/workspace/meet/api/guides/overview) —
  requires a Workspace service account with domain-wide delegation and scope
  `meetings.space.readonly` (recordings/transcripts are only exposed to
  Workspace admins/hosts, there is no consumer-Gmail equivalent). A bearer
  access token is injected (:token-fn, already OAuth2-resolved by the
  caller — this namespace does not implement the JWT/service-account flow
  itself, matching kekkai.kotoba's 'token or cacao, resolved by the caller'
  discipline) since Google's service-account JWT signing needs a full JWK/JWT
  stack out of scope for a zero-dep .clj client.

  Endpoints (Meet REST API v2):
    GET /v2/conferenceRecords/{conferenceRecord}                    — meeting-meta
    GET /v2/conferenceRecords/{conferenceRecord}/recordings         — recording (Drive-backed)
    GET /v2/conferenceRecords/{conferenceRecord}/transcripts
    GET /v2/conferenceRecords/{conferenceRecord}/transcripts/{id}/entries — paginated

  There is no signed-webhook equivalent from Meet directly; ingest is
  poll-driven (or via a Google Calendar/Pub-Sub watch the caller wires up),
  so `verify-webhook` always returns false — the caller must not route Meet
  through a webhook-trust path."
  (:require [gijiroku.platform :as p])
  (:import [java.net URI]
           [java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers]))

(defn jvm-http-fn [{:keys [url headers]}]
  (let [b (HttpRequest/newBuilder (URI/create url))]
    (doseq [[k v] headers] (.header b k v))
    (let [resp (.send (HttpClient/newHttpClient) (.build b) (HttpResponse$BodyHandlers/ofString))]
      {:status (.statusCode resp) :body (.body resp)})))

(defn- api-get [{:keys [http-fn json-read token-fn]} path]
  (json-read (:body (http-fn {:method :get :url (str "https://meet.googleapis.com/v2" path)
                              :headers {"Authorization" (str "Bearer " (token-fn))}}))))

(defn- ->meeting [tenant conference-record raw]
  {:id conference-record :platform :google-meet :external-id conference-record
   :title (:name raw) :host (:organizer raw) :tenant tenant
   :participants [] :status (if (:endTime raw) :ended :in-progress)
   :scheduled-start (:startTime raw)})

(defn- ->recording [conference-record raw]
  (let [rec (first (:recordings raw))]
    {:id (str "r-" conference-record) :meeting-id conference-record :platform :google-meet
     :asset-ref (get-in rec [:driveDestination :exportUri]) :duration-s nil :format "mp4"}))

(defn- entry->segment [{:keys [name text startTime endTime participant]}]
  {:seg-id name :speaker participant :t0 startTime :t1 endTime :text text :sensitive #{}})

(defn- ->transcript [conference-record cfg raw]
  (let [transcript-id (:name (first (:transcripts raw)))
        entries (when transcript-id
                  (:transcriptEntries (api-get cfg (str "/conferenceRecords/" conference-record
                                                        "/transcripts/" transcript-id "/entries"))))]
    {:id (str "t-" conference-record) :meeting-id conference-record :source :platform-native
     :lang "ja" :segments (mapv entry->segment entries)}))

(defrecord GoogleMeetPlatform [cfg tenant]
  p/MeetingPlatform
  (meeting-meta [_ external-id] (->meeting tenant external-id (api-get cfg (str "/conferenceRecords/" external-id))))
  (fetch-recording [_ external-id] (->recording external-id (api-get cfg (str "/conferenceRecords/" external-id "/recordings"))))
  (fetch-transcript [_ external-id] (->transcript external-id cfg (api-get cfg (str "/conferenceRecords/" external-id "/transcripts"))))
  (list-participants [_ _external-id] [])
  (verify-webhook [_ _headers _raw-body] false))

(defn client
  "cfg: {:token-fn (fn [] bearer-token) :http-fn (default jvm-http-fn)
         :json-write :json-read}
  tenant: the consuming org, e.g. \"cloud-manimani\"."
  [{:keys [http-fn] :as cfg} tenant]
  (->GoogleMeetPlatform (assoc cfg :http-fn (or http-fn jvm-http-fn)) tenant))
