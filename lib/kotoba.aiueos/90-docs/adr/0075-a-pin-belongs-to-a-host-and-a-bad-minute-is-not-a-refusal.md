# ADR-0075 — A pin belongs to a host, and a bad minute is not a refusal

Date: 2026-08-22

## Status

Accepted and executable **for the hosted profile**. Five things ADR-0073 listed
as still open are closed, and each one is exercised in both directions:

- the pin set is **bound to hosts**, so offering one authority's key for
  another is refused as `:peer-pinned-to-other-host` rather than admitted;
- the live policy expresses a rotation in `grant.anchors`' vocabulary — a
  per-host overlap window that the clock closes — instead of being one line
  somebody replaces;
- a transient upstream **5xx is `:response-upstream-fault`** and exits **3**,
  not 1, so the gate's could-not-answer code covers the case it was invented
  for;
- a **streamed** answer is `:response-streaming-unsupported`, named as the gap
  it is rather than reported as a malformed document;
- the contract's cross-repository **file paths are checked**, in both
  repositories, by two tests that each check the half they can see.

`kbb -M:cloud-live check` still exits **0** against the live
`kotobase.net`, `api.murakumo.cloud` and `infer.murakumo.cloud`, with a real
completion on the inference leg. The receipt now says which host each accepted
key was accepted *for*.

Not executable, and stated here rather than at the end:

- **The bare-metal profile is untouched.** ADR-0041's gap-ledger steps 1–5 are
  exactly where they were. Nothing in `os/aiueos/` changed.
- **Streaming is refused, not implemented.** Nothing here reads an
  `event-stream`; the change is that the refusal has a name.
- **This is not the signed anchor distribution of ADR-0045/0046.** What was
  borrowed is the overlap rule, not the publisher. A person still measures the
  new key and edits the file.
- **The anchor *document* still has no host field**, so a device booted from a
  release-borne set holds an unbound pin set. That is an OTA-plane change to a
  signed encoding and it has not been made.
- **The credentialed inference surface is still unmeasured**, and the live
  write still answers 401. Both unchanged from ADR-0073.

## Context

ADR-0073 ended with a list of things that were weaker than they read. Five of
them share a shape: the code produced the *same output* for two events that a
person would act on differently. That is the defect root ADR-2608136000 names,
and the reason it keeps appearing is that it is invisible from the inside —
each of these looked correct in isolation.

**`admit-peer` asked half a question.** It checked whether the measured key was
in the pin set. With two hosts that was nearly the right question; with three
it stopped being one. Any pinned key was accepted from any allowed host, so an
attacker able to answer for `infer.murakumo.cloud` could answer for
`kotobase.net` and the receipt would print `ADMITTED` beside the key it
expected to see. The mapping from key to host did exist — in an
`:aiueos.cloud-live/anchor-notes` map, which **nothing read**. A comment is not
a check, and a comment in an EDN file that the loader ignores is a comment.

**The pins were going to rotate and nothing said what to do.** All three hosts
are Cloudflare-fronted, so the leaf key is the edge's. `grant.anchors` had
already worked out the hard part in ADR-0045 — an ordinary rotation must
overlap, because a client that accepts exactly one key while the authority is
serving two goes red on a healthy authority — and the live policy was not
connected to any of it.

**A 503 and a digest mismatch exited the same code.** The gate has three exit
codes and the whole point of the third is that a check which could not run must
not return the value of one that ran clean. A transient 5xx is the purest case
of "could not answer" there is, and it was taking exit 1. ADR-0073 recorded
this as "defensible", which it was, and as a live event, which it also was: an
edge 5xx fired once during that day's testing and was reported identically to
bytes that did not match their CID.

**A stream had no name.** `admit-inference` parses the body as JSON, so an SSE
response would come back `:body-unparsable` — a refusal that says the authority
sent garbage, when what happened is that this client does not implement what it
was sent.

