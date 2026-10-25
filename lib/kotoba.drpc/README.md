# drpc

`drpc.*` — the wire format of [DRPC](https://github.com/storj/drpc), Storj's
replacement for gRPC, as portable `.cljc`.

DRPC keeps gRPC's request/response and streaming shapes and drops HTTP/2, which
makes the framing small enough to state in full:

```
control byte | stream id | message id | length | data
               <-------- varints -------->
```

and the control byte carries three things at once:

| bit | meaning |
|---|---|
| 0 | **done** — last frame of this packet |
| 1–6 | **kind** — invoke, message, error, cancel, close, close-send, invoke-metadata |
| 7 | **control** — forwards compatibility; unknown control packets are ignored, not fatal |

```clojure
(require '[drpc.wire :as w])

(w/encode-frame {:kind :invoke :stream 1 :message 1
                 :done? true :data (map int "/piecestore.Piecestore/Upload")})

(let [{:keys [state packets]} (w/feed (w/reader) bytes-from-a-socket)]
  ;; packets are complete; state holds whatever did not finish a frame
  packets)
```

`drpc.client` is the layer above: *which* packets a unary call is made of.

```clojure
(require '[drpc.client :as c])

(c/request {:stream 1 :rpc "/echo.Echo/Echo" :request (map int "hello storj")})
;; invoke, message, close-send — byte-identical to what drpcconn writes

(c/collect packets-received 1)
;; {:message bytes :error {:code n :message s} :closed? bool :ignored [...]}
```

`drpc.session` is the layer above that: several calls on one connection, and
which arriving packet belongs to which waiting call.

```clojure
(require '[drpc.session :as s])

(let [[state call] (s/begin (s/session) {:rpc "/node.Node/CheckIn" :request bs})]
  ;; write (:bytes call), remember (:stream call)
  (let [{:keys [state completed]} (s/feed state bytes-from-a-socket)]
    ;; [{:stream 1 :result {:message ... :error ...}}]
    completed))
```

`drpc.server` is the other side of it: recognising a call arriving and saying
which packets answer it. A client-only library cannot be a storage node, which
spends most of its life being dialled.

```clojure
(require '[drpc.server :as srv])

(let [{:keys [state calls]} (srv/feed (srv/incoming) bytes-from-a-socket)]
  (for [{:keys [stream rpc request]} calls]
    (srv/respond stream (handle rpc request))))
```

Bytes in, bytes out. No sockets, no TLS, no service dispatch, no code
generation — a host owns the connection and hands `feed` whatever a read
produced, in whatever chunking it arrived. `scripts/call.cljk` is the only
place in this repo with a socket in it, and it is a harness rather than part
of the library.

## What the reader refuses

Most of `feed` is refusal, and each rule is load-bearing:

- **Frame ids must not go backwards.** Ids are monotonic; a frame that
  regresses is a protocol error rather than something to reorder.
- **A new id abandons the packet in progress.** This is deliberate in DRPC —
  it is how an asynchronous interrupt is expressed — so the abandoned bytes
  must not be prepended to the next packet.
- **Frames of one packet must agree on their kind.**
- **Payload is bounded** (4 MiB by default). Otherwise a peer can hold memory
  open simply by never setting `done`.
- **Control is sticky.** One control frame makes the whole packet control; a
  later frame cannot clear it.

## Incomplete is not malformed

A frame declaring more data than has arrived is **not** an error. The reference
reader cannot distinguish `not enough bytes yet` from `length exceeds what I
hold`, and neither can this one: both mean read more. Only a varint that never
terminates is malformed. Conflating the two tears down a healthy connection
every time a frame straddles a TCP segment boundary.

## What a unary call is

Four writes and one read, from `drpcconn.Conn.doInvoke`:

| | |
|---|---|
| `InvokeMetadata` | only when there is metadata |
| `Invoke` | body is the rpc name |
| `Message` | body is the encoded request |
| `CloseSend` | empty — nothing more will be sent |
| ← `Message` | the response |

Message ids start at 1 and advance per packet within a stream, which is why
`drpc.client` computes them rather than leaving them to a caller: a call whose
ids restart is a call the far side discards as a replay.

## Streams

`Upload`, `Download`, `SettlementWithWindow` and `RetainBig` are streams, and
none of them can be expressed as a unary call. Opening one writes the invoke
and stops; the caller then sends as many messages as it likes and ends with
`end-send`.

```clojure
(let [[state open] (s/begin-stream (s/session) {:rpc "/piecestore.Piecestore/Upload"})
      [state bs]   (s/send-on state (:stream open) chunk)
      [state done] (s/end-send state (:stream open))]
  ...)
```

**A streaming receive ends on the peer's `CloseSend`, not on its first
message.** Applying the unary rule to a download reads the first chunk and
calls the file finished. The session records which kind each call is, because
both are open on the same connection at the same time.

On the server side `feed` reports both: the call when its client stops
speaking, and every message as it arrives. An upload handler wants the second
— waiting for the whole stream means buffering a piece in memory before
writing a byte of it.

## Several calls on one connection

Stream ids only increase — `drpc.wire`'s reader refuses a regression, and
`Manager.NewClientStream` allocates `last + 1`. `drpc.session` turns those two
facts into dispatch:

- **A stream id is never reused.** Two calls sharing one would each accept the
  other's answer, and neither would know.
- **A completed call is forgotten.** Its stream will not be spoken on again,
  and a connection that keeps every finished call grows without bound — which
  on a storage node's satellite connection is a leak with a schedule rather
  than a bug with a stack trace.
- **A packet for a stream nobody is waiting on is reported, not dropped.** It
  cannot happen from a healthy server; when it does, discarding it turns a
  protocol violation into a call that hangs.

No concurrency here either. Two threads feeding one value lose one of them,
and that is the host's problem to solve.

## Answering a call

A server sees `Invoke`, `Message`, `CloseSend` and answers with `Message` then
`CloseSend` — or `Error` instead. Not `Close`: that is what a *client* sends
when it is finished with a stream, and a server sending one tells the client
the stream is dead before it has read the answer.

Two orderings that read the wrong way round:

- **A call is not ready until `CloseSend`.** A handler that ran on the first
  `Message` would answer a request it had only partly heard.
- **`InvokeMetadata` arrives *before* the `Invoke`.** `doInvoke` writes it
  first, so metadata opens a stream and the name fills it in. Requiring the
  invoke first reads as the same obvious rule and refuses every call a real
  client makes with metadata attached — which is how it was written, and what
  the tests caught.

## Verification

The expected bytes come from `storj.io/drpc` itself. `testdata/gen_vectors.go`
links the reference implementation and records what `drpcwire.AppendFrame` and
`SplitN` emit; `testdata/echo_server.go -dump` drives a real `drpcconn.Conn`
over a transport that records its writes, so the bytes a unary call sends are
also the reference implementation's rather than this library's own. Those are
the literals in the tests.

And a call is actually made: `testdata/echo_server.go` is a DRPC server built
from `storj.io/drpc`, and CI has both runtimes call it. The reply is
`<rpc>:<request>`, so a pass means the rpc *name* was routed rather than that
some bytes came back.

For a format this small that is not ceremony. The control byte packs a kind, a
done bit and a control bit into eight bits, and **a kind shifted by the wrong
amount still round-trips perfectly through one's own codec** — it simply never
interoperates. So there is a vector per kind and per flag rather than a
round-trip property standing in for both. Reintroducing that exact mistake
fails 14 of the assertions here.

Both runtimes run the same suite. That is not a formality either: writing this
library surfaced a real bug in the varint underneath it
(`kotoba-lang/proto` `cd8b83a`), where ten `0x80` bytes — something any peer
can send — overflowed a JVM long and threw a different error than
ClojureScript did.

## Test

```sh
kbb -M:test                                              # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk
kbb -M:lint
cd testdata && go run gen_vectors.go                         # regenerate vectors
cd testdata && go run echo_server.go -dump                   # regenerate the call vector
cd testdata && go run echo_server.go -port 19500             # a real DRPC server
kbb -M:call 127.0.0.1:19500 /echo.Echo/Echo 'hello'      # and a real call
```

The only dependency is `kotoba-lang/proto`, for the varint — DRPC uses the
same LEB128 encoding protobuf does, and a third copy of a varint reader is how
encodings quietly diverge.
