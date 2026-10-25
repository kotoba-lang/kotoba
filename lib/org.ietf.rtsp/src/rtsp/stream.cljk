(ns rtsp.stream
  "One RTSP connection's byte stream is not just RTSP messages — §10.12
  lets a server interleave `$`-framed RTP/RTCP data between them, on the
  same TCP connection, with no length-prefixed envelope distinguishing
  'this next thing is a message' from 'this next thing is a frame' other
  than the first byte: a message never starts with `$` (RTSP method
  tokens are `[!-~]+` sans `$` per §10's own \"Method names may not start
  with a $ character\", and a Status-Line starts with `R`), so peeking
  one byte is sufficient and correct, not a heuristic.

  This namespace decodes *one* unit at a time and hands back how many
  bytes it consumed, rather than trying to decode a whole buffer in one
  call — a real connection's bytes arrive in arbitrary chunks, so
  'decode everything now' is not a shape a streaming caller can use
  without re-implementing the boundary tracking this namespace exists to
  do once.")

(require '[rtsp.message :as msg]
         '[rtsp.interleaved :as il])

(defn decode-one
  "Peek the first byte of `bs` and dispatch to `rtsp.interleaved/decode`
  or `rtsp.message/decode`. Returns `[:ok {:frame :interleaved ...} n]`
  or `[:ok {:frame :message :type :request|:response ...} n]`, or
  `[:error reason context]` — the same named-reason contract as the two
  namespaces underneath, not a new one, so a caller inspecting `:reason`
  never has to know which sub-decoder produced it. `:frame` (not
  `:type`) carries the interleaved-vs-message tag specifically so it
  never collides with `rtsp.message`'s own `:type :request`/`:type
  :response` key on the message map it returns unmodified."
  [bs]
  (cond
    (empty? bs) [:error :rtsp/empty-stream nil]
    (= (nth bs 0) il/marker)
    (let [[status v n] (il/decode bs)]
      (if (= status :error) [:error v n] [:ok (assoc v :frame :interleaved) n]))
    :else
    (let [{:keys [status message consumed reason context]} (msg/decode bs)]
      (if (= status :error) [:error reason context]
          [:ok (assoc message :frame :message) consumed]))))

(defn decode-all
  "Decode every complete unit `bs` holds, stopping (without error) at the
  first incomplete one — the caller's job is to keep the undecoded tail
  and append more bytes as they arrive, which is why this returns the
  leftover rather than treating it as a failure."
  [bs]
  (loop [bs (vec bs) acc []]
    (if (empty? bs)
      {:units acc :leftover []}
      (let [[status v n] (decode-one bs)]
        (if (= status :error)
          (if (contains? #{:rtsp/incomplete-headers :rtsp/incomplete-body
                            :rtsp/interleaved-incomplete-header :rtsp/interleaved-incomplete-payload
                            :rtsp/empty-stream}
                         v)
            {:units acc :leftover bs}
            {:units acc :leftover bs :error v})
          (recur (subvec bs n) (conj acc v)))))))
