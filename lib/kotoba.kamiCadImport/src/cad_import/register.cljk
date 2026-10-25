(ns cad-import.register
  "SBOM registration request builder for `sbom.etzhayyim.com`.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Ported 1:1 from the
   original `src/register.rs`.

   This namespace stays runtime-agnostic — it does not bring in an HTTP
   client or a JSON library (zero-dependency requirement,
   ADR-2607010930). `register-request` produces a `RegisterRequest` map
   describing the call envelope (URL + headers + body, where `body` is
   the *pre-serialised* SBOM registration payload as a Clojure map with
   string keys, matching the CycloneDX-registration Lexicon field
   names). The caller — a CLI tool, a build hook, or a Worker — performs
   the actual POST after JSON-encoding `:body`.

   Forward-compatible Lexicon (defined in
   `00-contracts/lexicons/ai/gftd/apps/sbom/registerArtifact.json`):

   ```text
   POST https://atproto.etzhayyim.com/xrpc/app.etzhayyim.sbom.registerArtifact
   Authorization: Bearer <Service Auth JWT, lxm=app.etzhayyim.sbom.registerArtifact>
   Content-Type: application/json

   {
     \"format\": \"CycloneDX\", \"specVersion\": \"1.5\",
     \"vehicleId\": \"<asm.vehicle-id>\", \"vehicleRevision\": \"<asm.revision>\",
     \"totalMassKg\": <number>, \"partCount\": <int>,
     \"sourceUri\": \"<asm.source.uri>\", \"sourceSha256\": \"<hex>\",
     \"license\": \"<spdx>\", \"cdxJson\": \"<full CycloneDX 1.5 document, JSON string>\"
   }
   ```"
  (:require [kotoba.lang.text :as str]
            [cad-import.part :as part]
            [cad-import.sbom :as sbom]))

(def default-endpoint
  "Default endpoint. Vehicles registered through this URL flow into the
   same `sbom.etzhayyim.com` SbomArtifact graph as software SBOMs from
   `cargo-cyclonedx` etc. The host is `atproto.etzhayyim.com` (sole XRPC
   gateway per Layer 2 routing — see ADR-2604231828)."
  "https://atproto.etzhayyim.com/xrpc/app.etzhayyim.sbom.registerArtifact")

(defn default-register-options []
  {:endpoint nil :bearer-token nil :serial-number nil :timestamp nil})

(defn register-request
  "Build a `RegisterRequest` map for the given assembly:
   `{:url :method :headers [[k v] ...] :body {...map with CDX-Lexicon
   string keys, :cdxJson is itself an SBOM map (not a JSON string,
   since this crate has no JSON dependency — see namespace docstring)}}`.

   Returns `[:ok request]` or `[:error error-map]`."
  ([asm] (register-request asm (default-register-options)))
  ([asm opts]
   (let [[status cdx-or-err] (sbom/emit asm {:serial-number (:serial-number opts)
                                              :timestamp (:timestamp opts)})]
     (if (= status :error)
       [:error cdx-or-err]
       (let [body {"format" "CycloneDX"
                   "specVersion" "1.5"
                   "vehicleId" (:vehicle-id asm)
                   "vehicleRevision" (:revision asm)
                   "totalMassKg" (part/total-mass-kg asm)
                   "partCount" (count (:parts asm))
                   "sourceUri" (get-in asm [:source :uri])
                   "sourceSha256" (get-in asm [:source :sha256])
                   "license" (get-in asm [:source :license])
                   "cdxJson" cdx-or-err}
             headers (cond-> [["Content-Type" "application/json"]]
                       (:bearer-token opts)
                       (conj ["Authorization" (str "Bearer " (:bearer-token opts))]))]
         [:ok {:url (or (:endpoint opts) default-endpoint)
               :method "POST"
               :headers headers
               :body body}])))))

(defn- shell-escape
  "Single-quote with embedded `'` -> `'\\''` substitution."
  [s]
  (str "'" (str/replace s "'" "'\\''") "'"))

(def ^:private hex-digits "0123456789abcdef")

(defn- hex4
  "4-digit hex for a JSON `\\uXXXX` escape (portable: bit ops + a lookup
  table, no Long/Integer interop that would only work on :clj)."
  [n]
  (apply str (for [shift [12 8 4 0]] (nth hex-digits (bit-and (bit-shift-right n shift) 0xf)))))

(def ^:private json-string-escapes
  "RFC 8259 §7: EVERY control character U+0000-U+001F must be escaped in a
  JSON string, not just the handful with a named shorthand (\\b \\t \\n \\f
  \\r) -- the previous map covered only \\n and \\t, so any other C0
  control byte (verified reachable: ingested CAD-file metadata such as a
  glTF `asset.copyright` string or a STEP header can carry a raw \\r or
  other control byte) was copied through raw, producing a JSON string
  literal with a literal control byte embedded in it -- invalid per
  RFC 8259, confirmed with Python's strict json module rejecting it."
  (into {\" "\\\"" \\ "\\\\"}
        (for [i (range 0x20)]
          [(char i) (case i
                      8 "\\b" 9 "\\t" 10 "\\n" 12 "\\f" 13 "\\r"
                      (str "\\u" (hex4 i)))])))

(defn- json-escape-string [s]
  (str "\"" (str/escape s json-string-escapes) "\""))

(defn edn->json
  "Minimal recursive EDN->JSON string encoder — covers the small subset
   of shapes this crate ever produces (maps with string/keyword keys,
   vectors, strings, numbers, booleans, nil). Kept in-namespace instead
   of taking a `clojure.data.json` dependency (zero-dependency
   requirement, ADR-2607010930); used only by `curl-command`'s
   `--data` argument, mirroring `serde_json::to_string` in the original
   Rust `curl_command`."
  [x]
  (cond
    (nil? x) "null"
    (string? x) (json-escape-string x)
    (keyword? x) (json-escape-string (name x))
    (boolean? x) (str x)
    (number? x) (str x)
    (map? x) (str "{" (str/join "," (map (fn [[k v]] (str (json-escape-string (if (keyword? k) (name k) (str k))) ":" (edn->json v))) x)) "}")
    (sequential? x) (str "[" (str/join "," (map edn->json x)) "]")
    :else (json-escape-string (str x))))

(defn curl-command
  "Convenience: emit a single `curl(1)` command line that performs the
   registration. Pipe the output to `bash` to actually run it. The token
   is read from the `etzhayyim_TOKEN` env var when not provided in
   `opts`.

   Returns `[:ok curl-string]` or `[:error error-map]`."
  ([asm] (curl-command asm (default-register-options)))
  ([asm opts]
   (let [[status req] (register-request asm opts)]
     (if (= status :error)
       [:error req]
       (let [body-json (edn->json (:body req))]
         [:ok (apply str
                      "curl -fsSL"
                      " -X " (:method req)
                      " \\\n  " (shell-escape (:url req))
                      (concat
                       (mapcat (fn [[k v]] [" \\\n  -H " (shell-escape (str k ": " v))])
                               (:headers req))
                       (when-not (:bearer-token opts)
                         [" \\\n  -H \"Authorization: Bearer ${etzhayyim_TOKEN:?etzhayyim_TOKEN must be set, run: gftd agent-token --lxm app.etzhayyim.sbom.registerArtifact}\""])
                       [" \\\n  --data " (shell-escape body-json)]))])))))
