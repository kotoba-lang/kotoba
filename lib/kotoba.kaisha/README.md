# kaisha 会社

Portable CLJC model for an EDN-native **communication space** (Slack/Teams
相当): one space per company, channels, threaded messages, mentions, reactions,
and read markers — as one EDN-native graph.

Sibling of the other kotoba-lang surfaces:

- `kotoba-lang/slides` — decks, docs, drive, sheets
- `kotoba-lang/calendar` — events, attendees
- `kotoba-lang/mail` / `contacts` — correspondence, people

Like those, `kaisha` stays pure data and pure functions. Hosts render it as web
apps, persist it in Datomic/kotoba (append-only datoms; CRDT via
`kotoba-lang/crdt` for live co-editing), or expose it over kotoba-server XRPC.
Identity is intended to be kotoba CACAO `did:key` (the `:kaisha/did` slot on
members); nothing in the model requires it.

## Model

```clojure
(require '[kaisha.model :as k])

(def sp
  (-> (k/space "acme")
      (k/add-member (k/member "jun"))
      (k/add-member (k/member "rin"))
      (k/add-channel (k/channel "general"))
      (k/join "general" "jun")
      (k/post "general" (k/message "m-1" {:kaisha/author "jun"
                                          :kaisha/body "morning @rin"
                                          :kaisha/at "2026-07-07T09:00:00Z"}))
      (k/reply "general" "m-1" (k/message "m-2" {:kaisha/author "rin"
                                                 :kaisha/body "on it"
                                                 :kaisha/at "2026-07-07T09:01:00Z"}))))

(k/messages-in-order sp "general")   ;; top-level messages, oldest first
(k/thread sp "general" "m-1")        ;; parent + replies
(k/mentions "morning @rin")          ;; => #{"rin"}
(k/visible-channels sp "rin")        ;; public + private-where-member
(k/unread sp "rin" "general")        ;; after the member's read marker
```

Semantics follow Slack: threads are one level deep (a reply's parent must be a
top-level message), private channels are visible to their members only, read
markers are per member per channel.

## Direct messages

```clojure
(-> sp (k/open-dm "jun" "rin"))            ;; idempotent
(k/dm-with sp "rin" "jun")                 ;; the same channel, from either side
(k/dms-of sp "jun")                        ;; their conversations
(k/dm-counterpart (k/dm-with sp "jun" "rin") "jun")  ;; => "rin"
```

A DM is a channel with `:kaisha/kind :dm`, `:private` visibility and two
members — not a separate collection, so threads, reactions, mentions, read
markers and validation all apply unchanged.

**Its id is derived, not allocated, and that is the whole design.** If each side
allocated a fresh id when it opened a conversation, two people messaging each
other at the same moment would create two DM channels for the same pair, with
the history split between them and nothing detecting it: each client would show
a conversation that looks complete and is missing half the messages. `dm-id`
makes that unrepresentable — both sides compute the same id without
coordinating, `open-dm` is idempotent, and `kaisha.validate` rejects a DM whose
id is not `dm-id` of its own members (`:dm/id-mismatch`), because such a channel
is unreachable from `dm-with` and would be written to by nobody.

The id is length-prefixed (`dm:3:jun:rin`) rather than separator-joined:
kaisha does not constrain the character set of a member id, and a plain
`dm:a|b` merges `["x|y" "z"]` with `["x" "y|z"]` into one channel.

`join` and `leave` are refused on a DM — its id describes exactly who is in it,
so a third member would make the id a lie while the original two kept resolving
to it. `active-channels` excludes DMs (they belong in their own list, addressed
by who they are with); `visible-channels` still returns them.

A note-to-self (`open-dm "jun" "jun"`) is a valid one-member DM, not a defect.

`kaisha.validate/problems` returns `{:kaisha/severity :kaisha/code ...}` maps
for structural defects (unknown author, orphan reply, nested thread, private
channel without members); `valid?` is false on any `:error`.

## Test

```bash
kbb -M:test                              # JVM
kbb --backend sci --classpath "src:test" run-tests.cljk    # ClojureScript
```

Both, always. `kaisha.model` runs in a Cloudflare Worker in production
(`cloud-itonami.edge.chat-store`), so ClojureScript is a real runtime here and
a JVM-only suite proves less than it appears to.

## Scope and follow-ups

v1 is the pure EDN model only. Deliberately out of scope, tracked as follow-ups
in ADR-2607072310:

- transport (kotoba-server XRPC lexicons, realtime fan-out over KSE)
- persistence (datom projection, CRDT message bodies)
- AI participation — LLM-drafted posts must go through a governed actor
  (post-LLM ⊣ Governor, human-approved send) in the `tayori`/`teian` pattern,
  never straight into the model.
