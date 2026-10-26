# ADR-0073 — The first request that left this machine, and the three answers a gate can give

Date: 2026-08-22

## Status

Accepted and executable **for the hosted profile**. On 2026-08-22 this
repository opened TLS connections to `kotobase.net`, `api.murakumo.cloud` and
`infer.murakumo.cloud`, accepted each peer because its key was one the policy
named, read a block whose bytes hash to its CID, refused a CID the store does
not hold, resolved the `murakumo-main` alias, and **obtained and judged a
completion**. The gate exits **0**. ADR-0041's sentence *"has never contacted
`kotobase.net` or `api.murakumo.cloud`"* is no longer true of the hosted profile
and remains true of the bare-metal profile.

This spans two repositories. The decision half — `grant.cloud`, `grant.json` and
the contract — is in `kotoba-lang/grant`, which the decision plane moved to on
2026-08-21 (root ADR-2608219500). The mechanism half, the operator gate and this
ADR are here. The edge is one-way: `aiueos` requires `grant`, and nothing in
`grant` requires `aiueos`.

Not executable, and stated here rather than at the end:

- **The bare-metal profile is untouched.** ADR-0041's gap-ledger steps 1–5 —
  DHCP, a DNS stub resolver, TCP as a usable stream, TLS 1.3, an HTTP/1.1
  client — are exactly where they were. Nothing in `os/aiueos/` changed except
  one script's dependency coordinate.
- **The credentialed inference surface is unmeasured.** The completion came
  from `infer.murakumo.cloud`, which answers without a credential;
  `api.murakumo.cloud/v1/messages` still answers 401 and no token for it is
  reachable from this workstation. One of the two surfaces is exercised.
- **The live write leg is unauthorised.** `PUT https://kotobase.net/ipfs/:cid`
  answers **401** without a bearer token, and this machine holds none. The
  mechanism exists and is proved in both directions offline.
- **The pins will rotate.** All three hosts are Cloudflare-fronted, so the leaf
  key is the edge's.

## Context

ADR-0042 gave the two cloud authorities a decision layer. ADR-0043 gave it a
provider that could take bytes off a socket — a *loopback* socket, over
plaintext, through the one policy exemption that exists to skip certificate
validation. ADR-0044 replaced the platform trust store with a pin set and
recorded no pin for anything real; ADR-0045 designed how a pin set rotates
without stranding a device. Every one of those is a mechanism whose subject was
absent.

ADR-0041's ledger said what was left. Row 6: the kotobase read is done for the
hosted profile, *"Write: unwritten, and it needs CACAO auth"*. Row 7: the
murakumo client is *"decision only … the hosted provider performs `GET` and
nothing else, so the POST plan has no mechanism behind it"*.

A `GET`-only provider is a specific kind of hole. `plan-block-write` emitted
`:put` and `plan-inference` emitted `:post`, and `perform!` hardcoded `.GET`.
A plan that said `:put` would therefore have been **performed as a read**: a 200
would come back, nothing would be stored, and a receipt would record a success.
That is the shape of defect root ADR-2608136000 is about — not a check that
failed, a check that could not run returning the value of one that did.

## Decision

### A JSON reader narrow enough to live in the TCB

Both authorities answer in JSON, and `admit-model` and `admit-inference` decide
on the values inside it. `deps.edn`'s runtime dependencies are `security`, `abi`
and Chicory, and that is an invariant the README states; adding a JSON library
would put a parser nobody here reviewed inside the boundary
`qualification/tcb-inventory.edn` exists to bound. So `src/aiueos/json.cljc`
follows the precedent `grant.cloud` set with its inlined base32/CID decoder:
the one shape that is needed, and a refusal for everything else.

It refuses **duplicate object keys** (two answers to one question, and which
survives would be the parser's opinion), **trailing bytes** (reading the prefix
of `{"ok":true} garbage` is agreeing with whoever sent the rest about where the
document ended), `NaN`, `Infinity`, `+1`, `.5`, `01`, raw control characters
inside strings, anything past a depth or input ceiling, and **an integer larger
than this runtime represents exactly** — refused as `:number-out-of-range`
rather than rounded, because a rounded identifier compares equal to nothing and
unequal to everything.

