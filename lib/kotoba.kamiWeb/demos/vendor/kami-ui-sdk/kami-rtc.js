/**
 * kami-rtc.js — KAMI WebRTC SDK (browser-side).
 *
 * Bridges kami-web WASM (room/signaling/spatial state machine) with
 * browser WebRTC APIs (RTCPeerConnection, getUserMedia, Web Audio).
 *
 * Architecture:
 *   WASM (kami-rtc Rust)  →  state machine, signaling protocol, spatial math
 *   JS (this file)        →  RTCPeerConnection, MediaStream, Web Audio API
 *   KNP (kami-knp)        →  signaling transport (WebTransport data channel)
 *
 * Usage:
 *   const rtc = KamiRTC.init(wasmModule, { onPeerJoined, onPeerLeft, ... });
 *   await rtc.createRoom("room-1", "my-did", "Alice");
 *   await rtc.startMedia({ audio: true, video: true });
 *   // ... signaling via KNP or WebSocket ...
 *   rtc.destroy();
 */

const KamiRTC = (() => {
  /** @type {Map<string, RTCPeerConnection>} peer_id → connection */
  let peerConnections = new Map();

  /** @type {MediaStream|null} local media stream */
  let localStream = null;

  /** @type {AudioContext|null} Web Audio context for spatial audio */
  let audioCtx = null;

  /** @type {Map<string, { source: MediaStreamAudioSourceNode, panner: PannerNode, gain: GainNode }>} */
  let spatialNodes = new Map();

  /** @type {object|null} WASM module reference */
  let wasm = null;

  /** @type {object} event callbacks */
  let callbacks = {};

  /** @type {number|null} spatial audio animation frame */
  let spatialFrame = null;

  /** ICE servers configuration */
  const ICE_CONFIG = {
    iceServers: [
      { urls: "stun:stun.l.google.com:19302" },
      { urls: "stun:stun1.l.google.com:19302" },
    ],
  };

  /**
   * Initialize the KAMI WebRTC SDK.
   * @param {object} wasmModule - kami-web WASM module (with rtc_* exports)
   * @param {object} opts - Event callbacks
   * @param {function} [opts.onPeerJoined] - (peerId, displayName) => void
   * @param {function} [opts.onPeerLeft] - (peerId) => void
   * @param {function} [opts.onTrackReceived] - (peerId, stream, track) => void
   * @param {function} [opts.onDataReceived] - (peerId, data) => void
   * @param {function} [opts.onSignalOut] - (signalJson) => void — send to remote
   * @param {function} [opts.onError] - (error) => void
   * @returns {object} KamiRTC API
   */
  function init(wasmModule, opts = {}) {
    wasm = wasmModule;
    callbacks = opts;
    return KamiRTC;
  }

  /**
   * Create and join a room.
   * @param {string} roomId
   * @param {string} localPeerId - DID or session ID
   * @param {string} displayName
   * @param {object} [config] - RoomConfig overrides
   * @returns {string} join signal JSON (send via KNP/WebSocket)
   */
  function createRoom(roomId, localPeerId, displayName, config = {}) {
    const configJson = Object.keys(config).length > 0 ? JSON.stringify(config) : "";
    const joinSignal = wasm.rtc_create_room(roomId, localPeerId, displayName, configJson);
    _startSpatialLoop();
    return joinSignal;
  }

  /**
   * Start local media capture.
   * @param {object} [constraints] - { audio: bool, video: bool }
   * @returns {Promise<MediaStream>}
   */
  async function startMedia(constraints = { audio: true, video: true }) {
    try {
      localStream = await navigator.mediaDevices.getUserMedia(constraints);
      return localStream;
    } catch (err) {
      console.error("[kami-rtc] getUserMedia failed:", err);
      if (callbacks.onError) callbacks.onError(err);
      throw err;
    }
  }

  /**
   * Process an incoming signaling message from a remote peer.
   * @param {string} signalJson - SignalMessage JSON from KNP/WebSocket
   */
  async function processSignal(signalJson) {
    const eventsJson = wasm.rtc_process_signal(signalJson);
    const events = JSON.parse(eventsJson);

    for (const event of events) {
      await _handleEvent(event);
    }
  }

  /**
   * Handle a room event from the WASM state machine.
   * @param {object} event - RoomEvent
   */
  async function _handleEvent(event) {
    if (event.PeerJoined) {
      const { peer_id, display_name } = event.PeerJoined;
      if (callbacks.onPeerJoined) callbacks.onPeerJoined(peer_id, display_name);
      // Initiate WebRTC connection to new peer
      await _createPeerConnection(peer_id, true);
    } else if (event.PeerLeft) {
      const { peer_id } = event.PeerLeft;
      _closePeerConnection(peer_id);
      if (callbacks.onPeerLeft) callbacks.onPeerLeft(peer_id);
    } else if (event.OfferReceived) {
      const { from, sdp } = event.OfferReceived;
      await _handleOffer(from, sdp);
    } else if (event.AnswerReceived) {
      const { from, sdp } = event.AnswerReceived;
      await _handleAnswer(from, sdp);
    } else if (event.IceCandidateReceived) {
      const { from, candidate } = event.IceCandidateReceived;
      await _handleIceCandidate(from, candidate);
    } else if (event.DataReceived) {
      const { from, data } = event.DataReceived;
      if (callbacks.onDataReceived) callbacks.onDataReceived(from, data);
    }
  }

  /**
   * Create RTCPeerConnection for a remote peer.
   * @param {string} peerId
   * @param {boolean} isInitiator - true if we send the offer
   */
  async function _createPeerConnection(peerId, isInitiator) {
    if (peerConnections.has(peerId)) return;

    const pc = new RTCPeerConnection(ICE_CONFIG);
    peerConnections.set(peerId, pc);

    // Add local tracks
    if (localStream) {
      for (const track of localStream.getTracks()) {
        pc.addTrack(track, localStream);
      }
    }

    // ICE candidate handler
    pc.onicecandidate = (ev) => {
      if (ev.candidate) {
        const candidateJson = JSON.stringify(ev.candidate.toJSON());
        const signal = wasm.rtc_create_ice_candidate(peerId, candidateJson);
        _sendSignal(signal);
      }
    };

    // Remote track handler
    pc.ontrack = (ev) => {
      const [remoteStream] = ev.streams;
      if (callbacks.onTrackReceived) {
        callbacks.onTrackReceived(peerId, remoteStream, ev.track);
      }
      // Set up spatial audio for audio tracks
      if (ev.track.kind === "audio") {
        _setupSpatialAudio(peerId, remoteStream);
      }
    };

    // Connection state
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {
        console.warn(`[kami-rtc] peer ${peerId} connection ${pc.connectionState}`);
      }
    };

    // Data channel
    if (isInitiator) {
      const dc = pc.createDataChannel("kami-data", { ordered: false });
      _setupDataChannel(peerId, dc);

      // Create and send offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      const signal = wasm.rtc_create_offer(peerId, offer.sdp);
      _sendSignal(signal);
    } else {
      pc.ondatachannel = (ev) => {
        _setupDataChannel(peerId, ev.channel);
      };
    }
  }

  /**
   * Handle incoming SDP offer.
   */
  async function _handleOffer(fromPeerId, sdp) {
    await _createPeerConnection(fromPeerId, false);
    const pc = peerConnections.get(fromPeerId);
    if (!pc) return;

    await pc.setRemoteDescription(new RTCSessionDescription({ type: "offer", sdp }));
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);

    const signal = wasm.rtc_create_answer(fromPeerId, answer.sdp);
    _sendSignal(signal);
  }

  /**
   * Handle incoming SDP answer.
   */
  async function _handleAnswer(fromPeerId, sdp) {
    const pc = peerConnections.get(fromPeerId);
    if (!pc) return;
    await pc.setRemoteDescription(new RTCSessionDescription({ type: "answer", sdp }));
  }

  /**
   * Handle incoming ICE candidate.
   */
  async function _handleIceCandidate(fromPeerId, candidateJson) {
    const pc = peerConnections.get(fromPeerId);
    if (!pc) return;
    const candidate = new RTCIceCandidate(JSON.parse(candidateJson));
    await pc.addIceCandidate(candidate);
  }

  /**
   * Set up data channel for a peer.
   */
  function _setupDataChannel(peerId, dc) {
    dc.onmessage = (ev) => {
      if (callbacks.onDataReceived) callbacks.onDataReceived(peerId, ev.data);
    };
    dc.onerror = (err) => {
      console.warn(`[kami-rtc] data channel error for ${peerId}:`, err);
    };
  }

  /**
   * Set up Web Audio spatial audio for a peer's audio stream.
   */
  function _setupSpatialAudio(peerId, stream) {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }

    // Clean up existing nodes
    _teardownSpatialAudio(peerId);

    const source = audioCtx.createMediaStreamSource(stream);
    const panner = audioCtx.createPanner();
    panner.panningModel = "HRTF";
    panner.distanceModel = "inverse";
    panner.refDistance = 1;
    panner.maxDistance = 50;
    panner.rolloffFactor = 1;

    const gain = audioCtx.createGain();
    gain.gain.value = 1.0;

    source.connect(panner);
    panner.connect(gain);
    gain.connect(audioCtx.destination);

    spatialNodes.set(peerId, { source, panner, gain });
  }

  /**
   * Tear down spatial audio for a peer.
   */
  function _teardownSpatialAudio(peerId) {
    const nodes = spatialNodes.get(peerId);
    if (nodes) {
      nodes.source.disconnect();
      nodes.panner.disconnect();
      nodes.gain.disconnect();
      spatialNodes.delete(peerId);
    }
  }

  /**
   * Start the spatial audio update loop (calls WASM rtc_spatialize at 30fps).
   */
  function _startSpatialLoop() {
    if (spatialFrame) return;

    let lastTime = 0;
    function loop(time) {
      // Throttle to ~30fps
      if (time - lastTime < 33) {
        spatialFrame = requestAnimationFrame(loop);
        return;
      }
      lastTime = time;

      try {
        const resultsJson = wasm.rtc_spatialize();
        const results = JSON.parse(resultsJson);

        for (const [peerId, leftVol, rightVol, pan] of results) {
          const nodes = spatialNodes.get(peerId);
          if (nodes) {
            // Apply WASM-computed spatial values
            nodes.gain.gain.setTargetAtTime(
              (leftVol + rightVol) / 2,
              audioCtx.currentTime,
              0.05,
            );
            nodes.panner.positionX.setTargetAtTime(pan * 5, audioCtx.currentTime, 0.05);
          }
        }
      } catch (e) {
        // Ignore errors during spatialization
      }

      spatialFrame = requestAnimationFrame(loop);
    }

    spatialFrame = requestAnimationFrame(loop);
  }

  /**
   * Stop the spatial audio loop.
   */
  function _stopSpatialLoop() {
    if (spatialFrame) {
      cancelAnimationFrame(spatialFrame);
      spatialFrame = null;
    }
  }

  /**
   * Send a signaling message to remotes via callback.
   */
  function _sendSignal(signalJson) {
    if (callbacks.onSignalOut && signalJson) {
      callbacks.onSignalOut(signalJson);
    }
  }

  /**
   * Close a peer connection and clean up.
   */
  function _closePeerConnection(peerId) {
    const pc = peerConnections.get(peerId);
    if (pc) {
      pc.close();
      peerConnections.delete(peerId);
    }
    _teardownSpatialAudio(peerId);
  }

  // ─── Public API ───

  /**
   * Update local user position for spatial audio.
   * @param {number} x
   * @param {number} y
   * @param {number} z
   * @returns {string} position signal JSON (broadcast to peers)
   */
  function updatePosition(x, y, z) {
    // Update Web Audio listener position
    if (audioCtx && audioCtx.listener.positionX) {
      audioCtx.listener.positionX.setTargetAtTime(x, audioCtx.currentTime, 0.05);
      audioCtx.listener.positionY.setTargetAtTime(y, audioCtx.currentTime, 0.05);
      audioCtx.listener.positionZ.setTargetAtTime(z, audioCtx.currentTime, 0.05);
    }
    return wasm.rtc_update_position(x, y, z);
  }

  /**
   * Send data to all peers (cursor position, annotation, reaction).
   * @param {object} data
   * @returns {string} signal JSON
   */
  function sendData(data) {
    return wasm.rtc_send_data(JSON.stringify(data));
  }

  /**
   * Mute/unmute local audio.
   * @param {boolean} muted
   */
  function muteAudio(muted) {
    if (localStream) {
      for (const track of localStream.getAudioTracks()) {
        track.enabled = !muted;
      }
    }
  }

  /**
   * Enable/disable local video.
   * @param {boolean} enabled
   */
  function setVideoEnabled(enabled) {
    if (localStream) {
      for (const track of localStream.getVideoTracks()) {
        track.enabled = enabled;
      }
    }
  }

  /**
   * Start screen sharing (replaces video track).
   * @returns {Promise<MediaStream>}
   */
  async function startScreenShare() {
    const screenStream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: false,
    });

    const screenTrack = screenStream.getVideoTracks()[0];

    // Replace video track on all peer connections
    for (const [, pc] of peerConnections) {
      const sender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
      if (sender) {
        await sender.replaceTrack(screenTrack);
      }
    }

    // Restore camera when screen share ends
    screenTrack.onended = () => {
      if (localStream) {
        const cameraTrack = localStream.getVideoTracks()[0];
        if (cameraTrack) {
          for (const [, pc] of peerConnections) {
            const sender = pc
              .getSenders()
              .find((s) => s.track && s.track.kind === "video");
            if (sender) {
              sender.replaceTrack(cameraTrack);
            }
          }
        }
      }
    };

    return screenStream;
  }

  /**
   * Get room summary from WASM state machine.
   * @returns {object}
   */
  function getRoomSummary() {
    const json = wasm.rtc_room_summary();
    return JSON.parse(json || "{}");
  }

  /**
   * Leave room, close all connections, clean up.
   * @returns {string} leave signal JSON
   */
  function destroy() {
    _stopSpatialLoop();

    // Close all peer connections
    for (const [peerId] of peerConnections) {
      _closePeerConnection(peerId);
    }

    // Stop local tracks
    if (localStream) {
      for (const track of localStream.getTracks()) {
        track.stop();
      }
      localStream = null;
    }

    // Close audio context
    if (audioCtx) {
      audioCtx.close();
      audioCtx = null;
    }

    // Leave room in WASM
    const leaveSignal = wasm.rtc_leave_room();
    wasm = null;
    callbacks = {};

    return leaveSignal;
  }

  return {
    init,
    createRoom,
    startMedia,
    processSignal,
    updatePosition,
    sendData,
    muteAudio,
    setVideoEnabled,
    startScreenShare,
    getRoomSummary,
    destroy,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = KamiRTC;
}
