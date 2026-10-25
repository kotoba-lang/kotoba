(ns cloudflare.pages
  "Cloudflare Pages projects and their bound domains (read-only). REST v4,
  JVM-only.

  W6 product-shell: pure REST paths via kotoba workers_path_core."
  (:require [cloudflare.client :as client]
            [cloudflare.kotoba.oracle :as oracle]))

(def ^:private oid :workers-path)

(defn- o
  "Call a pure export. Requires the shipped oracle on every platform (T6.4)."
  [export args]
  (oracle/require-ready! oid)
  (oracle/call oid export args))

(defn- o-record
  "T5.2: structural host map → call-record (requires shipped oracle)."
  [export host-map field-specs]
  (oracle/require-ready! oid)
  (oracle/call-record oid export host-map field-specs))

(defn projects-path
  "REST path for Pages projects under an account.
   JVM: kotoba `pages-projects-path`."
  [account-id]
  (o-record 'pages-projects-path {:account-id account-id} [[:account-id :string]]))

#?(:clj
(defn projects
  "Pages projects for `account-id`, each including its :domains vector
  (pages.dev subdomain + any custom domains bound directly to this
  project -- NOT the same list as cloudflare.workers/custom-domains, which
  covers Worker bindings; a hostname can be on either or neither)."
  ([account-id] (projects account-id {}))
  ([account-id http-opts]
   (client/rest! (projects-path account-id) http-opts))))

#?(:clj
(defn project-by-domain
  "The Pages project whose :domains includes `domain`, or nil."
  ([account-id domain] (project-by-domain account-id domain {}))
  ([account-id domain http-opts]
   (first (filter #(some #{domain} (:domains %)) (projects account-id http-opts))))))
