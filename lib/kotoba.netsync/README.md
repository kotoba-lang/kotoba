# kotoba-lang/netsync

**SSoT for `kami.netsync`** — EDN replication schema, snapshot/interp,
client-side prediction, and genre lag compensation (`.cljc`).

`kotoba.netsync` is a thin facade. See ADR-2607102200 addendum 7.

## What each namespace owns

| ns | Job |
|---|---|
| `kami.netsync` | What crosses the wire for an entity (fields, authority, interp, prediction) |
| `kami.relevancy` | Whether that entity crosses the wire to you at all (AoI) |
| `kami.netsync.fps` | Hitscan rewind. Client sends a fire intent; authority raycasts the world the shooter saw. Client never decides a hit. |
| `kami.netsync.fighting` | 2P lockstep. `:rollback` predicts missing input and rewinds on correction; `:delay` stalls until both real inputs exist. Confirm only past the rewrite window. |

Transport (T1 WebSocket, T2 WebRTC DataChannel, T3 libp2p P2P) is not this
package. All three ingest the same intent / per-tick input.

Movement prediction for an FPS is still `pred-reconcile`. The shot is
`kami.netsync.fps/resolve-hitscan`. Do not fold those into one function —
a predicted move is feel; a predicted hit is a lie.

Network fighting does not go through the guest DSL. The guest has one local
input stream, so true local 2P is not buildable; each network peer has its
own stream and both run the same `step`.

## Test

```sh
kbb -M:test
```
