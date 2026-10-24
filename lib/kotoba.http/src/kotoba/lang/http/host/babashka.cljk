(ns kotoba.lang.http.host.babashka
  "Babashka / JVM host adapter for outbound HTTP via `org.babashka/http-client`.

  Fleet CLIs run under Babashka, which bundles this client. On plain JVM, add
  `org.babashka/http-client` through `:babashka-client-host` — not top-level."
  #?(:clj (:require [babashka.http-client :as impl])))

#?(:clj
   (defn get
     ([url] (impl/get url {}))
     ([url opts] (impl/get url opts))))

#?(:clj
   (defn post
     ([url] (impl/post url {}))
     ([url opts] (impl/post url opts))))

#?(:clj
   (defn put
     ([url] (impl/put url {}))
     ([url opts] (impl/put url opts))))

#?(:clj
   (defn delete
     ([url] (impl/delete url {}))
     ([url opts] (impl/delete url opts))))

#?(:clj
   (defn request
     ([opts] (impl/request opts))
     ([method url opts] (impl/request method url opts))))
