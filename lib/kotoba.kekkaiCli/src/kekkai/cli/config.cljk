(ns kekkai.cli.config
  "Where a node's own configuration comes from.

  Deliberately the same map `kekkai.node.agent/start` already takes, read from
  the same `kekkai-node.edn` its README documents — this CLI is a front end for
  that agent, not a second configuration system with its own vocabulary."
  (:require [kotoba.lang.text :as str]
            ["node:fs" :as fs]
            ["node:os" :as os]
            ["node:path" :as path]))

(def default-locations
  "Searched in order. `./kekkai-node.edn` first so a checkout can carry its own
  test tailnet without touching the user's real one."
  ["kekkai-node.edn"
   ".kekkai/node.edn"])

(defn- home-location []
  (.join path (.homedir os) ".kekkai" "node.edn"))

(defn find-config
  "-> a path, or nil."
  []
  (or (first (filter #(.existsSync fs %) default-locations))
      (when (.existsSync fs (home-location)) (home-location))))

(defn load-config
  "-> the agent config map.

  Refuses rather than defaulting when `:netmap-authority-spki-b64` is absent
  and `:allow-unsigned-netmap?` is not set: `agent/load-netmap` would throw a
  less helpful error further in, and 'this node has no configured authority' is
  the actual problem."
  [explicit-path]
  (let [p (or explicit-path (find-config))]
    (when-not p
      (throw (ex-info (str "no kekkai-node.edn found. Looked in: "
                           (str/join ", " default-locations)
                           ", " (home-location)
                           "\n  `kekkai keygen` writes a starting one.")
                      {:type :kekkai/no-config})))
    (let [cfg (cljs.reader/read-string (.readFileSync fs p "utf8"))]
      (when-not (or (:allow-unsigned-netmap? cfg)
                    (seq (:netmap-authority-spki-b64 cfg)))
        (throw (ex-info
                (str p " has no :netmap-authority-spki-b64.\n"
                     "  A node that reads an unsigned netmap trusts whoever can "
                     "write the file — set the publisher's key, or set "
                     ":allow-unsigned-netmap? true and mean it.")
                {:type :kekkai/no-netmap-authority :config p})))
      (assoc cfg ::path p))))
