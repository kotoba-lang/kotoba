# kotoba-lang/org-ietf-sdp

**SDP — the Session Description Protocol, [RFC 4566](https://www.rfc-editor.org/rfc/rfc4566) — in portable `.cljc`, with no dependencies.**

The `v=`/`o=`/`s=`/`c=`/`t=`/`m=`/`a=` line grammar with §5's **fixed
line-type ordering enforced as a grammar rule, not a convention** —
session-level fields, the required `1*( t= *(r=) )` time-fields group,
and zero or more media descriptions each with their own `i= c=* b=* k=?
a=*` attribute scope, exactly as [RFC 4566] §9's ABNF defines it. Also:
`rtpmap`/`fmtp` ([RFC 4566] §6), `rtcp-fb` ([RFC 4585] §4.2) and `ssrc`
([RFC 5576] §4.1) attribute sub-grammars.

`kotoba-lang/org-ietf-sip` (this workspace's SIP codec) and
`kotoba-lang/org-ietf-rtp` (RTP/RTCP) both explicitly name SDP as a gap
in their own READMEs — SIP carries SDP as an opaque body, and RTP's
payload-type↔codec mapping is negotiated by SDP out of band. This closes
that hole.

## Surface

```clojure
(require '[sdp.core :as sdp])

(sdp/decode wire-text)
;; => {:status :ok :session {:version "0" :origin {...} :session-name "..."
;;                           :connection {...} :time [...] :media [...] ...}}
;;  | {:status :error :reason :sdp/line-out-of-order :context {:line 7 :type \a}}

(sdp/encode session)
;; => {:status :ok :text "v=0\r\n..."}
;;  | {:status :error :reason :sdp/missing-required-field :context {:fields [\s]}}

(sdp/validate session)
;; => {:status :ok} | {:status :error :reason :sdp/missing-connection :context {:media-index 1}}
```

| namespace | |
|---|---|
| `sdp.grammar` | line lexer — `type=value` split, the fourteen legal type characters |
| `sdp.core` | `decode` `encode` — the line-ordering state machine, `validate` for the `c=` semantic rule |
| `sdp.attrs` | `parse-rtpmap` `parse-fmtp` `parse-rtcp-fb` `parse-ssrc` |

Wire text uses CRLF on encode; decode accepts bare LF too (the same
permissive-in/canonical-out asymmetry `org-ietf-sip` uses for header
folding). Everything else is REAL grammar: the ordering check is a
position cursor walked once through [RFC 4566] §9's own slot sequence,
not `clojure.string/split` + `group-by`.

## The bug this line-ordering check actually catches

A naive parser groups lines by type character and looks each one up —
`group-by` doesn't care what order `v=`/`s=`/`c=` arrive in, so it
accepts `c=` before the required `s=` just as happily as after it. Worse:
if the "did we see everything required" check is a simple "is `:session-name`
present" test performed only at the very end, a `c=` that gets scanned
*past* a not-yet-filled `s=` slot (because the scanner doesn't distinguish
required from optional slots when skipping) can silently consume the `s=`
line's *position* without ever consuming an `s=` line — producing a `{:status
:ok}` decode with `:session-name` simply absent. That is exactly the bug this
implementation's own `advance` function had during development (see the
commit history / the "discrimination proof" in the project's report) and
fixed by refusing to let the scanner skip past an unsatisfied required
(`:one`-cardinality) slot.

## Test vectors — provenance

**[RFC 4566] §5's own worked example** (the `v=0`/`o=jdoe`/`s=SDP
Seminar`/.../`a=rtpmap:99 h263-1998/90000` session) is used verbatim,
fetched from `https://www.rfc-editor.org/rfc/rfc4566.txt` on 2026-08-30
— round-tripped through `decode`/`encode` and asserted to reproduce the
exact original bytes.

Everything else in the round-trip and negative-test suites is
constructed test data exercising the grammar's structure (multi-media
sessions, repeat-times, bandwidth/key/zone lines, every attribute
sub-parser) — labelled as such, not presented as spec text.

## Errors

Returned, never thrown. `:reason` is a keyword naming the rule:
`:sdp/line-out-of-order`, `:sdp/missing-required-field` (carries
`:fields`, the still-unsatisfied `:one` slots), `:sdp/missing-time-field`,
`:sdp/empty-session-name`, `:sdp/malformed-origin` /
`:sdp/malformed-connection` / `:sdp/malformed-bandwidth` /
`:sdp/malformed-time` / `:sdp/malformed-repeat` / `:sdp/malformed-media` /
`:sdp/malformed-key`, `:sdp/unknown-line-type`, `:sdp/empty-message`.
`sdp/validate`'s semantic (not grammar) check returns
`:sdp/missing-connection`.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript (see org-modbus for the pattern)
```

## Not here

**RFC 2822 email-address and phone-number sub-grammars** (`e=`/`p=`
values are carried as opaque strings). **The `z=` zone-adjustments line**
is parsed as one opaque string rather than decomposed into its
`(time, signed-typed-time)` pairs — nothing in this workspace currently
consumes it structurally, and RFC 4566 §5.6 itself calls it "an
obsolete feature." **`k=` values beyond the four defined methods**
(`prompt`/`clear:`/`base64:`/`uri:`) are, per the grammar, exhaustive —
there is nothing else to add. **Bandwidth-type semantics** (what `AS`
vs `CT` vs `TIAS` actually mean) — this codec parses the `type:value`
shape, not the registry of bandwidth-type names.
