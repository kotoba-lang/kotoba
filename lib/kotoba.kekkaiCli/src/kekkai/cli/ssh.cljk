(ns kekkai.cli.ssh
  "`kekkai ssh <node> [ssh args…]` — stand up an agent and a forwarder, hand the
  port to the real `ssh`, tear everything down when it exits.

  This is the command the whole stack exists for, and the reason it is a
  command rather than a runbook: the working fleet run on 2026-08-07 took a
  hand-written driver, two scratch scripts shipped to the far node, and four
  terminal windows. That produced a result nobody else could reproduce.

  What it deliberately does NOT do:

  - **It does not become an ssh client.** `ssh` is spawned with inherited
    stdio, so keys, agents, `~/.ssh/config`, `-J`, port forwards and interactive
    prompts all behave exactly as they always do. A CLI that re-implemented any
    of that would be a worse ssh that also has to be kept in step with OpenSSH.
  - **It does not touch the netmap.** Reachability comes from the signed netmap
    the node already has. If the edge is not granted, the forwarder refuses and
    says so; this command has no opinion that could override it.
  - **It does not keep the port.** The listener is ephemeral and bound to
    127.0.0.1, and it dies with the process. A long-lived forward is
    `kekkai up --forward`, which is a different intent and should look
    different."
  (:require [kotoba.lang.text :as str]
            [kekkai.cli.config :as config]
            [kekkai.node.agent :as agent]
            [kekkai.node.netmap :as netmap]
            [kekkai.node.stream-edge :as edge]
            ["node:child_process" :as cp]))

(def ^:const session-timeout-ms
  "How long to wait for the overlay session before giving up.

  Long enough for a relay handshake on a slow path, short enough that a node
  which will never answer fails rather than hangs — `ssh` waiting forever on a
  local port it cannot see behind is the worst of the failure modes, because it
  looks like the remote host is slow."
  30000)

(defn- sleep [ms] (js/Promise. (fn [res] (js/setTimeout res ms))))

(defn- wait-for [pred timeout-ms]
  (let [deadline (+ (.getTime (js/Date.)) timeout-ms)]
    (letfn [(step []
              (cond
                (pred) (js/Promise.resolve true)
                (> (.getTime (js/Date.)) deadline) (js/Promise.resolve false)
                :else (.then (sleep 100) step)))]
      (step))))