Failure is a value, not an exception: `read-json` returns the document or a map
carrying `:grant.json/error`. A parsed JSON object has **string** keys, so it
can never contain that keyword and `failed?` is unambiguous rather than a
convention. Object keys stay strings for a second reason — interning them would
let a remote authority decide what keywords this machine holds.

### The provider performs the methods the plans emit, and holds no credential

`aiueos.provider.cloud/perform!` now dispatches on the plan's `:method` for
`:get`, `:post` and `:put`, with a request body and caller-supplied headers.
A method it has no verb for is a **fault**, not a silent `GET`. A body that
`grant.json/write-json` refuses to encode is a fault too: a request whose body
could not be built was never made.

Everything that made this namespace worth trusting is unchanged. It reports what
arrived — status, byte count, SHA-256 — and judges nothing. Redirects are still
never followed. The body ceiling still refuses rather than truncates. A request
that could not complete is still `:aiueos.provider.cloud/error` and never a
status.

**Credentials arrive; they are never held.** An authorization header is an
injected value in `opts`. The namespace has no default, reads no environment
variable, and does not carry headers onto the result — so a credential cannot
reach a receipt, a log line or an exception message by travelling with the thing
that was measured. There is a test that prints the whole verdict and asserts the
token is not in it.

### The murakumo client, and the decision that was missing

`resolve-model!` performs the alias `GET`; `infer!` performs the `POST`;
`ready!` performs a liveness `GET`. All three are three steps — `grant.cloud`
plans, the provider performs, `grant.cloud` judges — and the translation from
the authority's JSON to the fields the decision layer reads happens in
`grant.cloud/admit-resolution`, narrowly and by name, so a field this machine
does not know about cannot become one it acts on.

`admit-inference` is the decision that did not exist. Three outcomes have to
stay distinguishable:

- **the provider could not measure** — no status, because the request faulted:
  `:response-unmeasured`. It is not a refusal; there was nothing to refuse;
- **the model returned nothing** — a 200 whose body carries no completion text:
  `:completion-empty`;
- **it worked** — an allow carrying the text, its length and the stop reason.

A non-200 is `:response-not-ok` with the status. A body that is not JSON is
`:body-unparsable` with the reader's own reason, because "could not read it" and
"read it and it was empty" are different facts.

Reasoning fields are deliberately not read. Measured 2026-08-22 against the live
endpoint at `max_tokens: 8`, a chat-completions response came back with
`"content": ""` and a full `"reasoning_content"`. A model that spent its whole
budget thinking produced no completion, and counting the thinking would have
turned that into a pass.

### The plan declares the answer shape; the reader does not sniff it

Both murakumo surfaces are live in front of the same fleet.
`api.murakumo.cloud/v1/messages` is Anthropic-shaped
(`content[].text`, `stop_reason`) and demands a token. The endpoint the alias
resolves onto, `infer.murakumo.cloud/v1/chat/completions`, is OpenAI-shaped
(`choices[].message.content`, `finish_reason`) and answers without one.

The obvious move is one reader that tries both keys. It is wrong for a specific
reason: when the container key is missing, "the model returned nothing" and
"this is not the document I asked for" look identical, and a gate that cannot
tell them apart cannot tell a busy model from the wrong host answering. So
`plan-inference` records `:aiueos.cloud/response-shape`, derived from the path
it is about to request and overridable in policy, and `admit-inference` reads
exactly that one. Two refusals follow from it:
`:response-shape-unknown` (a path this plane has no reader for — refused before
the body is read, because a machine that cannot say what it asked for cannot
judge what it got) and `:response-shape-mismatch` (the declared container is
absent). `:completion-empty` now means only what it says: the container was
there and carried nothing.

**Liveness is added and is less than inference, on purpose.** Without it, three
states collapse into one "inference did not happen": the authority is
unreachable, the authority answered but this machine holds no credential, and
the authority served a completion. `admit-liveness` returns
`:aiueos.cloud/live? true` and never a completion, and the gate's exit code
never reads it as one.