**And the contract made a claim across a repository boundary that nothing
checked.** `resources/aiueos/cloud_contract.edn` lives in `kotoba-lang/grant`
and names `src/aiueos/provider/cloud.cljk`, `src/aiueos/cloud_live.cljk` and
`resources/aiueos/cloud_live.edn`. Naming them is right — a contract that
stopped naming its own mechanism the day the mechanism moved would describe
half a story — but a rename here broke a sentence there in silence.

## Decision

### A pin is a pin *for a host*

`:aiueos.cloud/trust-anchors` is now a map from host to what this policy will
accept from that host:

```clojure
{"kotobase.net"         {:pins #{"5060…"} :measured "2026-08-21"}
 "api.murakumo.cloud"   {:pins #{"ec7f…"} :measured "2026-08-21"}
 "infer.murakumo.cloud" {:pins #{"014b…"} :measured "2026-08-21"}}
```

`admit-peer` takes `{:spki-sha256 … :host …}`, and the host comes from the URL
the plan named — carried into the trust manager by
`aiueos.provider.cloud`, which builds one client per request. That makes
"redirects are never followed" load-bearing twice over: a followed redirect
would reach a host other than the one the client was built to judge.

The refusals are split so that each names one fix:

| reason | what happened |
|---|---|
| `:no-trust-anchors` | nothing declared. Not permission |
| `:anchor-binding-malformed` | a declared pin cannot be a SHA-256 |
| `:trust-anchors-unbound` | a flat set where the deployment requires hosts |
| `:peer-unmeasured` | the provider reported no key |
| `:peer-host-unknown` | the caller did not say which host it reached |
| `:host-not-pinned` | no pins for that host at all |
| `:peer-pin-expired` | this host's own retired key, after the window closed |
| `:peer-pin-window-unevaluated` | the same key, with no clock to judge by |
| `:peer-pinned-to-other-host` | the key is pinned — for somebody else |
| `:peer-not-pinned` | a key nothing in this policy names |

Only the last two are an attack shape. `:peer-pin-expired` is a *schedule*, and
telling it apart from `:peer-pinned-to-other-host` matters because the first
sends an operator to a calendar and the second sends them to an incident.

`:peer-pin-window-unevaluated` exists for the same reason the third exit code
does. If the clock is missing, the window cannot be evaluated; the retiring key
is refused, which is the safe direction, but reporting that as
`:peer-pin-expired` would claim a measurement nobody made.

### The flat set is kept, and made impossible to hold by accident

The obvious move is to refuse the flat set outright. It is wrong, for a reason
outside this namespace: the release-borne anchor document (ADR-0045/0046)
carries a device-wide pin list with **no host field**, and a device that boots
from one has no other way to hold pins. Refusing it would strand exactly the
machines the anchors plane exists for.

So it is accepted, and it is not silent about it:

- every verdict from an unbound set carries
  `:aiueos.cloud/anchor-binding :unbound`, which the provider carries onto the
  result and the gate prints in the receipt's `:measured` map. An unbound
  acceptance is visible on the line of every leg;
- `:aiueos.cloud/require-host-bound-anchors?` makes it a refusal, and
  **the shipped live policy sets it**. That file cannot regress to the weaker
  shape by an edit nobody noticed;
- `grant.cloud/trust-anchors` still exists and still returns every pin flat —
  documented as a *reporting* view, for counting and for checking they are all
  well-formed. It is the question that let one host's key work for another, and
  `admit-peer` no longer asks it.

### A rotation is a window, and the window is `grant.anchors`'

Each host binding may carry `:previous` pins and an
`:accept-previous-until-ms`. Which keys work right now is answered by
`grant.anchors/usable-anchors` — the same function the release-borne plane
uses. There is one implementation of the overlap rule, because two would
eventually disagree and the disagreement would be invisible until a rotation.

