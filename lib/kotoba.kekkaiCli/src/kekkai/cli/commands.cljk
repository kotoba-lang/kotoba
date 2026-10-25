(ns kekkai.cli.commands
  "The commands that are not `ssh`: keys, verification, running an agent or a
  relay, and reading a node's own state."
  (:require [kotoba.lang.text :as str]
            [kekkai.cli.config :as config]
            [kekkai.cli.sign :as sign]
            [kekkai.node.agent :as agent]
            [kekkai.node.netmap :as netmap]
            [kekkai.node.relay-server :as relay-server]
            [kekkai.node.signed-netmap :as signed]
            [kekkai.node.stream-edge :as edge]
            [kekkai.node.udp :as udp]
            [kotoba.bytes :as b]
            [noise.core :as noise]
            [noise.provider.node :as provider]
            ["node:fs" :as fs]))

(def suite (noise/suite (provider/ports)))

;; ── keygen ──────────────────────────────────────────────────────────────────

(defn keygen
  "Write a node identity, and optionally a publishing authority.

  Two different keys, written separately on purpose. The Noise static is what
  peers dial; the Ed25519 authority is what signs netmaps. Reusing one for both
  would tie session compromise to publishing authority, which is the pairing
  this whole design keeps apart."
  [{:keys [node-id out kind]}]
  (case kind
    :authority
    (let [id (sign/generate-authority)
          p (or out "kekkai-authority.edn")]
      (when (.existsSync fs p)
        (throw (ex-info (str p " already exists — refusing to overwrite a "
                             "signing key. Move it aside if you mean to.")
                        {:type :kekkai/key-exists :path p})))
      (.writeFileSync fs p (str ";; kekkai netmap publishing authority (Ed25519).\n"
                                ";; The private half signs netmaps. Treat it as\n"
                                ";; the control plane's identity.\n"
                                (pr-str id) "\n"))
      (println (str "wrote " p))
      (println (str "fingerprint " (sign/fingerprint (:public-b64 id))))
      (println)
      (println "nodes trust this publisher with:")
      (println (str "  :netmap-authority-spki-b64 \"" (:public-b64 id) "\"")))

    (let [{:keys [priv pub]} (noise/keypair suite)
          static {:priv (b/hex priv) :pub (b/hex pub)}
          p (or out "kekkai-node.edn")]
      (when (.existsSync fs p)
        (throw (ex-info (str p " already exists — refusing to overwrite a node "
                             "key. A new key is a new node as far as every "
                             "netmap is concerned.")
                        {:type :kekkai/key-exists :path p})))
      (.writeFileSync
       fs p
       (str ";; kekkai node configuration. :static is this node's Noise identity —\n"
            ";; the public half is what the control plane publishes as :node/key.\n"
            (pr-str {:node/id (or node-id "unnamed")
                     :static static
                     :netmap-file "netmap.signed.edn"
                     :netmap-authority-spki-b64 ""
                     :listen-port 41641
                     :tick-ms 500})
            "\n"))
      (println (str "wrote " p))
      (println)
      (println "give the control plane this node's data-plane facts:")
      (println (str "  :static-pub \"" (:pub static) "\""))
      (println "  :overlay-ip \"100.64.0.x\"   ;; the control plane allocates this"))))

;; ── netmap verify ───────────────────────────────────────────────────────────

(defn verify
  "Verify a signed netmap and print what it grants.

  Prints the grants rather than just 'ok' because that is the question an
  operator actually has: not 'is this signed' but 'what does it let this node
  reach', and those are answered by the same file."
  [{:keys [netmap-file authority]}]
  (let [text (.readFileSync fs netmap-file "utf8")
        nm (signed/verify-envelope text authority)
        problems (netmap/validate nm)
        self (get-in nm [:netmap/self :node/id])
        now (js/Math.floor (/ (.getTime (js/Date.)) 1000))]
    (println (str "signature ok — signed by " (sign/fingerprint authority)))
    (println (str "tailnet " (:netmap/tailnet nm) " v" (:netmap/version nm)
                  "   self " self))
    (when (seq problems)
      (println (str "STRUCTURAL PROBLEMS: " (pr-str problems))))
    (println)
    (doseq [peer (:netmap/peers nm)]
      (let [id (:node/id peer)
            caps (netmap/capabilities nm self id)
            ok? (netmap/authorized? peer now)]
        (println (str "  " (if ok? "→" "✗") " " id
                      "  " (:node/overlay-ip peer)
                      "  " (if (seq caps)
                             (str/join "," (map name (sort caps)))
                             "(no outbound grant)")
                      (when-not ok?
                        (str "   NOT AUTHORIZED (" (:node/status peer) ")"))))))
    (println)
    (doseq [{:keys [peer denied capability granted]} (netmap/denials nm :ssh now)]
      (println (str "  ssh denied to " peer ": " (name denied)
                    (when capability (str " for " (name capability)))
                    (when (seq granted)
                      (str " (granted: " (str/join "," (map name granted)) ")")))))
    nm))