### The write mechanism, and what it actually needs

`write-block!` performs the `PUT`. Two decisions, in this order:
`admit-write-payload` judges the bytes **before the socket** — a CID is a claim
about bytes and this request is the machine making that claim, so bytes that
hash to something else never leave — and then `admit-write` judges the answer.

`admit-write` keeps three refusals apart, because three different people fix
them: **401** `:write-unauthorized` (no token, or one the authority does not
hold), **403** `:write-forbidden` (the feature is switched off; nothing the
caller sends will help), and **422** `:write-digest-rejected` (the store hashed
the body and disagreed). The third should be unreachable, since
`admit-write-payload` refuses those bytes first; reaching it means this machine
and the store disagree about what they hashed, which deserves a name rather than
a number in a field.

**ADR-0041's row 6 was wrong about the credential, and this ADR corrects it.**
kotobase's block plane is a first-party operator write gate: it wants
`Authorization: Bearer <token>` compared string-equal against a Worker secret,
with no signature, no scope, no DID and no CACAO verifier anywhere on that path.
CACAO is how a *tenant* authenticates to the datom plane, and a `CACAO …` header
fails the `Bearer ` prefix test before any verifier sees it. aiueos owes a
bearer-credential seam here, not a CACAO port — which is a smaller debt than the
ledger claimed, and a different one.

### A gate an operator runs, with three exit codes

`kbb -M:cloud-live` has three subcommands.

`pin <origin>…` **measures** a peer key and prints it. It writes no policy file,
and its output says `MEASURED, NOT TRUSTED`. It exists because a first pin
cannot be verified against a pin — somebody has to look at a key before anyone
can decide to trust it — and it is the one place in this repository with a trust
manager that accepts any peer. That code lives in a different namespace from
`check`, which uses the pinning provider, so neither can be reached from the
other by editing a flag.

`check` runs the legs and prints an EDN receipt. `write` runs the write leg
alone.

The exit codes are three:

- **0** every leg that was attempted was admitted;
- **1** a leg was refused — pins wrong, digest wrong, endpoint outside the
  allowlist. Something is wrong;
- **3** a leg could not be answered — no network, no route, nothing to ask.

`exit-code` prefers 1 over 3 over 0, so a real refusal is never hidden behind a
leg that was skipped, and no legs at all is 3 rather than 0. The receipt prints
the word `UNMEASURED` next to such a leg along with why, so a leg that could not
answer and a leg that passed are distinguishable in the text a person reads and
not only in a key they have to look for.

**A credential is attached when present and never required.** The first version
of this gate skipped the inference POST unless a token was set, reasoning that a
401 obtained without one says nothing about the mechanism. The reasoning was
sound and the rule it produced was not: on an endpoint that needs no credential,
declining to ask returns the same UNMEASURED whether the authority is healthy,
broken or gone. A gate that will not perform the one request it exists for has
made its own headline result unfalsifiable. So the request is always made, and a
401 — with or without a token — is a refusal that takes the exit code with it.

**It is not a fleet gate.** murakumo nodes hold no credentials by invariant and
their egress is not uniform. A gate that needs an open path to three named hosts
— one of which is the fleet itself — is an operator's to run, so it is an alias
in `deps.edn` and nothing in `scripts/fleet-ci` names it.

### The policy is a resource, because it is a deployment

`resources/aiueos/cloud_live.edn` holds the origins, the allowlist, the measured
pins with the date and method of measurement beside them, the CIDs the gate asks
for, and the names of the environment variables the credentials come from. None
of it is a property of this repository. The read CID in particular is a policy
value rather than a literal, so pointing the gate at a more interesting block is
an edit to one line.

## What the live run measured

Verbatim, `kbb -M:cloud-live check`, 2026-08-22:

```
LEG model-resolve       ADMITTED    {:alias "murakumo-main", :alias-for "qwen3.8-27b", :byte-count 497, :endpoint "https://infer.murakumo.cloud/v1/chat/completions", :endpoint-source :resolved, :peer-spki "ec7f258fc32457d84295f081a479910ee9b5250d34158fcf3c92eafb9dbd1af1", :status 200}
LEG inference-liveness  ADMITTED    {:byte-count 582, :live? true, :path "/ready", :peer-spki "ec7f258fc32457d84295f081a479910ee9b5250d34158fcf3c92eafb9dbd1af1", :status 200}
LEG inference           ADMITTED    {:byte-count 1228, :completion-chars 4, :credential :absent, :credential-env "AIUEOS_MURAKUMO_TOKEN", :peer-spki "014bccd86fa34b2a9dbc410b5d27e60e46fb938cc9c9b77058c567cc4b997038", :response-shape :chat-completions-v1, :status 200, :stop-reason "stop"}
LEG storage-read        ADMITTED    {:byte-count 0, :cid "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku", :digest "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", :peer-spki "50602ad366823fcf5274a7c917baa4fd24b9de4fd15635ff501177c83d05473e", :status 200}
LEG storage-absent      ADMITTED    {:byte-count 10, :cid "bafkreicjlihajri6k5g4n66xvq3xsffb45qddog7q2wpolck5kddammoey", :expected-reason :response-not-ok, :expected-status 404, :peer-spki "50602ad366823fcf5274a7c917baa4fd24b9de4fd15635ff501177c83d05473e", :refusal-reason :response-not-ok, :status 404}

exit 0
```

Five legs, five admissions. **The inference leg is the one worth reading
closely**: 1,228 bytes arrived from a peer whose key is the third pin in the
policy, they parsed as `:chat-completions-v1` because that is the shape the plan
declared for the path the alias named, they carried a four-character completion,
and `finish_reason` was `"stop"` rather than `"length"`. `:credential :absent`
is not a caveat on that — it is the fact that this endpoint requires none, said
out loud so nobody reads the pass as evidence about the gated surface.

The read leg is worth reading twice for the opposite reason. The block is the
empty byte string (sha256 `e3b0c442…b855`), so the gateway returned 200 with
**zero bytes** and `admit-block` still had to hash what arrived and agree with
the CID. A digest check that passes on nothing is the same check as one that
passes on a megabyte.

The write leg, run separately with a deliberately invalid token:

```
LEG storage-write       REFUSED     :write-unauthorized
```

That is the live `kotobase.net` answering 401 to a real `PUT` carrying a real
`Authorization: Bearer` header and 28 bytes. The mechanism reaches the
authority; the authority says no.

### Three deployment values that each faked a failure first

None of these are the authority's fault, and all three produce a receipt that
looks like the authority's fault. They are asserted in
`aiueos.cloud-live-test` for that reason.

- **`max_tokens`.** At 8, the model spends the entire budget in
  `reasoning_content` and returns a 200 with `content: ""` and
  `finish_reason: "length"` — a genuine `:completion-empty`, caused by the
  gate's own request. At 256 it answered `"pong"` after 152 completion tokens.
  The policy says 512.
- **The request timeout.** `aiueos.provider.cloud` defaults to 15s, which is
  right for a block and wrong for a 27B model with one production slot: the same
  request took **23s and 56s** on two consecutive runs. The first live run of
  this leg reported `UNMEASURED :request-failed "request timed out"` — honest,
  and indistinguishable from an endpoint that is gone. The policy now names
  180s. Being impatient there would not make the gate stricter, it would make
  it blind.
- **The third host in the allowlist.** Without `infer.murakumo.cloud`,
  `admit-model` refuses the resolution and the inference leg has no admitted
  endpoint to ask. That refusal is ADR-0042's re-check working, and it is one
  line in a policy file that says so.

## What the alias actually says, and a drift worth recording

Measured four times on 2026-08-21 between 13:30 and 13:53 UTC, and again on
2026-08-22, with headers and
`content-length: 497`, `GET https://api.murakumo.cloud/infer/models/murakumo-main`
returns an object that **does** carry an `endpoint` key, naming
`https://infer.murakumo.cloud/v1/chat/completions`. Two things follow.

