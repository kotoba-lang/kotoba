# ADR 0002: Browser UI is the aiueos desktop

- Status: accepted
- Contract: `browser.desktop-backend` version 1

## Decision

aiueos uses the existing browser surface as its desktop, rather than adding a
native-widget desktop. The browser guest owns shell policy, workspaces, window
geometry, focus, DOM/layout state and the retained draw list. An OS backend is
limited to presenting complete versioned frames, delivering canonical input,
and servicing explicitly permission-brokered ambient operations.

The v1 boundary consists of:

- `:frame/present`: atomic retained draw-list replacement with monotonic frame
  sequence, viewport, workspace and focus metadata;
- `:input/events`: pointer, wheel, keyboard, text and IME records normalized by
  `browser.input` and reduced by `browser.surface`;
- `:clipboard/read`, `:clipboard/write`, `:file-picker/open` and
  `:file-picker/save`: asynchronous requests carrying an origin and opaque
  request id, emitted only after an `:allow` broker decision;
- one-shot completions: stale or unknown request ids are rejected, and file
  results are opaque tokens rather than ambient host paths.

The contract is pure data and `.cljc`, so a DOM demo host, a native test host,
and a future aiueos compositor can implement the same boundary. It does not
assert that a compositor, GPU driver, filesystem or kernel IPC transport
already exists.

## Consequences

There is one desktop interaction model and one retained rendering model. The
aiueos integration must provide transport and presentation for the declared
effects, translate device events into the canonical vocabulary, and connect
privileged requests to its permission broker. Clipboard and picker access fail
closed when the broker does not grant the exact capability.
