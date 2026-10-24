(ns voicevox.client
  "Portable core for talking to a VOICEVOX Engine
  (https://github.com/VOICEVOX/voicevox_engine, by Hiroshiba Kazuyuki --
  hence this repo's `jp-hiroshiba-voicevox` name) HTTP server: the 2-step
  `POST /audio_query` then `POST /synthesis` flow every VOICEVOX client
  needs, plus one injectable HTTP boundary.

  Ported from `ai-gftd-project-yukkuri`'s `lg/lg_yukkuri/voicevox_client.py`
  (env vars, endpoint shape) and its already-`.cljc`-ported sibling
  `yukkuri.voicevox` (style_id catalog / emotion table / resolve-style-id --
  see `voicevox.speakers` in this repo), which deliberately left the real
  HTTP execution as a `:todo` plan (`ai-gftd-yukkuri/clj/README.md`'s
  no-external-IO design). This repo is that real execution, so any project
  in this ecosystem gets one tested VOICEVOX client instead of re-deriving
  the audio_query/synthesis dance per project.

  Query/response shaping is pure `.cljc`. The actual HTTP call is JVM-only
  by default (`java.net.http`) but every function takes an injectable
  `:http-fn` (`{:url :method :headers :body} -> {:status :body}`, the same
  convention `kotoba-lang/com-cloudflare`/`kotoba-lang/com-youtube` use) --
  `:body` may be a String (JSON) or absent; synthesis responses are raw WAV
  bytes, returned as a byte[] rather than routed through the JSON codec."
  (:require [kotoba.lang.text :as str]
            #?(:clj [json.compat :as json])))

(defn default-base-url []
  #?(:clj (or (System/getenv "VOICEVOX_URL") "http://localhost:50021")
     :cljs "http://localhost:50021"))

#?(:clj (defn write-json [x] (json/generate-string x)))
#?(:clj (defn read-json [s]
          (json/parse-string (if (bytes? s) (String. ^bytes s "UTF-8") s) true)))

#?(:clj
(defn jvm-http-fn
  "Real java.net.http transport. {:url :method :headers :body} ->
  {:status :body-bytes}. Response bodies are ALWAYS read as raw bytes
  (rather than a String) because `/synthesis` returns binary WAV -- callers
  reading a JSON response (`/audio_query`, `/version`, `/speakers`) decode
  `:body-bytes` themselves via `client/read-json` (it accepts a byte[])."
  ([] (jvm-http-fn {}))
  ([{:keys [timeout-seconds] :or {timeout-seconds 60}}]
   (fn [{:keys [url method headers body]}]
     (let [publisher (if body
                       (java.net.http.HttpRequest$BodyPublishers/ofString body)
                       (java.net.http.HttpRequest$BodyPublishers/noBody))
           builder (-> (java.net.http.HttpRequest/newBuilder (java.net.URI/create url))
                      (.timeout (java.time.Duration/ofSeconds timeout-seconds))
                      (as-> b (reduce-kv (fn [b k v] (.header b (name k) (str v))) b headers)))
           request (case method
                     :post (-> builder (.POST publisher) .build)
                     :get (-> builder .GET .build)
                     (throw (ex-info "Unsupported HTTP method" {:method method})))
           resp (.send (java.net.http.HttpClient/newHttpClient) request
                      (java.net.http.HttpResponse$BodyHandlers/ofByteArray))]
       {:status (.statusCode resp) :body-bytes (.body resp)})))))

#?(:clj
(defn audio-query!
  "POST /audio_query?speaker=<style-id>&text=<text> (no body) -> the parsed
  AudioQuery map. Throws ex-info on a non-2xx response."
  ([style-id text] (audio-query! style-id text {}))
  ([style-id text {:keys [http-fn base-url] :or {http-fn (jvm-http-fn) base-url (default-base-url)}}]
   (let [url (str base-url "/audio_query?speaker=" style-id
                 "&text=" (java.net.URLEncoder/encode text "UTF-8"))
         resp (http-fn {:url url :method :post})]
     (when-not (< (:status resp) 300)
       (throw (ex-info "voicevox audio_query failed"
                       {:stage :audio-query :status (:status resp)
                        :body (String. ^bytes (:body-bytes resp) "UTF-8")})))
     (read-json (:body-bytes resp))))))

#?(:clj
(defn synthesis!
  "POST /synthesis?speaker=<style-id> with an AudioQuery JSON body (already
  merged with any speedScale/pitchScale overrides by the caller) -> the WAV
  bytes (byte[]). Throws ex-info on a non-2xx response."
  ([style-id audio-query] (synthesis! style-id audio-query {}))
  ([style-id audio-query {:keys [http-fn base-url]
                          :or {http-fn (jvm-http-fn) base-url (default-base-url)}}]
   (let [resp (http-fn {:url (str base-url "/synthesis?speaker=" style-id)
                        :method :post
                        :headers {"Content-Type" "application/json" "Accept" "audio/wav"}
                        :body (write-json audio-query)})]
     (when-not (< (:status resp) 300)
       (throw (ex-info "voicevox synthesis failed"
                       {:stage :synthesis :status (:status resp)
                        :body (String. ^bytes (:body-bytes resp) "UTF-8")})))
     (:body-bytes resp)))))

#?(:clj
(defn version!
  "GET /version -> the engine version string. Useful as a liveness probe."
  ([] (version! {}))
  ([{:keys [http-fn base-url] :or {http-fn (jvm-http-fn) base-url (default-base-url)}}]
   (let [resp (http-fn {:url (str base-url "/version") :method :get})]
     (when-not (< (:status resp) 300)
       (throw (ex-info "voicevox version check failed" {:status (:status resp)})))
     (String. ^bytes (:body-bytes resp) "UTF-8")))))
