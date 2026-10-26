(ns kototama.browser
  "R2: browser-native host parity matrix vs kototama.tender (JVM).

   Pure data — no DOM, no Wasm. Documents what
   kotoba-lang/wasm-webcomponent `actor-host.js` implements synchronously
   vs what the JVM tender implements. Used by doctor / maturity report.

   Honest gaps:
   - http-post: real in a browser tab as of wasm-webcomponent PR #8
     (2026-07-16) -- a SharedArrayBuffer+Atomics.wait bridge
     (http-post-bridge.js's createSabHttpPostBridge), but only inside a
     cross-origin-isolated page (COOP/COEP headers) with the guest
     instantiated in a dedicated Worker (Atomics.wait is disallowed on the
     main/DOM thread) -- see kotoba-wasm-worker-host.js /
     kotoba-wasm-worker-element.js and
     test/browser/verify_http_post_browser.cljs there for the real,
     verified end-to-end path
   - llm-infer: real in a browser tab as of wasm-webcomponent PR #11
     (2026-07-16) -- reuses the SAME Worker+SAB+Atomics bridge http-post
     proved out (kotoba-wasm-worker-host.js passes ONE bridge instance as
     both httpPostBridge and llmInferBridge). NOT a direct call to a real
     LLM provider, though: a browser tab can never hold a provider API key
     without shipping it to every visitor, so this requires a
     developer-controlled proxy URL (llmInferUrl) that itself holds any
     real credential server-side -- see
     test/browser/verify_llm_infer_browser.cljs there.
   - http-fetch/http-post-headers: real as of wasm-webcomponent PR #15
     (2026-07-26), using the same injected or SAB+Worker network transport,
     exact JVM ABI shapes, independent quotas and the shared session authority.
   - kgraph-*: separate surface (kgraph.js), not actor:host"
  (:require [kototama.contract :as contract]
            [kototama.denial :as denial]
            [kototama.wasm-fields :as fields]))

(def host-impl
  "Per-import availability by host kind.

   :jvm     — kototama.tender (Chicory)
   :browser — wasm-webcomponent actor-host.js (sync only)
   :node    — same JS module under Node (inject only where actor-host implements:
             kagi-sign/http-post/http-fetch/http-post-headers/llm-infer;
             transport/tls/pg/scram absent — see kotoba-lang#356)"
  {:gen-keypair     {:jvm :yes :browser :yes :node :yes
                     :note "browser: @noble/curves vendored sync Ed25519"}
   :sign            {:jvm :yes :browser :yes :node :yes}
   :verify          {:jvm :yes :browser :yes :node :yes}
   :sha256-hex      {:jvm :yes :browser :yes :node :yes}
   ;; :browser is genuinely :yes as of wasm-webcomponent PR #8 (2026-07-16):
   ;; createSabHttpPostBridge (SharedArrayBuffer+Atomics.wait) is real and
   ;; verified end-to-end in real headless Chromium
   ;; (test/browser/verify_http_post_browser.cljs there) -- but only inside
   ;; a cross-origin-isolated page (COOP/COEP headers), with the guest
   ;; instantiated in a dedicated Worker (Atomics.wait can't run on the
   ;; main/DOM thread). Two real bugs had to be fixed to get here (a
   ;; TextDecoder-on-SharedArrayBuffer rejection, and a Worker-startup race)
   ;; -- an earlier merge to that repo's main had wired this import but
   ;; never actually completed a request.
   :http-post       {:jvm :yes :browser :coop-or-inject :node :inject
                     :note "browser: Worker-hosted guest + SAB+Atomics bridge, requires COOP/COEP headers (not ambient); node: opts.httpPost inject"}
   :log-read        {:jvm :yes :browser :yes :node :yes}
   :log-write       {:jvm :yes :browser :yes :node :yes}
   :clock-monotonic {:jvm :yes :browser :yes :node :yes}
   :random-bytes    {:jvm :yes :browser :yes :node :yes
                     :note "bounded OS/Web Crypto CSPRNG; default max-random-bytes 0 (deny-by-default)"}
   :kagi-sign       {:jvm :yes :browser :no :node :inject
                     :note "decision-aware trusted adapter only; finite max-kagi-signs; key never enters guest or browser"}
   ;; :browser is genuinely :yes as of wasm-webcomponent PR #11 (2026-07-16):
   ;; reuses the SAME Worker+SAB+Atomics bridge http-post proved out
   ;; (kotoba-wasm-worker-host.js constructs ONE bridge, passes it as both
   ;; httpPostBridge and llmInferBridge). Requires a caller-supplied
   ;; llmInferUrl pointing at a developer-controlled proxy that holds any
   ;; real LLM provider credential server-side -- never a provider endpoint
   ;; called directly with a key embedded in browser-shipped JS/HTML.
   :llm-infer       {:jvm :yes :browser :coop-or-inject :node :inject
                     :note "browser: Worker-hosted guest + SAME SAB+Atomics bridge as http-post (requires COOP/COEP headers, not ambient), via a caller-supplied proxy URL (never a provider key embedded client-side); node: opts.llmInfer inject"}
   :http-fetch          {:jvm :yes :browser :yes :node :inject
                         :note "browser: shared Worker+SAB transport; node: opts.httpFetch inject; independent maxHttpFetches quota"}
   ;; Ported to wasm-webcomponent's actor-host.js as a byte-for-byte JS
   ;; port of tender.clj's flat-pairs -> CBOR/JSON encoders and bounded
   ;; JSON field scan (pure computation, no SAB/Worker bridge needed).
   ;; Byte-parity against the JVM outputs is locked by that repo's
   ;; test/verify-codec-host.mjs (the maturity.md R1 fixture values:
   ;; cbor {"a":"b"} = a1 61 61 61 62, 25-byte nested cbor, the nested
   ;; JSON object+array string, json-extract present/absent).
   :cbor-encode         {:jvm :yes :browser :yes :node :yes
                         :note "browser: byte-for-byte JS port in wasm-webcomponent actor-host.js (pure computation, no bridge)"}
   :json-encode         {:jvm :yes :browser :yes :node :yes
                         :note "browser: byte-for-byte JS port in wasm-webcomponent actor-host.js (pure computation, no bridge)"}
   :json-extract-field  {:jvm :yes :browser :yes :node :yes
                         :note "browser: byte-for-byte JS port in wasm-webcomponent actor-host.js (pure computation, no bridge)"}
   :http-post-headers  {:jvm :yes :browser :yes :node :inject
                        :note "browser: shared Worker+SAB transport; exact flat-pair headers ABI and shared maxHttpPosts quota"}
   :transport-connect {:jvm :inject :browser :no :node :inject
                       :note "JVM: transport-provider via :provider-host-functions; Node: actor-host fail-closed inject (wasm-webcomponent#17); browser intentional native boundary"}
   :tls-open {:jvm :inject :browser :no :node :inject
              :note "JVM transport-provider inject; Node: actor-host fail-closed inject (wasm-webcomponent#17); browser intentional native boundary"}
   :tls-server-end-point {:jvm :inject :browser :no :node :inject
                          :note "JVM transport-provider inject; Node: actor-host fail-closed inject (wasm-webcomponent#17); browser intentional native boundary"}
   :transport-write {:jvm :inject :browser :no :node :inject
                     :note "JVM transport-provider inject; Node: actor-host fail-closed inject (wasm-webcomponent#17); browser intentional native boundary"}
   :transport-read {:jvm :inject :browser :no :node :inject
                    :note "JVM transport-provider inject; Node: actor-host fail-closed inject (wasm-webcomponent#17); browser intentional native boundary"}
   :transport-close {:jvm :inject :browser :no :node :inject
                     :note "JVM transport-provider inject; Node: actor-host fail-closed inject (wasm-webcomponent#17); browser intentional native boundary"}
   :pg-cancel-register {:jvm :inject :browser :no :node :inject
                        :note "JVM transport-provider inject; browser native boundary"}
   :pg-cancel {:jvm :inject :browser :no :node :inject
               :note "JVM transport-provider inject; browser native boundary"}
   :pg-pool-open {:jvm :inject :browser :no :node :inject
                  :note "JVM postgresql-pool-provider; Node: actor-host fail-closed inject (wasm-webcomponent#18); browser intentional native boundary"}
   :pg-pool-acquire {:jvm :inject :browser :no :node :inject
                     :note "JVM postgresql-pool-provider inject; browser native boundary"}
   :pg-pool-query {:jvm :inject :browser :no :node :inject
                   :note "JVM postgresql-pool-provider inject; browser native boundary"}
   :pg-pool-release {:jvm :inject :browser :no :node :inject
                     :note "JVM postgresql-pool-provider inject; browser native boundary"}
   :pg-pool-stats {:jvm :inject :browser :no :node :inject
                   :note "JVM postgresql-pool-provider inject; browser native boundary"}
   :pg-pool-health {:jvm :inject :browser :no :node :inject
                    :note "JVM postgresql-pool-provider inject; browser native boundary"}
   :pg-pool-drain {:jvm :inject :browser :no :node :inject
                   :note "JVM postgresql-pool-provider inject; browser native boundary"}
   :pg-pool-close {:jvm :inject :browser :no :node :inject
                   :note "JVM postgresql-pool-provider inject; browser native boundary"}
   :pg-open {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-query {:jvm :inject :browser :no :node :inject
              :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-simple-query {:jvm :inject :browser :no :node :inject
                     :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-prepare {:jvm :inject :browser :no :node :inject
                :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-session-reset {:jvm :inject :browser :no :node :inject
                      :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-close-statement {:jvm :inject :browser :no :node :inject
                        :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-query-state {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-prepare-typed {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-execute-params2 {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-execute-params {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-bind-portal {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-fetch-portal {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-close-portal {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-copy-out {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-copy-in {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-execute-batch {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :scram-sha256 {:jvm :yes :browser :no :node :inject
             :note "JVM host crypto; Node: actor-host PBKDF2/HMAC inject (wasm-webcomponent#18); browser intentional absence"}
   :pg-open-scram {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-open-scram-random {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-open-scram-cancellable-random {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-cancel-authority-use {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :pg-close-scram {:jvm :inject :browser :no :node :inject
             :note "JVM postgresql-wire-provider fail-closed inject; browser native boundary"}
   :http-get-stream {:jvm :yes :browser :inject :node :inject
                     :note "linear Component provider; browser/node require an injected bounded stream adapter"}
   :object-get-stream {:jvm :yes :browser :inject :node :inject
                       :note "linear Component provider; browser/node require an injected object store"}
   :object-put-block {:jvm :yes :browser :inject :node :inject
                      :note "linear Component provider; browser/node require an injected object store"}
   :object-compare-and-set-ref
   {:jvm :yes :browser :inject :node :inject
    :note "linear Component provider; browser/node require an injected object store"}})

(defn import-status
  "Status map for one import id under :jvm | :browser | :node."
  [id host]
  (let [id (contract/import-id id)
        row (get host-impl id)]
    (when row
      {:import id
       :host host
       :status (get row host)
       :wasm-field (fields/wasm-field-name id)
       :note (:note row)})))

(def production-requirements
  "Host configuration evidence required for conditional production imports.
   Empty means the implementation is built in. These facts are supplied by
   the host operator; a guest cannot grant them to itself."
  {:jvm {:http-post #{:http-policy :request-purpose :credential-provider}
         :log-read #{:store}
         :log-write #{:store}
         :llm-infer #{:llm-client}}
   :browser {:http-post #{:cross-origin-isolated :worker :http-bridge}
             :llm-infer #{:cross-origin-isolated :worker :llm-proxy}}
   :node {:http-post #{:http-post-provider}
          :llm-infer #{:llm-provider}
          :http-get-stream #{:bounded-stream-provider}
          :object-get-stream #{:object-store-provider}
          :object-put-block #{:object-store-provider}
          :object-compare-and-set-ref #{:object-store-provider}}})

(defn host-admission
  "Machine-enforced host support admission for REQUESTED imports.

   Production requires every conditional implementation's evidence in
   CONFIGURED. Unknown hosts/imports and unavailable implementations fail
   closed in every profile."
  [host requested {:keys [profile configured]
                   :or {profile :development configured #{}}}]
  (let [known-host? (contains? #{:jvm :browser :node} host)
        requested (mapv contract/import-id requested)
        unknown? (some nil? requested)
        checks (mapv (fn [id]
                       (let [status (get-in host-impl [id host])
                             required (get-in production-requirements [host id] #{})
                             missing (set (remove (set configured) required))]
                         {:import id :status status :required required
                          :missing missing
                          :ok? (and (some? status)
                                    (not= :no status)
                                    (or (not= :production profile)
                                        (empty? missing)))}))
                     (remove nil? requested))
        errors (cond-> []
                 (not known-host?) (conj {:code :unknown-host :host host})
                 unknown? (conj {:code :unknown-import})
                 true (into
                       (keep (fn [{:keys [import status missing ok?]}]
                               (when-not ok?
                                 {:code (if (seq missing)
                                          :missing-host-configuration
                                          :unsupported-import)
                                  :host host :import import :status status
                                  :missing missing}))
                             checks)))]
    {:ok? (empty? errors)
     :host host :profile profile :requested requested
     :configured (set configured) :checks checks :errors errors}))

(defn admit-host!
  "Return admission or throw before guest instantiation.

   The throw is the one denial shape (`kototama.denial`, koto-h5): reason
   `:host-surface-rejected` under both names, the REQUESTED surface as the
   refused value, and HOST naming itself -- so the JVM tender (which calls
   this with :jvm) and the browser/Node hosts refuse the same input with maps
   that differ only in `:kototama.tender/host`. The historical
   `:kototama.host/code` / `:kototama.host/admission` keys stay beside the
   shape for the readers that pin them.

   A HOST that `kototama.denial/hosts` does not register is a caller bug
   (there is no host to attribute the denial to) and surfaces as
   `denial`'s own \"unknown host\" ex-info, not as a denial of the guest;
   `host-admission` (no bang) still reports it as `:unknown-host` data."
  [host requested opts]
  (let [result (host-admission host requested opts)]
    (when-not (:ok? result)
      (denial/deny! host :host-surface-rejected requested
                    {:kototama.host/code :host-surface-rejected
                     :kototama.host/admission result}))
    result))

(defn parity-matrix
  "Full matrix: vector of {:import :jvm :browser :node :wasm-field :note}."
  []
  (mapv (fn [id]
          (let [row (get host-impl id)]
            {:import id
             :jvm (:jvm row)
             :browser (:browser row)
             :node (:node row)
             :wasm-field (fields/wasm-field-name id)
             :note (:note row)}))
        (map :import/id (:abi/imports contract/import-surface))))

(defn- browser-linkable?
  "True when browser can link the import (possibly needing COOP/inject)."
  [status]
  (contains? #{:yes :coop-or-inject :inject} status))

(defn browser-available-ids
  "Import ids linkable in a browser (incl. COOP/inject paths)."
  []
  (vec (keep (fn [[id row]]
               (when (browser-linkable? (:browser row)) id))
             host-impl)))

(defn browser-missing-ids
  "Import ids not available as host imports in a standard browser tab
   without a special backend."
  []
  (vec (keep (fn [[id row]]
               (when-not (browser-linkable? (:browser row)) id))
             host-impl)))

(defn parity-score
  "R2 score: fraction of actor:host imports browser-linkable."
  []
  (let [rows (parity-matrix)
        n (count rows)
        yes (count (filter #(browser-linkable? (:browser %)) rows))]
    {:total n
     :browser-yes yes
     :browser-no (- n yes)
     :ratio (if (pos? n) (double (/ yes n)) 0.0)
     :available (browser-available-ids)
     :missing (browser-missing-ids)
     ;; :sab-coop is real as of wasm-webcomponent PR #8 (2026-07-16, see
     ;; ADR-0007's second addendum) -- :jspi-experimental remains unbuilt
     ;; (Chrome-only, not broadly shipped).
     :http-post-paths {:inject :implemented
                       :sab-coop :implemented
                       :jspi-experimental :not-yet-built}
     ;; llm-infer's browser path (PR #11) reuses :sab-coop above, not a
     ;; distinct bridge -- tracked separately here since it additionally
     ;; requires a caller-supplied proxy URL.
     :llm-infer-paths {:inject :implemented
                       :sab-coop-via-proxy :implemented}}))

(defn r2-status
  "The R2 status, derived from a `parity-score` and from nothing else.

   :qualified        every actor:host import in the contract surface is
                     browser-linkable (:yes / :coop-or-inject / :inject)
   :advanced-partial some are, some are an explicit browser :no
   :planned          none are, or there is no surface to score

   Three hand-copied statuses used to coexist (this fn's :qualified,
   guest/maturity-levels' :advanced-partial, docs/maturity.md's
   \"qualified 14/14\") while parity-score measured something else. The
   score is the one thing that is computed, so it is the one source."
  [{:keys [browser-yes total]}]
  (cond
    (or (nil? total) (nil? browser-yes) (zero? total)) :planned
    (= browser-yes total) :qualified
    (pos? browser-yes) :advanced-partial
    :else :planned))

(defn r2-ratio-text
  "\"19/58\" -- the literal docs/maturity.md's R2 row must quote."
  [{:keys [browser-yes total]}]
  (str browser-yes "/" total))

(defn r2-note
  "Human-readable R2 note generated from a `parity-score`; the guest ladder
   quotes this rather than carrying its own prose copy."
  [{:keys [browser-no missing] :as score}]
  (str (r2-ratio-text score) " browser-linkable (:yes/:coop-or-inject/:inject); "
       browser-no " intentional browser :no ("
       (count (filter #(re-find #"^(transport|tls)" (name %)) missing)) " transport/TLS, "
       (count (filter #(re-find #"^pg-" (name %)) missing)) " pg, "
       (count (remove #(re-find #"^(transport|tls|pg-)" (name %)) missing))
       " other: " (pr-str (vec (remove #(re-find #"^(transport|tls|pg-)" (name %)) missing)))
       "). http-post and llm-infer are real in a cross-origin-isolated tab via a "
       "Worker-hosted SAB+Atomics bridge (llm-infer additionally needs a "
       "caller-supplied proxy URL); see kototama.browser/host-impl."))

(defn r2-level
  "The R2 entry of the maturity ladder, derived from `parity-score`.
   `kototama.guest/maturity-levels` embeds this value."
  []
  (let [score (parity-score)]
    {:id :r2
     :title "Browser-native host parity"
     :status (r2-status score)
     :score (select-keys score [:total :browser-yes :browser-no :ratio])
     :note (r2-note score)}))

(defn r2-report
  "Aggregate R2 snapshot for CLI doctor. :status is `r2-status` of the
   score below -- never a literal."
  []
  (let [score (parity-score)]
  {:level :r2
   :status (r2-status score)
   :title "Browser-native host parity"
   :score score
   :matrix (parity-matrix)
   :host-free-guests ["web/host-free-fact.wasm"
                      "web/host-free-peak-cells.wasm"
                      "web/demo.wasm"]
   :actor-host-demo "web/actor-host-demo.wasm"
   :library "kotoba-lang/wasm-webcomponent (actor-host.js, http-post-bridge.js, kotoba-wasm-worker-host.js, kotoba-wasm-worker-element.js, kgraph.js)"
   :verify ["node web/verify.mjs"
            "node web/verify-kgraph.mjs"
            "node web/verify-actor-host.mjs"
            "node web/verify-host-free.mjs"
            "npm run test:http-post-browser  ; in wasm-webcomponent"
            "npm run test:llm-infer-browser  ; in wasm-webcomponent"]
   :notes ["Policy re-enforcement at load: actor-host.js yes; kgraph.js no"
           "http-post: real in a cross-origin-isolated tab via a Worker-hosted SAB+Atomics bridge; inject (Node) also available"
           "llm-infer: real in a cross-origin-isolated tab via the SAME bridge as http-post, through a caller-supplied proxy URL (never a provider key embedded client-side); inject (Node) also available"]}))
