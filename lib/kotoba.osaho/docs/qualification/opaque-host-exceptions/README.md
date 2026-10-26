# Preserve host capability exception provenance

A native host capability throwing `RangeError("Maximum call stack size exceeded")`
previously lost its exception identity: execute's interpreter resource classifier
rewrote it as a guest trap. A controlled classifier-disabled diagnostic preserves
identity, isolating that owner. Both capability forms now remember host-thrown
identity in a private execution-local cell and rethrow it without classification.
NaN uses a static numeric self-comparison; no property/coercion is needed to match
it. Guest/interpreter stack exhaustion still uses the existing shared classifier.
A subsequent execution with a genuine division trap still enters that classifier.

The fixed-count JVM-shadowed Node bootstrap gate passes 274 tests / 2,312
assertions. The same tests against an archive of published D1 source report ten
failures with the same assertion count. Two new tests cover fourteen thrown
values across typed/untyped capabilities, 28 identity checks, classifier exclusion
and provenance isolation across executions. Existing guest stack/fuel/frame
controls stay in the maintained suite. No emitter or shared classifier was changed.

The passive Proxy observation goes from twelve reads to eleven: the `message`
read disappears, while nbb/SCI protocol/prototype reads remain. The initial
throwing-getter observation terminates inside the bootstrap evaluator and is not
zero-probe or native-product qualification. This patch cannot establish a raw
Proxy exception ABI for the full harness. Native/browser callback bridge and full
API/plugin parity remain separate work. System One made no model attempt.
Exact-head CI/main publication remains pending.
