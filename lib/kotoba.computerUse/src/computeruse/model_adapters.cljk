(ns computeruse.model-adapters
  "Interpretation adapters for the resident bot layer (ADR-0003).

  An adapter is a plain function

      (fn [{:keys [prompt image-path]}]
        → {:text \"…\" :tokens n :adapter :kw :raw {…}}
        | {:error \"…\" :adapter :kw})

  — text in, text out, with an optional screenshot. That is the whole
  seam. It is deliberately NOT langchain's ChatModel protocol: the
  resident CLI has to load under nbb from a bare checkout, where the
  langgraph/langchain git deps are not resolvable. computeruse.agent
  and computeruse.openai-model keep the ChatModel seam for the JVM
  tool-calling loop; this namespace is the seam the resident loop uses.
  computeruse.bots/backend->computer bridges the two.

  All I/O goes through the injected sh seam (curl / the claude CLI), so
  no HTTP client is needed on either host.

  MEASURED 2026-08-29 — both adapters were proved to actually read an
  image, not merely to accept one:
    :claude-cli   described a Japanese conversation about bread storage
                  that is visible only inside the screenshot (9.3s,
                  exit 0, permission_denials empty)
    :murakumo     answered \"the ChatGPT desktop application window\"
                  for a capture of the ChatGPT window (64s)
  Neither answer is derivable from the prompt or the file name."
  (:require [computeruse.hostfs :as fs]
            [computeruse.json :as json]
            [kotoba.lang.text :as str]))

;; ───────────────────────── claude CLI ─────────────────────────

(def claude-default-model
  "An ALIAS, not a concrete model id — the CLI resolves it, so this
  follows model rotation the way murakumo-main does. Override with
  CUA_CLAUDE_MODEL. Never write a dated model id here."
  "haiku")

(defn claude-cli-adapter
  "Shells `claude -p` and hands it the screenshot by path.

  The subprocess is spawned with its cwd set to the directory holding
  the image and the image referenced by basename, because Claude Code
  will not Read outside its working directory — a bot whose frames live
  in /tmp and whose CLI runs in a checkout would otherwise get a silent
  'I cannot see an image' answer that looks exactly like a model that
  looked and saw nothing.

  opts: {:sh :bin :model :timeout-ms :extra-args}"
  [{:keys [sh bin model timeout-ms extra-args]}]
  (let [bin (or bin (fs/getenv "CUA_CLAUDE_BIN") "claude")
        model (or model (fs/getenv "CUA_CLAUDE_MODEL") claude-default-model)
        timeout-ms (or timeout-ms 300000)]
    (fn claude-cli [{:keys [prompt image-path]}]
      (let [dir (if image-path (fs/dirname image-path) (fs/cwd))
            prompt (if image-path
                     (str "Read the image file ./" (fs/basename image-path)
                          " in the current directory. It is a screenshot.\n\n"
                          prompt)
                     prompt)
            argv (into [bin "-p" prompt
                        "--allowedTools" "Read"
                        "--output-format" "json"
                        "--model" model]
                       (or extra-args []))
            r (sh argv {:cwd dir :timeout-ms timeout-ms})]
        (if (= -1 (:exit r))
          {:error (str "claude CLI never ran: " (str/trim (str (:err r))))
           :adapter :claude-cli}
          (let [parsed (json/read-safe (:out r))]
            (cond
              (nil? parsed)
              {:error (str "claude CLI output was not JSON (exit " (:exit r) "): "
                           (str/trim (subs (str (:out r)) 0 (min 400 (count (str (:out r)))))))
               :adapter :claude-cli}

              (true? (:is_error parsed))
              {:error (str "claude CLI reported an error: " (:result parsed))
               :adapter :claude-cli :raw (select-keys parsed [:subtype :stop_reason])}

              :else
              (let [u (:usage parsed)]
                {:text (str (:result parsed))
                 ;; Only the turn's own input+output. cache_read is Claude
                 ;; Code's own system-prompt cache (35k on an empty call,
                 ;; measured) and would exhaust any bot budget instantly;
                 ;; the whole usage map is kept in :raw so nothing is lost.
                 :tokens (+ (or (:input_tokens u) 0) (or (:output_tokens u) 0))
                 :adapter :claude-cli
                 :model model
                 :raw {:usage u :num_turns (:num_turns parsed)
                       :permission_denials (:permission_denials parsed)}}))))))))

;; ───────────────────────── OpenAI-compatible ─────────────────────────

(defn- base64-file
  "PNG → base64 string, via the sh seam. Tries BSD `base64 -i` then the
  GNU form. Returns nil when neither works."
  [sh path]
  (let [try1 (sh ["base64" "-i" (str path)] {:timeout-ms 60000})
        r (if (zero? (:exit try1)) try1 (sh ["base64" (str path)] {:timeout-ms 60000}))]
    (when (zero? (:exit r))
      (str/replace (str (:out r)) #"\s" ""))))

(defn- post-json
  "curl a JSON body (written to a temp file — a base64 screenshot is far
  past ARG_MAX) and read the response. → parsed map or {:error ..}."
  [sh url body-edn timeout-ms headers]
  (let [body-file (str (fs/tmp-dir) "/cua-req-" (fs/epoch-ms) ".json")
        out-file (str (fs/tmp-dir) "/cua-resp-" (fs/epoch-ms) ".json")]
    (fs/write-file! body-file (json/write body-edn))
    (let [r (sh (into ["curl" "-sS" "--max-time" (str (quot (or timeout-ms 300000) 1000))
                       "-o" out-file "-w" "%{http_code}"
                       "-X" "POST" url
                       "-H" "content-type: application/json"]
                      (into (vec (mapcat (fn [[k v]] ["-H" (str k ": " v)]) headers))
                            ["--data-binary" (str "@" body-file)]))
                {:timeout-ms (+ 10000 (or timeout-ms 300000))})
          status (str/trim (str (:out r)))]
      (cond
        (not (zero? (:exit r)))
        {:error (str "curl failed (" (:exit r) "): " (str/trim (str (:err r))))}

        (not (str/starts-with? status "2"))
        {:error (str "HTTP " status " from " url ": "
                     (when (fs/path-exists? out-file)
                       (let [b (fs/read-file out-file)]
                         (subs b 0 (min 400 (count b))))))}

        :else
        (let [parsed (json/read-safe (when (fs/path-exists? out-file) (fs/read-file out-file)))]
          (or parsed {:error (str "response from " url " was not JSON")}))))))

(defn openai-compat-adapter
  "Any OpenAI-compatible /chat/completions endpoint (llama.cpp, Ollama,
  vLLM, a gateway). Images go as image_url data: parts — the same wire
  shape computeruse.openai-model builds for the JVM ChatModel seam.

  opts: {:sh :url :model :api-key :max-tokens :timeout-ms :adapter-id}"
  [{:keys [sh url model api-key max-tokens timeout-ms adapter-id]}]
  (let [adapter-id (or adapter-id :openai-compat)]
    (fn openai-compat [{:keys [prompt image-path]}]
      (let [b64 (when image-path (base64-file sh image-path))]
        (if (and image-path (nil? b64))
          {:error (str "could not base64-encode " image-path) :adapter adapter-id}
          (let [content (cond-> [{:type "text" :text prompt}]
                          b64 (conj {:type "image_url"
                                     :image_url {:url (str "data:image/png;base64," b64)}}))
                body {:model model
                      :max_tokens (or max-tokens 1024)
                      :messages [{:role "user" :content content}]}
                headers (cond-> {} api-key (assoc "authorization" (str "Bearer " api-key)))
                resp (post-json sh url body timeout-ms headers)]
            (if (:error resp)
              (assoc (select-keys resp [:error]) :adapter adapter-id)
              (let [text (get-in resp [:choices 0 :message :content])]
                (if (nil? text)
                  {:error (str "no choices[0].message.content in the response from " url)
                   :adapter adapter-id}
                  {:text (str text)
                   :tokens (or (get-in resp [:usage :total_tokens]) 0)
                   :adapter adapter-id
                   :model (:model resp)
                   :raw {:usage (:usage resp) :endpoint url}})))))))))

;; ───────────────────────── murakumo ─────────────────────────

(def murakumo-alias
  "The workspace-wide fleet-main alias. Resolution order per the
  repo-wide rule: env override → the alias entry → an endpoint-only
  fallback. The concrete model id behind it is never written down."
  "murakumo-main")

(def murakumo-alias-url
  (str "https://api.murakumo.cloud/infer/models/" murakumo-alias))

(def murakumo-fallback-endpoint
  "Endpoint only — no model id. Measured 2026-08-29: this answers, while
  the endpoint the alias entry itself declares (infer.murakumo.cloud)
  returned HTTP 404 for both a text and a vision request on the same day.
  The resolver therefore tries the alias's endpoint first and falls back
  here, and records which one answered."
  "https://api.murakumo.cloud/v1/chat/completions")

(defn resolve-murakumo-endpoints
  "→ {:endpoints [url…] :alias-entry {…}|nil :why str}. Never throws:
  an unreachable alias service is a reason to fall back, not to fail."
  [sh]
  (if-let [override (fs/getenv "CUA_MURAKUMO_URL")]
    {:endpoints [override] :alias-entry nil :why "CUA_MURAKUMO_URL override"}
    (let [r (sh ["curl" "-sS" "--max-time" "20" murakumo-alias-url] {:timeout-ms 30000})
          entry (when (zero? (:exit r)) (json/read-safe (:out r)))
          declared (:endpoint entry)]
      {:alias-entry entry
       :endpoints (vec (distinct (remove nil? [declared murakumo-fallback-endpoint])))
       :why (cond
              (nil? entry) "alias entry unreadable; endpoint-only fallback"
              declared (str "alias " murakumo-alias " → " (:alias-for entry)
                            "; declared endpoint " declared ", fallback "
                            murakumo-fallback-endpoint)
              :else "alias entry had no :endpoint; endpoint-only fallback")})))

(defn murakumo-adapter
  "The murakumo fleet main model, resolved through the murakumo-main
  alias. `model` sent on the wire is the alias itself, so a rotation on
  the fleet side is picked up with no change here.

  opts: {:sh :max-tokens :timeout-ms}"
  [{:keys [sh max-tokens timeout-ms]}]
  (let [{:keys [endpoints why alias-entry]} (resolve-murakumo-endpoints sh)]
    (fn murakumo [req]
      (loop [[url & more] endpoints
             tried []]
        (if (nil? url)
          {:error (str "no murakumo endpoint answered (" why "); tried "
                       (str/join ", " tried))
           :adapter :murakumo}
          (let [f (openai-compat-adapter {:sh sh :url url :model murakumo-alias
                                          :max-tokens max-tokens
                                          :timeout-ms (or timeout-ms 300000)
                                          :adapter-id :murakumo})
                r (f req)]
            (if (:error r)
              (recur more (conj tried (str url " → " (:error r))))
              (assoc r :raw (merge (:raw r)
                                   {:alias murakumo-alias
                                    :alias-for (:alias-for alias-entry)
                                    :resolution why})))))))))

;; ───────────────────────── selection ─────────────────────────

(def adapter-ids #{:claude-cli :murakumo :openai-compat})

(def default-adapter-id
  "The measured-working default (2026-08-29). :claude-cli read the image
  in 9.3s; :murakumo read it correctly too but took 64s on the same
  frame. Both work; the faster one is the default."
  :claude-cli)

(defn make-adapter
  "id + opts → adapter fn, or nil for an unknown id."
  [id opts]
  (case id
    :claude-cli (claude-cli-adapter opts)
    :murakumo (murakumo-adapter opts)
    :openai-compat (openai-compat-adapter opts)
    nil))