`grant.cloud` is pure and cannot read a clock, so the window is evaluated
against `:aiueos.cloud/now-ms`, which `aiueos.cloud-live/with-clock` stamps
**once per run**. Once matters: a run that straddled an expiry would otherwise
report two different answers about one policy and blame the authority for one
of them.

**What a person does when the Cloudflare edge rotates**, which is the question
ADR-0073 left unanswered:

1. `kbb -M:cloud-live pin https://<host>` measures the new key and prints
   `MEASURED, NOT TRUSTED`. It writes nothing — deciding to trust a key is a
   person's act, and a tool must not make it.
2. In `resources/aiueos/cloud_live.edn`, move that host's `:pins` into
   `:previous`, put the measured key in `:pins`, and set
   `:accept-previous-until-ms`.
3. Nothing else. During the window both keys are admitted and the receipt says
   `:window :open`; after it, the old key is `:peer-pin-expired`. The clock
   retires it, not a second edit.

The window is the point rather than a nicety. A Cloudflare edge mid-rotation
serves the old key from some POPs and the new one from others, so a client
pinned to exactly one of them fails intermittently against a healthy authority
— and intermittent pin failures are the single most expensive kind of false
alarm this gate could produce.

**This is deliberately *not* the signed, sequenced distribution of
ADR-0045/0046**, and saying why is the honest half of the decision. That path
admits a set through `grant.publisher`: root keys, a threshold of signatures, a
sequence, a revocation bitmap, a release that carries the document. An operator
workstation running this gate has none of those, and there is no publisher on
this path — **the file is the trusted channel**, which is exactly the situation
the release-borne path exists to escape *for devices that receive anchors over
a network they cannot yet judge*. Wiring `admit-set` in here would have meant
fabricating a state map and a signature list to satisfy a check whose premises
are absent: a gate that looks like it verifies a signed document and does not.
What the anchors plane genuinely has to lend is its rotation vocabulary and its
overlap rule, and that is what was taken.

### A bad minute at the authority is not a refusal

`grant.cloud/upstream-fault-status?` is 5xx, all of it — which covers
Cloudflare's own 520–527 origin errors, the most literal possible form of
"the edge could not reach the origin". Every admission routes its non-success
status through one function, so a new request kind cannot classify 503
differently from the one beside it.

`grant.cloud/unmeasurable-reasons` names the two refusals that mean nobody has
been shown to be wrong: `:response-unmeasured` and `:response-upstream-fault`.
The **gate reads that set** rather than keeping a list beside it. Two lists
would have drifted, and the way they drift is that the gate keeps calling a 503
a refusal — the bug being fixed, re-introduced by the fix.

**429 is deliberately still a refusal.** It is retryable, and it is the
authority answering about *this caller's* behaviour, which is a fact about this
machine rather than about the weather. A gate that shrugged at rate limiting
would hide a misconfigured loop behind the exit code for a network outage.
Nothing retries anything: the classification says what happened, and whether to
ask again is the caller's decision.

### A stream is a gap, and gaps get names

`:response-streaming-unsupported`, decided by the content type when the
provider reported one and by the body's own framing when it did not — an SSE
payload begins with an `event:`, `data:`, `id:` or `retry:` field, and a JSON
document cannot. The sniff is written as a fallback because a server that
streams without saying so is precisely the case where the header cannot be
relied on.

`aiueos.provider.cloud` now reports `:content-type` and, as ever, judges
nothing by it: `grant.cloud` decides what `text/event-stream` means. No parser
was written. `stream: true` is still never sent.

### The contract's paths are checked twice, because neither test can do it once

`aiueos.cloud-contract-paths-test` reads the contract off the classpath, walks
the whole document for strings matching `kotoba-lang/aiueos: <path>` — so a
claim added to a field nobody thought of is checked the day it is written — and
requires each path to exist. `grant.cloud-test` does the same for
`:aiueos.cloud/source-files`, which names `src/grant/*`.

