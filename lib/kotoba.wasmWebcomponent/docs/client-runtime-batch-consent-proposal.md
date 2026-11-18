# Bounded batch consent: a design proposal (not implemented)

Status: **proposal**, 2026-11-18. Nothing in `src/kotoba-client-runtime.js` changes with this
document. Points that would change the shared architecture contract are marked
**Owner decision pending**.

Tracking: [AWAI-3276](https://linear.app/kotobalabs/issue/AWAI-3276) (design unit
[AWAI-3451](https://linear.app/kotobalabs/issue/AWAI-3451)). It was found in Nagare ADR 0001
(`network-awai/app-itonami-nagare` `docs/adr/0001-distribution.md`).

Written against `src/kotoba-client-runtime.js` at `09f0b0b` (1,253 lines, sha256 `9c875d77…`).

## Problem

Today every request is one operation and one consent. That works for a post or a single read. It
does not work for two common cases:

- **A large upload is several requests.**
  - The broker snapshots a body before consent and refuses one over 16 MiB (`boundedBytes(…,
    16777216, …)`). Yataverse's CAR import also caps a request at 32 MiB and 256 blocks.
  - So a 100 MiB video is at least 7 requests, and today that means 7 consent dialogs.
  - Nagare now refuses videos over 16 MiB − 64 KiB for this reason.
- **A feed reads many things.**
  - Opening a feed of 20 public videos is 20 reads and 20 dialogs.
  - People learn to press Allow without reading, which defeats the dialog.

Products must not solve this themselves (for example with a remembered approval). The contract
forbids app code minting, persisting or broadening approval. The fix belongs in the canonical broker.

## Proposal in one paragraph

One consent may approve a **batch**: a bounded number of invocations of **one** declared
operation. The batch's limits are all shown in the dialog before the person decides, and the
broker counts them. The approval is held only by the broker, ends at a fixed time or when the page
goes away, and can be stopped by the person at any time. Nothing about it is persisted or handed
to app code as a token.

## Decision 1: the units of the limit

A batch is limited in all four units at once. A batch with any limit missing is invalid.

| Unit | Declared in the descriptor (ceiling) | Chosen per batch (≤ ceiling), shown in the dialog | Enforced by |
| -- | -- | -- | -- |
| Destination | one `capability`/`service`/`operation`, its existing `endpoint` routes | the same; in manifest mode, the exact list of requests | existing route match, plus the manifest match |
| Count | `max-requests` (≤ 256) | number of requests | broker counter |
| Bytes | `max-request-bytes` (sum of request bodies), `max-response-bytes` (sum of response bodies) | total bytes each way | broker: body length per snapshot, and a counting reader on each response body |
| Time | `max-duration-s` (≤ 600) | an absolute end time | broker clock; the batch also ends on `pagehide`, `destroy()` and the person's Stop |

**Destination is one operation, never several.** A batch never spans operations, services or
origins. "Upload these CARs and then write the record" is two consents: a batch for the upload
and a single consent for the record. This keeps the existing rule that approving one operation
does not authorize another.

There are two modes:

- **Manifest.** Before consent, the caller gives the exact list of requests: method, URL and,
  for requests with a body, the body's SHA-256 and length.
  - The dialog shows the count, the total bytes and a short digest of the manifest.
  - Each `invoke` must match an unused entry exactly, and the body is hashed and compared when it
    is snapshotted. Each entry can be used once.
  - **Required for every request with a body (writes).** The person approves exactly these bytes,
    as they do today.
- **Budget.** Only for `GET`/`HEAD` without a body. Any request that matches the declared routes
  is admitted, within the count, bytes and time limits.
  - Used when the exact URLs are not known in advance, for example scrolling a feed.
  - **Owner decision pending:** whether budget mode is acceptable at all (see Decision 3).

The existing per-request limits stay unchanged inside a batch:

- the 16 MiB, 5-second body snapshot per request;
- the redirect rules;
- the final-response origin check.

A batch does not lift the 16 MiB per-request limit. It removes the need to ask once per request.

**Failure is closed.** A request outside the manifest, over a limit, after the end time or for
another operation is refused before it is sent, and the batch closes. The remaining approval is
gone, and a new batch needs a new consent. A plain network error on an approved request does not
close the batch, but it does count toward the request count.

## Decision 2: what the dialog shows

This is the existing dialog (`createClientConsentHost`), with batch lines added. Everything shown
is derived from the frozen operation and the frozen batch request, never from later app input.

```text
Allow this operation up to 7 times?
Service:          yataverse
Operation:        upload-video-bytes
Endpoint:         https://yataverse.com
Action:           POST /ipfs
Data categories:  request-ip, account-did, service-auth-token, video-bytes
Requests:         up to 7 (listed: 7 exact requests, manifest 3f9a…c2)
Sending:          up to 104,857,600 bytes in total, at most 16,777,216 per request
Receiving:        up to 1,048,576 bytes in total
Ends:             at 16:42 (in 10 minutes), when this page closes, or when you press Stop
[Deny]  [Allow 7 requests]
```

- **The number is in the button.** Allow names the count ("Allow 7 requests"), so a press is an
  approval of that count. The existing arming delay (`ALLOW_ARM_MS`, 600 ms) and the trusted-press
  rule apply unchanged.
- **Long lists are truncated.** A manifest of many requests shows the count, total bytes and
  digest, never a scrolling list that can hide the data categories (review finding R5). Showing
  the first and last few entries is optional.
- **A running batch stays visible.** While it runs, the trusted host shows an indicator outside
  app control: the operation, how many requests are used and remain, and a **Stop** button.
  - Stop ends the batch at once. Requests already sent are not recalled; nothing more is sent.
  - Without this indicator, a batch would be an approval the person can no longer see.
- **Single-request operations look exactly as they do today.**

## Decision 3: compatibility with the each-operation contract

The workspace contract says:

- each external operation is its own `each-operation` consent;
- approval for one operation or endpoint does not authorize another;
- app or bot code must not mint, persist or broaden approval.

How this proposal keeps each point:

| Contract point | How a batch keeps it |
| -- | -- |
| Fresh, operation-specific approval | One batch is one operation. It is approved by a fresh trusted press, with the operation, endpoint, data categories and every limit shown first. |
| One approval never authorizes another operation or endpoint | The batch covers one operation's declared endpoint. Writes are further pinned to an exact manifest. |
| App code cannot mint, persist or broaden approval | Only the broker creates and holds batch state, branded like consent hosts (a `WeakMap`, no token object). The app gets a handle that can invoke and close, never widen. Nothing is stored; a reload ends the batch. |
| Denial sends nothing | Unchanged: denying the batch dialog sends no request. |

What still changes, so **Owner decision pending**:

1. **The meaning of `each-operation`.** Today one consent equals one request. A batch makes one
   consent equal up to N bounded requests of one operation. Two ways to write that:
   - **(a)** A new explicit consent value, `consent: "each-batch"`, together with a required
     `batch` block. An operation without it can never be batched.
   - **(b)** Keep `each-operation` and redefine "operation" in the workspace contract as "one
     displayed, bounded invocation set".

   This proposal recommends **(a)**. It leaves every existing descriptor's meaning unchanged, and
   it makes batching visible in the descriptor and in review.
2. **Budget mode for reads.** The contract says reading public content still needs per-operation
   consent. Budget mode approves reads whose exact URLs are not shown. One option is to allow it
   only for operations whose data categories contain no account data (for example `request-ip`
   and `content-cid` only). The other is to disallow it, so only manifest mode exists.
3. **Profiles.** KOTOBA-159 finding 1 (open, High) is that `trusted-page-v1` cannot enforce
   consent against same-document app code. A batch gives that code a larger approval to misuse.
   This proposal recommends allowing `each-batch` only for `restricted-wasm-v1` guests until
   finding 1 is resolved.
4. **The ceilings.** The proposed caps (256 requests, 600 s) are starting points, not measured
   values.

## Proposed API (sketch, for review only)

The descriptor operation:

```js
{
  capability: 'nagare-publish', service: 'yataverse', operation: 'upload-video-bytes',
  consent: 'each-batch',                       // Owner decision pending: (a) above
  'data-categories': ['request-ip', 'account-did', 'service-auth-token', 'video-bytes'],
  endpoint: { origin: 'https://yataverse.com',
              routes: [{ method: 'POST', path: '/ipfs', 'query-params': [] }] },
  batch: { modes: ['manifest'], 'max-requests': 16,
           'max-request-bytes': 268435456, 'max-response-bytes': 1048576,
           'max-duration-s': 600 },
}
```

The broker:

```js
const batch = await broker.openBatch(selector, {
  manifest: [{ method: 'POST', url: 'https://yataverse.com/ipfs', sha256: '…', bytes: 16711680 }, /* … */],
  // or, for budget mode: requests, responseBytes, durationS
}, { signal });              // shows the dialog; throws 'client operation was not approved' on deny
const response = await batch.invoke(payload, { signal });  // same payload shape as broker.invoke
batch.state;                 // { used, remaining, endsAt, closed }
batch.close();               // the app may end early; it cannot extend
```

In `invoke`, each request goes through the existing checks plus the batch checks, in this order:

1. The batch is open, not expired and not stopped.
2. The request matches the operation's declared route (existing check).
3. The body is snapshotted under the 16 MiB, 5-second bound (existing check).
4. Manifest mode: the snapshot's method, URL, length and SHA-256 match an unused entry, which is
   then consumed. Budget mode: the counters are decremented.
5. The request is fetched (existing).
6. The final-response origin is checked (existing).
7. The response body is read through a counter. Going over the receive limit aborts the body and
   closes the batch.

A violation at step 2 or 4 closes the batch before anything is sent.

## How Nagare would use it

- **Upload.** A video over 16 MiB becomes K CARs of at most 16 MiB each (blocks of at most 1 MiB,
  each CAR closed under its own root, plus one top-level root CAR).
  - One manifest batch covers the K uploads, then one single consent covers `createRecord`.
  - Two dialogs instead of K + 1.
  - The per-video bound would then come from the batch ceiling (for example 16 × 16 MiB), not from
    one request body.
- **Feed.** `listRecords` (one consent) returns up to 20 video CIDs. One manifest batch covers
  those 20 `GET /ipfs/<cid>?format=car` reads, with the total bytes taken from the records' sizes.

## Acceptance when implemented (negative controls)

Each of these must send nothing (checked with a fetch spy or a local listener), and each must
differ from the passing case in one input:

- Denying the batch dialog. A synthetic click or a `true`-returning callback in place of a trusted
  press.
- Request number N + 1. Request or response bytes one over the limit. A request after the end
  time, after Stop, after `pagehide`, after `close()`.
- In manifest mode: a body whose bytes changed after `openBatch` (same length, different hash). A
  manifest entry used twice. A URL or method not in the manifest.
- An `invoke` of another operation through the batch handle. A forged or copied batch handle. A
  handle used after reload.
- A descriptor with `each-batch` but a limit missing or over its ceiling, which `clientRuntimeProblems`
  must refuse. A budget-mode batch on a route that has a body.
- The trusted host's indicator cannot be removed, hidden or relabelled by app code, and Stop works
  while a request is in flight.
- Existing single-operation tests stay unchanged and passing.

## Not covered

- No implementation.
- No browser run.
- No measurement of how people read a count-bearing dialog.
- Resuming an interrupted upload (which manifest entries were stored) is the product's job, using
  the bytes plane's own receipts. The broker does not track it.