**The endpoint is a URL, not an origin.** `plan-inference` used to append
`/v1/messages` unconditionally, which against this value would have produced
`…/v1/chat/completions/v1/messages` — an address the authority never named. It
now appends only to a bare origin and records
`:aiueos.cloud/endpoint-carries-path?` either way. The URL still goes through
the same allowlist and transport check.

**The endpoint names a third host.** ADR-0041 names two authorities; the alias
resolves onto `infer.murakumo.cloud`. With an allowlist of the two,
`admit-model` refuses with `:resolved-endpoint-not-allowed` — which is ADR-0042's
re-check doing precisely what it was built for, on its first live contact. The
shipped policy admits the third host **with its own measured pin**, and says in
the file that deleting the entry makes the leg refuse. That is an operator
decision recorded where operators look, not a resolver being allowed to make it.

**The endpoint answers without a credential, and that is what made the leg
measurable.** `POST https://infer.murakumo.cloud/v1/chat/completions` with no
credential answers 200 with a completion; `POST
https://api.murakumo.cloud/v1/messages` answers 401. Both measured 2026-08-22.

The gate first skipped the POST unless a credential was set, on the reasoning
that a 401 obtained without one says nothing about the mechanism. That reasoning
was fine and the rule built on it was not, because it made the leg
**unfalsifiable**: on an endpoint that needs no credential, declining to ask
produces the same UNMEASURED whether the authority is healthy, broken or gone.
So the credential is now *attached when present* and never required. A 200 with
a completion is an admit; a 401 — with or without a token — is a refusal that
takes the exit code with it; only a request that could not complete is
unmeasured. The receipt carries `:credential :present`/`:absent` so a 401 reads
as what it is.

**An earlier reading of this entry said it had no `endpoint` key.** It did have
one; the reading came from a body truncated at 300 bytes, and the key sits past
the cut. Recorded because the failure is this workspace's recurring one — a
measurement that could not see the answer returning the same shape as one that
looked and found nothing — and because it is the reason the four timed
re-measurements above exist rather than a single confirming one.

The decision layer is built for the key's absence anyway: a resolution with no
endpoint is `:alias-unresolved`, full stop, unless
`:aiueos.cloud/endpoint-from-origin?` is turned on in policy — it is off in the
shipped file — in which case the admission records
`:endpoint-source :configured-origin` so the receipt says which of the two
happened. **A machine authorised by an omission has not been authorised.**

## Executable evidence

Two repositories, both green.

**`kotoba-lang/grant`** — `kbb -M:test`: **324 tests, 1056 assertions, 0
failures**, against a baseline at `7ed742b` of **291 / 918 / 0**. The 33 new
tests are `grant.json-test` and the decision additions to `grant.cloud-test`.

**`kotoba-lang/aiueos`** — `kbb -M:test`: **396 tests, 8694 assertions, 0 failures**, against a baseline
at `25744d5` of **371 / 8580 / 0**. `kbb -M:test-fleet`: **393 tests, 1246 assertions, 0 failures** (baseline 368 / 1132 / 0).
`kbb -M:tcb-check`: `{:valid? true :classpath-scope :measured :files 21
:external 6 :classpath 9 :properties 6}`. `kbb -M:lint`: **0 errors, 56 warnings — the same 56 as the baseline**.