Three ways that test could have gone green without checking anything, each
turned into a failure: the contract not being on the classpath, the test being
run from somewhere that is not the repository root, and the contract naming no
files here at all (an evidence floor of three). While writing it, the same
smell turned up one field over — the contract *declares* a set of deny reasons
and nothing compared it to the ones the code produces — so that is asserted
too, in `grant`.

## What the live run measured

Verbatim, `kbb -M:cloud-live check`, 2026-08-22, exit **0**:

```
LEG model-resolve       ADMITTED    {:alias "murakumo-main", :alias-for "qwen3.8-27b", :anchor-binding :host, :byte-count 497, :endpoint "https://infer.murakumo.cloud/v1/chat/completions", :endpoint-source :resolved, :host "api.murakumo.cloud", :peer-spki "ec7f258fc32457d84295f081a479910ee9b5250d34158fcf3c92eafb9dbd1af1", :status 200}
LEG inference-liveness  ADMITTED    {:anchor-binding :host, :byte-count 582, :host "api.murakumo.cloud", :live? true, :path "/ready", :peer-spki "ec7f258fc32457d84295f081a479910ee9b5250d34158fcf3c92eafb9dbd1af1", :status 200}
LEG inference           ADMITTED    {:anchor-binding :host, :byte-count 817, :completion-chars 4, :credential :absent, :credential-env "AIUEOS_MURAKUMO_TOKEN", :host "infer.murakumo.cloud", :peer-spki "014bccd86fa34b2a9dbc410b5d27e60e46fb938cc9c9b77058c567cc4b997038", :response-shape :chat-completions-v1, :status 200, :stop-reason "stop"}
LEG storage-read        ADMITTED    {:anchor-binding :host, :byte-count 0, :cid "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku", :digest "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", :host "kotobase.net", :peer-spki "50602ad366823fcf5274a7c917baa4fd24b9de4fd15635ff501177c83d05473e", :status 200}
LEG storage-absent      ADMITTED    {:anchor-binding :host, :byte-count 10, :cid "bafkreicjlihajri6k5g4n66xvq3xsffb45qddog7q2wpolck5kddammoey", :expected-reason :response-not-ok, :expected-status 404, :host "kotobase.net", :peer-spki "50602ad366823fcf5274a7c917baa4fd24b9de4fd15635ff501177c83d05473e", :refusal-reason :response-not-ok, :status 404}

exit 0
```

Five legs, five admissions, a real completion with `stop_reason "stop"` — and
every line now carries `:anchor-binding :host` and the host it was reached at.
That is the difference this ADR is about, said on the line a person reads: the
key was accepted **for that host**, not merely found in a set.

The receipt's header says what the policy will accept from whom:

```clojure
:trust-anchors
{:shape :host-bound,
 :pins 3,
 :hosts
 {"api.murakumo.cloud"   {:pins 1, :retiring 0, :usable-now 1, :window :none},
  "infer.murakumo.cloud" {:pins 1, :retiring 0, :usable-now 1, :window :none},
  "kotobase.net"         {:pins 1, :retiring 0, :usable-now 1, :window :none}}}
```

`:window :none` on every host is the statement that no rotation is in progress.
It matters that this is printed on a **green** run: an `:open` window is the
only warning that a key is still working because a deadline has not passed yet,
and a receipt that only mentioned windows when something failed would say it
too late.

## Executable evidence

**`kotoba-lang/grant`** — `kbb -M:test`: **340 tests, 1156 assertions, 0
failures**, against a baseline at `a8ed303` of **324 / 1056 / 0**.

**`kotoba-lang/aiueos`** — `kbb -M:test`: **414 tests, 8785 assertions, 0
failures**, against a baseline at `5e8df52` of **396 / 8694 / 0**.
`kbb -M:test-fleet`: **411 tests, 1337 assertions, 0 failures** (baseline
393 / 1246 / 0). `kbb -M:tcb-check`:
`{:valid? true :classpath-scope :measured :files 21 :external 6 :classpath 9
:properties 6}`. `kbb -M:lint`: **0 errors, 56 warnings — the same 56 as
the baseline**.

