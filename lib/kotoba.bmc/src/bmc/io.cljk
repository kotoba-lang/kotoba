(ns bmc.io
  "Minimal synchronous Node.js fs/env bridge for the :cljs (nbb) side of this
   library. Deliberately self-contained: nbb has no cross-repo :deps mechanism
   (flat :paths classpath only — see README), so this library cannot assume
   the workspace's shared scripts/nbb_compat.cljs shim is on the classpath
   when consumed standalone. This is a small, intentionally duplicated subset
   of that shim's surface, scoped to exactly what bmc.canvas / bmc.ledger /
   bmc.cli-core need (file exists?/parent/mkdirs, slurp, spit, spit-append,
   getenv, exit). :clj call sites use java.io.File / core slurp / core spit
   directly instead (no shim needed on the JVM)."
  (:require [kotoba.lang.text :as str]))

#?(:cljs
   (do
     (def fs (js/require "node:fs"))
     (def node-path (js/require "node:path"))

     (defn- file-path [f] (if (string? f) f (.-path f)))

     (defn file
       "Variadic path-join, mirroring java.io.File's (File. parent child) /
        scripts.nbb-compat's `file` — returns a JS object exposing the small
        subset of java.io.File this library's :cljs branches call."
       [x & xs]
       (let [p (.apply (.-resolve node-path) node-path (to-array (map file-path (cons x xs))))]
         (js-obj
          "path" p
          "exists" (fn [] (try (.existsSync fs p) (catch :default _ false)))
          "getPath" (fn [] (str p))
          "getCanonicalFile" (fn [] (file (.realpathSync fs p)))
          "getParentFile" (fn [] (file (.dirname node-path p)))
          "mkdirs" (fn [] (do (.mkdirSync fs p #js {:recursive true}) true))
          "toString" (fn [] p))))

     (defn slurp [f] (.readFileSync fs (file-path f) "utf8"))

     (defn spit [f s]
       (.mkdirSync fs (.dirname node-path (file-path f)) #js {:recursive true})
       (.writeFileSync fs (file-path f) (str s)))

     (defn spit-append
       "`(spit f s :append true)` の nbb 版。"
       [f s]
       (.mkdirSync fs (.dirname node-path (file-path f)) #js {:recursive true})
       (.appendFileSync fs (file-path f) (str s)))

     (defn getenv [k] (aget (.-env js/process) k))
     (defn exit [status] (.exit js/process status))))
