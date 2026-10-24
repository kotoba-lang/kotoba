(ns engineer-render.draw-list
  "Per-frame engineering draw-command buffer. Restored from kami-eng-render's
  `EngDrawList` (deleted PR #82). A draw command is a plain EDN map — the
  original Rust `EngDrawCmd` enum's 10 variants (:line/:arc/:circle/:pad/
  :dimension/:hatch/:grid/:crosshair/:color-map-quad/:waveform-trace) map
  1:1 to a `{:cmd <kind> ...fields}` shape. This namespace only owns the
  buffer (push/clear/len); the native kami-render provider consumes the EDN
  command list and dispatches to wgpu — the recorder itself stays Rust
  (ADR-2607010930: what-to-record -> EDN, the recorder stays native).")

(def cmd-kinds
  #{:line :arc :circle :pad :dimension :hatch :grid :crosshair
    :color-map-quad :waveform-trace})

(defn draw-list
  "A fresh, empty draw-command buffer."
  []
  {:commands []})

(defn push
  "Append a draw command `{:cmd <kind> ...}` to the buffer."
  [draw-list cmd]
  (update draw-list :commands conj cmd))

(defn clear [draw-list] (assoc draw-list :commands []))
(defn commands [draw-list] (:commands draw-list))
(defn draw-count [draw-list] (count (:commands draw-list)))
(defn draw-empty? [draw-list] (empty? (:commands draw-list)))