The TCB inventory is unchanged at 21 files: nothing new was added to the
trusted set, and `resources/aiueos/cloud_live.edn` stays deliberately unpinned
because it is deployment configuration that is meant to change.

New offline coverage, against a real `com.sun.net.httpserver` on loopback, a
real TLS handshake against a certificate the test generates, or pure functions:

- **`grant.cloud-test`** — the eight peer refusals as separate assertions,
  including a key pinned to another host and a host with no pins; the flat set
  accepted, marked, and refused under
  `:aiueos.cloud/require-host-bound-anchors?`; a rotation admitted during its
  window and `:peer-pin-expired` after it; `:peer-pin-window-unevaluated` for
  both ways a window cannot be evaluated; the 5xx range and the statuses
  deliberately outside it; a real SSE body refused by content type and by
  framing.
- **`grant.anchors-test`** — the release-borne set still reaching
  `grant.cloud` as an unbound policy, and a host-bound policy getting the *same
  set* out of `usable-anchors` that the flat path does. One overlap rule, seen
  from both sides.
- **`aiueos.provider.cloud-tls-test`** — the host binding over a real
  handshake. The server's own key, pinned to another host, is refused
  mid-handshake with **zero server hits**; the retiring key still serves inside
  the window and is `:peer-pin-expired` outside it.
- **`aiueos.provider.cloud-test`** — a streamed answer refused by name with the
  status still reported; a JSON answer with a content type still read; genuinely
  unreadable bytes still `:body-unparsable`; 503 and 502 classified apart from
  401 off the same socket.
- **`aiueos.cloud-live-test`** — the shipped policy is host-bound, the
  allowlist and the pin map name the same three hosts in both directions, and
  the receipt's anchor summary reports an open window, a closed one and an
  unevaluated one as three different things.

### Both directions

Each mutation was made on its own, the reported reason was checked against the
injected fault, and the mutation was reverted.

**The pin bound to the wrong host, live.** `--policy` with the `kotobase.net`
and `api.murakumo.cloud` entries' keys **swapped**, nothing else changed:

```
LEG model-resolve       REFUSED     :peer-pinned-to-other-host (decision :response-unmeasured)
LEG inference-liveness  REFUSED     :peer-pinned-to-other-host (decision :response-unmeasured)
LEG inference           UNMEASURED  the alias did not resolve, so there was no admitted endpoint to ask
LEG storage-read        REFUSED     :peer-pinned-to-other-host
LEG storage-absent      REFUSED     :peer-pinned-to-other-host

exit 1
```

and, from the EDN below the lines, the two facts that make it actionable:

```clojure
{:leg :model-resolve, :outcome :refused,
 :measured {:host "api.murakumo.cloud",
            :observed-spki "ec7f258f…1af1",
            :pinned-for ["kotobase.net"]}, …}
{:leg :storage-read, :outcome :refused,
 :measured {:host "kotobase.net",
            :observed-spki "50602ad3…473e",
            :pinned-for ["api.murakumo.cloud"]}, …}
```

The reported reason is `:peer-pinned-to-other-host` — the fault that was
injected, not a neighbouring one — and each refusal names the host the policy
thinks that key belongs to. **Under ADR-0073's flat set this same policy would
have exited 0**, because both keys were in the set. Restoring the file restored
exit 0.

**A pin that is simply wrong, live.** One hex digit of `kotobase.net`'s pin,
as in ADR-0073: 

