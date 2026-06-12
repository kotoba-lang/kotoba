# ossekai_consent_registry — Pregel cell

Paired with `20-actors/ossekai/`.
Murakumo node: **issachar**.
This cell continuously observes the AT Protocol firehose for `app.bsky.graph.block` and `app.bsky.graph.mute` events related to the actor, updating the global consent state.

Resident in Kotoba WASM.
