# com-google-gmail

**Gmail as a connector** — search, read, file under labels, send. Three scopes,
not one.

Portable `.cljc`. One dependency, [`kotoba-lang/connector`](https://github.com/kotoba-lang/connector).

## Tools

| tool | effect | scope |
|---|---|---|
| `gmail_search_messages` | read | `gmail.readonly` |
| `gmail_get_message` | read | `gmail.readonly` |
| `gmail_list_labels` | read | `gmail.readonly` |
| `gmail_modify_labels` | **write** | `gmail.modify` |
| `gmail_send_message` | **write** | `gmail.send` |

## Why three scopes

`cloud-itonami-app` holds `gmail.modify` for everything, because one provider
entry carries one scope list and `modify` covers reading. It was the right call
for one application with one grant — but it means a deployment that only wanted
to *search* a mailbox also held permission to file and relabel it.

Here the scope follows the tool. Enable search and read, and the consent screen
asks for `gmail.readonly`. Enable sending, and `gmail.send` appears — visibly,
as a separate line a person can decline.

No tool asks for `https://mail.google.com/` (full account access, including
permanent delete), and there is a test asserting none ever does. Nothing here
deletes: moving to `TRASH` is a label change and is reversible.

## `messages.list` returns ids, and says so

Gmail's search returns message ids with no headers and no snippet. The
normalizer returns `{:message-ids [...] :note "ids only; call
gmail_get_message for headers"}` rather than a list of message maps with empty
`:subject` keys — an invented empty subject reads as "this message has no
subject", which is a different and wrong claim.

`gmail_get_message` defaults to `format=metadata`. A search result that
silently pulled full bodies would be an expensive surprise.

## Usage

```clojure
(require '[connector.registry :as reg]
         '[connector.invoke :as invoke]
         '[google-gmail.connector :as gmail])

(def registry (reg/registry [gmail/provider]))

(invoke/call registry "gmail_search_messages" {"q" "is:unread newer_than:7d"}
             {:http my-http :tokens my-tokens})
```

This namespace cannot obtain a credential; `connector.invoke` attaches it.

## Known limit

Gmail takes `labelIds` as a repeated query parameter and
`connector.ports`' query map is single-valued, so one label filter works and
several do not. The code sends a single label and omits the parameter for
several rather than silently sending the first.

## Declaration

`connector.edn` is generated; the test suite fails if it has drifted.

```sh
kbb --backend sci --classpath "src:../connector/src" emit-connector-edn.cljk
```

## Tests

```sh
kbb --backend sci --classpath "src:test:../connector/src" run-tests.cljk   # 11 tests, 43 assertions
kbb -M:test
```

## Naming

`google.com` → `com-google`, subject `gmail`. The Gmail API's authority is
Google's `developers.google.com`, so the recorded origin domain is `google.com`
and not `gmail.com` — the same domain Drive and Calendar record, which is what
lets `connector.consent` group all three into one grant (ADR-2608040100).