```
LEG model-resolve       ADMITTED    {:alias "murakumo-main", :alias-for "qwen3.8-27b", :anchor-binding :host, :byte-count 497, :endpoint "https://infer.murakumo.cloud/v1/chat/completions", :endpoint-source :resolved, :host "api.murakumo.cloud", :peer-spki "ec7f258fc32457d84295f081a479910ee9b5250d34158fcf3c92eafb9dbd1af1", :status 200}
LEG inference-liveness  ADMITTED    {:anchor-binding :host, :byte-count 582, :host "api.murakumo.cloud", :live? true, :path "/ready", :peer-spki "ec7f258fc32457d84295f081a479910ee9b5250d34158fcf3c92eafb9dbd1af1", :status 200}
LEG inference           ADMITTED    {:anchor-binding :host, :byte-count 1317, :completion-chars 4, :credential :absent, :credential-env "AIUEOS_MURAKUMO_TOKEN", :host "infer.murakumo.cloud", :peer-spki "014bccd86fa34b2a9dbc410b5d27e60e46fb938cc9c9b77058c567cc4b997038", :response-shape :chat-completions-v1, :status 200, :stop-reason "stop"}
LEG storage-read        REFUSED     :peer-not-pinned
LEG storage-absent      REFUSED     :peer-not-pinned

exit 1
```

Exactly the two kotobase legs go red with `:peer-not-pinned` — **not**
`:peer-pinned-to-other-host`, because that key is now in no host's set — and
the three murakumo legs stay green, inference included, with a fresh
completion. Restoring the digit restored exit 0.

**The unbound shape, live.** The same three pins as a flat set, with
`:aiueos.cloud/require-host-bound-anchors?` left true:


```
LEG model-resolve       REFUSED     :trust-anchors-unbound (decision :response-unmeasured)
LEG inference-liveness  REFUSED     :trust-anchors-unbound (decision :response-unmeasured)
LEG inference           UNMEASURED  the alias did not resolve, so there was no admitted endpoint to ask
LEG storage-read        REFUSED     :trust-anchors-unbound
LEG storage-absent      REFUSED     :trust-anchors-unbound

exit 1
```

The same three keys that pass when they are bound to their hosts. The inference
leg is `UNMEASURED` because the alias never resolved, which is the honest
report: there was no admitted endpoint to ask.

**A transient 5xx.** `status-refusal` was reverted to return `:response-not-ok`
for every status, and both suites were run:

- `grant` — **5 failing assertions in 4 tests**, and every one of them is a 5xx
  assertion: `liveness-asks-the-smallest-question`,
  `a-resolver-that-could-not-be-measured-is-not-an-unresolved-alias`,
  `the-three-write-refusals-are-kept-apart`, and both halves of
  `a-block-read-tells-a-bad-minute-apart-from-a-bad-answer`. The assertions
  beside them that check 401, 404, 405 and 429 all stayed green, which is how
  the change is shown to be about 5xx rather than about status handling in
  general;
- `aiueos` — **4 failing assertions in 2 tests**, both about upstream faults off
  a real socket: `a-transient-server-fault-is-classified-apart-from-a-refusal`
  and the 502 half of `liveness-is-a-get-and-says-nothing-about-completions`.

**And one test that should have failed and did not.**
`a-bad-minute-at-the-authority-is-not-the-same-event-as-bad-bytes` stayed green
through the mutation, because it constructs verdict maps carrying
`:response-upstream-fault` rather than obtaining them from a socket — so it
checks that `outcome-of` classifies the reason correctly, which is true no
matter what produces the reason. That is ADR-0073's lesson repeating in the
work written after it: **a test written from the docstring passes when the wire
changes.** It is kept, because the classification rule is worth asserting on
its own; the assertion that would have caught the revert is the one in
`aiueos.provider.cloud-test` that gets its 503 from a server.

**The contract path check.** `src/aiueos/cloud_live.cljk` was moved out of the
tree and the namespace was run: **one failure**,
`every-file-the-contract-names-in-this-repository-exists`, on the assertion
that reads that path, with the message
`resources/aiueos/cloud_contract.edn (in kotoba-lang/grant) claims this
repository has src/aiueos/cloud_live.cljk and it does not`. The premise test
beside it stayed green, which is right — the contract was still reachable and
the working directory was still the repository root. Moving the file back
restored exit 0.

