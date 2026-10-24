(ns kotoba.webrtc.whip
  "WHIP -- WebRTC-HTTP Ingestion Protocol (RFC 9725) -- as pure data.

  WHIP is how a browser publishes a single outbound media stream to an
  ingest server (Cloudflare Stream Live, Cloudflare Realtime, MediaMTX,
  Broadcast Box, Dolby, ...) over plain HTTP: one POST carries the SDP
  offer, the response carries the SDP answer plus a resource URL, and that
  resource URL is later PATCHed (trickle ICE) and DELETEd (teardown).

  Same contract as the rest of this library: no socket is opened, no
  `RTCPeerConnection` is touched, no HTTP client is required. Every
  function here maps data to data --

    request builders  : args           -> {:url :method :headers :body}
    response readers  : {:status :headers :body} -> parsed map
    `apply-event`     : session + event -> {:session :effects}

  -- and the host runtime supplies the transport and performs the effects,
  exactly as `kotoba.webrtc.session` does for peer-to-peer call signaling.
  This one models the *ingest* leg instead: one publisher, one server, no
  remote peer to negotiate with.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

(def sdp-content-type "application/sdp")

(def trickle-content-type
  "RFC 9725 §4.6 -- the media type carrying an SDP fragment for trickle ICE
  and ICE restart. NOT application/sdp: a server that only accepts whole
  session descriptions must be able to reject a fragment on content type
  alone."
  "application/trickle-ice-sdpfrag")

;; ---------------------------------------------------------------------------
;; URL resolution
;;
;; The single most common WHIP client bug: RFC 9725 §4.1 lets the server
;; return a *relative* Location, and a client that treats it as absolute
;; then PATCHes/DELETEs a URL that does not exist (silently leaking the
;; ingest session until the server times it out). Resolution is pure string
;; work here rather than java.net.URI / goog.Uri so the same code runs on
;; every target this library supports.
;; ---------------------------------------------------------------------------

(defn- absolute-url? [s]
  (boolean (re-find #"^[a-zA-Z][a-zA-Z0-9+.-]*://" s)))

(defn- split-url
  "Break an absolute URL into {:origin :path}. :origin keeps the scheme and
  authority (no trailing slash); :path always starts with \"/\" and keeps
  any query/fragment."
  [url]
  (if-let [m (re-find #"^([a-zA-Z][a-zA-Z0-9+.-]*://[^/?#]+)(.*)$" url)]
    (let [origin (nth m 1)
          rest' (nth m 2)]
      {:origin origin
       :path (if (str/blank? rest') "/" rest')})
    {:origin "" :path url}))

(defn- parent-path
  "Directory portion of an URL path, with its trailing slash -- the base a
  relative reference resolves against (RFC 3986 §5.2.3). Query and fragment
  are dropped: they belong to the base URL, not to its directory."
  [path]
  (let [path (str/replace path #"[?#].*$" "")
        idx (str/last-index-of path "/")]
    (if idx (subs path 0 (inc idx)) "/")))

(defn resolve-url
  "Resolve `location` (as returned in a Location header) against `base`.

  Handles the four forms RFC 3986 §4.2 allows a server to reply with:
  absolute (`https://host/x`), network-path (`//host/x`), absolute-path
  (`/x`), and relative-path (`x` / `../x`). Returns `base` itself when
  `location` is blank."
  [base location]
  (cond
    (str/blank? location) base
    (absolute-url? location) location
    :else
    (let [{:keys [origin path]} (split-url base)
          scheme (or (second (re-find #"^([a-zA-Z][a-zA-Z0-9+.-]*):" origin)) "https")]
      (cond
        (str/starts-with? location "//") (str scheme ":" location)
        (str/starts-with? location "/") (str origin location)
        :else (str origin (parent-path path) location)))))

;; ---------------------------------------------------------------------------
;; Headers
;;
;; Header names are case-insensitive (RFC 9110 §5.1) but the maps handed to
;; us come from whatever HTTP client the host chose -- fetch lowercases,
;; java.net.http preserves, some hand-rolled stubs title-case. Every read
;; goes through `header` so a correct server response is never missed over
;; capitalization.
;; ---------------------------------------------------------------------------

(defn header
  "Case-insensitive header lookup. `headers` may key by string or keyword.
  Returns the first match, or nil."
  [headers header-name]
  (let [wanted (str/lower (name header-name))]
    (some (fn [[k v]]
            (when (= wanted (str/lower (name k)))
              (if (sequential? v) (first v) v)))
          headers)))

(defn header-values
  "Every value for `header-name`, flattened. A server may send Link either
  as repeated headers (a sequential value here) or as one comma-joined
  value; callers should not have to care which."
  [headers header-name]
  (let [wanted (str/lower (name header-name))]
    (into []
          (comp (filter (fn [[k _]] (= wanted (str/lower (name k)))))
                (mapcat (fn [[_ v]] (if (sequential? v) v [v]))))
          headers)))

;; ---------------------------------------------------------------------------
;; Link headers -> ICE servers (RFC 9725 §4.4, RFC 8288)
;; ---------------------------------------------------------------------------

(defn- split-links
  "Split one Link header value on the commas that separate link-values,
  ignoring commas inside a quoted string or inside the <URI-Reference>.
  (A naive split on #\",\" corrupts every TURN entry, whose credential
  routinely contains one.)"
  [s]
  (loop [chars (seq s), acc [], cur [], in-quotes? false, in-angle? false, escaped? false]
    (if-let [c (first chars)]
      (let [rest' (rest chars)]
        (cond
          escaped? (recur rest' acc (conj cur c) in-quotes? in-angle? false)
          (and in-quotes? (= c \\)) (recur rest' acc (conj cur c) in-quotes? in-angle? true)
          (= c \") (recur rest' acc (conj cur c) (not in-quotes?) in-angle? false)
          (and (not in-quotes?) (= c \<)) (recur rest' acc (conj cur c) in-quotes? true false)
          (and (not in-quotes?) (= c \>)) (recur rest' acc (conj cur c) in-quotes? false false)
          (and (= c \,) (not in-quotes?) (not in-angle?))
          (recur rest' (conj acc (apply str cur)) [] false false false)
          :else (recur rest' acc (conj cur c) in-quotes? in-angle? false)))
      (conj acc (apply str cur)))))

(defn- unquote-param [s]
  (let [s (str/trim s)]
    (if (and (> (count s) 1) (str/starts-with? s "\"") (str/ends-with? s "\""))
      (str/replace (subs s 1 (dec (count s))) #"\\(.)" "$1")
      s)))

(defn- split-params
  "Split a link-value's parameter section on `;`, respecting quoted strings."
  [s]
  (loop [chars (seq s), acc [], cur [], in-quotes? false, escaped? false]
    (if-let [c (first chars)]
      (let [rest' (rest chars)]
        (cond
          escaped? (recur rest' acc (conj cur c) in-quotes? false)
          (and in-quotes? (= c \\)) (recur rest' acc (conj cur c) in-quotes? true)
          (= c \") (recur rest' acc (conj cur c) (not in-quotes?) false)
          (and (= c \;) (not in-quotes?)) (recur rest' (conj acc (apply str cur)) [] false false)
          :else (recur rest' acc (conj cur c) in-quotes? false)))
      (conj acc (apply str cur)))))

(defn parse-link
  "Parse one RFC 8288 link-value into {:uri :params}, or nil if it has no
  <URI-Reference>. Parameter names are lower-cased keywords; values are
  unquoted."
  [link-value]
  (let [s (str/trim link-value)]
    (when-let [m (re-find #"^<([^>]*)>\s*(.*)$" s)]
      (let [uri (nth m 1)
            param-str (nth m 2)
            params (into {}
                         (keep (fn [p]
                                 (let [p (str/trim p)]
                                   (when-not (str/blank? p)
                                     (let [idx (str/index-of p "=")]
                                       (if idx
                                         [(keyword (str/lower (str/trim (subs p 0 idx))))
                                          (unquote-param (subs p (inc idx)))]
                                         [(keyword (str/lower p)) true]))))))
                         (rest (split-params param-str)))]
        {:uri uri :params params}))))

(defn parse-links
  "Every link-value across every Link header in `headers`, parsed."
  [headers]
  (into [] (comp (mapcat split-links)
                 (keep parse-link))
        (header-values headers :link)))

(defn ice-servers
  "The `rel=\"ice-server\"` links in `headers`, as RTCIceServer-shaped maps
  ({:urls :username :credential :credential-type}) ready to hand to
  `RTCPeerConnection`. Keys with no value present are omitted rather than
  set to nil, so the map can be passed straight through to the browser API
  (which rejects an explicit null credential)."
  [headers]
  (into []
        (comp (filter #(= "ice-server" (get-in % [:params :rel])))
              (map (fn [{:keys [uri params]}]
                     (cond-> {:urls uri}
                       (:username params) (assoc :username (:username params))
                       (:credential params) (assoc :credential (:credential params))
                       (:credential-type params) (assoc :credential-type (:credential-type params))))))
        (parse-links headers)))

;; ---------------------------------------------------------------------------
;; Requests
;; ---------------------------------------------------------------------------

(defn- auth-headers [bearer-token]
  (if (str/blank? (str bearer-token))
    {}
    {"Authorization" (str "Bearer " bearer-token)}))

(defn publish-request
  "The POST that starts an ingest session (RFC 9725 §4.1).

  opts:
    :endpoint     WHIP endpoint URL (required)
    :offer-sdp    local SDP offer (required)
    :bearer-token optional; omitted entirely when blank rather than sent as
                  \"Bearer \" -- some ingest servers reject a malformed
                  Authorization header outright where they would have
                  accepted no header at all."
  [{:keys [endpoint offer-sdp bearer-token]}]
  {:url endpoint
   :method :post
   :headers (merge {"Content-Type" sdp-content-type} (auth-headers bearer-token))
   :body offer-sdp})

(def ^:private status->error
  {400 :bad-request
   401 :unauthorized
   403 :forbidden
   404 :not-found
   405 :method-not-allowed
   406 :unsupported-content-type
   409 :conflict
   412 :precondition-failed
   415 :unsupported-content-type
   422 :unprocessable
   429 :rate-limited})

(defn- error-for [status]
  (or (status->error status)
      (cond
        (>= status 500) :server-error
        (>= status 400) :client-error
        :else :unexpected-status)))

(defn publish-response
  "Read the ingest server's reply to `publish-request`.

  On success returns {:ok? true :answer-sdp :resource-url :ice-servers
  :etag}; `:resource-url` is already resolved against the endpoint. On
  failure returns {:ok? false :error <keyword> :status :body}.

  A 2xx whose body is empty is treated as a failure (`:missing-answer`):
  without an answer SDP there is nothing to feed
  `setRemoteDescription`, and reporting \"connected\" here would be the
  kind of silent lie that leaves a broadcaster staring at a live button
  with no stream behind it. A 2xx with an answer but no Location is
  accepted -- the session works, only teardown/trickle is unavailable --
  and flagged via :resource-url nil."
  [endpoint {:keys [status headers body]}]
  (if (and (number? status) (<= 200 status 299))
    (if (str/blank? (str body))
      {:ok? false :error :missing-answer :status status :body body}
      (let [location (header headers :location)]
        {:ok? true
         :answer-sdp body
         :resource-url (when-not (str/blank? (str location))
                         (resolve-url endpoint location))
         :ice-servers (ice-servers headers)
         :etag (header headers :etag)}))
    {:ok? false :error (error-for (or status 0)) :status status :body body}))

(defn trickle-request
  "The PATCH that delivers additional local ICE candidates, or an ICE
  restart, to an established resource (RFC 9725 §4.6).

  opts:
    :resource-url  from `publish-response` (required)
    :sdp-fragment  body, see `candidates->sdp-fragment` (required)
    :etag          when present, sent as If-Match. RFC 9725 requires this
                   for an ICE *restart*; for plain candidate delivery it is
                   optional and simply makes the request fail closed (412)
                   if the session was replaced underneath us."
  [{:keys [resource-url sdp-fragment etag bearer-token]}]
  {:url resource-url
   :method :patch
   :headers (cond-> (merge {"Content-Type" trickle-content-type} (auth-headers bearer-token))
              (not (str/blank? (str etag))) (assoc "If-Match" etag))
   :body sdp-fragment})

(defn trickle-supported?
  "Whether a trickle PATCH reply means the server supports trickle ICE at
  all. RFC 9725 §4.6 lets a server that only accepts the initial offer
  answer 405/501; that is not an error to surface to the user -- the
  candidates in the original offer still stand -- it just means the client
  should stop sending them."
  [{:keys [status]}]
  (not (contains? #{405 501} status)))

(defn terminate-request
  "The DELETE that ends the ingest session and frees the server's resource
  (RFC 9725 §4.7). Sending this is what stops an ingest server from
  charging for -- or continuing to advertise -- a session whose publisher
  has already gone away."
  [{:keys [resource-url bearer-token]}]
  {:url resource-url
   :method :delete
   :headers (auth-headers bearer-token)})

;; ---------------------------------------------------------------------------
;; SDP fragments (RFC 8840 §6)
;; ---------------------------------------------------------------------------

(defn- candidate-line
  "`a=candidate:...` for one candidate. Accepts the raw string a browser's
  RTCIceCandidate carries (which already begins with \"candidate:\") as
  well as a bare attribute value."
  [candidate]
  (let [c (str/trim (str candidate))]
    (cond
      (str/blank? c) nil
      (str/starts-with? c "a=") c
      :else (str "a=" (if (str/starts-with? c "candidate:") c (str "candidate:" c))))))

(defn candidates->sdp-fragment
  "Build the `application/trickle-ice-sdpfrag` body carrying `candidates`.

  opts:
    :ice-ufrag   local ICE username fragment (required by RFC 8840 -- it is
                 how the server binds the fragment to the right ICE
                 generation, so an omitted ufrag makes the whole PATCH
                 unmatchable)
    :ice-pwd     local ICE password
    :candidates  seq of maps {:candidate :sdp-mid :media}. `:candidate` may
                 be the raw browser string. Candidates are grouped by
                 :sdp-mid so a bundled audio+video session emits one
                 m-section per mid, in first-seen order.

  An end-of-candidates signal is expressed by passing a candidate map whose
  :candidate is blank -- it emits `a=end-of-candidates` for that mid, which
  is how the server learns it can stop waiting."
  [{:keys [ice-ufrag ice-pwd candidates]}]
  (let [groups (reduce (fn [acc {:keys [sdp-mid] :as c}]
                         (let [mid (str (or sdp-mid "0"))]
                           (update acc mid (fnil conj []) c)))
                       {}
                       candidates)
        ;; first-seen mid order: a map would reorder mids, and the server
        ;; matches m-sections positionally against the original offer.
        mids (distinct (map #(str (or (:sdp-mid %) "0")) candidates))
        lines (concat
               (when-not (str/blank? (str ice-ufrag)) [(str "a=ice-ufrag:" ice-ufrag)])
               (when-not (str/blank? (str ice-pwd)) [(str "a=ice-pwd:" ice-pwd)])
               (mapcat (fn [mid]
                         (let [cs (get groups mid)
                               media (or (some :media cs) "audio")]
                           (concat [(str "m=" media " 9 RTP/AVP 0")
                                    (str "a=mid:" mid)]
                                   (let [ls (keep #(candidate-line (:candidate %)) cs)]
                                     (if (seq ls) ls ["a=end-of-candidates"])))))
                       mids))]
    (when (seq lines)
      (str (str/join "\r\n" lines) "\r\n"))))

;; ---------------------------------------------------------------------------
;; Session reducer
;; ---------------------------------------------------------------------------

(def states
  "Valid ingest-session states."
  #{:idle :publishing :published :terminating :ended :failed})

(def terminal-states #{:ended :failed})

(defn create-session
  "A new ingest session against `endpoint`, in :idle."
  ([endpoint] (create-session endpoint nil))
  ([endpoint bearer-token]
   {:whip/endpoint endpoint
    :whip/bearer-token bearer-token
    :whip/state :idle
    :whip/resource-url nil
    :whip/etag nil
    :whip/ice-servers []
    :whip/trickle? true
    :whip/pending-candidates []
    :whip/error nil}))

(defn- transition [session next-state effects]
  (if (contains? terminal-states (:whip/state session))
    {:session session :effects []}
    {:session (assoc session :whip/state next-state) :effects effects}))

(defn apply-event
  "Apply an ingest event to `session`, returning {:session :effects}.

    {:type :publish :offer-sdp sdp}
      :idle -> :publishing, effect [:http-request <publish-request>]

    {:type :response :response {:status :headers :body}}
      :publishing -> :published, effects [[:set-remote-description answer]
                                          [:use-ice-servers servers]]
                  -> :failed on a non-2xx, effect [:report-error err]

    {:type :ice-candidate :candidate c :sdp-mid m :media media
     :ice-ufrag u :ice-pwd p}
      buffered while :publishing (the resource URL does not exist yet --
      dropping them instead, as a naive client does, costs exactly the
      candidates gathered during the round trip, which on a mobile network
      are often the only ones that would have worked);
      flushed as one [:http-request <trickle-request>] once :published.

    {:type :trickle-response :response r}
      turns :whip/trickle? off on 405/501; no effects either way.

    {:type :terminate}
      -> :terminating with [:http-request <terminate-request>] when a
      resource URL is known, else straight to :ended.

    {:type :terminated} -> :ended
    {:type :failed :error e} -> :failed, effect [:report-error e]

  Unknown or out-of-state events return the session unchanged."
  [session {:keys [type offer-sdp response candidate sdp-mid media ice-ufrag ice-pwd error]}]
  (let [state (:whip/state session)]
    (case type
      :publish
      (if (= state :idle)
        (transition session :publishing
                    [[:http-request (publish-request {:endpoint (:whip/endpoint session)
                                                      :offer-sdp offer-sdp
                                                      :bearer-token (:whip/bearer-token session)})]])
        {:session session :effects []})

      :response
      (if (= state :publishing)
        (let [parsed (publish-response (:whip/endpoint session) response)]
          (if (:ok? parsed)
            (let [pending (:whip/pending-candidates session)
                  next (assoc session
                              :whip/resource-url (:resource-url parsed)
                              :whip/etag (:etag parsed)
                              :whip/ice-servers (:ice-servers parsed)
                              :whip/pending-candidates [])
                  flush-effects (when (and (seq pending) (:resource-url parsed))
                                  [[:http-request
                                    (trickle-request
                                     {:resource-url (:resource-url parsed)
                                      :bearer-token (:whip/bearer-token session)
                                      :sdp-fragment (candidates->sdp-fragment
                                                     {:ice-ufrag (:ice-ufrag (first pending))
                                                      :ice-pwd (:ice-pwd (first pending))
                                                      :candidates pending})})]])]
              (transition next :published
                          (into [[:set-remote-description (:answer-sdp parsed)]
                                 [:use-ice-servers (:ice-servers parsed)]]
                                flush-effects)))
            (transition (assoc session :whip/error parsed) :failed
                        [[:report-error parsed]])))
        {:session session :effects []})

      :ice-candidate
      (let [entry {:candidate candidate :sdp-mid sdp-mid :media media
                   :ice-ufrag ice-ufrag :ice-pwd ice-pwd}]
        (cond
          (= state :publishing)
          {:session (update session :whip/pending-candidates conj entry) :effects []}

          (and (= state :published) (:whip/trickle? session) (:whip/resource-url session))
          {:session session
           :effects [[:http-request
                      (trickle-request {:resource-url (:whip/resource-url session)
                                        :bearer-token (:whip/bearer-token session)
                                        :sdp-fragment (candidates->sdp-fragment
                                                       {:ice-ufrag ice-ufrag
                                                        :ice-pwd ice-pwd
                                                        :candidates [entry]})})]]}

          :else {:session session :effects []}))

      :trickle-response
      {:session (cond-> session
                  (not (trickle-supported? response)) (assoc :whip/trickle? false))
       :effects []}

      :terminate
      (if (contains? terminal-states state)
        {:session session :effects []}
        (if-let [resource (:whip/resource-url session)]
          (transition session :terminating
                      [[:http-request (terminate-request {:resource-url resource
                                                          :bearer-token (:whip/bearer-token session)})]])
          (transition session :ended [])))

      :terminated (transition session :ended [])

      :failed (transition (assoc session :whip/error error) :failed [[:report-error error]])

      {:session session :effects []})))