ADR-0065 recorded the suite as 635 tests with 12 expected failures. That is
stale in both directions: the twelve upstream-blocked failures ADR-0050 owned
are gone (amu#625 and #626 were answered on 2026-08-20), and nineteen files left
for `grant` on 2026-08-21 taking their tests with them.

New offline coverage, against a real `com.sun.net.httpserver` on loopback or
against pure functions:

- **`grant.json-test`** — 16 tests. Every hazard the namespace claims to refuse,
  refused, including the live alias entry parsed from the bytes the authority
  actually sent rather than from a fixture written out of the docstring.
- **`grant.cloud-test`** — the three inference outcomes plus the two the
  declared shape adds, the three write refusals, the endpoint-with-a-path plan,
  and the endpointless resolution that does not quietly become the origin.
  `each-reader-reads-only-its-own-shape` feeds each reader the *other* shape's
  body and requires `:response-shape-mismatch` both ways — the assertion one
  lenient reader could not make.
- **`aiueos.provider.cloud-test`** — grows from 11 to 26 tests. The server
  records the method, path, body and headers it received, so "the plan said
  `:post`" is checked against **what arrived**, not against the client's own
  record of what it meant to send. A `PUT` carries the caller's bytes verbatim.
  An injected credential arrives; without one, none is sent. Bytes that do not
  hash to the CID produce **zero server hits**. A policy that declares the
  endpoint's shape is obeyed all the way through the provider.
- **`aiueos.cloud-live-test`** — 11 tests, no network. The exit-code rule as a
  pure function, including that a refusal beats a skip and that an empty leg
  list is 3. The shipped policy is loaded and checked: every pin is 64 lowercase
  hex with a note saying which host and when, `:endpoint-from-origin?` is off,
  the three CIDs decode, the write CID really is the digest of the bytes the
  gate would send, and the three deployment values that each faked a failure are
  each above the value that faked it.

### Both directions, at the gate — and one real defect it caught

Two mutations of the live policy, one hex digit each, nothing else changed.

**Breaking `kotobase.net`'s pin** (`…473e` → `…473f`) moved the gate from exit
**0 to 1**. Exactly the two kotobase legs became `REFUSED :peer-not-pinned`
with the observed key printed beside them; the three murakumo legs stayed
`ADMITTED`, inference included, with a fresh completion. Restoring the digit
restored exit 0.

**Breaking `infer.murakumo.cloud`'s pin** was supposed to be the same
demonstration for the new leg. It was not: the gate reported
`UNMEASURED :response-unmeasured (fault :peer-not-pinned)` and exited **3**.

That is the defect this repository keeps writing ADRs about, in the code written
to prevent it. `outcome-of` consulted the deny *reason* before the fault, and a
rejected pin produces both: the handshake fails, so `grant.cloud` never sees a
status and says `:response-unmeasured`, while the provider knows perfectly well
the peer was refused. The storage legs classified correctly only because
`read-block!` short-circuits on a fault and returns the peer verdict directly —
so the rule was wrong and three of five legs hid it.

The unit test that was supposed to cover this
(`a-rejected-pin-is-a-refusal-even-though-it-arrives-as-a-fault`) passed
throughout, because it constructed a verdict carrying reason
`:peer-not-pinned` — the shape the storage path produces, not the shape the
inference path produces. **A test written from the docstring instead of from
the wire.**

Fixed by making the fault decisive whenever there is one, which is what that
function's own docstring already claimed. With the fix, breaking the inference
pin gives `REFUSED` and exit **1**; the receipt line now leads with the fault,
because `REFUSED :response-unmeasured` contradicts its own first word. Both the
new verdict shape and the line format are asserted.

### Both directions, at the unit level

Two mutations, each producing exactly the failure it should and no other:

- putting `.GET` back where `:put` dispatches — the defect ADR-0041's row 7
  describes — fails **only** `a-block-write-arrives-as-a-put-carrying-the-bytes`,
  on the two assertions that read the server's record of the method and the
  body. Every other test in that namespace stays green, which is the point: a
  write performed as a read looks like a success from the client's side;
- carrying the request headers onto the verdict fails **only**
  `a-credential-does-not-travel-onto-the-verdict`. Without that mutation the
  assertion could have been vacuous, since nothing puts headers there today;
  with it, the test is shown to be load-bearing.

Two more tests are non-vacuous by construction:
`a-method-the-provider-has-no-verb-for-is-a-fault-not-a-get` and
`bytes-that-do-not-hash-to-the-cid-never-reach-the-socket` both assert an
**empty hit list** on a server that would have answered 200, so each fails if
the refusal moves to after the socket instead of before it.

## What the split did to the TCB record

`src/aiueos/cloud_live.cljk` is pinned as `:remote-authority-live-gate` because
it carries the accept-any-peer trust manager `pin` needs, and a change that let
`check` reach that code would remove the pinning `grant.cloud/admit-peer`
exists for. That takes this inventory from 20 file entries to 21, asserted
rather than derived, because an inventory that can grow unnoticed is the record
ADR-0016 called "not evidence".

`grant.json` is trusted code and is **not** in this inventory, which is correct
and worth stating: it is in `kotoba-lang/grant`, and the way this repository
records that is the pinned `io.github.kotoba-lang/grant` SHA under
`:tcb/external` — the same mechanism the nineteen files that left on 2026-08-21
are recorded by. Advancing that pin is a review action here.
`resources/aiueos/cloud_live.edn` is deliberately unpinned: it is deployment
configuration, it is meant to change, and every key in it carries the date and
method it was measured by.

The gate is `.cljc` rather than `.clj` because ADR-2608201300 forbids new
production `.clj`, and the split it forced is an improvement: the decision rule
— what counts as admitted, refused or unanswerable, and which exit code follows
— sits in the open and is tested without a socket, while the sockets and the
`System/exit` are behind one `#?(:clj …)`.

## Remaining boundary

- **Steps 1–5 are exactly where ADR-0041 left them.** This is the hosted
  profile, the same split ADR-0019 made between boot authority and workload
  authority. The bare-metal profile has reached nothing.
- **One of two inference surfaces is exercised.** The completion came from
  `infer.murakumo.cloud`, which needs no credential. `api.murakumo.cloud/v1/messages`
  answers 401 and no token for it is reachable here, so the Anthropic-shaped
  reader is proved on loopback only. `admit-inference` handles both; only one
  has been asked.
- **The receipt records the completion's length, not its text.** Four
  characters and `finish_reason: "stop"` is evidence that something arrived and
  was judged; it is not evidence about *what* the model said, and nothing here
  checks that.
- **Streaming is refused by name, and still not implemented.** ADR-0075 gave it
  `:response-streaming-unsupported` rather than letting an SSE response arrive
  as a shape mismatch or an unparsable body, so a reader can tell "we do not do
  this yet" from "the server sent us something wrong". No murakumo surface has
  been asked to stream and this plane never sets `stream: true`.
- **The live write has never succeeded.** 401, for want of a bearer token.
- **The pin set is host-bound** (ADR-0075). `grant.cloud/admit-peer` takes the
  host the provider was reaching, and offering one authority's key for another
  is `:peer-pinned-to-other-host`. The flat set survives as the shape a
  release-borne anchor document produces, is marked `:unbound` on every
  verdict, and is refused outright where the deployment sets
  `:aiueos.cloud/require-host-bound-anchors?` — which the live policy does.
  What has *not* changed: the ADR-0045 anchor document still has no host field,
  so a device booted from one holds an unbound set.
- **The live policy borrows `grant.anchors`' rotation rule, not its
  distribution** (ADR-0075). Each host may carry `:previous` pins and an
  `:accept-previous-until-ms`, evaluated by `grant.anchors/usable-anchors` — so
  a Cloudflare rotation is an overlap window that the clock closes, and a
  retired key is `:peer-pin-expired` rather than an unexplained
  `:peer-not-pinned`. It is still not the signed, sequenced distribution of
  ADR-0045/0046: an operator measures with `pin` and edits the file, because
  there is no publisher and no root key on the path this gate runs on.
- **A transient upstream 5xx is `:response-upstream-fault`** (ADR-0075), which
  the gate reports as UNMEASURED and exit 3. A 429 is still a refusal,
  deliberately: it is the authority answering about this caller's behaviour.
- **The contract's file paths are checked, in two halves** (ADR-0075).
  `aiueos.cloud-contract-paths-test` checks the paths it names in this
  repository; `grant.cloud-test` checks the ones in `grant`. Neither test can
  see the other's tree, which is why there are two.

The next thing is a credential for the gated surface. Everything under it is
built.
