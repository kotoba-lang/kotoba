(ns epp.transport
  "RFC 5734 framing: EPP over TCP is a stream of length-prefixed XML documents.

  Each data unit is a 32-bit **network-byte-order** total length followed by
  the XML. The length **includes its own four header bytes** — RFC 5734 §4 says
  so in one sentence, and getting it wrong by four is the single most common
  EPP interop bug. The two directions are written next to each other here so
  that the `+ 4` and the `- 4` cannot be maintained separately.

  Bytes are plain integer vectors, not host buffers, so this namespace is
  `.cljc` and the framing is testable without a socket. A JVM socket layer that
  fills a `byte[]` and a Node one that fills a `Buffer` both hand a vector of
  unsigned bytes to `decode` and get a string back.

  Why a maximum frame size is enforced here rather than by the caller: the
  length prefix is attacker-controlled. A peer that sends `0xFFFFFFFF` and then
  stops is asking a server to allocate 4 GiB and wait — the read loop is the
  only place with the information to refuse, and refusing after allocation is
  too late."
  (:require [kotoba.lang.text :as str]))

(def ^:const header-bytes 4)

(def ^:const default-max-frame
  "64 KiB. RFC 5734 sets no limit; real registry frames are a few kilobytes and
  the largest legitimate one — a `<check>` of many names, or a poll message
  carrying a full `<infData>` — stays well inside this. An operator serving
  unusually large frames should raise it deliberately rather than discover the
  cap in production."
  65536)

(defn- utf8-bytes [s]
  #?(:clj (vec (.getBytes ^String s "UTF-8"))
     :cljs (vec (.encode (js/TextEncoder.) s))))

(defn- utf8-string [bs]
  #?(:clj (String. (byte-array (map unchecked-byte bs)) "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8") (js/Uint8Array.from (clj->js bs)))))

(defn encode
  "XML string → a vector of unsigned bytes ready for the wire.

  The length is computed over the **UTF-8 encoding**, not the string. A frame
  containing a single non-ASCII character — an IDN registrant name, a Japanese
  contact address — has more bytes than characters, and a length taken from
  `count` on the string truncates it. That is the second most common EPP bug
  and it only appears once a non-English registrar connects."
  [xml-string]
  (let [body (utf8-bytes xml-string)
        total (+ header-bytes (count body))]
    (into [(bit-and (bit-shift-right total 24) 0xff)
           (bit-and (bit-shift-right total 16) 0xff)
           (bit-and (bit-shift-right total 8) 0xff)
           (bit-and total 0xff)]
          body)))

(defn frame-length
  "Read the declared total length from the first four bytes, or nil if fewer
  than four are available yet."
  [bs]
  (when (>= (count bs) header-bytes)
    (let [[a b c d] (take header-bytes bs)]
      (bit-or (bit-shift-left (bit-and a 0xff) 24)
              (bit-shift-left (bit-and b 0xff) 16)
              (bit-shift-left (bit-and c 0xff) 8)
              (bit-and d 0xff)))))

(defn decode
  "Take one complete frame off the front of a byte buffer.

  Returns `{:frame xml-string :rest bytes}` when a whole frame is present,
  `{:rest bytes}` when more bytes are needed, or `{:error …}` for a length that
  cannot be honoured. Never throws and never blocks: the caller owns the
  socket, this owns the framing."
  ([bs] (decode bs default-max-frame))
  ([bs max-frame]
   (let [total (frame-length bs)]
     (cond
       (nil? total) {:rest (vec bs)}

       (< total header-bytes)
       {:error (str "Frame length " total " is shorter than the " header-bytes
                    "-byte header that is included in it")}

       (> total max-frame)
       {:error (str "Frame length " total " exceeds the maximum " max-frame)}

       (< (count bs) total) {:rest (vec bs)}

       :else
       {:frame (utf8-string (subvec (vec bs) header-bytes total))
        :rest (subvec (vec bs) total)}))))

(defn decode-all
  "Drain every complete frame from a buffer. Returns `{:frames [...] :rest …}`,
  or adds `:error` and stops at the first unusable length — a stream that
  desynchronized cannot be resynchronized by skipping ahead, because there is
  no delimiter to resynchronize on."
  ([bs] (decode-all bs default-max-frame))
  ([bs max-frame]
   (loop [buf (vec bs) frames []]
     (let [{:keys [frame rest error]} (decode buf max-frame)]
       (cond
         error {:frames frames :rest buf :error error}
         frame (recur rest (conj frames frame))
         :else {:frames frames :rest rest})))))

(defn hex
  "Byte vector as hex — for test failure output, where a wrong length prefix is
  otherwise invisible."
  [bs]
  (str/join " " (map #(let [s #?(:clj (Integer/toHexString (bit-and % 0xff))
                                 :cljs (.toString (bit-and % 0xff) 16))]
                        (if (= 1 (count s)) (str "0" s) s))
                     bs)))
