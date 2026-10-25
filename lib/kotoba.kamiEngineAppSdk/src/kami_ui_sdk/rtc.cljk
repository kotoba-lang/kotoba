(ns kami-ui-sdk.rtc
  "Ported from kami-engine's live `kami-ui-sdk/kami-rtc.js` (JS, not
   deleted Rust — see `kami-ui-sdk` root docstring). ADR-2607010930.

   `kami-rtc.js` is browser-side glue that bridges the `kami-web` WASM
   module's room/signaling/spatial *state machine* — the same domain
   already restored as `kotoba-lang/rtc` from the Rust `kami-rtc`
   crate (`rtc.media`/`rtc.peer`/`rtc.room`/`rtc.signal`/`rtc.spatial`,
   16 tests / 44 assertions) — with the browser's `RTCPeerConnection`,
   `getUserMedia`, and Web Audio `PannerNode` APIs. The domain logic
   (room state, peer state machine, signaling wire format, and the
   spatial pan/volume *calculation itself*) already lives in
   `kotoba-lang/rtc`'s `rtc.spatial` (equal-power pan + inverse-distance
   rolloff) — this JS file only *calls into* that logic (via
   `wasm.rtc_spatialize()`) and *applies* the results to
   `RTCPeerConnection`/`PannerNode` objects. There is very little
   independent logic left once the WASM calls and DOM/WebRTC glue are
   excluded.

   Ported (pure, portable — the little that is genuinely new here):
   - `ice-config` — the `ICE_CONFIG` STUN-server data constant.
   - `spatial-frame-due?` — pure port of `_startSpatialLoop`'s ~30fps
     throttle check (`time - lastTime < 33`).
   - `spatial-result->audio-params` — pure port of the per-peer mapping
     applied to each `[peer_id, leftVol, rightVol, pan]` tuple returned
     by `wasm.rtc_spatialize()` (i.e. by `kotoba-lang/rtc`'s
     `rtc.spatial` calculation): `gain = (leftVol + rightVol) / 2`,
     `panner.positionX = pan * 5`. This is JS-side unit conversion from
     `rtc.spatial`'s output to Web Audio `PannerNode` parameters — the
     spatial math itself is *not* re-implemented here.

   Excluded (WebRTC/DOM/Web-Audio-only, no CLJC equivalent — the vast
   majority of the file):
   - All `RTCPeerConnection`/`RTCSessionDescription`/`RTCIceCandidate`
     construction, offer/answer/ICE-candidate exchange
     (`_createPeerConnection`, `_handleOffer`, `_handleAnswer`,
     `_handleIceCandidate`).
   - `navigator.mediaDevices.getUserMedia`/`getDisplayMedia`
     (`startMedia`, `startScreenShare`).
   - `AudioContext`/`MediaStreamAudioSourceNode`/`PannerNode`/
     `GainNode` graph construction (`_setupSpatialAudio`,
     `_teardownSpatialAudio`).
   - The `requestAnimationFrame` spatial-audio loop driver
     (`_startSpatialLoop`/`_stopSpatialLoop`) — only its throttle
     *predicate* was ported.
   - Data-channel wiring (`_setupDataChannel`), mute/video toggling
     (`muteAudio`, `setVideoEnabled`), and all `wasm.rtc_*` calls
     themselves (they invoke the WASM module, which is
     `kotoba-lang/rtc`'s domain).")

;; ─── ICE config ──────────────────────────────────────────────────

(def ice-config
  "Pure data port of `ICE_CONFIG`."
  {:ice-servers [{:urls "stun:stun.l.google.com:19302"}
                 {:urls "stun:stun1.l.google.com:19302"}]})

;; ─── Spatial loop throttle ───────────────────────────────────────

(defn spatial-frame-due?
  "Pure port of `_startSpatialLoop`'s ~30fps throttle check: given the
   current `time`, `last-time`, and `min-interval` (33ms in the JS),
   returns true when a new spatialize pass should run (i.e. NOT
   `time - last-time < min-interval`)."
  ([time last-time] (spatial-frame-due? time last-time 33))
  ([time last-time min-interval]
   (not (< (- time last-time) min-interval))))

;; ─── Spatial result -> Web Audio params ──────────────────────────

(defn spatial-result->audio-params
  "Pure port of the per-peer mapping applied to each `rtc_spatialize()`
   result tuple `[peer-id left-vol right-vol pan]` (as produced by
   `kotoba-lang/rtc`'s `rtc.spatial`): `{:peer-id :gain :pan-x}` where
   `gain = (left-vol + right-vol) / 2` and `pan-x = pan * 5`."
  [[peer-id left-vol right-vol pan]]
  {:peer-id peer-id
   :gain (/ (+ left-vol right-vol) 2.0)
   :pan-x (* pan 5)})

(defn spatial-results->audio-params
  "Maps `spatial-result->audio-params` over a whole `rtc_spatialize()`
   results seq."
  [results]
  (mapv spatial-result->audio-params results))