`a-path-that-does-not-exist-is-what-this-test-fails-on` covers the other
direction without touching the tree: it feeds `named-paths` a document naming
one real file and one that does not, and asserts that the extraction finds both
— nested and top-level — and ignores the `kotoba-lang/grant` entry beside them.

**And one that had to be broken in the right way.** The first attempt at the
cross-host demonstration bound the server's key to `kotobase.net` and gave
`127.0.0.1` no pins at all. It went red — with `:host-not-pinned`, not
`:peer-pinned-to-other-host`. A red run caused by a different fault than the
one being injected is not a demonstration, and the fix was to the *test*: pin
both hosts, each to the other's key, which is the shape the live policy has
when two entries are swapped.

## A defect the receipt showed, which no test was asking about

The first run of the swapped-pin demonstration went red for the right reason
and printed this:

```clojure
{:leg :model-resolve, :outcome :refused, :measured {},
 :reason :response-unmeasured, :fault :peer-pinned-to-other-host}
```

`:measured {}`. The storage legs of the same receipt named the key they refused
and the host it was pinned to; the murakumo legs said nothing at all. Same
refusal, same policy, same run — one of them actionable and the other only
correct.

The cause is a seam that had no reason to be symmetric and needed to be:
`read-block!` short-circuits on a fault and returns the peer verdict map whole,
so `:aiueos.cloud/observed-spki` and `:aiueos.cloud/pinned-for` survive; the
other three legs go through `judged`, which hands the arrived map to an
admission and keeps only what the admission returns — a fresh deny map that
never saw the peer verdict. `aiueos.cloud-live/observations` was reading
`:aiueos.cloud/observed-spki` all along, with a comment saying *a refusal that
will not say what it saw cannot be acted on*. It was right, and on three legs
out of five it was reading a key that was never put there.

`judged` now carries the peer verdict's observations onto the verdict, and
`a-refused-peer-names-the-key-it-saw-on-every-leg-not-only-the-storage-ones`
asserts it over a real handshake. The rerun prints
`:pinned-for ["kotobase.net"]` on the resolve leg and
`:pinned-for ["api.murakumo.cloud"]` on the storage leg — each naming the host
whose key it was actually offered.

Worth recording for how it was found: not by a failing test, and not by
reading the code. By running the demonstration and **reading the output it
produced** rather than only its first line. The exit code was right, the leg
lines were right, and the map underneath them was empty.

## Consequences, and the remaining boundary

- **A device booted from a release-borne anchor set holds an unbound pin set.**
  It is accepted, marked on every verdict, and weaker than what the live policy
  holds. Making the ADR-0045 anchor document host-aware is a change to a signed
  encoding and to the OTA plane, and is the natural next piece of this.
- **The rotation is operator-driven.** A person measures, edits and sets a
  deadline. Nothing watches for an edge that rotated early, and a window that
  is too short produces `:peer-pin-expired` — which is at least a sentence
  naming its own fix.
- **Nothing retries.** A 5xx is classified, not re-requested. A gate that
  retried would be a different tool, and the exit code would stop meaning what
  it says.
- **`:peer-host-unknown` is reachable only by a caller that omits the host.**
  The provider always supplies it, so this is a guard against a future caller,
  and it is refused rather than defaulted.
- **Streaming is still not implemented.** The refusal names the gap. If a
  murakumo surface ever streams by default, this gate goes red for a reason a
  person can act on, which is the most that can be claimed for it.
- **The credentialed surface is still unmeasured and the live write still
  answers 401.** Unchanged from ADR-0073, and still the next thing.
- **Two hosts' keys being swapped is now detectable; a single host's key being
  replaced by an attacker who can also mint it is not.** Pinning bounds who can
  answer, not who can be compromised.
