(ns gijiroku.teams
  "Microsoft Teams MeetingPlatform client (JVM). Microsoft Graph, app-only
  (client-credentials) with `OnlineMeetings.Read.All`,
  `OnlineMeetingRecording.Read.All`, `OnlineMeetingTranscript.Read.All`
  (admin-consented Entra ID app registration).

  Endpoints (Graph v1.0):
    POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token   — client-credentials token
    GET  /v1.0/users/{userId}/onlineMeetings/{meetingId}
    GET  /v1.0/users/{userId}/onlineMeetings/{meetingId}/recordings
    GET  /v1.0/users/{userId}/onlineMeetings/{meetingId}/transcripts
    GET  /v1.0/users/{userId}/onlineMeetings/{meetingId}/transcripts/{id}/content?$format=text/vtt"
  (:require [gijiroku.zoom :as zoom-http] ; reuse vtt->segments + jvm-http-fn (same VTT cue shape)
            [gijiroku.platform :as p]))

(def jvm-http-fn zoom-http/jvm-http-fn)

(defn fetch-token
  [{:keys [http-fn json-read tenant-id client-id client-secret]}]
  (let [body (str "client_id=" client-id "&client_secret=" client-secret
                  "&scope=https%3A%2F%2Fgraph.microsoft.com%2F.default&grant_type=client_credentials")
        resp (http-fn {:method :post
                       :url (str "https://login.microsoftonline.com/" tenant-id "/oauth2/v2.0/token")
                       :headers {"Content-Type" "application/x-www-form-urlencoded"}
                       :body body})]
    (:access_token (json-read (:body resp)))))

(defn- api-get [{:keys [http-fn json-read]} token path]
  (json-read (:body (http-fn {:method :get :url (str "https://graph.microsoft.com/v1.0" path)
                              :headers {"Authorization" (str "Bearer " token)}}))))

(defn- meeting-path [user-id meeting-id] (str "/users/" user-id "/onlineMeetings/" meeting-id))

(defn- ->meeting [tenant raw]
  {:id (:id raw) :platform :teams :external-id (:id raw)
   :title (:subject raw) :host nil :tenant tenant
   :participants [] :status (if (:endDateTime raw) :ended :in-progress)
   :scheduled-start (:startDateTime raw)})

(defn- ->recording [external-id raw]
  (let [rec (first (:value raw))]
    {:id (str "r-" external-id) :meeting-id external-id :platform :teams
     :asset-ref (:recordingContentUrl rec) :duration-s nil :format "mp4"}))

(defn- ->transcript [external-id {:keys [http-fn]} token user-id raw]
  (let [transcript-id (:id (first (:value raw)))
        vtt (when transcript-id
              (:body (http-fn {:method :get
                               :url (str "https://graph.microsoft.com/v1.0"
                                         (meeting-path user-id external-id)
                                         "/transcripts/" transcript-id "/content?$format=text/vtt")
                               :headers {"Authorization" (str "Bearer " token)}})))]
    {:id (str "t-" external-id) :meeting-id external-id :source :platform-native
     :lang "ja" :segments (zoom-http/vtt->segments vtt)}))

(defrecord TeamsPlatform [cfg tenant user-id token-delay]
  p/MeetingPlatform
  (meeting-meta [_ external-id] (->meeting tenant (api-get cfg @token-delay (meeting-path user-id external-id))))
  (fetch-recording [_ external-id] (->recording external-id (api-get cfg @token-delay (str (meeting-path user-id external-id) "/recordings"))))
  (fetch-transcript [_ external-id]
    (->transcript external-id cfg @token-delay user-id
                   (api-get cfg @token-delay (str (meeting-path user-id external-id) "/transcripts"))))
  (list-participants [_ _external-id] [])
  (verify-webhook [_ _headers _raw-body] false))

(defn client
  "cfg: {:tenant-id :client-id :client-secret :http-fn (default jvm-http-fn)
         :json-write :json-read}
  user-id: the Graph user whose onlineMeetings own the target meetings.
  tenant: the consuming org, e.g. \"cloud-itonami\"."
  [{:keys [http-fn] :as cfg} user-id tenant]
  (let [cfg (assoc cfg :http-fn (or http-fn jvm-http-fn))]
    (->TeamsPlatform cfg tenant user-id (delay (fetch-token cfg)))))
