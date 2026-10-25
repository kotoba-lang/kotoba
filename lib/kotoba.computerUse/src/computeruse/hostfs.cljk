(ns computeruse.hostfs
  "The filesystem host-capability seam, portable across the JVM and
  nbb/Node. Kept tiny and dependency-free on purpose: the resident bot
  CLI runs under nbb from a bare checkout (no tools.deps resolution), so
  every namespace it reaches must load on both hosts."
  (:require [kotoba.lang.text :as str]))

(defn path-exists?
  "Named path-exists? rather than exists? because cljs.core/exists? is a
  macro; shadowing it in a .cljc consumed from ClojureScript is a trap."
  [path]
  #?(:clj (.exists (java.io.File. ^String (str path)))
     :cljs (try (.existsSync (js/require "node:fs") (str path))
                (catch :default _ false))))

(defn directory? [path]
  #?(:clj (.isDirectory (java.io.File. ^String (str path)))
     :cljs (try (.isDirectory (.statSync (js/require "node:fs") (str path)))
                (catch :default _ false))))

(defn read-file [path]
  #?(:clj (slurp (str path))
     :cljs (.readFileSync (js/require "node:fs") (str path) "utf8")))

(defn mkdirs! [path]
  #?(:clj (.mkdirs (java.io.File. ^String (str path)))
     :cljs (try (.mkdirSync (js/require "node:fs") (str path) #js {:recursive true})
                (catch :default _ nil)))
  path)

(defn dirname [path]
  (let [p (str path)
        i (str/last-index-of p "/")]
    (cond (nil? i) "." (zero? i) "/" :else (subs p 0 i))))

(defn basename [path]
  (let [p (str path)
        i (str/last-index-of p "/")]
    (if i (subs p (inc i)) p)))

(defn write-file! [path content]
  (mkdirs! (dirname path))
  #?(:clj (spit (str path) content)
     :cljs (.writeFileSync (js/require "node:fs") (str path) content))
  path)

(defn absolute
  "Resolves `path` against `base` unless it is already absolute."
  [base path]
  (let [p (str path)]
    (if (str/starts-with? p "/") p (str base "/" p))))

(defn cwd []
  #?(:clj (System/getProperty "user.dir")
     :cljs (.cwd js/process)))

(defn getenv [k]
  #?(:clj (System/getenv (str k))
     :cljs (aget (.-env js/process) (str k))))

(defn tmp-dir []
  (or (getenv "CUA_TMPDIR") "/tmp"))

(defn now-iso []
  #?(:clj (str (java.time.Instant/now))
     :cljs (.toISOString (js/Date.))))

(defn epoch-ms []
  #?(:clj (System/currentTimeMillis)
     :cljs (.now js/Date)))