(defn- established? [handle peer]
  (let [peers (:peers ((:status handle)))]
    (boolean (some #(and (= peer (:peer %)) (:established? %)) peers))))

(defn- listening [server]
  (js/Promise.
   (fn [resolve _]
     (if-let [a (.address server)]
       (resolve (.-port a))
       (.on server "listening" #(resolve (.-port (.address server))))))))

(def ssh-options-taking-a-value
  "OpenSSH options that consume the next argument.

  Needed because the destination has to be inserted at exactly one place —
  after the options and **before** the remote command. `ssh [options]
  destination [command]` is positional: ssh takes the first non-option argument
  as the destination, so appending ours at the end makes it part of the
  command, and putting it before the options makes the options part of the
  command. Measured the wrong way round first: `kekkai ssh judah … 'echo hi;
  hostname'` produced `hostname contains invalid characters`, because ssh read
  the remote command as the host."
  #{"-B" "-b" "-c" "-D" "-E" "-e" "-F" "-I" "-i" "-J" "-L" "-l" "-m" "-O" "-o"
    "-p" "-Q" "-R" "-S" "-W" "-w"})

(defn ssh-argv
  "The argument vector handed to `ssh`.

  The destination is supplied by this command, because the user already named
  the node — being made to type `judah@127.0.0.1` too would be asking them to
  know the forwarder's implementation. If the caller already gave a
  destination, theirs stands and nothing is inserted."
  [port ssh-args login]
  (let [dest (if login (str login "@127.0.0.1") "127.0.0.1")]
    (loop [xs (vec ssh-args) opts []]
      (cond
        ;; nothing but options: the destination goes last
        (empty? xs) (into (into ["-p" (str port)] opts) [dest])

        (contains? ssh-options-taking-a-value (first xs))
        (recur (drop 2 xs) (into opts (take 2 xs)))

        (str/starts-with? (str (first xs)) "-")
        (recur (rest xs) (conj opts (first xs)))

        ;; the first non-option. If it names a host, it IS the destination and
        ;; everything after it is the command; otherwise it is the command and
        ;; the destination belongs in front of it.
        (str/includes? (str (first xs)) "@")
        (into (into ["-p" (str port)] opts) xs)

        :else
        (into (into (into ["-p" (str port)] opts) [dest]) xs)))))

(defn- spawn-ssh
  "-> Promise of the exit code. stdio is inherited, so this is the user's ssh."
  [port ssh-args login]
  (js/Promise.
   (fn [resolve _]
     (let [args (ssh-argv port ssh-args login)
           ps (.spawn cp "ssh" (clj->js args) #js {:stdio "inherit"})]
       (.on ps "close" (fn [code] (resolve (or code 0))))
       (.on ps "error" (fn [e]
                         (println (str "kekkai: could not run ssh: " (str e)))
                         (resolve 127)))))))

(defn- preflight
  "Refuse before starting anything if the netmap does not grant the edge.

  Checked here as well as inside the forwarder because the message can be
  better: at this point we know the node id the user typed, and can say which
  grant is missing instead of dropping a TCP connection they never made."
  [handle peer port]
  (let [st @(:state handle)
        self (:self-id st)
        nm (:netmap st)]
    (cond
      (nil? (get (netmap/peer-table nm) peer))
      (str "node '" peer "' is not in this netmap. Known: "
           (str/join ", " (sort (keys (netmap/peer-table nm)))))

      (not (netmap/permitted? nm self peer :ssh port))
      (str "the netmap does not grant " self " -> " peer
           " :ssh on port " port
           ".\n  Reachability is the control plane's decision, not this "
           "command's — publish a policy grant with :capabilities [:overlay "
           ":ssh] and :ports [" port "]."))))

(defn run
  "`kekkai ssh <node> [ssh args…]`."
  [{:keys [config-file node port ssh-args login]}]
  (let [cfg (config/load-config config-file)
        registry (atom {})
        handle (atom nil)
        port (or port 22)]
    (-> (agent/start
         {:config cfg
          :on-event (fn [e]
                      (when (and (= :data (:event e)) @handle)
                        (edge/on-peer-data registry @handle e)))})
        (.then
         (fn [h]
           (reset! handle h)
           (if-let [refusal (preflight h node port)]
             (do (println (str "kekkai: " refusal))
                 ((:stop h))
                 (js/Promise.resolve 78))   ; EX_CONFIG
             (let [timer (js/setInterval #(edge/tick! registry h) edge/tick-ms)]
               (-> (wait-for #(established? h node) session-timeout-ms)
                   (.then
                    (fn [up?]
                      (if-not up?
                        (do (println
                             (str "kekkai: no overlay session with " node
                                  " after " (quot session-timeout-ms 1000) "s."
                                  "\n  The netmap grants the edge, so this is "
                                  "connectivity: check the relay is running and "
                                  "reachable from both sides."))
                            (js/clearInterval timer)
                            ((:stop h))
                            69)             ; EX_UNAVAILABLE
                        (let [server (edge/forward!
                                      registry h
                                      {:listen-port 0 :peer node :port port
                                       :capability :ssh})]
                          (-> (listening server)
                              (.then (fn [p] (spawn-ssh p ssh-args login)))
                              (.then (fn [code]
                                       (js/clearInterval timer)
                                       (.close server)
                                       ((:stop h))
                                       code))))))))))))
        (.then (fn [code] (js/setTimeout #(.exit js/process code) 100)))
        (.catch (fn [e]
                  (println (str "kekkai ssh failed: " (or (ex-message e) e)))
                  (js/setTimeout #(.exit js/process 70) 100))))))
