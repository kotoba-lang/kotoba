# AWAI-174 asynchronous publication race — 2026-11-13 UTC

The actual Prolly engine builds two transactions using one provider. A
Promise-controlled local backend holds the first upload; the second
transaction finishes building its blocks before the first upload completes.
The driver delays only delivery of the second transaction result, then lets
the first publish and releases the second. Both publish to independent refs.
A fresh provider must restore the second ref and scan its actual data.

On the prior provider (`d3887183769eaadcdbe04fe727b73301f10268268521142053115e4bfb546d38`),
the second CAS reported success but its root block was absent: the driver
failed with `published root missing from backend`. The candidate passes:
`concurrent publish restores complete second transaction`. The fix removes
only captured batch entries whose byte values have not been replaced, retaining
blocks added while the upload was in flight. A failed upload does not remove
its pending batch. An injected upload failure produced no CAS; a retry from the same state published and restored its data.

This local ClojureScript 1.12.42 / Node 26.0.0 reference oracle uses real
engine and provider code with a Promise-controlled in-memory protocol backend
and synthetic identity crypto. `with-redefs` delays delivery of the second
real engine transaction; it does not replace its results. It is not proof of
remote durability, native operation, signed basis or production authorization.
The pre-existing v5 oracle classpath and its adaptations are documented in
`docs/evidence/awai-174-prolly-root/README.md`. No dependencies were downloaded
for this run. `inputs.json` records staged source hashes. Compile with
`clojure -Sdeps '{:deps {org.clojure/clojurescript {:mvn/version "1.12.42"}} :paths [".agent-output/classpath"]}' -M -m cljs.main -co '{:target :nodejs :output-dir ".agent-output/cljs-out-fixed" :output-to ".agent-output/publish-race-fixed.js" :optimizations :none}' -c awai-oracle.publish-race`, then run `node .agent-output/publish-race-fixed.js`.

The full library local-changes pin audit initially found three stale legacy
configuration pins. Their file bytes matched base revision 426ddd2; the ledger
now records their actual hashes and retains the previous hashes in each reason.
The complete source pin audit then passed.