;; ── relay ───────────────────────────────────────────────────────────────────

(defn relay
  "Run a relay: one UDP port, no state, no database.

  Where to run it is not a detail — a relay has to be reachable by every peer,
  and a workstation behind a NAT usually is not. Measured 2026-08-07: UDP
  flowed workstation→fleet-node but not the reverse, so the relay had to live
  on the node."
  [{:keys [port host static-file tailnet version]}]
  (let [{:keys [priv pub]} (:static (cljs.reader/read-string
                                     (.readFileSync fs static-file "utf8")))]
    (-> (relay-server/start
         {:port (or port 41999) :host (or host "0.0.0.0")
          :static {:priv (b/unhex priv) :pub (b/unhex pub)}
          :region "kekkai"
          :prologue (b/utf8-encode
                     (netmap/prologue-string {:netmap/tailnet tailnet
                                              :netmap/version version}))
          :on-event (fn [e]
                      ;; A relay that logs nothing is a relay you cannot tell
                      ;; from a firewall. Registrations and expiries are the
                      ;; two things an operator needs when peers cannot find
                      ;; each other.
                      (when (#{:registered :expired :roamed :rejected}
                             (:event e))
                        (println (str "  [" (.toISOString (js/Date.)) "] "
                                      (name (:event e))
                                      (when-let [k (:key e)]
                                        (str " key=" (subs (str k) 0 16) "…"))))))})
        (.then (fn [r]
                 (println (str "kekkai relay on " (or host "0.0.0.0") ":"
                               (udp/local-port (:sock r))))
                 (println (str "publish it as :relay/key \"" pub "\""))
                 (println (str "bound to tailnet " tailnet " v" version
                               " — a peer on another netmap version fails the "
                               "handshake loudly rather than running on stale "
                               "ACLs")))))))

;; ── up ──────────────────────────────────────────────────────────────────────

(defn- parse-forward
  "`2222:judah:22` -> {:listen-port 2222 :peer \"judah\" :port 22}."
  [s]
  (let [[l peer p] (str/split (str s) #":")]
    (when-not (and l peer p (re-matches #"\d+" l) (re-matches #"\d+" p))
      (throw (ex-info (str "bad --forward " s " (want LOCALPORT:NODE:REMOTEPORT)")
                      {:type :kekkai/bad-forward :value s})))
    {:listen-port (parse-long l) :peer peer :port (parse-long p)
     :capability :ssh}))

(def notable-events
  "What a resident agent prints without being asked.

  Not everything, and not nothing. A daemon that logs every datagram is unread;
  one that logs nothing leaves an operator with a session that stopped working
  and no way to see when or why — which is exactly the state this command was
  in the first time its session dropped during a real run."
  #{:session-established :session-lost :rekey-due :handler-error
    :relay-connected :relay-disconnected :dropped :stream-reset})

(defn- log-event [verbose? e]
  (when (or verbose? (contains? notable-events (:event e)))
    (println (str "  [" (.toISOString (js/Date.)) "] "
                  (name (or (:event e) :unknown))
                  (when-let [p (:peer e)] (str " peer=" p))
                  (when-let [r (:reason e)] (str " reason=" (name r)))
                  (when-let [d (:detail e)] (str " " d))))))

(defn up
  "Run the node agent, with any long-lived forwards."
  [{:keys [config-file forwards verbose?]}]
  (let [cfg (config/load-config config-file)
        registry (atom {})
        handle (atom nil)
        fs* (mapv parse-forward forwards)]
    (-> (agent/start
         {:config cfg
          :on-event (fn [e]
                      (log-event verbose? e)
                      (when (and (= :data (:event e)) @handle)
                        (edge/on-peer-data registry @handle e)))})
        (.then
         (fn [h]
           (reset! handle h)
           (js/setInterval #(edge/tick! registry h) edge/tick-ms)
           (println (str "kekkai node " (:node/id cfg) " up"))
           (doseq [f fs*]
             (edge/forward! registry h f)
             (println (str "  forward 127.0.0.1:" (:listen-port f)
                           " -> " (:peer f) ":" (:port f))))
           (when (empty? fs*)
             (println "  no forwards; serving inbound streams the netmap grants")))))))

;; ── status ──────────────────────────────────────────────────────────────────

(defn status
  "What this node currently believes: peers, sessions, paths."
  [{:keys [config-file]}]
  (let [cfg (config/load-config config-file)]
    (-> (agent/start {:config cfg :on-event (fn [_])})
        (.then (fn [h]
                 (js/setTimeout
                  (fn []
                    (let [s ((:status h))]
                      (println (str "node " (:node/id cfg)))
                      (println (str "relay: "
                                    (if (:connected? (:relay s))
                                      "connected" "not connected")))
                      (doseq [p (:peers s)]
                        (println (str "  " (:peer p)
                                      "  " (if (:established? p)
                                             "established" "handshaking")
                                      "  path=" (name (or (:route p) :none)))))
                      ((:stop h))
                      (js/setTimeout #(.exit js/process 0) 100)))
                  3000))))))
