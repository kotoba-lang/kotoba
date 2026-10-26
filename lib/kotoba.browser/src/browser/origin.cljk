(ns browser.origin
  "Small origin model for kotoba browser policy and storage.

   This is not a WHATWG URL parser. It is a deterministic subset for
   scheme://authority/path style URLs plus kotoba internal URLs."
  (:require [kotoba.lang.text :as str]))

(def default-ports
  "Per-scheme default port -- RFC 6454 origin comparison (and the
   WHATWG URL spec's own port-normalization step) treats an explicit
   default port as equivalent to no port at all (`https://x` and
   `https://x:443` are the SAME origin), but this file previously
   compared the raw authority string verbatim, including any port,
   confirmed via direct REPL reproduction:
   `(same-origin? \"https://example.com\" \"https://example.com:443\")`
   returned false. This is more than cosmetic -- `origin`/`same-origin?`
   are the load-bearing primitives behind browser.net's fetch-cache
   credential partitioning, CORS Origin-header decisions, and
   :net/fetch permission checks, plus browser.storage's per-origin key
   partitioning, so a page that navigates between an implicit- and
   explicit-default-port form of the SAME real URL (explicit default
   ports show up in redirects, hand-authored links, and some server
   configs) would see its storage/cache/cookies silently split across
   two \"different\" origins."
  {"http" "80" "https" "443" "ws" "80" "wss" "443"})

(defn- strip-default-port
  "Removes a trailing `:<port>` from `authority` when `port` is exactly
   `scheme`'s own default (see `default-ports`) -- any OTHER explicit
   port (including a non-default one on a scheme with no listed
   default) is left untouched, so `https://example.com:8443` still
   correctly compares as a DIFFERENT origin from `https://example.com`."
  [scheme authority]
  (let [default-port (get default-ports scheme)]
    (if (and default-port (str/ends-with? authority (str ":" default-port)))
      (subs authority 0 (- (count authority) (inc (count default-port))))
      authority)))

(defn parse-url
  [url]
  (let [s (str url)
        [_ scheme rest] (re-matches #"^([A-Za-z][A-Za-z0-9+.-]*):(.*)$" s)]
    (if scheme
      (let [scheme (str/lower scheme)]
        (if (str/starts-with? rest "//")
          (let [without-slashes (subs rest 2)
                slash (.indexOf without-slashes "/")
                authority-with-userinfo (if (neg? slash) without-slashes (subs without-slashes 0 slash))
                ;; Strip any "userinfo@" prefix before the host (WHATWG URL:
                ;; everything up to the LAST "@" in the authority is
                ;; userinfo, never part of the host) -- without this, a URL
                ;; like "https://victim.com@attacker.com/" (a real, network-
                ;; reachable shape: a malicious/compromised server can return
                ;; it verbatim in a redirect Location header) produces the
                ;; origin "https://victim.com@attacker.com" instead of the
                ;; real "https://attacker.com" per RFC 6454 (origin excludes
                ;; userinfo), silently breaking cookie/permission-store
                ;; lookups keyed by host for any such URL.
                at (.lastIndexOf authority-with-userinfo "@")
                authority (if (neg? at)
                            authority-with-userinfo
                            (subs authority-with-userinfo (inc at)))
                authority (strip-default-port scheme (str/lower authority))
                path (if (neg? slash) "/" (subs without-slashes slash))]
            {:url s
             :scheme scheme
             :authority authority
             :path path
             :origin (str scheme "://" authority)})
          {:url s
           :scheme scheme
           :path rest
           :origin (str scheme ":")}))
      {:url s
       :scheme nil
       :path s
       :origin "opaque:"})))

(defn origin
  [url]
  (:origin (parse-url url)))

(defn same-origin?
  [a b]
  (= (origin a) (origin b)))

(defn internal?
  [url]
  (= "kotoba" (:scheme (parse-url url))))
